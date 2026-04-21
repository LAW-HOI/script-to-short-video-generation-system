# Architecture

Script2Short uses a lightweight layered architecture:

```text
Web UI (web_app.py)
  -> Task orchestration (web_app.py)
  -> Pipeline engine (video_pipeline.py)
  -> External AI / media services
  -> Local FFmpeg rendering
```

## Layer Breakdown

### 1. Web UI Layer

Implemented in `web_app.py`.

- Receives script ideas, script text, language, voice, subtitle, background, and BGM settings
- Provides Pexels candidate preview and voice preview
- Displays task progress, timestamps, logs, and final video preview

### 2. Task Orchestration Layer

Also implemented in `web_app.py`.

- Validates form payloads
- Resolves secrets from the UI or `.env`
- Builds command arguments for the pipeline
- Creates background worker threads and tracks job state

### 3. Pipeline Engine Layer

Implemented in `video_pipeline.py`.

- Splits long scripts into storyboard segments
- Prepares background assets from manual files, Pexels, or webhook providers
- Generates narration audio
- Generates heuristic or Whisper-based subtitles
- Renders segment videos and merges them with transitions and BGM

### 4. Subtitle Utility Layer

Implemented in `services/subtitle_utils.py`.

- Detects Chinese vs English subtitle content
- Splits subtitles differently for Chinese and English
- Estimates subtitle timing weights
- Parses and rewrites SRT blocks

### 5. External Service Layer

- Gemini: script and background prompt generation
- Pexels: image and video asset search
- Edge TTS: narration generation
- Whisper / whisper.cpp: precise subtitle generation
- FFmpeg: rendering, transitions, subtitles, and BGM mixing

## Repository Layout

Current project layout is intentionally lightweight:

```text
auto_digit/
├── web_app.py
├── video_pipeline.py
├── services/
│   ├── __init__.py
│   └── subtitle_utils.py
├── examples/
│   ├── background_webhook_config.example.json
│   └── music_library.example.json
├── docs/
│   ├── architecture.md
│   ├── github-launch-kit.md
│   └── screenshots/
├── .env.example
├── README.md
├── PROJECT_STATUS.md
├── THIRD_PARTY_NOTICES.md
└── requirements.txt
```

Locally, you may also see runtime and personal assets such as:

- `web_runs/`
- `output/`
- `models/`
- `music_library/`
- local test images or videos

These are intentionally excluded from Git tracking and should be treated as workspace data rather than source code.

## Data Flow

```text
User input
  -> Web form payload
  -> Task/job creation
  -> Script split
  -> Background asset preparation
  -> Audio synthesis
  -> Subtitle generation
  -> Segment rendering
  -> Video merge / subtitle burn / BGM mix
  -> Final video + logs + cached assets
```

## Why not LangGraph right now?

The current project is still a deterministic media pipeline rather than a multi-agent reasoning graph.

That means readability improves more from:

- smaller modules
- clearer function ownership
- explicit pipeline comments

than from adding a graph orchestration framework.

If the project later grows into:

- multi-model routing
- human approval checkpoints
- agent-based rewriting loops
- stateful retry / recovery nodes

then LangGraph may become a better fit.
