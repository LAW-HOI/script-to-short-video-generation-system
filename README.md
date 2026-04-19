# AI 短视频生成平台

一个面向中文创作场景的本地 AI 短视频生成平台，支持：

- AI 生成标题、文案、背景提示词
- 内容短视频模式：背景视频 + 配音 + 字幕 + 分镜编排
- 数字人口播模式：接入腾讯云智能数智人 API
- Pexels 背景图 / 背景视频检索与候选挑选
- 本地上传背景素材与 BGM
- Whisper 精准字幕与普通快速字幕

项目同时提供：

- 命令行脚本：[video_pipeline.py](./video_pipeline.py)
- 本地网页平台：[web_app.py](./web_app.py)

适合的场景包括：

- 治愈系旁白短视频
- 校园 / 生活 / 氛围向内容短视频
- 产品介绍 / 数字人口播视频
- 想法到成片的快速验证

## 界面预览

项目截图可以放在 `docs/screenshots/` 目录中，推荐补充以下三类图片：

- 网页首页截图：`docs/screenshots/home.png`
- 候选背景挑选页：`docs/screenshots/candidates.png`
- 任务状态与成片预览：`docs/screenshots/jobs.png`

## 第三方服务与素材说明

本项目会调用或引用一些第三方服务/素材，上传 GitHub 前建议保留这段说明：

- `Gemini API`：用于文案生成，需要用户自行配置 API Key。
- `Pexels API`：用于搜索背景图片/视频，需要用户自行配置 API Key；素材使用需遵守 Pexels 许可和平台条款。
- `腾讯云智能数智人 API`：用于数字人口播，需要用户自行配置腾讯云参数。
- `Edge TTS`：用于本地配音合成，依赖 `edge-tts` Python 包。
- `Whisper/whisper.cpp`：用于精准字幕，可选，需要用户自行下载模型文件。
- `Unsplash`：网页背景封面图来自 Unsplash，代码中仅引用远程图片 URL。
- `Wikimedia Commons`：网页真实海浪背景视频引用 Wikimedia Commons 远程视频 URL。

真实密钥、生成视频、缓存素材、本地模型文件不应提交到仓库。

## 系统架构

```text
想法 / 文案输入
        │
        ├── Gemini：生成标题 / 文案 / 背景提示词 / 推荐模式
        │
        ├── Pexels：检索背景图 / 背景视频候选
        │
        ├── Edge TTS：生成中文配音
        │
        ├── Whisper：生成精准字幕时间戳（可选）
        │
        ├── 腾讯云智能数智人：数字人口播模式（可选）
        │
        └── ffmpeg：素材拼接 / 字幕烧录 / BGM 混音 / 成片导出
                           │
                           └── 最终视频 / 日志 / 中间素材输出到本地
```

对应关系：

- [web_app.py](./web_app.py)：网页交互层
- [video_pipeline.py](./video_pipeline.py)：核心生成链路
- `web_runs/` / `output/`：本地产物目录

## 功能亮点

- 同时支持 `内容短视频模式` 和 `数字人口播模式`
- 支持 AI 生成标题、文案、背景提示词和推荐模式
- 支持 Pexels 背景图 / 背景视频候选预览、挑选和排序
- 支持本地上传背景素材、BGM，以及按情绪标签选择本地音乐库
- 支持自动字幕、Whisper 精准字幕和字幕偏移微调
- 支持长文案自动分段、自动拼接和轻微转场
- 支持网页端和命令行双入口，底层共用同一条生成链路
- 支持 `.env` 自动读取本地配置，适合长期使用

## Roadmap

后续还可以继续演进这些方向：

- 批量任务队列与任务历史持久化
- 更多短视频模板预设，如校园、治愈、产品讲解
- 更完整的素材面板与时间线式背景排序
- 自动封面图与标题卡
- 更丰富的字幕样式、重点词高亮与双语字幕
- 更稳定的数字人背景融合与口播模板
- 本地模型与在线模型的统一配置中心

## 文件说明

