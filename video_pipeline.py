from __future__ import annotations

import argparse
import ast
import asyncio
import base64
import hashlib
import hmac
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlencode, quote_plus
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parent


def load_local_env(env_path: Path | None = None) -> None:
    env_file = env_path or BASE_DIR / ".env"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = clean_env_value(value)
        current_value = os.environ.get(key, "")
        if key and not is_placeholder_env_value(value) and (key not in os.environ or is_placeholder_env_value(current_value)):
            os.environ[key] = value


def clean_env_value(value: str) -> str:
    text = value.strip()
    quote_char = text[0] if text[:1] in {"'", '"'} else ""
    if quote_char:
        end_index = text.find(quote_char, 1)
        if end_index != -1:
            return text[1:end_index].strip()
    if " #" in text:
        text = text.split(" #", 1)[0]
    return text.strip().strip("'\"")


def is_placeholder_env_value(value: str) -> bool:
    normalized = value.strip().lower()
    return not normalized or normalized.startswith("your_") or "你的" in normalized


load_local_env()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI视频自动化脚本：手动输入文案 -> 音频合成 -> 在线数字人视频生成"
    )
    parser.add_argument("--title", default="auto_digit_video", help="任务名称，会用于输出文件命名")
    parser.add_argument("--text", help="直接传入文案内容")
    parser.add_argument("--text-file", help="从文本文件读取文案")
    parser.add_argument(
        "--output-dir",
        default="output",
        help="输出目录，默认在当前目录下创建 output",
    )
    parser.add_argument(
        "--tts-provider",
        default="edge",
        choices=["edge", "none"],
        help="配音提供方，默认 edge",
    )
    parser.add_argument("--voice", default="zh-CN-XiaoxiaoNeural", help="Edge TTS 音色")
    parser.add_argument("--rate", default="+0%", help="语速，例如 +10%% / -5%%")
    parser.add_argument("--volume", default="+0%", help="音量，例如 +0%% / +20%%")
    parser.add_argument(
        "--avatar-mode",
        default="manual",
        choices=["manual", "webhook", "none"],
        help="人像来源：手动提供、本地跳过、或通过 AI 接口生成",
    )
    parser.add_argument(
        "--video-mode",
        default="tencent",
        choices=["tencent", "storyboard", "local-image", "local-video", "webhook", "none"],
        help="视频生成模式，默认 tencent 在线数字人",
    )
    parser.add_argument("--avatar-image", help="本地头像图片路径，用于静态口播视频")
    parser.add_argument("--avatar-video", help="本地人物视频路径，用于循环拼接")
    parser.add_argument("--avatar-prompt", help="AI 生成人像时使用的提示词")
    parser.add_argument(
        "--avatar-config",
        help="AI 生成人像配置文件(JSON)，avatar-mode=webhook 时必填",
    )
    parser.add_argument(
        "--webhook-config",
        help="数字人 API 配置文件(JSON)，video-mode=webhook 时必填",
    )
    parser.add_argument("--tencent-appkey", help="腾讯云智能数智人 appkey")
    parser.add_argument("--tencent-access-token", help="腾讯云智能数智人 access token")
    parser.add_argument("--tencent-virtualman-key", help="腾讯云智能数智人 VirtualmanKey")
    parser.add_argument(
        "--tencent-driver-type",
        default="text",
        choices=["text", "original-voice"],
        help="腾讯云驱动模式：text 为文本驱动，original-voice 为音频驱动",
    )
    parser.add_argument("--tencent-audio-url", help="腾讯云音频驱动时使用的公网音频 URL")
    parser.add_argument(
        "--tencent-output-format",
        default="Mp4",
        help="腾讯云输出格式，常见值如 Mp4 / TransparentWebm / TransparentMov",
    )
    parser.add_argument(
        "--tencent-concurrency-type",
        default="Shared",
        choices=["Shared", "Exclusive"],
        help="腾讯云视频生成并发类型",
    )
    parser.add_argument(
        "--tencent-speed",
        type=float,
        default=1.0,
        help="腾讯云文本驱动语速，官方常见范围 0.5-1.5",
    )
    parser.add_argument(
        "--tencent-volume",
        type=float,
        default=1.0,
        help="腾讯云文本驱动音量",
    )
    parser.add_argument(
        "--tencent-list-assets",
        action="store_true",
        help="查询腾讯云账号下的形象资产，便于找到 VirtualmanKey",
    )
    parser.add_argument(
        "--tencent-virtualman-type-code",
        help="查询腾讯云形象资产时使用的 VirtualmanTypeCode",
    )
    parser.add_argument(
        "--tencent-page-size",
        type=int,
        default=20,
        help="腾讯云资产查询分页大小，默认 20",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="轮询超时时间，单位秒，默认 900",
    )
    parser.add_argument(
        "--retry-count",
        type=int,
        default=3,
        help="接口失败后的最大重试次数，默认 3",
    )
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=5,
        help="接口重试等待秒数，默认 5",
    )
    parser.add_argument(
        "--auto-split",
        action="store_true",
        help="长文案自动分段生成并拼接",
    )
    parser.add_argument(
        "--split-max-chars",
        type=int,
        default=120,
        help="自动分段时每段最大字符数，默认 120",
    )
    parser.add_argument(
        "--storyboard-dynamic-backgrounds",
        action="store_true",
        help="内容短视频模式下，按分段分别搜索/生成背景素材",
    )
    parser.add_argument(
        "--storyboard-transitions",
        action="store_true",
        help="内容短视频模式下，分段拼接时添加淡化转场",
    )
    parser.add_argument(
        "--storyboard-transition-duration",
        type=float,
        default=0.6,
        help="内容短视频模式转场时长，默认 0.6 秒",
    )
    parser.add_argument(
        "--storyboard-video-trim-start",
        type=float,
        default=0.4,
        help="内容短视频模式背景视频起始裁切秒数，默认 0.4 秒，用于跳过开头停顿",
    )
    parser.add_argument(
        "--fast-mode",
        action="store_true",
        help="启用快速生成模式：使用更快的 ffmpeg 编码参数，适合预览和调试",
    )
    parser.add_argument(
        "--storyboard-backgrounds-manifest",
        help="内容短视频模式下的分段背景清单 JSON 文件",
    )
    parser.add_argument(
        "--add-subtitles",
        action="store_true",
        help="自动生成并烧录中文字幕",
    )
    parser.add_argument(
        "--subtitle-provider",
        default="heuristic",
        choices=["heuristic", "whisper"],
        help="字幕时间轴生成方式：heuristic 为快速估算，whisper 为基于语音识别的精准模式",
    )
    parser.add_argument(
        "--subtitle-max-chars",
        type=int,
        default=22,
        help="每条字幕最大字数，默认 22",
    )
    parser.add_argument(
        "--subtitle-font-size",
        type=int,
        default=18,
        help="字幕字号，默认 18",
    )
    parser.add_argument(
        "--subtitle-margin-v",
        type=int,
        default=36,
        help="字幕底部边距，默认 36",
    )
    parser.add_argument(
        "--subtitle-bar-height",
        type=int,
        default=170,
        help="字幕条高度，默认 170",
    )
    parser.add_argument(
        "--subtitle-bar-opacity",
        type=float,
        default=0.34,
        help="字幕条透明度，默认 0.34",
    )
    parser.add_argument(
        "--subtitle-safe-lift",
        type=int,
        default=46,
        help="开启字幕时人物向上抬升像素，默认 46",
    )
    parser.add_argument(
        "--subtitle-offset",
        type=float,
        default=-0.15,
        help="字幕时间偏移秒数，负数表示字幕提前，默认 -0.15 秒",
    )
    parser.add_argument("--whisper-model", help="Whisper/whisper.cpp 模型文件路径，例如 ggml-base.bin")
    parser.add_argument("--whisper-language", default="zh", help="Whisper 识别语言，默认 zh")
    parser.add_argument("--bgm-audio", help="背景音乐文件路径，支持 mp3/wav/m4a 等 ffmpeg 可读取格式")
    parser.add_argument(
        "--bgm-volume",
        type=float,
        default=0.18,
        help="背景音乐音量比例，默认 0.18",
    )
    parser.add_argument("--background-image", help="绿幕替换用的背景图片路径")
    parser.add_argument("--background-video", help="绿幕替换用的背景视频路径")
    parser.add_argument(
        "--background-mode",
        default="manual",
        choices=["manual", "webhook", "pexels", "pexels-video", "none"],
        help="背景来源：手动提供、本地跳过、Pexels 图片/Pexels 视频，或通过自定义接口生成",
    )
    parser.add_argument("--background-prompt", help="AI 生成背景图时使用的提示词")
    parser.add_argument(
        "--background-config",
        help="AI 生成背景图配置文件(JSON)，background-mode=webhook 时必填",
    )
    parser.add_argument("--pexels-api-key", help="Pexels API Key，留空则读取 PEXELS_API_KEY")
    parser.add_argument(
        "--pexels-per-page",
        type=int,
        default=8,
        help="Pexels 搜索候选数量，默认 8",
    )
    parser.add_argument(
        "--background-color",
        default="0x00FF00",
        help="绿幕色值，默认 0x00FF00",
    )
    parser.add_argument(
        "--background-similarity",
        type=float,
        default=0.18,
        help="抠像相似度，默认 0.18",
    )
    parser.add_argument(
        "--background-blend",
        type=float,
        default=0.08,
        help="抠像边缘融合值，默认 0.08",
    )
    parser.add_argument(
        "--background-despill",
        type=float,
        default=0.10,
        help="去绿边强度，默认 0.10",
    )
    parser.add_argument(
        "--background-shadow",
        type=float,
        default=0.45,
        help="人物阴影强度，默认 0.45",
    )
    parser.add_argument(
        "--background-feather",
        type=float,
        default=0.8,
        help="前景轻微柔化半径，默认 0.8",
    )
    parser.add_argument(
        "--subject-scale",
        type=float,
        default=0.82,
        help="人物缩放比例，默认 0.82",
    )
    parser.add_argument(
        "--subject-offset-x",
        type=int,
        default=0,
        help="人物水平偏移，默认 0",
    )
    parser.add_argument(
        "--subject-offset-y",
        type=int,
        default=18,
        help="人物垂直偏移，默认 18",
    )
    parser.add_argument(
        "--subject-saturation",
        type=float,
        default=0.96,
        help="人物饱和度，默认 0.96",
    )
    parser.add_argument(
        "--subject-gamma",
        type=float,
        default=1.03,
        help="人物 gamma，默认 1.03",
    )
    return parser.parse_args(argv)


