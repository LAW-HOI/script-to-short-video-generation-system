# Third-Party Notices

This project can integrate with third-party APIs and remote media sources. Users are responsible for reviewing and complying with each provider's terms, pricing, license, and attribution requirements.

## Services

- Google Gemini API: used for AI copywriting and prompt generation when configured by the user.
- Pexels API: used for searching background images and videos when configured by the user.
- Microsoft Edge TTS via `edge-tts`: used for local text-to-speech synthesis.
- Whisper / whisper.cpp: optional local speech recognition model for more accurate subtitle timestamps.
- FFmpeg: used for media composition, transcoding, subtitle rendering, and audio mixing.

## Remote UI Media

The web interface references remote visual assets to create the ocean-style background:

- Unsplash image URL used as the ocean poster/background cover:
  `https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=2400&q=85`
- Wikimedia Commons ocean video URL used as the animated ocean background:
  `https://upload.wikimedia.org/wikipedia/commons/transcoded/9/9c/Ocean_surface_waves_04.ogv/Ocean_surface_waves_04.ogv.480p.webm`

For stricter production or commercial usage, replace these remote assets with self-owned or explicitly licensed media.

## Generated And Downloaded Assets

Generated videos, downloaded Pexels media, uploaded user files, BGM files, local models, and runtime logs should stay local. They are ignored by `.gitignore` and should not be committed to the repository unless you have the right to publish them.

The optional `music_library/` feature is designed for user-provided audio files. Do not add copyrighted music to the repository unless you have explicit permission to redistribute it.
