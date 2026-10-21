# Avatar Cinema Director

`avatar-cinema-director` is a Codex skill for producing a finished talking-head
or dialogue video from still photos.

It supports:

- One presenter or two alternating speakers.
- One or both output aspects: `16x9` and `9x16`.
- Kokoro text-to-speech.
- Wav2Lip lip synchronization.
- Explicit background crop before compositing.
- Transparent character panels with refined alpha edges.
- Contact shadows and subtle color matching.
- Speaker-colored captions.
- Subtle independent body sway.
- Optional background music.
- Output verification through `ffprobe` and a complete decode pass.

The important visual rule in version `0.2.0` is:

> Crop the background to the final frame first, then place the people into that
> cropped scene.

The renderer no longer relies on a transient scale-and-crop inside the same
filter graph as the character overlay. Background preparation is now a separate,
inspectable stage.

---

## Table of Contents

- [What Changed In 0.2.0](#what-changed-in-020)
- [Supported Routes](#supported-routes)
- [Composition Model](#composition-model)
- [Repository Layout](#repository-layout)
- [System Requirements](#system-requirements)
- [Reference PC Configurations](#reference-pc-configurations)
- [Installation](#installation)
- [Required User Assets](#required-user-assets)
- [Project Setup](#project-setup)
- [Manifest Reference](#manifest-reference)
- [Stage Reference](#stage-reference)
- [Commands](#commands)
- [Background Crop Controls](#background-crop-controls)
- [Character Blending Controls](#character-blending-controls)
- [Output Layout](#output-layout)
- [Verification Checklist](#verification-checklist)
- [Troubleshooting](#troubleshooting)
- [Environment Variables](#environment-variables)
- [Performance Notes](#performance-notes)
- [Licensing And Consent](#licensing-and-consent)

---

## What Changed In 0.2.0

Version `0.2.0` adds a dedicated background-crop stage and improves character
integration.

New behavior:

1. The source background is cover-cropped to the exact target resolution.
2. Crop focus can be controlled independently for `16x9` and `9x16`.
3. Characters receive a cleaner alpha edge with low-alpha fringe removal.
4. Each character gets a soft contact shadow derived from the bottom of its
   mask.
5. The shadow is composited before the character, not over the character.
6. Character color is lightly harmonized before the final grade.
7. The renderer automatically creates cropped backgrounds if the render stage
   is run and `work/backgrounds/<aspect>.png` is missing.

This fixes the common "person pasted onto a photo" result caused by:

- Different source and output aspect ratios.
- Cropping the background at the same time as overlaying the person.
- Hard or dirty alpha edges.
- No contact shadow.
- Character and background color temperatures that do not match.

---

## Supported Routes

### Single Presenter

Input:

- One character photo.
- One character voice.
- One background photo, or separate background photos per aspect.

Output:

- The character is centered.
- `16x9` uses a nearly full-height centered composition.
- `9x16` uses a centered composition with additional headroom.

### Two-Person Dialogue

Input:

- Two distinct character photos.
- Two voices.
- One background per aspect, or one shared `default` background.
- Dialogue where every line names the active speaker.

Output:

- `16x9`: first character on the left, second character on the right.
- `9x16`: first character on top, second character on the bottom.
- Both characters remain visible throughout the video.

Character order in `project.json` controls placement.

---

## Composition Model

### 1. Background Cover-Crop

For each requested output aspect:

1. Read the user-supplied background.
2. Compute a scale factor that covers the target canvas without distortion:

   ```text
   scale = max(target_width / source_width,
               target_height / source_height)
   ```

3. Resize the image by that scale.
4. Crop the resized image to the exact target frame.
5. Apply a focus point to decide which area is retained.

Target sizes:

| Aspect | Resolution |
|---|---:|
| `16x9` | 1920x1080 |
| `9x16` | 1080x1920 |

Output file:

```text
work/backgrounds/16x9.png
work/backgrounds/9x16.png
```

The `backgrounds` stage writes these files so they can be inspected before the
expensive render.

### 2. Character Cutout

The character photo is processed through `rembg` using the
`u2net_human_seg` model.

Generated files:

```text
work/panels/<id>_panel.png
work/panels/<id>_mask.png
work/panels/<id>_cutout.png
work/panels/<id>_shadow.png
```

The panel is a 768x1280 vertical staging canvas. The alpha mask identifies the
person silhouette.

### 3. Alpha Edge Cleanup

The mask is converted to grayscale and passed through a curve that removes
very-low-alpha background residue. It is then blurred slightly.

Approximate filter behavior:

```text
remove low-alpha fringe -> preserve hair and shoulders -> feather edge
```

`options.edge_feather` controls the final blur. Typical values are `0.8` to
`1.6`.

### 4. Contact Shadow

A contact shadow is generated from the bottom of the character mask.

The shadow:

- Uses the visible mask bounds.
- Is centered under the character.
- Is wider than it is tall.
- Uses a soft Gaussian blur.
- Remains in the same coordinate system as the 768x1280 panel.

During rendering, the shadow is overlaid first and the character is overlaid
second.

Approximate order per person:

```text
cropped background
  -> contact shadow
  -> color-matched character
```

### 5. Character Color Matching

The character receives a restrained correction:

```text
contrast: 1.012
saturation: 0.98
brightness: -0.006
```

This is intentionally subtle. It reduces the most common pasted-cutout effect
without making the face gray or flat.

### 6. Final Scene

After all people are placed:

1. Apply a gentle contrast and saturation pass.
2. Apply light sharpening.
3. Add a vignette.
4. Burn captions.
5. Add a short fade-in and fade-out.
6. Mix dialogue and optional background music.
7. Encode H.264/AAC MP4.

---

## Repository Layout

```text
avatar-cinema-director/
|-- SKILL.md
|-- README.md
|-- agents/
|   `-- openai.yaml
|-- assets/
|   |-- project-single.example.json
|   `-- project-two.example.json
|-- references/
|   |-- input-contract.md
|   |-- single-speaker.md
|   `-- two-speaker.md
`-- scripts/
    |-- audio_worker.py
    `-- pipeline.py
```

The repository contains no model weights and no user media.

---

## System Requirements

### Main Pipeline Environment

The pipeline interpreter needs:

- Python 3.9 or newer.
- `opencv-python` or `opencv-python-headless`.
- `numpy`.
- `rembg`.
- `onnxruntime`.
- Wav2Lip dependencies in the same environment.

### Audio Environment

Kokoro may be installed in a different environment. The audio worker only needs:

- `kokoro`.
- `numpy`.
- `soundfile`.

The pipeline launches `audio_worker.py` through
`TALKING_VIDEO_AUDIO_PYTHON`, so Kokoro does not have to share an environment
with `rembg`.

### Lip-Sync Backend

The Wav2Lip checkout needs:

- `inference.py`.
- `face_detection/`.
- `checkpoints/wav2lip_gan.pth`.
- `face_detection/detection/sfd/s3fd.pth`.
- PyTorch with CUDA for reasonable performance.

### FFmpeg

Both `ffmpeg.exe` and `ffprobe.exe` must be available. The configured FFmpeg
must support:

- H.264 encoding through `libx264`.
- AAC audio.
- `subtitles`, `zoompan`, `overlay`, `curves`, `eq`, `unsharp`, and `vignette`
  filters.

---

## Reference PC Configurations

The skill renders 1080p video and runs a neural lip-sync model. A discrete
GPU is strongly recommended.

### Minimum Usable Configuration

| Component | Minimum |
|---|---|
| OS | Windows 10/11 64-bit, Linux, or macOS |
| CPU | 6 physical cores |
| RAM | 16 GB |
| GPU | NVIDIA GPU with 6 GB VRAM |
| CUDA | CUDA 11.8 or newer |
| Free disk | 20 GB |
| Storage | SSD recommended |
| Python | 3.9+ |
| FFmpeg | 6.0+ with `libx264`, `libass`, and common filters |

This tier can work, but long two-person jobs may need lower Wav2Lip batch sizes
and may spend a long time rendering.

### Recommended Configuration

| Component | Recommended |
|---|---|
| OS | Windows 11 64-bit or modern Linux |
| CPU | 10+ cores |
| RAM | 32 GB |
| GPU | NVIDIA GPU with 8 GB VRAM or more |
| CUDA | CUDA 12.x |
| Free disk | 50 GB |
| Storage | NVMe SSD |
| Python | 3.10-3.12 for audio, 3.9-3.12 for main pipeline |
| FFmpeg | 7.0+ or newer |

Recommended GPUs broadly include:

- RTX 3060 12 GB.
- RTX 4060 Ti 16 GB.
- RTX 4070 / 4070 SUPER and above.
- RTX 5070 / 5070 Ti and above.
- Professional or workstation GPUs with at least 8 GB VRAM.

### Reference Test Machine

The current version was validated on this machine:

| Component | Value |
|---|---|
| System | Windows 11 Home 64-bit, build 26200 |
| CPU | Intel Core Ultra 9 275HX, 24 cores |
| RAM | 32 GB |
| Model | Lenovo 83F4 |
| GPU | NVIDIA GeForce RTX 5070 Laptop GPU |
| VRAM | 8 GB |
| NVIDIA driver | 592.01 |
| CUDA | 12.8 |
| Main Python | 3.9.13 |
| Kokoro Python | 3.12.12 |
| PyTorch | 2.7.0+cu128 |
| OpenCV | 4.10.0 |
| FFmpeg | 9.0.2 |

Both single-person and two-person regression projects were rendered at:

- `1920x1080`, 30 fps.
- `1080x1920`, 30 fps.
- H.264 video and stereo AAC audio.

### CPU-Only Operation

CPU-only Wav2Lip is possible in theory, but it is not a practical default.
Expect:

- Much lower frame throughput.
- High CPU use for the entire lip-sync stage.
- Several hours for a three-minute two-person project.
- More chance of thermal throttling.

Use a CUDA-capable GPU for normal production.

### Disk And Model Budget

Plan for model and dependency storage:

| Item | Approximate footprint |
|---|---:|
| Kokoro model and voices | 300-500 MB |
| Wav2Lip checkpoint | 500 MB |
| Wav2Lip face detector | 100 MB |
| PyTorch, CUDA libraries, and Python environments | 8-15 GB |
| Temporary image and video frames per project | 2-8 GB |

Recommended total free space:

- Minimum: 20 GB.
- Comfortable: 50 GB.
- Multi-project or model-heavy use: 100 GB.

### Resolution Limits

This version targets:

- 1920x1080 landscape.
- 1080x1920 portrait.
- 30 fps.
- H.264 MP4.

4K rendering is not a supported default. A 4K background can be used, but it
will be cover-cropped to the configured target resolution.

### Reference Time

On the tested RTX 5070 Laptop 8 GB system, a three-minute two-person dialogue
with both `16x9` and `9x16` outputs generally takes roughly 10-25 minutes from
audio generation through final verification.

Actual time depends on:

- Dialogue length.
- Number of characters.
- GPU performance and thermals.
- Wav2Lip batch size.
- Source photo size.
- Background resolution.
- Caption complexity.
- CPU encoder speed.

---

## Installation

### Install Into Codex User Skills

```powershell
$dest = Join-Path $env:USERPROFILE '.codex\skills\avatar-cinema-director'
git clone https://github.com/xingguangYan/avatar-cinema-director.git $dest
```

If the directory already exists, update it instead:

```powershell
Set-Location $dest
git pull --ff-only
```

The skill becomes available on the next Codex turn.

### Configure The Interpreter

Set the main pipeline interpreter:

```powershell
$env:TALKING_VIDEO_PYTHON = 'D:\path\to\venv\Scripts\python.exe'
```

Set the Kokoro interpreter when it is different:

```powershell
$env:TALKING_VIDEO_AUDIO_PYTHON = 'D:\path\to\kokoro-venv\Scripts\python.exe'
```

Set local model and tool roots:

```powershell
$env:TALKING_VIDEO_KOKORO_ROOT = 'D:\models\kokoro'
$env:TALKING_VIDEO_WAV2LIP_ROOT = 'D:\tools\Wav2Lip-master'
$env:TALKING_VIDEO_WAV2LIP_CHECKPOINT = 'D:\tools\Wav2Lip-master\checkpoints\wav2lip_gan.pth'
$env:TALKING_VIDEO_FFMPEG = 'D:\tools\ffmpeg\bin\ffmpeg.exe'
$env:TALKING_VIDEO_ASCII_ROOT = 'C:\talking_video_work'
```

The ASCII staging root is especially important on Windows accounts with
non-ASCII usernames or project paths.

---

## Required User Assets

### Character Photos

Provide one photo per character.

Requirements:

- Front-facing or near-front-facing.
- Eyes and mouth clearly visible.
- Mouth not covered by a hand, microphone, mask, hair, or scarf.
- Neutral or closed mouth.
- Even lighting.
- No heavy motion blur.
- At least 768 pixels on the long side.
- 1024 pixels or more is preferred.
- Space around the head and shoulders.

Do not silently use a stock photo or an old character when the user has not
provided the requested person.

### Background Photos

Provide at least one background.

Requirements:

- High enough resolution for the target aspect.
- No unwanted text, watermark, UI, or logo.
- Clear space for the people.
- Clear lower area for captions.
- No unrelated person unless explicitly requested.

For best results, provide:

- A dedicated wide background for `16x9`.
- A dedicated vertical background for `9x16`.

If only a `default` background is available, the pipeline cover-crops it for
both aspects.

### Dialogue

Every line must include:

- `speaker`
- `text`

The speaker must match a character `id` or `display_name`.

### Voices

Use a Kokoro `.pt` voice file for each character.

Two-person projects should use different voices. A shared voice triggers a
warning.

### Optional Music

Set `options.bgm` to a local audio file. The renderer applies low-volume music
under the dialogue.

---

## Project Setup

Create a project directory:

```text
my-video/
|-- project.json
|-- inputs/
|   |-- eddie.png
|   |-- starlight.png
|   |-- background-16x9.jpg
|   `-- background-9x16.jpg
`-- output/                 # created by the pipeline
```

Copy a template:

```powershell
Copy-Item `
  "$env:USERPROFILE\.codex\skills\avatar-cinema-director\assets\project-two.example.json" `
  ".\my-video\project.json"
```

Then update the paths and dialogue.

---

## Manifest Reference

Top-level fields:

| Field | Required | Description |
|---|---|---|
| `route` | yes | `single` or `two` |
| `title` | recommended | Video title and output-name source |
| `subtitle` | no | Secondary label in the opening title |
| `characters` | yes | One or two character objects |
| `backgrounds` | yes | `default`, `16x9`, and/or `9x16` |
| `dialogue` | yes | Ordered dialogue lines |
| `outputs` | yes | Any subset of `16x9`, `9x16` |
| `options` | no | Rendering, voice, crop, and blend settings |

Character fields:

| Field | Required | Description |
|---|---|---|
| `id` | recommended | Stable filesystem-safe identifier |
| `display_name` | yes | Name shown in captions |
| `photo` | yes | Character photo path |
| `voice` | yes | Absolute, relative, or Kokoro voice name |
| `lang_code` | no | Kokoro language code, default `a` |
| `speed` | no | Voice speed multiplier |

Dialogue fields:

| Field | Required | Description |
|---|---|---|
| `speaker` | yes | Character ID or display name |
| `text` | yes | Spoken line |

Background fields:

```json
"backgrounds": {
  "16x9": "inputs/background-16x9.jpg",
  "9x16": "inputs/background-9x16.jpg",
  "default": "inputs/background.jpg"
}
```

Aspect-specific keys take priority over `default`.

---

## Stage Reference

### `validate`

Checks:

- Route and character count.
- Required paths.
- Character image readability and minimum size.
- Background readability.
- Voice files.
- FFmpeg, Wav2Lip, checkpoint, Kokoro, and Python paths.
- Dialogue speaker mapping.
- Background focus ranges.
- Output aspect names.
- Optional BGM.

### `audio`

Creates:

```text
work/audio/lines/
work/audio/padded/
work/audio/dialogue_master_24k.wav
work/audio/dialogue_master_48k.wav
work/audio/timeline.json
```

### `backgrounds`

Cover-crops user backgrounds and writes:

```text
work/backgrounds/16x9.png
work/backgrounds/9x16.png
```

Run this stage alone when tuning crop focus:

```powershell
& $env:TALKING_VIDEO_PYTHON scripts/pipeline.py `
  --project .\my-video `
  --stage backgrounds
```

### `panels`

Creates transparent panels, cleaned masks, cutouts, and contact shadows.

### `talk`

Runs one Wav2Lip render per character against its full padded track.

The temporary input files are copied into an ASCII-only staging directory to
avoid Windows Unicode-path failures.

### `render`

Builds captions, loads cropped backgrounds, overlays shadows and characters,
mixes audio, encodes MP4, and verifies each result.

### `all`

Runs:

```text
validate -> audio -> backgrounds -> panels -> talk -> render
```

---

## Commands

Validate a project:

```powershell
& $env:TALKING_VIDEO_PYTHON scripts/pipeline.py `
  --project .\my-video `
  --stage validate
```

Run everything:

```powershell
& $env:TALKING_VIDEO_PYTHON scripts/pipeline.py `
  --project .\my-video `
  --stage all
```

Force replacement of existing talk and render outputs:

```powershell
& $env:TALKING_VIDEO_PYTHON scripts/pipeline.py `
  --project .\my-video `
  --stage all `
  --force
```

Rebuild only the backgrounds and render:

```powershell
& $env:TALKING_VIDEO_PYTHON scripts/pipeline.py `
  --project .\my-video `
  --stage backgrounds

& $env:TALKING_VIDEO_PYTHON scripts/pipeline.py `
  --project .\my-video `
  --stage render `
  --force
```

---

## Background Crop Controls

Focus values use a normalized `0.0` to `1.0` range.

```text
0.0 = retain the left or top side
0.5 = center
1.0 = retain the right or bottom side
```

Example:

```json
"background_focus": {
  "16x9": {
    "x": 0.42,
    "y": 0.50
  },
  "9x16": {
    "x": 0.55,
    "y": 0.35
  }
}
```

Use cases:

- Keep a tavern sign on the left.
- Preserve a countertop in the lower third.
- Keep the vertical crop centered on the bar rather than the room.
- Avoid cutting the main architectural feature.

The crop never stretches the image. It always uses a cover-crop.

---

## Character Blending Controls

### Shadow Opacity

```json
"shadow_opacity": 0.30
```

Recommended:

- Too invisible: below `0.15`.
- Normal: `0.20` to `0.40`.
- Too heavy: above `0.50`.

### Shadow Blur

```json
"shadow_blur": 16.0
```

Recommended:

- Crisp: `10` to `14`.
- Natural: `14` to `20`.
- Very soft: `20` to `26`.

### Edge Feather

```json
"edge_feather": 1.15
```

Recommended:

- Keep more hair detail: `0.8` to `1.1`.
- Natural blend: `1.1` to `1.4`.
- Softer edge: `1.4` to `1.6`.

### Panel Fallback

```json
"panel_fallback": [48, 34, 26]
```

This fallback fills transparent areas before final masking. It should be close
to the character's original background tone or a neutral warm brown.

---

## Output Layout

```text
my-video/
|-- work/
|   |-- audio/
|   |-- backgrounds/
|   |-- panels/
|   |-- render/
|   `-- talk/
`-- output/
    |-- <title>_16x9.mp4
    `-- <title>_9x16.mp4
```

The output name comes from `options.output_name`, or a slug of `title`.

---

## Verification Checklist

### Technical

- `ffprobe` finds one video stream and one audio stream.
- Duration is within one second of the timeline.
- Dimensions are exactly `1920x1080` or `1080x1920`.
- The full file decodes without errors.
- Audio is not silent or clipped.

### Visual

Inspect the first, middle, and last frames.

Confirm:

- The background was cropped, not stretched.
- The main subject of the background survives the crop.
- Both faces are visible.
- The mouth area is not covered by captions.
- Character edges do not show a rectangle or source-background halo.
- A soft contact shadow is visible where the character meets the lower scene.
- The character does not look brighter or more saturated than the scene.
- Captions do not clip on either side.
- `9x16` keeps faces above the caption safe area.

---

## Troubleshooting

### `ModuleNotFoundError: kokoro`

`TALKING_VIDEO_AUDIO_PYTHON` points to an interpreter without Kokoro.

Set it to a Python environment where this succeeds:

```powershell
& $env:TALKING_VIDEO_AUDIO_PYTHON -c "import kokoro; print('ok')"
```

### `ModuleNotFoundError: rembg`

`TALKING_VIDEO_PYTHON` points to an interpreter without `rembg`.

Set it to the main pipeline environment:

```powershell
& $env:TALKING_VIDEO_PYTHON -c "import cv2, rembg, torch; print('ok')"
```

### Wav2Lip CUDA Out Of Memory

Lower:

```json
"wav2lip_batch_size": 64
```

Try `32` or `16` if needed.

### Wav2Lip Cannot Find A Face

- Use a clearer character photo.
- Ensure the face is not covered.
- Increase the bottom pad:

  ```json
  "face_pads": [0, 32, 0, 0]
  ```

### Chinese Or Non-ASCII Paths Fail

Set:

```powershell
$env:TALKING_VIDEO_ASCII_ROOT = 'C:\talking_video_work'
```

The pipeline copies temporary Wav2Lip inputs into that directory.

### Character Still Looks Pasted On

Adjust in this order:

1. Tune `background_focus`.
2. Inspect `work/backgrounds/<aspect>.png`.
3. Increase `shadow_opacity` slightly.
4. Increase `shadow_blur` slightly.
5. Increase `edge_feather`.
6. Choose a background with matching lighting and camera height.

### Shadow Looks Like A Black Oval

Lower `shadow_opacity` and increase `shadow_blur`.

### Captions Overlap The Lower Character

- Provide a less crowded `9x16` background.
- Keep the second character's face higher.
- Shorten lines.
- Reduce caption font size.

Capture files preserve their original paths; work products are disposable and
can be rebuilt.

---

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `TALKING_VIDEO_PYTHON` | Main pipeline interpreter | Current interpreter |
| `TALKING_VIDEO_AUDIO_PYTHON` | Kokoro worker interpreter | Current machine's FreeVideoAI venv if present |
| `TALKING_VIDEO_KOKORO_ROOT` | Kokoro config, model, and voices | Local configured root |
| `TALKING_VIDEO_WAV2LIP_ROOT` | Wav2Lip checkout | Local configured root |
| `TALKING_VIDEO_WAV2LIP_CHECKPOINT` | Wav2Lip checkpoint | `<root>/checkpoints/wav2lip_gan.pth` |
| `TALKING_VIDEO_FFMPEG` | FFmpeg executable | Local configured path |
| `TALKING_VIDEO_ASCII_ROOT` | ASCII-only temporary workspace | `C:\talking_video_work` on Windows |

The defaults are specific to the original Windows installation. Override them
on another machine.

---

## Performance Notes

- Kokoro audio generation is CPU-oriented by default.
- Wav2Lip is the expensive stage.
- Two-person mode runs Wav2Lip sequentially to avoid GPU memory contention.
- The render stage uses `libx264` for compatibility.
- Static scenes compress efficiently, but the file still contains all frames at
  30 fps.
- Reusing `work/talk/` clips saves the most time during visual iteration.

During composition tuning, this loop is usually fastest:

```text
backgrounds -> render --force
```

Regenerate `panels` only when the character photo, mask settings, shadow
settings, or panel crop changes.

Regenerate `talk` only when the character panel, voice track, or lip-sync
settings change.

---

## Licensing And Consent

Wav2Lip's open-source release is intended for personal and research use. Review
its upstream license before commercial delivery.

Kokoro, Wav2Lip, rembg, FFmpeg, and model weights have their own licenses.

Only create videos of people when you have the necessary permission and rights.
The pipeline does not verify identity or consent.

---

## Release Notes

### 0.2.0

- Added dedicated background crop stage.
- Added crop focus controls.
- Added cleaned alpha mask curves.
- Added character contact shadows.
- Added subtle character color harmonization.
- Added detailed README.
- Added single- and two-person regression checks.

### 0.1.0

- Initial single- and two-person talking video pipeline.
- Kokoro audio worker.
- Wav2Lip talk generation.
- 16:9 and 9:16 rendering.
- Captions, music, and output verification.