def load_script_text(args: argparse.Namespace) -> str:
    if args.text:
        return clean_script_text(args.text)

    if args.text_file:
        return clean_script_text(Path(args.text_file).read_text(encoding="utf-8"))

    print("请输入文案内容，结束后按回车：", file=sys.stderr)
    return clean_script_text(input())


def clean_script_text(value: str) -> str:
    text = value.strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, (list, tuple)):
            text = "\n".join(str(item).strip() for item in parsed if str(item).strip())
    text = text.replace("', '", "\n").replace('", "', "\n")
    for prefix, suffix in (("['", "']"), ('["', '"]')):
        if text.startswith(prefix) and text.endswith(suffix):
            text = text[len(prefix) : -len(suffix)]
    return text.strip()


def slugify(value: str) -> str:
    safe = []
    for char in value.strip().lower():
        if char.isalnum():
            safe.append(char)
        elif char in {" ", "-", "_"}:
            safe.append("_")
    return "".join(safe).strip("_") or "video_job"


def clone_args(args: argparse.Namespace, **updates: Any) -> argparse.Namespace:
    data = vars(args).copy()
    data.update(updates)
    return argparse.Namespace(**data)


def load_storyboard_backgrounds_manifest(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return []
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"分段背景清单不存在: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("分段背景清单格式错误，必须是数组 JSON。")
    return [item for item in data if isinstance(item, dict)]


def rotate_storyboard_backgrounds(items: list[dict[str, Any]], offset: int) -> list[dict[str, Any]]:
    if not items:
        return []
    normalized_offset = offset % len(items)
    return items[normalized_offset:] + items[:normalized_offset]


def check_command(name: str) -> None:
    if shutil.which(name):
        return
    raise RuntimeError(f"未找到命令 `{name}`，请先安装后再运行。")


@dataclass
class JobContext:
    title: str
    script: str
    output_dir: Path
    audio_path: Path
    video_path: Path
    final_video_path: Path
    subtitle_path: Path
    avatar_image_path: Path
    background_image_path: Path
    manifest_path: Path
    log_path: Path
    segment_index: int = 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "script": self.script,
            "output_dir": str(self.output_dir),
            "audio_path": str(self.audio_path),
            "video_path": str(self.video_path),
            "final_video_path": str(self.final_video_path),
            "subtitle_path": str(self.subtitle_path),
            "avatar_image_path": str(self.avatar_image_path),
            "background_image_path": str(self.background_image_path),
            "manifest_path": str(self.manifest_path),
            "log_path": str(self.log_path),
        }

    def clone_for_segment(
        self,
        index: int,
        script: str,
        segment_dir: Path,
    ) -> "JobContext":
        segment_title = f"{self.title}_part_{index:02d}"
        return JobContext(
            title=segment_title,
            script=script,
            output_dir=segment_dir,
            audio_path=segment_dir / f"{segment_title}.mp3",
            video_path=segment_dir / f"{segment_title}.mp4",
            final_video_path=segment_dir / f"{segment_title}_final.mp4",
            subtitle_path=segment_dir / f"{segment_title}.srt",
            avatar_image_path=self.avatar_image_path,
            background_image_path=self.background_image_path,
            manifest_path=segment_dir / "job_manifest.json",
            log_path=segment_dir / "run.log.jsonl",
            segment_index=index,
        )


class EdgeTTSProvider:
    async def synthesize(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str,
        volume: str,
    ) -> Path:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError(
                "缺少依赖 `edge-tts`，请执行 `pip install edge-tts` 后重试。"
            ) from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None
        for attempt in range(1, 4):
            communicator = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=rate,
                volume=volume,
            )
            try:
                await communicator.save(str(output_path))
                return output_path
            except Exception as exc:
                last_error = exc
                if output_path.exists():
                    output_path.unlink()
                if attempt < 3:
                    print(f"[重试] Edge TTS 合成失败，第 {attempt}/3 次：{exc}，2 秒后重试...", file=sys.stderr)
                    await asyncio.sleep(2)
        if last_error:
            raise last_error
        return output_path


class LocalComposer:
    def build_story_from_image(
        self,
        image_path: Path,
        audio_path: Path,
        output_path: Path,
        fast_mode: bool = False,
    ) -> Path:
        if not image_path.exists():
            raise FileNotFoundError(f"背景图片不存在: {image_path}")

        check_command("ffmpeg")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-i",
            str(audio_path),
            "-vf",
            "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast" if fast_mode else "veryfast",
            "-tune",
            "stillimage",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output_path),
        ]
        run_command(cmd)
        return output_path

    def build_story_from_video(
        self,
        background_video: Path,
        audio_path: Path,
        output_path: Path,
        trim_start: float = 0.4,
        fast_mode: bool = False,
        segment_index: int = 1,
    ) -> Path:
        if not background_video.exists():
            raise FileNotFoundError(f"背景视频不存在: {background_video}")

        check_command("ffmpeg")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        safe_trim = self.resolve_story_video_start(background_video, audio_path, trim_start, segment_index)
        cmd = [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(background_video),
            "-i",
            str(audio_path),
            "-vf",
            f"trim=start={safe_trim:.2f},setpts=PTS-STARTPTS,"
            "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv420p",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast" if fast_mode else "veryfast",
            "-crf",
            "28" if fast_mode else "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
        run_command(cmd)
        return output_path

    def build_story_from_video_playlist(
        self,
        backgrounds: list[dict[str, Any]],
        audio_path: Path,
        output_path: Path,
        trim_start: float = 0.4,
        fast_mode: bool = False,
    ) -> Path:
        video_paths = [
            Path(str(item.get("background_video") or "")).resolve()
            for item in backgrounds
            if str(item.get("background_video") or "").strip()
        ]
        video_paths = [path for path in video_paths if path.exists()]
        if not video_paths:
            raise FileNotFoundError("分镜背景清单里没有可用背景视频。")
        if len(video_paths) == 1:
            return self.build_story_from_video(
                video_paths[0],
                audio_path,
                output_path,
                trim_start=trim_start,
                fast_mode=fast_mode,
            )

        check_command("ffmpeg")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio_duration = get_video_duration(audio_path)
        concat_list_path = output_path.parent / f"{output_path.stem}_background_playlist.txt"
        lines: list[str] = []
        total_duration = 0.0
        cursor = 0
        while total_duration < audio_duration + max(0.0, trim_start) + 1.0:
            path = video_paths[cursor % len(video_paths)]
            lines.append(f"file {shlex.quote(str(path))}")
            total_duration += max(get_video_duration(path), 0.1)
            cursor += 1
            if cursor > len(video_paths) * 12:
                break
        concat_list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        safe_trim = max(0.0, trim_start)
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list_path),
            "-i",
            str(audio_path),
            "-vf",
            f"trim=start={safe_trim:.2f},setpts=PTS-STARTPTS,"
            "fps=30,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv420p",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast" if fast_mode else "veryfast",
            "-crf",
            "28" if fast_mode else "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
        run_command(cmd)
        return output_path

    def resolve_story_video_start(
        self,
        background_video: Path,
        audio_path: Path,
        trim_start: float,
        segment_index: int,
    ) -> float:
        base_start = max(0.0, trim_start)
        try:
            background_duration = get_video_duration(background_video)
            audio_duration = get_video_duration(audio_path)
        except Exception:
            return base_start
        if background_duration <= audio_duration + base_start + 1.0:
            return base_start
        max_start = max(base_start, background_duration - audio_duration - 0.8)
        offset = (max(1, segment_index) - 1) * max(audio_duration * 0.37, 3.0)
        return min(base_start + offset, max_start)

    def build_from_image(self, image_path: Path, audio_path: Path, output_path: Path) -> Path:
        if not image_path.exists():
            raise FileNotFoundError(f"头像图片不存在: {image_path}")

        check_command("ffmpeg")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-i",
            str(audio_path),
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output_path),
        ]
        run_command(cmd)
        return output_path

    def build_from_video(self, avatar_video: Path, audio_path: Path, output_path: Path) -> Path:
        if not avatar_video.exists():
            raise FileNotFoundError(f"人物视频不存在: {avatar_video}")

        check_command("ffmpeg")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(avatar_video),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
        run_command(cmd)
        return output_path


