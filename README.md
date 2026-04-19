# Script2Short

Script-to-Short-Video Generation System

Script2Short 是一个面向中文创作场景的本地 AI 短视频生成系统，支持从想法 / 文案到配音、字幕、背景素材、BGM 和成片导出的一体化生成。

## Features

- AI 生成标题、文案、背景提示词和推荐配置
- 支持中文 / English 双语文案生成、配音和字幕配置
- 内容短视频模式：背景视频 / 背景图 + 配音 + 字幕 + BGM
- Pexels 背景图 / 背景视频检索、候选预览、手动挑选和排序
- Edge TTS 中文配音与音色试听
- Whisper 精准字幕和快速字幕两种模式
- 本地上传背景素材、BGM，以及按情绪标签选择本地音乐库
- 长文案自动分段、背景自动编排、转场和最终视频导出
- 本地网页工作台，任务日志、缓存素材和成片都保存在本机

## Architecture

```text
想法 / 文案输入
        │
        ├── Gemini：生成标题 / 文案 / 背景提示词
        ├── Pexels：检索背景图 / 背景视频候选
        ├── Edge TTS：生成中文配音
        ├── Whisper：生成精准字幕时间戳（可选）
        └── FFmpeg：素材拼接 / 字幕烧录 / BGM 混音 / 成片导出
                           │
                           └── 最终视频 / 日志 / 中间素材输出到本地
```

核心文件：

- [web_app.py](./web_app.py)：本地网页工作台
- [video_pipeline.py](./video_pipeline.py)：核心视频生成链路
- [.env.example](./.env.example)：本地密钥配置模板
- [music_library.example.json](./music_library.example.json)：本地音乐库配置示例
- [PROJECT_STATUS.md](./PROJECT_STATUS.md)：当前功能状态
- [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)：第三方服务与素材说明

## Quick Start

安装 Python 依赖：

```bash
pip install -r requirements.txt
```

安装 FFmpeg。macOS 推荐：

```bash
brew install ffmpeg-full
```

复制本地配置：

```bash
cp .env.example .env
```

在 `.env` 中填写你的 Key：

```env
GEMINI_API_KEY=your_gemini_api_key
PEXELS_API_KEY=your_pexels_api_key
WHISPER_MODEL_PATH=/absolute/path/to/ggml-base.bin
```

启动网页：

```bash
python3 web_app.py
```

默认地址：

```text
http://127.0.0.1:8765
```

## Web Workflow

推荐优先使用网页，而不是直接敲命令行：

1. 输入想法或文案
2. 使用 Gemini 生成标题、文案和背景提示词
3. 选择懒人模式或精修模式
4. 使用 Pexels 自动搜索或手动挑选背景素材
5. 选择配音音色、字幕模式和 BGM
6. 点击开始生成
7. 在任务状态区查看日志、预览和下载成片

## Local Music Library

项目不会内置音乐文件，避免版权风险。你可以把自己有权使用的音乐放入本地目录：

```text
music_library/
├── warm_campus.mp3
├── city_night_chill.mp3
└── hopeful_piano.mp3
```

复制示例配置：

```bash
cp music_library.example.json music_library.json
```

示例：

```json
{
  "tracks": [
    {
      "file": "warm_campus.mp3",
      "mood": "校园",
      "start": 0,
      "volume": 0.18
    }
  ]
}
```

网页里的 `BGM 来源` 选择 `本地音乐库` 后，就可以按情绪标签自动挑选音乐。

`music_library/` 和 `music_library.json` 默认不会提交到 GitHub。

## CLI Example

网页是推荐入口；命令行主要用于调试。

```bash
python3 video_pipeline.py \
  --title "campus_story" \
  --text "清晨的校园被阳光慢慢照亮，新的故事也从这一刻开始。" \
  --video-mode storyboard \
  --background-mode pexels-video \
  --background-prompt "university campus morning light students walking cinematic" \
  --auto-split \
  --add-subtitles
```

## Screenshots

项目截图可以放在 `docs/screenshots/` 目录中，推荐补充：

- `docs/screenshots/home.png`
- `docs/screenshots/candidates.png`
- `docs/screenshots/jobs.png`

## Local-Only Files

API Key、Whisper 模型、运行产物和本地音乐素材都只在本机管理。仓库已通过 `.gitignore` 排除 `.env`、`web_runs/`、`output/`、`models/`、`music_library/` 和 `music_library.json` 等本地文件，避免把密钥、大文件或未授权素材提交到 GitHub。

## Third-Party Services

本项目会调用或引用以下第三方服务 / 素材：

- Gemini API：用于文案生成
- Pexels API：用于搜索背景图片 / 视频
- Edge TTS：用于本地语音合成
- Whisper / whisper.cpp：用于精准字幕，可选
- FFmpeg：用于视频合成、转码、字幕和混音
- Unsplash / Wikimedia Commons：网页背景视觉素材远程引用

详见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)。

## License

MIT License，详见 [LICENSE](./LICENSE)。