- `video_pipeline.py`: 主脚本
- `requirements.txt`: Python 依赖
- `webhook_config.example.json`: 数字人 API 示例配置
- `avatar_webhook_config.example.json`: AI 人像生成接口示例配置
- `background_webhook_config.example.json`: AI 背景图生成接口示例配置
- `web_app.py`: 本地网页工作台
- `.env.example`: 本地密钥配置模板，复制为 `.env` 后可自动读取
- `LICENSE`: MIT 开源许可证
- `THIRD_PARTY_NOTICES.md`: 第三方服务与素材说明
- `PROJECT_STATUS.md`: 当前功能状态与开源检查说明
- `music_library.example.json`: 本地音乐库配置示例，不包含真实音乐文件

## 快速开始

```bash
pip install -r requirements.txt
```

如果你走 `webhook` 在线数字人模式，只需要 Python 依赖，不需要 `ffmpeg`。
只有 `local-image`、`local-video` 和“绿幕换背景”后处理才需要 `ffmpeg`。

推荐先配置本地 `.env`：

```bash
cp .env.example .env
```

把 `.env` 改成你的真实 key：

```text
GEMINI_API_KEY="你的 Gemini API Key"
PEXELS_API_KEY="你的 Pexels API Key"
TENCENT_DH_APPKEY="你的 appkey"
TENCENT_DH_ACCESS_TOKEN="你的 access token"
TENCENT_DH_VIRTUALMAN_KEY="你的 VirtualmanKey"
WHISPER_MODEL_PATH="/你的模型路径/ggml-base.bin"
```

### 启动网页平台

如果你更喜欢在网页里操作，而不是每次敲命令，可以直接启动本地平台：

```bash
python3 web_app.py
```

默认地址：

```text
http://127.0.0.1:8765
```

### 最短命令行示例

只生成音频：

```bash
python3 video_pipeline.py \
  --title "demo" \
  --text "大家好，今天给大家介绍我们的新产品。" \
  --video-mode none
```

直接生成腾讯云数字人口播：

```bash
python3 video_pipeline.py \
  --title "demo_tencent" \
  --text "大家好，今天给大家介绍我们的新产品。" \
  --video-mode tencent
```

## 核心能力

网页端已经内置这些能力：

- 文案输入
- AI 生成标题 / 文案 / 背景提示词
- 腾讯云参数输入
- 长文案自动分段开关
- 自动字幕开关
- Whisper 精准字幕
- 背景图 / 背景视频 / Pexels 候选素材
- 本地上传背景和 BGM
- 本地音乐库：按情绪标签自动选择 BGM
- 任务状态轮询、日志查看、成片预览与下载

网页版本本质上还是调用同目录下的 `video_pipeline.py`，所以命令行版和网页版的生成结果会保持一致。

`.env` 已经被 `.gitignore` 忽略，不建议把真实密钥写进 Python 源码或提交到仓库。

## 本地音乐库

项目不会内置音乐文件，避免版权风险。你可以把自己有权使用的音乐放入本地目录：

```text
music_library/
├── warm_campus.mp3
├── city_night_chill.mp3
└── hopeful_piano.mp3
```

然后复制示例配置：

```bash
cp music_library.example.json music_library.json
```

把 `music_library.json` 改成你的真实文件名和情绪标签：

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

网页里的 `BGM 来源` 选择 `本地音乐库` 后，就可以按情绪标签自动挑选音乐。`music_library/` 和 `music_library.json` 默认不会提交到 GitHub。

## 推荐使用路径

如果你是第一次使用，推荐按这个顺序体验：

1. 在 `.env` 中配置 `GEMINI_API_KEY` 和 `PEXELS_API_KEY`
2. 启动网页平台：`python3 web_app.py`
3. 先使用 `内容短视频模式（无数字人）`
4. 让 AI 生成标题、文案和背景提示词
5. 用 `Pexels 背景视频` 预览并挑选候选素材
6. 打开自动字幕，先用快速模式验证成片
7. 如果需要更准的字幕，再切到 Whisper 精准模式

如果你明确需要人物口播，再切换到腾讯云数字人口播模式。

