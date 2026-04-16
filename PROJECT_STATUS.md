# Project Status

This document summarizes the current implementation status before publishing the project.

## Implemented

- Local web app for creating AI short videos.
- AI copywriting through Gemini text models.
- Pexels image and video search with candidate preview, selection, ordering, and refresh.
- Storyboard-style short-video generation with TTS, subtitles, BGM, transitions, and background sequencing.
- Tencent Cloud digital human mode for talking-head videos.
- Edge TTS voice selection and preview.
- Heuristic subtitle timing and optional Whisper-based precise subtitle timing.
- `.env` loading for local secrets and model paths.
- FFmpeg-based video composition, subtitle rendering, audio mixing, and final export.

## Optional Integrations

- Tencent Cloud Digital Human API requires user-provided credentials.
- Pexels API requires a user-provided API key.
- Gemini text generation requires a user-provided API key.
- Whisper subtitle mode requires a local model file such as `ggml-base.bin`.
- Custom webhook templates can be adapted for other image or digital-human services.

## Removed Or Not Included

- Gemini / Imagen image generation is not included.
- The repository does not include paid API keys, generated videos, downloaded media, BGM files, or local Whisper models.
- The web app is designed as a local single-user workbench, not a production multi-user service.

## Local Files To Keep Out Of Git

The following files and folders are local runtime data and should not be committed:

- `.env`
- `web_runs/`
- `output/`
- `models/`
- `__pycache__/`
- generated `.mp4`, `.mp3`, `.wav`, `.m4a`, `.mov`, `.webm` files

These paths are already covered by `.gitignore`.