class BackgroundComposer:
    def replace_green_screen(
        self,
        foreground_video: Path,
        output_path: Path,
        background_image: Path | None = None,
        background_video: Path | None = None,
        color: str = "0x00FF00",
        similarity: float = 0.18,
        blend: float = 0.08,
        despill: float = 0.18,
        shadow: float = 0.45,
        feather: float = 1.2,
        subject_scale: float = 0.82,
        subject_offset_x: int = 0,
        subject_offset_y: int = 18,
        subject_saturation: float = 0.96,
        subject_gamma: float = 1.03,
    ) -> Path:
        if not foreground_video.exists():
            raise FileNotFoundError(f"前景视频不存在: {foreground_video}")
        if not background_image and not background_video:
            raise ValueError("请提供背景图片或背景视频。")
        if background_image and not background_image.exists():
            raise FileNotFoundError(f"背景图片不存在: {background_image}")
        if background_video and not background_video.exists():
            raise FileNotFoundError(f"背景视频不存在: {background_video}")

        check_command("ffmpeg")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        filter_complex = self.build_filter_complex(
            color=color,
            similarity=similarity,
            blend=blend,
            despill=despill,
            shadow=shadow,
            feather=feather,
            subject_scale=subject_scale,
            subject_offset_x=subject_offset_x,
            subject_offset_y=subject_offset_y,
            subject_saturation=subject_saturation,
            subject_gamma=subject_gamma,
        )
        if background_video:
            cmd = [
                "ffmpeg",
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                str(background_video),
                "-i",
                str(foreground_video),
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-c:a",
                "copy",
                "-shortest",
                str(output_path),
            ]
        else:
            cmd = [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                str(background_image),
                "-i",
                str(foreground_video),
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-c:a",
                "copy",
                "-shortest",
                str(output_path),
        ]
        run_command(cmd)
        return output_path

    def build_filter_complex(
        self,
        color: str,
        similarity: float,
        blend: float,
        despill: float,
        shadow: float,
        feather: float,
        subject_scale: float,
        subject_offset_x: int,
        subject_offset_y: int,
        subject_saturation: float,
        subject_gamma: float,
    ) -> str:
        shadow_alpha = max(0.0, min(shadow, 1.0))
        blur_sigma = max(0.3, feather)
        green_gain = max(0.0, 1.0 - despill)
        scale_value = max(0.55, min(subject_scale, 1.2))
        return (
            f"[0:v][1:v]scale2ref[bg][fgsrc];"
            f"[fgsrc]chromakey={color}:{similarity}:{blend},"
            f"colorchannelmixer=gg={green_gain},"
            f"eq=saturation={subject_saturation}:gamma={subject_gamma},"
            f"gblur=sigma={blur_sigma},"
            f"scale=iw*{scale_value}:ih*{scale_value}[fg];"
            f"[fg]split[fgmain][fgshadowsrc];"
            f"[fgshadowsrc]colorchannelmixer=aa={shadow_alpha}:rr=0:gg=0:bb=0,"
            f"gblur=sigma={blur_sigma * 2.2}[shadow];"
            f"[bg][shadow]overlay=(W-w)/2+{subject_offset_x + 18}:(H-h)/2+{subject_offset_y + 28}:format=auto[bgshadow];"
            f"[bgshadow][fgmain]overlay=(W-w)/2+{subject_offset_x}:(H-h)/2+{subject_offset_y}:format=auto,format=yuv420p[v]"
        )


class ConcatComposer:
    def concat_videos(self, input_paths: list[Path], output_path: Path) -> Path:
        if not input_paths:
            raise ValueError("没有可拼接的视频片段。")
        check_command("ffmpeg")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        concat_list_path = output_path.parent / "concat_inputs.txt"
        lines = [f"file {shlex.quote(str(path.resolve()))}" for path in input_paths]
        concat_list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list_path),
            "-c",
            "copy",
            str(output_path),
        ]
        run_command(cmd)
        return output_path

    def concat_with_transitions(
        self,
        input_paths: list[Path],
        output_path: Path,
        transition_duration: float = 0.6,
        fast_mode: bool = False,
    ) -> Path:
        if not input_paths:
            raise ValueError("没有可拼接的视频片段。")
        if len(input_paths) == 1:
            shutil.copyfile(input_paths[0], output_path)
            return output_path

        check_command("ffmpeg")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        safe_duration = max(0.2, min(transition_duration, 1.5))
        durations = [get_video_duration(path) for path in input_paths]

        cmd = ["ffmpeg", "-y"]
        for path in input_paths:
            cmd += ["-i", str(path)]

        filter_parts: list[str] = []
        for index in range(len(input_paths)):
            filter_parts.append(
                f"[{index}:v]fps=30,scale=1920:1080:force_original_aspect_ratio=increase,"
                f"crop=1920:1080,format=yuv420p,settb=AVTB[vsrc{index}]"
            )
            filter_parts.append(
                f"[{index}:a]aresample=24000,asetpts=N/SR/TB[asrc{index}]"
            )

        current_video = "[vsrc0]"
        current_audio = "[asrc0]"
        accumulated = durations[0]

        for index in range(1, len(input_paths)):
            offset = max(accumulated - safe_duration, 0.0)
            next_video = f"[vsrc{index}]"
            next_audio = f"[asrc{index}]"
            video_out = f"[v{index}]"
            audio_out = f"[a{index}]"
            filter_parts.append(
                f"{current_video}{next_video}xfade=transition=fade:duration={safe_duration}:offset={offset}{video_out}"
            )
            filter_parts.append(
                f"{current_audio}{next_audio}acrossfade=d={safe_duration}:c1=tri:c2=tri{audio_out}"
            )
            current_video = video_out
            current_audio = audio_out
            accumulated += durations[index] - safe_duration

        cmd += [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            current_video,
            "-map",
            current_audio,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast" if fast_mode else "veryfast",
            "-crf",
            "28" if fast_mode else "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(output_path),
        ]
        run_command(cmd)
        return output_path


class SubtitleComposer:
    def generate_srt(
        self,
        segments: list[tuple[str, float]],
        output_path: Path,
        max_chars: int = 22,
        transition_overlap: float = 0.0,
        subtitle_offset: float = 0.0,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        entries: list[str] = []
        current_time = 0.0
        index = 1
        for segment_index, (text, duration) in enumerate(segments):
            subtitle_lines = split_script_text(text, max_chars)
            weights = [max(len(item.strip()), 1) for item in subtitle_lines]
            total_weight = max(sum(weights), 1)
            segment_start = current_time
            elapsed = 0.0
            for line, weight in zip(subtitle_lines, weights):
                share = duration * (weight / total_weight)
                start = max(0.0, segment_start + elapsed + subtitle_offset)
                elapsed += share
                end = max(start + 0.1, segment_start + elapsed + subtitle_offset)
                entries.append(
                    f"{index}\n{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}\n{line.strip()}\n"
                )
                index += 1
            overlap = transition_overlap if segment_index < len(segments) - 1 else 0.0
            current_time += max(duration - overlap, 0.0)
        output_path.write_text("\n".join(entries) + "\n", encoding="utf-8")
        return output_path

    def generate_srt_from_whisper(
        self,
        audio_path: Path,
        output_path: Path,
        model_path: Path,
        language: str = "zh",
        max_chars: int = 22,
        subtitle_offset: float = 0.0,
    ) -> Path:
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        if not model_path.exists():
            raise FileNotFoundError(f"Whisper 模型文件不存在: {model_path}")
        check_command("ffmpeg")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        escaped_model = escape_ffmpeg_filter_path(model_path)
        escaped_destination = escape_ffmpeg_filter_path(output_path)
        whisper_filter = (
            f"whisper=model={escaped_model}:language={language}:"
            f"format=srt:destination={escaped_destination}:max_len={max_chars}"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_path),
            "-af",
            whisper_filter,
            "-f",
            "null",
            "-",
        ]
        run_command(cmd)
        if subtitle_offset:
            self.apply_srt_offset(output_path, subtitle_offset)
        return output_path

    def apply_srt_offset(self, subtitle_path: Path, subtitle_offset: float) -> Path:
        if not subtitle_path.exists() or abs(subtitle_offset) < 1e-6:
            return subtitle_path
        lines = subtitle_path.read_text(encoding="utf-8").splitlines()
        shifted: list[str] = []
        for line in lines:
            if " --> " not in line:
                shifted.append(line)
                continue
            start_text, end_text = line.split(" --> ", 1)
            start_seconds = max(0.0, parse_srt_timestamp(start_text) + subtitle_offset)
            end_seconds = max(start_seconds + 0.1, parse_srt_timestamp(end_text) + subtitle_offset)
            shifted.append(f"{format_srt_timestamp(start_seconds)} --> {format_srt_timestamp(end_seconds)}")
        subtitle_path.write_text("\n".join(shifted) + "\n", encoding="utf-8")
        return subtitle_path

    def burn_subtitles(
        self,
        input_video: Path,
        subtitle_path: Path,
        output_path: Path,
        font_size: int,
        margin_v: int,
        bar_height: int,
        bar_opacity: float,
        fast_mode: bool = False,
    ) -> Path:
        check_command("ffmpeg")
        if not self.has_subtitles_filter():
            print("[提示] 当前 ffmpeg 不支持 subtitles 滤镜，改用软字幕封装。", file=sys.stderr)
            return self.mux_soft_subtitles(input_video, subtitle_path, output_path)
        escaped_subtitle = escape_ffmpeg_filter_path(subtitle_path)
        style = (
            "FontName=Arial,"
            f"FontSize={font_size},"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00502010,"
            "BorderStyle=1,Outline=2,Shadow=0,"
            f"MarginV={margin_v},Alignment=2"
        )
        escaped_style = escape_ffmpeg_filter_style(style)
        safe_bar_height = max(80, bar_height)
        safe_opacity = max(0.0, min(bar_opacity, 0.95))
        filter_value = (
            f"drawbox=x=0:y=ih-{safe_bar_height}:w=iw:h={safe_bar_height}:"
            f"color=black@{safe_opacity}:t=fill,"
            f"subtitles=filename={escaped_subtitle}:force_style={escaped_style}"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_video),
            "-vf",
            filter_value,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast" if fast_mode else "veryfast",
            "-crf",
            "28" if fast_mode else "23",
            "-c:a",
            "copy",
            str(output_path),
        ]
        run_command(cmd)
        return output_path

    def mux_soft_subtitles(
        self,
        input_video: Path,
        subtitle_path: Path,
        output_path: Path,
    ) -> Path:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_video),
            "-i",
            str(subtitle_path),
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=chi",
            str(output_path),
        ]
        run_command(cmd)
        return output_path

    def has_subtitles_filter(self) -> bool:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            check=False,
        )
        return " subtitles " in result.stdout


class AudioComposer:
    def mix_bgm(
        self,
        input_video: Path,
        bgm_audio: Path,
        output_path: Path,
        bgm_volume: float = 0.18,
        fast_mode: bool = False,
    ) -> Path:
        if not input_video.exists():
            raise FileNotFoundError(f"视频文件不存在: {input_video}")
        if not bgm_audio.exists():
            raise FileNotFoundError(f"BGM 文件不存在: {bgm_audio}")
        check_command("ffmpeg")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        safe_volume = max(0.0, min(bgm_volume, 1.0))
        filter_complex = (
            "[0:a]volume=1.0[a0];"
            f"[1:a]volume={safe_volume}[a1];"
            "[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[a]"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_video),
            "-stream_loop",
            "-1",
            "-i",
            str(bgm_audio),
            "-filter_complex",
            filter_complex,
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
        run_command(cmd)
        return output_path


