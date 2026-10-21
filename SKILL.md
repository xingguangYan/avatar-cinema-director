---
name: talking-dialogue-video
description: Create single- or two-person talking videos from user-supplied character photos, background photos, and dialogue, with lip sync, captions, and optional 16:9 and 9:16 renders.
metadata:
  short-description: Single- and two-person talking video production
---

# Talking Dialogue Video

Produce a finished talking video from still portraits. The workflow supports a
single presenter or a two-person dialogue, with one or both output aspects.

## Required User Assets

Do not begin generation until the user has supplied:

- One clear, front-facing photo per character.
- At least one background photo. Prefer a dedicated 16:9 and 9:16 image when
  both aspects are requested.
- Dialogue text with a speaker assigned to every line.
- A Kokoro voice for every character, or explicit approval for default voices.

Never silently substitute stock people, previous characters, or an unrelated
background. If a required asset is missing, ask for it before running the
pipeline.

## Choose The Route

- **Single presenter:** one character, one photo, one padded voice track,
  centered composition, one lip-sync render.
- **Two-person dialogue:** two characters, two distinct photos and voices,
  alternating dialogue, two padded voice tracks, left/right composition for
  16:9 and top/bottom composition for 9:16.

Read the route-specific checklist before preparing a project:

- [Single presenter](references/single-speaker.md)
- [Two-person dialogue](references/two-speaker.md)
- [Input and manifest contract](references/input-contract.md)

## Create The Project

1. Create a project directory.
2. Copy the nearest example from `assets/` to `<project>/project.json`.
3. Copy or reference the user's character photos and background photos.
4. Fill in character IDs, display names, voice files, dialogue, outputs, and
   optional background music.
5. Remove output aspects that were not requested.

Use relative paths inside `project.json`; they resolve from the project
directory. Character order controls left/right and top/bottom placement.

## Run

Use the Python environment that contains Kokoro, rembg, OpenCV, SoundFile, and
PyTorch:

```powershell
& $env:TALKING_VIDEO_PYTHON scripts/pipeline.py --project <project-dir> --stage validate
& $env:TALKING_VIDEO_PYTHON scripts/pipeline.py --project <project-dir> --stage all
```

Override local tool locations when they differ:

```text
TALKING_VIDEO_PYTHON
TALKING_VIDEO_AUDIO_PYTHON
TALKING_VIDEO_KOKORO_ROOT
TALKING_VIDEO_WAV2LIP_ROOT
TALKING_VIDEO_WAV2LIP_CHECKPOINT
TALKING_VIDEO_FFMPEG
TALKING_VIDEO_ASCII_ROOT
```

If `TALKING_VIDEO_PYTHON` is unset, use the interpreter running the pipeline.
The defaults target the current Windows installation and must be overridden on
another machine.

Useful partial stages are `validate`, `audio`, `panels`, `talk`, `render`, and
`all`. Add `--force` only when existing generated media should be replaced.

## Verify

The render stage checks output duration, dimensions, streams, and a complete
decode. Also inspect one frame from the beginning, middle, and end of each
aspect for framing and caption clipping. Report every generated file with its
absolute path.

## Boundaries

- Wav2Lip is suitable for personal or research use under its upstream license.
  For commercial delivery, confirm rights or replace the lip-sync backend.
- Keep generated work under the project directory; do not modify the source
  photos.
- Do not claim real-person consent or identity verification from an uploaded
  photo.