## 项目结构

```text
Code/auto_digit/
├── video_pipeline.py                         # 主生成脚本，命令行和网页共用
├── web_app.py                      # 本地网页平台
├── requirements.txt                # Python 依赖
├── .env.example                    # 本地密钥配置模板
├── LICENSE                         # MIT 开源许可证
├── docs/screenshots/               # 项目截图目录
├── webhook_config.example.json     # 数字人 webhook 配置模板
├── avatar_webhook_config.example.json
├── background_webhook_config.example.json
├── models/                         # Whisper 模型等本地模型文件，本地使用，默认不提交
└── web_runs/                       # 网页任务输出目录，本地使用，默认不提交
```

## 开源前检查

上传 GitHub 前，请确认以下文件和目录没有被提交：

- `.env`
- `web_runs/`
- `output/`
- `models/`
- `__pycache__/`
- `.DS_Store`
- 本地生成的 `*.mp4`、`*.mp3`、`*.wav`、`*.m4a`

这些内容已写入 `.gitignore`，但首次提交前仍建议使用 `git status` 再确认一次。

## 模式说明

### 内容短视频模式

适合：

- 治愈系旁白视频
- 校园 / 生活 / 氛围内容
- 产品宣传片的 B-roll 版本

特点：

- 本地 TTS 配音
- 背景视频 / 背景图自动编排
- 自动字幕
- 支持 BGM
- 更自然，不依赖数字人绿幕合成

### 腾讯云数字人口播模式

适合：

- 明确需要人像口播
- 主播式讲解
- 数字人品牌视频

特点：

- 调用腾讯云智能数智人 API
- 可配绿幕换背景
- 更接近口播展示，但对背景匹配要求更高

如果你不想用 `.env`，也可以继续临时设置环境变量：

```bash
export TENCENT_DH_APPKEY="你的 appkey"
export TENCENT_DH_ACCESS_TOKEN="你的 access token"
export TENCENT_DH_VIRTUALMAN_KEY="你的 VirtualmanKey"
export GEMINI_API_KEY="你的 Gemini API Key"
export PEXELS_API_KEY="你的 Pexels API Key"
```

## 数字人口播模式

```bash
python3 video_pipeline.py \
  --title "demo_tencent" \
  --text "大家好，今天给大家介绍我们的新产品。" \
  --video-mode tencent
```

这条链路会做三件事：

- 直接把文案发给腾讯云
- 由腾讯云侧完成语音驱动
- 轮询任务状态并下载生成后的视频

默认使用 `text` 文本驱动，所以不依赖本地 `ffmpeg`，也不强制依赖本地 TTS。

## 给绿幕视频换背景

如果腾讯云输出的是绿幕视频，你可以在生成后自动替换背景。

用背景图：

```bash
python3 video_pipeline.py \
  --title "demo_tencent_bg" \
  --text "大家好，今天给大家介绍我们的新产品。" \
  --video-mode tencent \
  --background-image ./background.jpg
```

用背景视频：

```bash
python3 video_pipeline.py \
  --title "demo_tencent_bg_video" \
  --text "大家好，今天给大家介绍我们的新产品。" \
  --video-mode tencent \
  --background-video ./background.mp4
```

相关参数：

- `--background-color`：默认 `0x00FF00`
- `--background-similarity`：默认 `0.22`
- `--background-blend`：默认 `0.09`
- `--background-despill`：默认 `0.10`
- `--background-shadow`：默认 `0.45`
- `--background-feather`：默认 `0.8`
- `--subject-scale`：默认 `0.82`
- `--subject-offset-y`：默认 `18`
- `--subject-saturation`：默认 `0.96`
- `--subject-gamma`：默认 `1.03`

如果抠像边缘发虚、绿边明显，或人物像贴在背景上，可以小幅调整这些值。

生成后：

- 腾讯云原始视频：`output/<title>/<title>.mp4`
- 换背景后的成片：`output/<title>/<title>_final.mp4`
- 运行日志：`output/<title>/run.log.jsonl`

## 用 Pexels 自动找背景图

