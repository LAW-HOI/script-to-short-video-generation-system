# GitHub Launch Kit

This note collects the recommended repository presentation assets for Script2Short.

## Repository Description

Use this in the GitHub repository "About" section:

```text
A local AI short-video generation system for script writing, voice-over, subtitles, background asset orchestration, and final video export.
```

## Suggested Topics

Use the following GitHub topics:

```text
ai
short-video
video-generation
gemini
pexels
edge-tts
whisper
ffmpeg
python
web-ui
automation
storyboard
```

## Screenshot Checklist

Recommended screenshot order for the README:

1. `docs/screenshots/home.png`
   Main workspace with script input, language selection, and generation controls.
2. `docs/screenshots/candidates.png`
   Pexels candidate preview, manual selection, and ordering workflow.
3. `docs/screenshots/jobs.png`
   Job status panel, timestamps, logs, and final video preview.

Avoid screenshots that expose API keys, personal file paths, tokens, or private media assets.

## Release Draft

Suggested first release title:

```text
v1.0.0 - Initial public release
```

Suggested release notes:

```md
## Highlights

- Web-based AI short-video workflow for script, background, voice, subtitles, and BGM
- Lazy mode for one-click generation and custom mode for manual background selection
- Chinese / English bilingual script and subtitle configuration
- Pexels background image / video search with candidate preview and ordering
- Edge TTS voice-over preview and Whisper subtitle support
- Local-first project structure with output logs, cached assets, and generated videos saved on device

## Core Stack

- Python
- Gemini API
- Pexels API
- Edge TTS
- Whisper / whisper.cpp
- FFmpeg

## Notes

- API keys, Whisper models, generated outputs, and local music assets are intentionally excluded from the repository.
- Add your own `.env`, model files, and licensed media assets before running the project locally.
```