class WebhookDigitalHumanProvider:
    def __init__(self, config_path: Path) -> None:
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        self.config = json.loads(config_path.read_text(encoding="utf-8"))

    def generate(self, job: JobContext, timeout: int) -> Path:
        requests = import_requests()
        submit_url = self.config["submit_url"]
        method = self.config.get("method", "POST").upper()
        request_mode = self.config.get("request_mode", "json")
        headers = render_env_mapping(self.config.get("headers", {}))
        payload_template = self.config.get("payload_template", {})
        payload = render_payload(payload_template, job)
        file_handles = []
        files = None
        request_kwargs: dict[str, Any] = {
            "method": method,
            "url": submit_url,
            "headers": headers,
            "timeout": 60,
        }

        if request_mode == "form":
            files = build_upload_files(self.config.get("files_template", {}), job, file_handles)
            request_kwargs["data"] = flatten_form_payload(payload)
            if files:
                request_kwargs["files"] = files
        else:
            request_kwargs["json"] = payload

        try:
            response = requests.request(**request_kwargs)
        finally:
            for handle in file_handles:
                handle.close()
        response.raise_for_status()
        submit_data = response.json()

        job_id = read_json_path(submit_data, self.config.get("job_id_field", "id"))
        if not job_id:
            raise RuntimeError("提交成功，但没有在响应中找到 job_id。")

        status_url_template = self.config["status_url"]
        status_url = Template(status_url_template).safe_substitute(job_id=job_id)
        status_field = self.config.get("status_field", "status")
        result_url_field = self.config.get("result_url_field", "video_url")
        done_values = set(self.config.get("done_values", ["success", "completed"]))
        error_values = set(self.config.get("error_values", ["failed", "error"]))
        poll_interval = int(self.config.get("poll_interval", 8))

        start = time.time()
        while time.time() - start < timeout:
            poll_response = requests.get(status_url, headers=headers, timeout=60)
            poll_response.raise_for_status()
            poll_data = poll_response.json()

            status = str(read_json_path(poll_data, status_field))
            if status in done_values:
                video_url = read_json_path(poll_data, result_url_field)
                if not video_url:
                    raise RuntimeError("任务已完成，但没有找到视频下载地址。")
                download_file(video_url, job.video_path)
                return job.video_path

            if status in error_values:
                raise RuntimeError(f"数字人任务失败，状态: {status}，响应: {poll_data}")

            print(f"[轮询] 当前状态: {status}，{poll_interval} 秒后重试...", file=sys.stderr)
            time.sleep(poll_interval)

        raise TimeoutError(f"等待数字人视频生成超时，已等待 {timeout} 秒。")


class WebhookAvatarProvider:
    def __init__(self, config_path: Path) -> None:
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        self.config = json.loads(config_path.read_text(encoding="utf-8"))

    def generate(self, job: JobContext, prompt: str) -> Path:
        requests = import_requests()
        submit_url = self.config["submit_url"]
        method = self.config.get("method", "POST").upper()
        request_mode = self.config.get("request_mode", "json")
        headers = render_env_mapping(self.config.get("headers", {}))
        payload_template = self.config.get("payload_template", {})
        payload = render_payload(payload_template, job, avatar_prompt=prompt)
        request_kwargs: dict[str, Any] = {
            "method": method,
            "url": submit_url,
            "headers": headers,
            "timeout": 60,
        }
        if request_mode == "form":
            request_kwargs["data"] = flatten_form_payload(payload)
        else:
            request_kwargs["json"] = payload

        response = requests.request(**request_kwargs)
        response.raise_for_status()
        data = response.json()

        image_url = read_json_path(data, self.config.get("image_url_field", "data.url"))
        if not image_url:
            raise RuntimeError(f"AI 人像生成成功，但没有找到图片地址。响应: {data}")

        download_file(image_url, job.avatar_image_path)
        return job.avatar_image_path


class WebhookBackgroundProvider:
    def __init__(self, config_path: Path) -> None:
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        self.config = json.loads(config_path.read_text(encoding="utf-8"))

    def generate(self, job: JobContext, prompt: str) -> Path:
        requests = import_requests()
        submit_url = self.config["submit_url"]
        method = self.config.get("method", "POST").upper()
        request_mode = self.config.get("request_mode", "json")
        headers = render_env_mapping(self.config.get("headers", {}))
        payload_template = self.config.get("payload_template", {})
        payload = render_payload(payload_template, job, background_prompt=prompt)
        request_kwargs: dict[str, Any] = {
            "method": method,
            "url": submit_url,
            "headers": headers,
            "timeout": 60,
        }
        if request_mode == "form":
            request_kwargs["data"] = flatten_form_payload(payload)
        else:
            request_kwargs["json"] = payload

        response = requests.request(**request_kwargs)
        response.raise_for_status()
        data = response.json()

        image_url = read_json_path(data, self.config.get("image_url_field", "data.url"))
        if not image_url:
            raise RuntimeError(f"AI 背景图生成成功，但没有找到图片地址。响应: {data}")

        download_file(image_url, job.background_image_path)
        return job.background_image_path


class PexelsBaseProvider:
    keyword_mapping = {
        "便利店": "convenience store",
        "凌晨": "late night",
        "深夜": "night",
        "夜晚": "night",
        "夜景": "night city",
        "夜色": "night",
        "雨夜": "rainy night",
        "下雨": "rainy",
        "雨后": "after rain",
        "霓虹": "neon",
        "咖啡": "coffee",
        "落地窗": "window",
        "街头": "street",
        "城市": "city",
        "都市": "urban",
        "电影感": "cinematic",
        "温柔": "cozy",
        "孤独": "solitary",
        "治愈": "calm",
        "氛围": "atmospheric",
        "店内": "interior",
        "室内": "interior",
        "街景": "street",
        "反光": "reflections",
        "倒影": "reflections",
        "玻璃": "window",
        "窗边": "window side",
        "星河": "lights",
        "打篮球": "basketball game",
        "篮球": "basketball court",
        "球场": "basketball court",
        "教室": "classroom interior",
        "课堂": "classroom",
        "走廊": "school hallway",
        "廊道": "corridor",
        "校园": "school campus",
        "学校": "school",
        "学生": "students",
    }
    fallback_queries = [
        "night convenience store interior b roll",
        "coffee shop window at night b roll",
        "rainy window neon reflections b roll",
        "empty urban night storefront b roll",
        "close up coffee cup night window",
        "vending machine night close up",
        "empty city lights reflection",
        "quiet storefront interior night",
    ]

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.requests = import_requests()

    def build_queries(self, prompt: str) -> list[str]:
        normalized = prompt.strip().lower()
        if not normalized:
            return self.fallback_queries[:]

        english_hint = all(ord(char) < 128 for char in normalized)
        queries: list[str] = []
        if english_hint:
            queries.append(self.compact_query(normalized))
            queries.append(self.compact_query(f"{normalized} b roll"))
            queries.append(self.compact_query(f"{normalized} cinematic"))
        else:
            translated_terms: list[str] = []
            for source, target in self.keyword_mapping.items():
                if source in prompt:
                    translated_terms.append(target)
            translated_terms = list(dict.fromkeys(translated_terms))
            if translated_terms:
                queries.append(self.compact_query(" ".join(translated_terms)))
                queries.extend(self.compact_query(term) for term in translated_terms)
                queries.extend(self.compact_query(f"{term} b roll") for term in translated_terms[:3])

        if not queries:
            queries.extend(self.fallback_queries)
        deduped: list[str] = []
        for item in queries:
            compact = self.compact_query(item)
            if compact and compact not in deduped:
                deduped.append(compact)
        return deduped[:6]

    def compact_query(self, query: str) -> str:
        words = [word for word in query.replace(",", " ").split() if word]
        return " ".join(words[:10])

    def rotate_queries(self, queries: list[str], offset: int) -> list[str]:
        if not queries:
            return queries
        normalized_offset = offset % len(queries)
        return queries[normalized_offset:] + queries[:normalized_offset]