如果你已经申请到 `Pexels API Key`，这是目前最省事的背景方案。

先设置环境变量：

```bash
export PEXELS_API_KEY="你的 Pexels API Key"
```

然后直接执行：

```bash
python3 video_pipeline.py \
  --title "midnight_store" \
  --text "你的长文案" \
  --video-mode tencent \
  --auto-split \
  --background-mode pexels \
  --background-prompt "midnight convenience store, rainy street, neon reflections, cinematic, cozy, city night"
```

网页版里也可以直接把 `背景方式` 切到 `Pexels 背景图`。
当前脚本会对中文/氛围化提示词做一层检索词优化，再去 Pexels 搜索，更适合找图库背景素材。

## 用 Pexels 自动找背景视频

如果你希望效果更接近 `short-video-maker` 的动态背景思路，可以直接使用 Pexels 背景视频：

```bash
export PEXELS_API_KEY="你的 Pexels API Key"

python3 video_pipeline.py \
  --title "midnight_store" \
  --text "你的长文案" \
  --video-mode tencent \
  --auto-split \
  --background-mode pexels-video \
  --background-prompt "midnight convenience store, rainy city street, neon reflections, cinematic, cozy, urban night"
```

网页版里也可以直接把 `背景方式` 切到 `Pexels 背景视频`。

如果同时是长文案分段：

```bash
python3 video_pipeline.py \
  --title "midnight_store" \
  --text "你的长文案" \
  --video-mode tencent \
  --auto-split \
  --background-mode pexels-video \
  --background-prompt "midnight convenience store, rainy city street, neon reflections, cinematic, cozy, urban night"
```

## 腾讯云原声驱动模式

如果你有已经放在公网的音频地址，可以切换成音频驱动：

```bash
python3 video_pipeline.py \
  --title "demo_tencent_audio" \
  --text "大家好，今天用一段真实录音来驱动数字人口播。" \
  --video-mode tencent \
  --tencent-driver-type original-voice \
  --tencent-audio-url "https://your-public-audio.example.com/demo.mp3"
```

## 查询腾讯云形象资产

如果你还没有找到 `VirtualmanKey`，可以先查询账号下的形象资产：

```bash
python3 video_pipeline.py \
  --video-mode tencent \
  --tencent-list-assets \
  --tencent-virtualman-type-code "你的 VirtualmanTypeCode"
```

返回结果里一般能继续看到形象相关字段，你可以据此去确认可用资产。

## 稳定性参数

脚本支持简单重试和日志输出：

- `--retry-count`：接口最大重试次数，默认 `3`
- `--retry-delay`：每次重试间隔秒数，默认 `5`

## 长文案自动分段

如果文案较长，推荐开启自动分段，让脚本逐段生成后再自动拼接：

```bash
python3 video_pipeline.py \
  --title "midnight_store" \
  --text "你的长文案" \
  --video-mode tencent \
  --auto-split \
  --split-max-chars 120
```

如果同时要换背景：

```bash
python3 video_pipeline.py \
  --title "midnight_store" \
  --text "你的长文案" \
  --video-mode tencent \
  --auto-split \
  --split-max-chars 120 \
  --background-image ./background.jpg
```

生成后目录中会多出：

- `output/<title>/segments/`：每一段的中间文件
- `output/<title>/<title>_final.mp4`：最终拼接成片

## 自动字幕

如果你希望成片直接带字幕，可以加：

```bash
python3 video_pipeline.py \
  --title "midnight_store" \
  --text "你的长文案" \
  --video-mode tencent \
  --auto-split \
  --add-subtitles
```

可调参数：

- `--subtitle-max-chars`：每条字幕最大字数，默认 `22`
- `--subtitle-font-size`：字幕字号，默认 `18`
- `--subtitle-margin-v`：底部边距，默认 `36`
- `--subtitle-bar-height`：底部字幕条高度，默认 `170`
- `--subtitle-bar-opacity`：底部字幕条透明度，默认 `0.34`
- `--subtitle-safe-lift`：开启字幕时人物自动上移，默认 `46`