class PexelsBackgroundProvider(PexelsBaseProvider):
    search_url = "https://api.pexels.com/v1/search"

    def generate(
        self,
        job: JobContext,
        prompt: str,
        per_page: int = 8,
        avoid_ids: set[str] | None = None,
        preferred_index: int = 0,
    ) -> Path:
        queries = self.build_queries(prompt)
        best_photo: dict[str, Any] | None = None
        selected_query = ""
        last_data: dict[str, Any] | None = None
        for query in queries:
            response = self.requests.get(
                self.search_url,
                headers={"Authorization": self.api_key},
                params={
                    "query": query,
                    "orientation": "landscape",
                    "size": "large",
                    "locale": "en-US",
                    "per_page": per_page,
                    "page": 1,
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            last_data = data
            photos = data.get("photos") or []
            if photos:
                best_photo = self.select_best_photo(
                    photos,
                    avoid_ids=avoid_ids,
                    preferred_index=preferred_index,
                )
                selected_query = query
                break

        if not best_photo:
            raise RuntimeError(f"Pexels 没有找到匹配背景图，请调整提示词。响应: {last_data}")

        print(
            f"[提示] Pexels 使用检索词: {selected_query} (素材ID: {best_photo.get('id')})",
            file=sys.stderr,
        )
        source = best_photo.get("src") or {}
        image_url = (
            source.get("landscape")
            or source.get("large2x")
            or source.get("large")
            or source.get("original")
        )
        if not image_url:
            raise RuntimeError(f"Pexels 返回了结果，但没有可下载图片地址。响应: {best_photo}")

        download_file(
            str(image_url),
            job.background_image_path,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.pexels.com/",
            },
        )
        return job.background_image_path

    def select_best_photo(
        self,
        photos: list[dict[str, Any]],
        avoid_ids: set[str] | None = None,
        preferred_index: int = 0,
    ) -> dict[str, Any]:
        def score(photo: dict[str, Any]) -> tuple[int, int]:
            width = int(photo.get("width") or 0)
            height = int(photo.get("height") or 1)
            landscape_bonus = 1 if width >= height else 0
            return (landscape_bonus, width * height)

        ranked = sorted(photos, key=score, reverse=True)
        if avoid_ids:
            filtered = [photo for photo in ranked if str(photo.get("id")) not in avoid_ids]
            if filtered:
                ranked = filtered
        index = max(0, preferred_index) % max(len(ranked), 1)
        return ranked[index]


class PexelsVideoBackgroundProvider(PexelsBaseProvider):
    search_url = "https://api.pexels.com/videos/search"

    def generate(
        self,
        output_path: Path,
        prompt: str,
        per_page: int = 8,
        avoid_ids: set[str] | None = None,
        preferred_index: int = 0,
        preferred_page: int = 1,
    ) -> tuple[Path, str | None]:
        queries = self.rotate_queries(self.build_queries(prompt), preferred_index)
        best_video: dict[str, Any] | None = None
        selected_query = ""
        last_data: dict[str, Any] | None = None
        for query in queries:
            response = self.requests.get(
                self.search_url,
                headers={"Authorization": self.api_key},
                params={
                    "query": query,
                    "orientation": "landscape",
                    "size": "medium",
                    "per_page": per_page,
                    "page": max(1, preferred_page),
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            last_data = data
            videos = data.get("videos") or []
            if videos:
                best_video = self.select_best_video(
                    videos,
                    avoid_ids=avoid_ids,
                    preferred_index=preferred_index,
                )
                selected_query = query
                break

        if not best_video:
            raise RuntimeError(f"Pexels 没有找到匹配背景视频，请调整提示词。响应: {last_data}")

        print(
            f"[提示] Pexels 使用视频检索词: {selected_query} (素材ID: {best_video.get('id')})",
            file=sys.stderr,
        )
        video_files = best_video.get("video_files") or []
        file_info = self.select_best_video_file(video_files)
        if not file_info:
            raise RuntimeError(f"Pexels 返回了视频结果，但没有可下载文件。响应: {best_video}")

        download_file(
            str(file_info["link"]),
            output_path,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.pexels.com/",
            },
        )
        return output_path, str(best_video.get("id")) if best_video.get("id") is not None else None

    def select_best_video(
        self,
        videos: list[dict[str, Any]],
        avoid_ids: set[str] | None = None,
        preferred_index: int = 0,
    ) -> dict[str, Any]:
        def score(video: dict[str, Any]) -> tuple[int, int, int, int]:
            width = int(video.get("width") or 0)
            height = int(video.get("height") or 1)
            duration = int(video.get("duration") or 0)
            storyboard_duration_bonus = 1 if 18 <= duration <= 45 else 0
            duration_score = min(duration, 45)
            return (1 if width >= height else 0, storyboard_duration_bonus, duration_score, width * height)

        ranked = sorted(videos, key=score, reverse=True)
        if avoid_ids:
            filtered = [video for video in ranked if str(video.get("id")) not in avoid_ids]
            if filtered:
                ranked = filtered
        index = max(0, preferred_index) % max(len(ranked), 1)
        return ranked[index]

    def select_best_video_file(self, video_files: list[dict[str, Any]]) -> dict[str, Any] | None:
        mp4_files = [item for item in video_files if str(item.get("file_type", "")).lower() == "video/mp4"]
        if not mp4_files:
            return None
        landscape_files = [
            item for item in mp4_files
            if int(item.get("width") or 0) >= int(item.get("height") or 0)
        ] or mp4_files
        hd_files = [
            item for item in landscape_files
            if 960 <= int(item.get("width") or 0) <= 1920 and int(item.get("height") or 0) <= 1080
        ]
        if hd_files:
            return max(hd_files, key=lambda item: int(item.get("width") or 0) * int(item.get("height") or 0))
        medium_files = [
            item for item in landscape_files
            if int(item.get("width") or 0) <= 1920 and int(item.get("height") or 0) <= 1080
        ]
        if medium_files:
            return max(medium_files, key=lambda item: int(item.get("width") or 0) * int(item.get("height") or 0))
        return min(landscape_files, key=lambda item: int(item.get("width") or 99999) * int(item.get("height") or 99999))


class TencentDigitalHumanProvider:
    base_url = "https://gw.tvs.qq.com"

    def __init__(self, appkey: str, access_token: str, retry_count: int = 3, retry_delay: int = 5) -> None:
        self.appkey = appkey
        self.access_token = access_token
        self.requests = import_requests()
        self.retry_count = retry_count
        self.retry_delay = retry_delay

    def list_assets(self, virtualman_type_code: str, page_size: int = 20) -> dict[str, Any]:
        payload = {
            "Header": {},
            "Payload": {
                "VirtualmanTypeCode": virtualman_type_code,
                "PageIndex": 1,
                "PageSize": page_size,
            },
        }
        return self._post("/v2/ivh/crmserver/customerassetservice/getimagebyanchor", payload)

    def generate(
        self,
        job: JobContext,
        virtualman_key: str,
        driver_type: str,
        output_format: str,
        concurrency_type: str,
        speed: float,
        volume: float,
        timeout: int,
        input_audio_url: str | None = None,
    ) -> Path:
        driver_type_mapping = {
            "text": "Text",
            "original-voice": "OriginalVoice",
        }
        api_driver_type = driver_type_mapping[driver_type]
        payload_body: dict[str, Any] = {
            "VirtualmanKey": virtualman_key,
            "DriverType": api_driver_type,
            "VideoParam": {
                "Format": output_format,
            },
            "ConcurrencyType": concurrency_type,
            "ReqId": uuid4().hex,
        }

        if api_driver_type == "Text":
            payload_body["InputSsml"] = job.script
            payload_body["SpeechParam"] = {
                "Speed": speed,
                "Volume": volume,
            }
        else:
            if not input_audio_url:
                raise ValueError("腾讯云音频驱动模式必须提供 --tencent-audio-url")
            payload_body["InputAudioUrl"] = input_audio_url

        submit_data = self._post(
            "/v2/ivh/videomaker/broadcastservice/videomake",
            {"Header": {}, "Payload": payload_body},
        )
        self._raise_on_api_error(submit_data)
        task_id = read_json_path(submit_data, "Payload.TaskId")
        if not task_id:
            raise RuntimeError(f"腾讯云提交成功，但没有返回 TaskId。响应: {submit_data}")

        start_time = time.time()
        while time.time() - start_time < timeout:
            progress_data = self._post(
                "/v2/ivh/videomaker/broadcastservice/getprogress",
                {"Header": {}, "Payload": {"TaskId": task_id}},
            )
            self._raise_on_api_error(progress_data)
            status = str(read_json_path(progress_data, "Payload.Status") or "")
            progress = read_json_path(progress_data, "Payload.Progress")
            if status == "SUCCESS":
                media_url = read_json_path(progress_data, "Payload.MediaUrl")
                if not media_url:
                    raise RuntimeError(f"腾讯云任务成功，但没有返回 MediaUrl。响应: {progress_data}")
                download_file(str(media_url), job.video_path)
                return job.video_path

            if status == "FAIL" or progress == -1:
                fail_code = read_json_path(progress_data, "Payload.FailCode")
                fail_message = read_json_path(progress_data, "Payload.FailMessage")
                raise RuntimeError(
                    f"腾讯云视频生成失败，FailCode={fail_code}，FailMessage={fail_message}"
                )

            print(
                f"[轮询] 腾讯云任务状态: {status or 'UNKNOWN'}，进度: {progress}，8 秒后重试...",
                file=sys.stderr,
            )
            time.sleep(8)

        raise TimeoutError(f"等待腾讯云视频生成超时，已等待 {timeout} 秒。")

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = self._signed_url(path)
        return self._request_with_retry(url, payload)

    def _signed_url(self, path: str) -> str:
        timestamp = str(int(time.time()))
        query_params = {
            "appkey": self.appkey,
            "timestamp": timestamp,
        }
        signing_content = "&".join(
            f"{key}={query_params[key]}" for key in sorted(query_params.keys())
        )
        digest = hmac.new(
            self.access_token.encode("utf-8"),
            signing_content.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = quote_plus(base64.b64encode(digest).decode("utf-8"))
        return f"{self.base_url}{path}?{urlencode(query_params)}&signature={signature}"

    def _raise_on_api_error(self, data: dict[str, Any]) -> None:
        code = read_json_path(data, "Header.Code")
        if code in (None, 0):
            return
        message = read_json_path(data, "Header.Message")
        request_id = read_json_path(data, "Header.RequestID")
        raise RuntimeError(f"腾讯云接口返回错误，Code={code}，Message={message}，RequestID={request_id}")

    def _request_with_retry(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.retry_count + 1):
            try:
                response = self.requests.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json;charset=utf-8"},
                    timeout=60,
                )
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_error = exc
                if attempt >= self.retry_count:
                    break
                print(
                    f"[重试] 腾讯云请求失败，第 {attempt} 次重试后仍未成功，{self.retry_delay} 秒后继续...",
                    file=sys.stderr,
                )
                time.sleep(self.retry_delay)
        raise RuntimeError(f"腾讯云请求失败，已重试 {self.retry_count} 次。原始错误: {last_error}")


def import_requests() -> Any:
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError(
            "缺少依赖 `requests`，请执行 `python3 -m pip install requests` 后重试。"
        ) from exc
    return requests


def render_env_mapping(mapping: dict[str, Any]) -> dict[str, str]:
    rendered: dict[str, str] = {}
    for key, value in mapping.items():
        rendered[key] = Template(str(value)).safe_substitute(os.environ)
    return rendered


def flatten_form_payload(value: Any, prefix: str = "") -> dict[str, str]:
    if isinstance(value, dict):
        flattened: dict[str, str] = {}
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten_form_payload(item, next_prefix))
        return flattened

    if isinstance(value, list):
        flattened: dict[str, str] = {}
        for index, item in enumerate(value):
            next_prefix = f"{prefix}[{index}]"
            flattened.update(flatten_form_payload(item, next_prefix))
        return flattened

    if prefix == "":
        return {}
    return {prefix: "" if value is None else str(value)}


def build_upload_files(
    files_template: dict[str, Any],
    job: JobContext,
    file_handles: list[Any],
) -> dict[str, Any]:
    files: dict[str, Any] = {}
    rendered = render_payload(files_template, job)
    for field_name, file_path_value in rendered.items():
        file_path = Path(str(file_path_value)).expanduser().resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"上传文件不存在: {file_path}")
        mime_type = (
            "audio/mpeg"
            if file_path.suffix.lower() == ".mp3"
            else "image/png"
            if file_path.suffix.lower() == ".png"
            else "image/jpeg"
            if file_path.suffix.lower() in {".jpg", ".jpeg"}
            else "application/octet-stream"
        )
        handle = file_path.open("rb")
        file_handles.append(handle)
        files[field_name] = (file_path.name, handle, mime_type)
    return files