## 先用 AI 生成人像，再交给在线数字人平台

1. 复制 `avatar_webhook_config.example.json`
2. 按你的人像生成平台接口文档修改请求地址和字段
3. 设置环境变量 `AVATAR_API_KEY`
4. 执行：

```bash
python3 video_pipeline.py \
  --title "demo_avatar" \
  --text "大家好，今天给大家介绍我们的新产品。" \
  --avatar-mode webhook \
  --avatar-prompt "一个亚洲年轻女性，正面半身肖像，职业装，自然微笑，写实风格，纯色背景" \
  --avatar-config ./avatar_webhook_config.example.json \
  --video-mode webhook \
  --webhook-config ./webhook_config.example.json
```

## 适合对接的在线数字人平台

- HeyGen
- D-ID
- 腾讯智影
- 阿里云智能媒体服务
- 任何支持 HTTP API 的数字人平台

你需要按平台文档改两类字段：

- 提交任务接口：`submit_url`、`payload_template`、`files_template`
- 查询结果接口：`status_url`、`job_id_field`、`status_field`、`result_url_field`

## 用本地人物视频做循环拼接

```bash
python3 video_pipeline.py \
  --title "demo_video" \
  --text "大家好，今天给大家介绍我们的新产品。" \
  --avatar-video ./avatar.mp4 \
  --video-mode local-video
```

也可以通过 `webhook_config.example.json` 将项目扩展到其他支持 HTTP API 的数字人服务。

## FAQ

### 1. 页面提示 `Whisper 模型未配置` 是什么意思？

说明当前没有检测到本地 Whisper 模型文件路径。你需要：

- 下载 `ggml-base.bin` 这类模型文件
- 放到 `models/` 目录
- 在 `.env` 中配置：

```env
WHISPER_MODEL_PATH="./models/ggml-base.bin"
```

### 2. 为什么字幕有一点延迟？

默认快速模式按文案长度估算时间，速度快但不一定完全精准。  
如果你更在意对齐效果：

- 先下载 Whisper 模型
- 切换到 `精准模式（Whisper 时间戳）`
- 必要时再用 `字幕自校对偏移` 微调

### 3. 为什么 Pexels 预览候选里会有重复素材？

Pexels 本身经常返回同一场景的相似镜头。当前平台已经做了：

- 跨检索词搜索
- 跨分页搜索
- 素材 ID / 创作者 / 标题去重
- 按场景词分组搜索

如果你还觉得不够分散，建议把背景提示词写得更具体，比如：

- `indoor basketball court`
- `school hallway`
- `classroom interior`

### 4. 为什么背景视频看起来会重复播放？

内容短视频模式现在按“背景序列”播放：一条素材播完会切下一条，只有整组背景都播完了才会回到开头。  
如果整组背景总时长仍然短于旁白总时长，就会再次循环。建议：

- 多选几条背景视频
- 选择总时长更长的素材
- 把长文案分成更多段落

### 5. 为什么 Gemini / Pexels 留空时读取不到？

通常是 `.env` 还没填真实 key，或者写成了模板占位值。请确认：

```env
GEMINI_API_KEY="你的真实 Gemini API Key"
PEXELS_API_KEY="你的真实 Pexels API Key"
```

### 6. 这个项目更适合哪种使用方式？

如果你追求自然感和效率，优先用：

- `内容短视频模式`
- `Pexels 背景视频`
- `自动字幕`
- `BGM`

如果你明确需要人物出镜，再切到腾讯云数字人口播模式。

## 开源前检查

上传 GitHub 前建议确认以下内容：

- 不提交 `.env`、真实 API Key、Access Token 或任何个人凭据
- 不提交 `web_runs/`、`output/`、`models/`、`__pycache__/` 等本地产物
- 不提交未授权的图片、视频、音乐素材
- 如果使用第三方背景视频、图片或 BGM，请确认授权范围
- 如果 README 中展示截图，建议使用自己生成的示例内容，避免包含真实密钥或个人信息

## License

本项目使用 MIT License，详见 [LICENSE](./LICENSE)。