def render_payload(
    template_data: Any,
    job: JobContext,
    avatar_prompt: str = "",
    background_prompt: str = "",
) -> Any:
    context = {
        "title": job.title,
        "script": job.script,
        "audio_file_path": str(job.audio_path),
        "video_file_path": str(job.video_path),
        "avatar_file_path": str(job.avatar_image_path),
        "background_file_path": str(job.background_image_path),
        "avatar_prompt": avatar_prompt,
        "background_prompt": background_prompt,
    }

    if isinstance(template_data, dict):
        return {
            key: render_payload(
                value,
                job,
                avatar_prompt=avatar_prompt,
                background_prompt=background_prompt,
            )
            for key, value in template_data.items()
        }
    if isinstance(template_data, list):
        return [
            render_payload(
                item,
                job,
                avatar_prompt=avatar_prompt,
                background_prompt=background_prompt,
            )
            for item in template_data
        ]
    if isinstance(template_data, str):
        return Template(template_data).safe_substitute(context)
    return template_data


def read_json_path(data: Any, path: str) -> Any:
    current = data
    for segment in path.split("."):
        if segment == "":
            continue
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
    return current


def download_file(url: str, output_path: Path, headers: dict[str, str] | None = None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    request_headers = headers or {}
    if request_headers:
        requests = import_requests()
        with requests.get(url, headers=request_headers, stream=True, timeout=120) as response:
            response.raise_for_status()
            with output_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        handle.write(chunk)
        return

    with urllib.request.urlopen(url) as response, output_path.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def split_script_text(script: str, max_chars: int) -> list[str]:
    normalized = clean_script_text(script).replace("\r\n", "\n").strip()
    if len(normalized) <= max_chars:
        return [normalized]

    chunks: list[str] = []
    current = ""
    paragraphs = [item.strip() for item in normalized.split("\n") if item.strip()]
    for paragraph in paragraphs:
        sentences = split_paragraph(paragraph)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) > max_chars:
                smaller_parts = [sentence[i : i + max_chars] for i in range(0, len(sentence), max_chars)]
            else:
                smaller_parts = [sentence]

            for part in smaller_parts:
                part = part.strip()
                if not current:
                    current = part
                    continue
                separator = "" if current.endswith(("。", "！", "？", ".", "!", "?")) else " "
                candidate = current + separator + part
                if len(candidate) <= max_chars:
                    current = candidate
                else:
                    chunks.append(current.strip())
                    current = part
    if current:
        chunks.append(current.strip())
    return chunks


def split_paragraph(paragraph: str) -> list[str]:
    sentences: list[str] = []
    buffer = ""
    for char in paragraph:
        buffer += char
        if char in "。！？!?":
            sentences.append(buffer)
            buffer = ""
    if buffer.strip():
        sentences.append(buffer)
    return sentences


def get_video_duration(video_path: Path) -> float:
    check_command("ffprobe")
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"读取视频时长失败: {video_path}\n{result.stderr}")
    return float(result.stdout.strip())


def concat_audio_files(audio_paths: list[Path], output_path: Path) -> Path:
    existing_paths = [path for path in audio_paths if path.exists()]
    if not existing_paths:
        raise FileNotFoundError("没有找到可用于 Whisper 字幕的分段音频文件。")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    concat_file = output_path.with_suffix(".audio_concat.txt")
    concat_file.write_text(
        "\n".join(f"file {shlex.quote(str(path))}" for path in existing_paths),
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c:a",
        "libmp3lame",
        str(output_path),
    ]
    run_command(cmd)
    return output_path


def format_srt_timestamp(seconds: float) -> str:
    milliseconds = int(round(max(seconds, 0) * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def parse_srt_timestamp(value: str) -> float:
    hours, minutes, rest = value.strip().split(":")
    seconds, milliseconds = rest.split(",")
    total = (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(milliseconds) / 1000
    )
    return float(total)


def escape_ffmpeg_filter_path(path: Path) -> str:
    value = str(path.resolve())
    value = value.replace("\\", "\\\\")
    value = value.replace(":", "\\:")
    value = value.replace("'", r"\'")
    return value


def escape_ffmpeg_filter_style(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace(":", r"\:")
    escaped = escaped.replace(",", r"\,")
    escaped = escaped.replace("'", r"\'")
    return escaped


def build_manifest(job: JobContext, args: argparse.Namespace) -> None:
    manifest = {
        "job": job.as_dict(),
        "settings": {
            "tts_provider": args.tts_provider,
            "avatar_mode": args.avatar_mode,
            "video_mode": args.video_mode,
            "voice": args.voice,
            "rate": args.rate,
            "volume": args.volume,
            "avatar_image": args.avatar_image,
            "avatar_prompt": args.avatar_prompt,
            "avatar_config": args.avatar_config,
            "avatar_video": args.avatar_video,
            "webhook_config": args.webhook_config,
            "tencent_driver_type": args.tencent_driver_type,
            "tencent_virtualman_key": args.tencent_virtualman_key,
            "tencent_output_format": args.tencent_output_format,
            "retry_count": args.retry_count,
            "retry_delay": args.retry_delay,
            "auto_split": args.auto_split,
            "split_max_chars": args.split_max_chars,
            "add_subtitles": args.add_subtitles,
            "subtitle_provider": args.subtitle_provider,
            "subtitle_max_chars": args.subtitle_max_chars,
            "subtitle_offset": args.subtitle_offset,
            "subtitle_font_size": args.subtitle_font_size,
            "subtitle_margin_v": args.subtitle_margin_v,
            "subtitle_bar_height": args.subtitle_bar_height,
            "subtitle_bar_opacity": args.subtitle_bar_opacity,
            "subtitle_safe_lift": args.subtitle_safe_lift,
            "whisper_model": args.whisper_model,
            "whisper_language": args.whisper_language,
            "bgm_audio": args.bgm_audio,
            "bgm_volume": args.bgm_volume,
            "background_mode": args.background_mode,
            "background_image": args.background_image,
            "background_video": args.background_video,
            "background_prompt": args.background_prompt,
            "background_config": args.background_config,
            "pexels_per_page": args.pexels_per_page,
            "background_color": args.background_color,
            "background_similarity": args.background_similarity,
            "background_blend": args.background_blend,
            "background_despill": args.background_despill,
            "background_shadow": args.background_shadow,
            "background_feather": args.background_feather,
            "subject_scale": args.subject_scale,
            "subject_offset_x": args.subject_offset_x,
            "subject_offset_y": args.subject_offset_y,
            "subject_saturation": args.subject_saturation,
            "subject_gamma": args.subject_gamma,
        },
        "created_at": int(time.time()),
    }
    job.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_command(cmd: list[str]) -> None:
    printable = " ".join(shlex.quote(part) for part in cmd)
    print(f"[执行] {printable}", file=sys.stderr)
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"命令执行失败: {printable}")


def log_event(log_path: Path, event: str, **details: Any) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": int(time.time()),
        "event": event,
        "details": details,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_storyboard_prompt(base_prompt: str | None, segment_text: str) -> str:
    normalized = segment_text.replace("\n", " ").strip()
    lower_text = normalized.lower()
    scene_terms: list[str] = []
    if "便利店" in normalized:
        scene_terms.append("convenience store interior")
    if "咖啡" in normalized:
        scene_terms.append("coffee cup window")
    if "落地窗" in normalized or "窗" in normalized:
        scene_terms.append("window reflections")
    if "霓虹" in normalized:
        scene_terms.append("neon reflections")
    if "雨" in normalized:
        scene_terms.append("rainy night")
    if "城市" in normalized or "都市" in normalized:
        scene_terms.append("urban night")
    if "加班" in normalized or "独处" in normalized or "沉默" in normalized:
        scene_terms.append("quiet night b roll")
    if "自动贩卖机" in normalized:
        scene_terms.append("vending machine close up")
    if "黎明" in normalized or "明天" in normalized:
        scene_terms.append("night to dawn city lights")
    if not scene_terms and lower_text:
        scene_terms.append("cinematic night b roll")

    scene_suffix = " ".join(dict.fromkeys(scene_terms))
    base = (base_prompt or "").strip()
    guidance = "cinematic b roll realistic empty scene no crowd no traffic no vehicles"
    return " ".join(part for part in [base, scene_suffix, guidance] if part).strip()


def prepare_background_assets(job: JobContext, args: argparse.Namespace, prompt_override: str | None = None) -> argparse.Namespace:
    prepared_args = clone_args(args)
    if prepared_args.background_mode == "manual" and prepared_args.background_image:
        job.background_image_path = Path(prepared_args.background_image).resolve()
    elif prepared_args.background_mode == "webhook":
        if not prepared_args.background_config:
            raise ValueError("background-mode=webhook 时必须提供 --background-config")
        background_prompt = prompt_override or prepared_args.background_prompt
        if not background_prompt:
            raise ValueError("background-mode=webhook 时必须提供 --background-prompt")
        print("[步骤] 正在通过 AI 接口生成背景图...", file=sys.stderr)
        WebhookBackgroundProvider(Path(prepared_args.background_config)).generate(job, prompt=background_prompt)
        prepared_args.background_image = str(job.background_image_path)
        log_event(job.log_path, "background_generated", background_path=str(job.background_image_path))
    elif prepared_args.background_mode == "pexels":
        background_prompt = prompt_override or prepared_args.background_prompt or job.script
        if not background_prompt:
            raise ValueError("background-mode=pexels 时必须提供 --background-prompt")
        pexels_api_key = prepared_args.pexels_api_key or os.getenv("PEXELS_API_KEY")
        if not pexels_api_key:
            raise ValueError("background-mode=pexels 时必须提供 --pexels-api-key 或环境变量 PEXELS_API_KEY")
        print("[步骤] 正在通过 Pexels 搜索背景图...", file=sys.stderr)
        avoid_ids = getattr(prepared_args, "_pexels_avoid_ids", None)
        preferred_index = int(getattr(prepared_args, "_pexels_preferred_index", 0) or 0)
        PexelsBackgroundProvider(pexels_api_key).generate(
            job,
            prompt=background_prompt,
            per_page=prepared_args.pexels_per_page,
            avoid_ids=avoid_ids,
            preferred_index=preferred_index,
        )
        prepared_args.background_image = str(job.background_image_path)
        prepared_args.background_video = None
        log_event(job.log_path, "background_generated_pexels", background_path=str(job.background_image_path))
    elif prepared_args.background_mode == "pexels-video":
        background_prompt = prompt_override or prepared_args.background_prompt or job.script
        if not background_prompt:
            raise ValueError("background-mode=pexels-video 时必须提供 --background-prompt")
        pexels_api_key = prepared_args.pexels_api_key or os.getenv("PEXELS_API_KEY")
        if not pexels_api_key:
            raise ValueError("background-mode=pexels-video 时必须提供 --pexels-api-key 或环境变量 PEXELS_API_KEY")
        background_video_path = job.output_dir / f"{job.title}_background.mp4"
        print("[步骤] 正在通过 Pexels 搜索背景视频...", file=sys.stderr)
        avoid_ids = getattr(prepared_args, "_pexels_avoid_ids", None)
        preferred_index = int(getattr(prepared_args, "_pexels_preferred_index", 0) or 0)
        preferred_page = int(getattr(prepared_args, "_pexels_preferred_page", 1) or 1)
        _, selected_id = PexelsVideoBackgroundProvider(pexels_api_key).generate(
            background_video_path,
            prompt=background_prompt,
            per_page=prepared_args.pexels_per_page,
            avoid_ids=avoid_ids,
            preferred_index=preferred_index,
            preferred_page=preferred_page,
        )
        prepared_args.background_video = str(background_video_path)
        prepared_args.background_image = None
        if avoid_ids is not None and selected_id:
            avoid_ids.add(selected_id)
        log_event(job.log_path, "background_video_generated_pexels", background_video_path=str(background_video_path))
    return prepared_args


def validate_tencent_requirements(args: argparse.Namespace) -> None:
    if args.video_mode != "tencent" or args.tencent_list_assets:
        return
    appkey = args.tencent_appkey or os.getenv("TENCENT_DH_APPKEY")
    access_token = args.tencent_access_token or os.getenv("TENCENT_DH_ACCESS_TOKEN")
    virtualman_key = args.tencent_virtualman_key or os.getenv("TENCENT_DH_VIRTUALMAN_KEY")
    missing: list[str] = []
    if not appkey:
        missing.append("--tencent-appkey 或环境变量 TENCENT_DH_APPKEY")
    if not access_token:
        missing.append("--tencent-access-token 或环境变量 TENCENT_DH_ACCESS_TOKEN")
    if not virtualman_key:
        missing.append("--tencent-virtualman-key 或环境变量 TENCENT_DH_VIRTUALMAN_KEY")
    if missing:
        raise ValueError("video-mode=tencent 缺少腾讯云参数：" + "；".join(missing))


def render_video(job: JobContext, args: argparse.Namespace) -> Path:
    effective_subject_offset_y = args.subject_offset_y
    if args.add_subtitles:
        effective_subject_offset_y -= args.subtitle_safe_lift
    resolved_background_image = (
        Path(args.background_image).resolve()
        if args.background_image
        else job.background_image_path if job.background_image_path.exists() else None
    )
    resolved_background_video = Path(args.background_video).resolve() if args.background_video else None
    if args.video_mode == "local-image":
        if not job.avatar_image_path.exists():
            raise ValueError("未找到可用的人像图片，请提供 --avatar-image 或使用 --avatar-mode webhook")
        print("[步骤] 正在使用人像图片合成视频...", file=sys.stderr)
        LocalComposer().build_from_image(job.avatar_image_path, job.audio_path, job.video_path)
        log_event(job.log_path, "video_rendered_local_image", video_path=str(job.video_path))
    elif args.video_mode == "storyboard":
        storyboard_playlist = getattr(args, "_storyboard_background_playlist", None)
        if storyboard_playlist:
            print("[步骤] 正在生成无数字人短视频（背景视频序列 + 配音）...", file=sys.stderr)
            LocalComposer().build_story_from_video_playlist(
                storyboard_playlist,
                job.audio_path,
                job.video_path,
                trim_start=args.storyboard_video_trim_start,
                fast_mode=args.fast_mode,
            )
        elif resolved_background_video:
            print("[步骤] 正在生成无数字人短视频（背景视频 + 配音）...", file=sys.stderr)
            LocalComposer().build_story_from_video(
                resolved_background_video,
                job.audio_path,
                job.video_path,
                trim_start=args.storyboard_video_trim_start,
                fast_mode=args.fast_mode,
                segment_index=job.segment_index or 1,
            )
        elif resolved_background_image:
            print("[步骤] 正在生成无数字人短视频（背景图 + 配音）...", file=sys.stderr)
            LocalComposer().build_story_from_image(
                resolved_background_image,
                job.audio_path,
                job.video_path,
                fast_mode=args.fast_mode,
            )
        else:
            raise ValueError("video-mode=storyboard 时必须提供背景图或背景视频。")
        job.final_video_path = job.video_path
        log_event(job.log_path, "video_rendered_storyboard", video_path=str(job.video_path))
    elif args.video_mode == "local-video":
        if not args.avatar_video:
            raise ValueError("video-mode=local-video 时必须提供 --avatar-video")
        print("[步骤] 正在使用本地人物视频合成视频...", file=sys.stderr)
        LocalComposer().build_from_video(Path(args.avatar_video), job.audio_path, job.video_path)
        log_event(job.log_path, "video_rendered_local_video", video_path=str(job.video_path))
    elif args.video_mode == "webhook":
        if not args.webhook_config:
            raise ValueError("video-mode=webhook 时必须提供 --webhook-config")
        print("[步骤] 正在调用数字人 API 生成视频...", file=sys.stderr)
        WebhookDigitalHumanProvider(Path(args.webhook_config)).generate(job, timeout=args.timeout)
        log_event(job.log_path, "video_rendered_webhook", video_path=str(job.video_path))
    elif args.video_mode == "tencent":
        appkey = args.tencent_appkey or os.getenv("TENCENT_DH_APPKEY")
        access_token = args.tencent_access_token or os.getenv("TENCENT_DH_ACCESS_TOKEN")
        virtualman_key = args.tencent_virtualman_key or os.getenv("TENCENT_DH_VIRTUALMAN_KEY")
        if not appkey:
            raise ValueError("video-mode=tencent 时必须提供 --tencent-appkey 或环境变量 TENCENT_DH_APPKEY")
        if not access_token:
            raise ValueError(
                "video-mode=tencent 时必须提供 --tencent-access-token 或环境变量 TENCENT_DH_ACCESS_TOKEN"
            )
        if not virtualman_key:
            raise ValueError(
                "video-mode=tencent 时必须提供 --tencent-virtualman-key 或环境变量 TENCENT_DH_VIRTUALMAN_KEY"
            )
        print("[步骤] 正在调用腾讯云智能数智人生成视频...", file=sys.stderr)
        TencentDigitalHumanProvider(
            appkey,
            access_token,
            retry_count=args.retry_count,
            retry_delay=args.retry_delay,
        ).generate(
            job=job,
            virtualman_key=virtualman_key,
            driver_type=args.tencent_driver_type,
            output_format=args.tencent_output_format,
            concurrency_type=args.tencent_concurrency_type,
            speed=args.tencent_speed,
            volume=args.tencent_volume,
            timeout=args.timeout,
            input_audio_url=args.tencent_audio_url,
        )
        log_event(job.log_path, "video_rendered_tencent", video_path=str(job.video_path))
    else:
        print("[步骤] 跳过视频生成。", file=sys.stderr)

    if args.video_mode == "storyboard":
        return job.final_video_path

    if args.background_image or args.background_video or job.background_image_path.exists():
        print("[步骤] 正在替换绿幕背景...", file=sys.stderr)
        BackgroundComposer().replace_green_screen(
            foreground_video=job.video_path,
            output_path=job.final_video_path,
            background_image=resolved_background_image,
            background_video=resolved_background_video,
            color=args.background_color,
            similarity=args.background_similarity,
            blend=args.background_blend,
            despill=args.background_despill,
            shadow=args.background_shadow,
            feather=args.background_feather,
            subject_scale=args.subject_scale,
            subject_offset_x=args.subject_offset_x,
            subject_offset_y=effective_subject_offset_y,
            subject_saturation=args.subject_saturation,
            subject_gamma=args.subject_gamma,
        )
        log_event(job.log_path, "background_replaced", final_video_path=str(job.final_video_path))
    else:
        job.final_video_path = job.video_path
    return job.final_video_path


def process_segment_job(job: JobContext, args: argparse.Namespace) -> Path:
    job.output_dir.mkdir(parents=True, exist_ok=True)
    log_event(job.log_path, "segment_started", title=job.title)
    should_run_tts = True
    if args.video_mode == "tencent" and args.tencent_driver_type == "text":
        should_run_tts = False

    if should_run_tts and args.tts_provider == "edge":
        print("[步骤] 正在合成音频...", file=sys.stderr)
        asyncio.run(
            EdgeTTSProvider().synthesize(
                text=job.script,
                output_path=job.audio_path,
                voice=args.voice,
                rate=args.rate,
                volume=args.volume,
            )
        )
        log_event(job.log_path, "audio_synthesized", audio_path=str(job.audio_path))
    else:
        print("[步骤] 跳过音频合成。", file=sys.stderr)

    print("[步骤] 正在写入任务清单...", file=sys.stderr)
    build_manifest(job, args)
    final_path = render_video(job, args)
    log_event(job.log_path, "segment_completed", final_video_path=str(final_path))
    return final_path


def generate_subtitles_for_job(
    subtitle_composer: SubtitleComposer,
    subtitle_segments: list[tuple[str, float]],
    job: JobContext,
    args: argparse.Namespace,
    transition_overlap: float = 0.0,
) -> Path:
    if args.subtitle_provider == "whisper":
        whisper_model = args.whisper_model or os.getenv("WHISPER_MODEL_PATH") or ""
        if not whisper_model:
            raise ValueError("字幕模式为 whisper 时，必须提供 --whisper-model 或环境变量 WHISPER_MODEL_PATH")
        print("[步骤] 正在使用 Whisper 生成精准字幕...", file=sys.stderr)
        return subtitle_composer.generate_srt_from_whisper(
            audio_path=job.audio_path,
            output_path=job.subtitle_path,
            model_path=Path(whisper_model).resolve(),
            language=args.whisper_language,
            max_chars=args.subtitle_max_chars,
            subtitle_offset=args.subtitle_offset,
        )
    print("[步骤] 正在生成并烧录字幕...", file=sys.stderr)
    return subtitle_composer.generate_srt(
        subtitle_segments,
        job.subtitle_path,
        max_chars=args.subtitle_max_chars,
        transition_overlap=transition_overlap,
        subtitle_offset=args.subtitle_offset,
    )


def run_with_args(args: argparse.Namespace) -> dict[str, Any]:
    script = load_script_text(args)
    if not script and not args.tencent_list_assets:
        raise ValueError("文案为空，请传入 --text 或输入有效内容。")

    title = slugify(args.title)
    output_dir = Path(args.output_dir).resolve() / title
    audio_path = output_dir / f"{title}.mp3"
    video_path = output_dir / f"{title}.mp4"
    final_video_path = output_dir / f"{title}_final.mp4"
    subtitle_path = output_dir / f"{title}.srt"
    avatar_image_path = output_dir / f"{title}_avatar.png"
    background_image_path = output_dir / f"{title}_background.png"
    manifest_path = output_dir / "job_manifest.json"
    log_path = output_dir / "run.log.jsonl"
    output_dir.mkdir(parents=True, exist_ok=True)

    job = JobContext(
        title=title,
        script=script,
        output_dir=output_dir,
        audio_path=audio_path,
        video_path=video_path,
        final_video_path=final_video_path,
        subtitle_path=subtitle_path,
        avatar_image_path=avatar_image_path,
        background_image_path=background_image_path,
        manifest_path=manifest_path,
        log_path=log_path,
    )
    log_event(job.log_path, "job_started", title=job.title, video_mode=args.video_mode)

    if args.avatar_mode == "manual" and args.avatar_image:
        job.avatar_image_path = Path(args.avatar_image).resolve()
    elif args.avatar_mode == "webhook":
        if not args.avatar_config:
            raise ValueError("avatar-mode=webhook 时必须提供 --avatar-config")
        if not args.avatar_prompt:
            raise ValueError("avatar-mode=webhook 时必须提供 --avatar-prompt")
        print("[步骤] 正在通过 AI 接口生成人像...", file=sys.stderr)
        WebhookAvatarProvider(Path(args.avatar_config)).generate(job, prompt=args.avatar_prompt)
        log_event(job.log_path, "avatar_generated", avatar_path=str(job.avatar_image_path))
    elif args.avatar_mode == "manual" and not args.avatar_image and args.video_mode == "local-image":
        raise ValueError("video-mode=local-image 时必须提供 --avatar-image，或改用 --avatar-mode webhook")

    validate_tencent_requirements(args)

    dynamic_storyboard_backgrounds = (
        args.video_mode == "storyboard" and args.auto_split and args.storyboard_dynamic_backgrounds
    )
    if not dynamic_storyboard_backgrounds:
        args = prepare_background_assets(job, args)

    if args.video_mode == "tencent" and args.tencent_list_assets:
        appkey = args.tencent_appkey or os.getenv("TENCENT_DH_APPKEY")
        access_token = args.tencent_access_token or os.getenv("TENCENT_DH_ACCESS_TOKEN")
        if not appkey or not access_token:
            raise ValueError("查询腾讯云资产前，请提供 --tencent-appkey 和 --tencent-access-token")
        if not args.tencent_virtualman_type_code:
            raise ValueError("查询腾讯云资产时必须提供 --tencent-virtualman-type-code")
        provider = TencentDigitalHumanProvider(appkey, access_token)
        asset_data = provider.list_assets(
            virtualman_type_code=args.tencent_virtualman_type_code,
            page_size=args.tencent_page_size,
        )
        log_event(job.log_path, "tencent_assets_listed", virtualman_type_code=args.tencent_virtualman_type_code)
        return asset_data

    if args.auto_split:
        segments = split_script_text(job.script, args.split_max_chars)
        log_event(job.log_path, "script_split", segment_count=len(segments), split_max_chars=args.split_max_chars)
        print(f"[步骤] 文案已拆分为 {len(segments)} 段，开始逐段生成...", file=sys.stderr)
        segment_outputs: list[Path] = []
        subtitle_segments: list[tuple[str, float]] = []
        segment_audio_paths: list[Path] = []
        segments_dir = job.output_dir / "segments"
        used_pexels_ids: set[str] = set()
        storyboard_backgrounds = load_storyboard_backgrounds_manifest(args.storyboard_backgrounds_manifest)
        for index, segment_text in enumerate(segments, start=1):
            print(f"[步骤] 正在生成第 {index}/{len(segments)} 段...", file=sys.stderr)
            segment_dir = segments_dir / f"part_{index:02d}"
            segment_job = job.clone_for_segment(index=index, script=segment_text, segment_dir=segment_dir)
            segment_args = args
            if args.video_mode == "storyboard" and storyboard_backgrounds:
                background_item = storyboard_backgrounds[(index - 1) % len(storyboard_backgrounds)]
                storyboard_playlist = rotate_storyboard_backgrounds(storyboard_backgrounds, index - 1)
                segment_args = clone_args(
                    args,
                    background_mode="manual",
                    background_image=background_item.get("background_image") or None,
                    background_video=background_item.get("background_video") or None,
                    _storyboard_background_playlist=storyboard_playlist,
                )
            if dynamic_storyboard_backgrounds:
                segment_prompt = build_storyboard_prompt(args.background_prompt, segment_text)
                override_args = clone_args(
                    segment_args,
                    _pexels_avoid_ids=used_pexels_ids,
                    _pexels_preferred_index=max(0, index - 1),
                    _pexels_preferred_page=((index - 1) % 3) + 1,
                )
                if segment_args.background_mode in {"pexels", "pexels-video", "webhook", "none"}:
                    override_args = clone_args(
                        override_args,
                        background_image=None,
                        background_video=None,
                    )
                segment_args = prepare_background_assets(
                    segment_job,
                    override_args,
                    prompt_override=segment_prompt,
                )
            segment_output = process_segment_job(segment_job, segment_args)
            segment_outputs.append(segment_output)
            if segment_job.audio_path.exists():
                segment_audio_paths.append(segment_job.audio_path)
            subtitle_segments.append((segment_text, get_video_duration(segment_output)))
        print("[步骤] 正在拼接分段视频...", file=sys.stderr)
        transition_overlap = 0.0
        if args.video_mode == "storyboard" and args.storyboard_transitions:
            transition_overlap = max(0.2, min(args.storyboard_transition_duration, 1.5))
            ConcatComposer().concat_with_transitions(
                segment_outputs,
                job.final_video_path,
                transition_duration=transition_overlap,
                fast_mode=args.fast_mode,
            )
        else:
            ConcatComposer().concat_videos(segment_outputs, job.final_video_path)
        log_event(job.log_path, "segments_concatenated", final_video_path=str(job.final_video_path))
        if args.add_subtitles:
            if args.subtitle_provider == "whisper" and not job.audio_path.exists() and segment_audio_paths:
                print("[步骤] 正在拼接分段音频供 Whisper 识别...", file=sys.stderr)
                concat_audio_files(segment_audio_paths, job.audio_path)
            subtitle_composer = SubtitleComposer()
            generate_subtitles_for_job(
                subtitle_composer,
                subtitle_segments,
                job,
                args,
                transition_overlap=transition_overlap,
            )
            subtitled_output = job.output_dir / f"{job.title}_subtitled.mp4"
            subtitle_composer.burn_subtitles(
                input_video=job.final_video_path,
                subtitle_path=job.subtitle_path,
                output_path=subtitled_output,
                font_size=args.subtitle_font_size,
                margin_v=args.subtitle_margin_v,
                bar_height=args.subtitle_bar_height,
                bar_opacity=args.subtitle_bar_opacity,
                fast_mode=args.fast_mode,
            )
            job.final_video_path = subtitled_output
            log_event(job.log_path, "subtitles_burned", final_video_path=str(job.final_video_path))
    else:
        process_segment_job(job, args)
        if args.add_subtitles:
            subtitle_composer = SubtitleComposer()
            generate_subtitles_for_job(
                subtitle_composer,
                [(job.script, get_video_duration(job.final_video_path))],
                job,
                args,
            )
            subtitled_output = job.output_dir / f"{job.title}_subtitled.mp4"
            subtitle_composer.burn_subtitles(
                input_video=job.final_video_path,
                subtitle_path=job.subtitle_path,
                output_path=subtitled_output,
                font_size=args.subtitle_font_size,
                margin_v=args.subtitle_margin_v,
                bar_height=args.subtitle_bar_height,
                bar_opacity=args.subtitle_bar_opacity,
                fast_mode=args.fast_mode,
            )
            job.final_video_path = subtitled_output
            log_event(job.log_path, "subtitles_burned", final_video_path=str(job.final_video_path))

    if args.bgm_audio:
        print("[步骤] 正在混入背景音乐...", file=sys.stderr)
        bgm_output = job.output_dir / f"{job.title}_with_bgm.mp4"
        AudioComposer().mix_bgm(
            input_video=job.final_video_path,
            bgm_audio=Path(args.bgm_audio).resolve(),
            output_path=bgm_output,
            bgm_volume=args.bgm_volume,
            fast_mode=args.fast_mode,
        )
        job.final_video_path = bgm_output
        log_event(job.log_path, "bgm_mixed", final_video_path=str(job.final_video_path), bgm_audio=args.bgm_audio)

    log_event(job.log_path, "job_completed", final_video_path=str(job.final_video_path))
    return job.as_dict()


def main() -> None:
    args = parse_args()
    result = run_with_args(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
