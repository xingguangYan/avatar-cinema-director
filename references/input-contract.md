# Input Contract

Every project requires a `project.json` manifest. Relative paths resolve from
the directory containing the manifest.

## Manifest Schema

```json
{
  "route": "single",
  "title": "Morning Update",
  "characters": [
    {
      "id": "host",
      "display_name": "Host",
      "photo": "inputs/host.png",
      "voice": "am_michael",
      "lang_code": "a",
      "speed": 0.98
    }
  ],
  "backgrounds": {
    "default": "inputs/background.jpg"
  },
  "dialogue": [
    {
      "speaker": "Host",
      "text": "Hello and welcome."
    }
  ],
  "outputs": ["16x9", "9x16"],
  "options": {
    "bgm": "",
    "caption_font": "Arial",
    "device": "cpu",
    "wav2lip_batch_size": 96,
    "background_focus": {
      "16x9": {"x": 0.5, "y": 0.5},
      "9x16": {"x": 0.5, "y": 0.5}
    },
    "shadow_opacity": 0.30,
    "shadow_blur": 16.0,
    "edge_feather": 1.15
  }
}
```

`route` is `single` or `two`. A single project must have exactly one character;
a two-person project must have exactly two. Character order controls
left/right or top/bottom placement.

`backgrounds` accepts aspect-specific keys such as `16x9` and `9x16`, or a
`default` image that will be cropped for every requested aspect.

`speaker` must match either a character `id` or `display_name`.

`voice` can be an absolute `.pt` path, a project-relative path, or a voice
filename without `.pt` under the configured Kokoro voice directory.

## Required User Photos

Character photo:

- One person, front-facing, eyes and mouth clearly visible.
- Closed or neutral mouth; no hand, microphone, mask, or hair covering it.
- At least 768 pixels on the long side; 1024 pixels or more is preferred.
- Even lighting, minimal motion blur, and enough headroom to include chin and
  upper shoulders.
- PNG or JPG without transparency required.

Background photo:

- No prominent unrelated people unless the user explicitly wants them.
- No captions, watermarks, UI elements, or critical detail inside the area
  where people and captions will be placed.
- At least the target aspect resolution when possible.

Two-person projects need two different photos and should use two different
voices. A single shared voice is allowed only when the user explicitly accepts
the result.

## Optional Assets

- `options.bgm`: local audio file for low-volume background music.
- `outputs`: any subset of `16x9` and `9x16`.
- `options.wav2lip_batch_size`: lower this if the lip-sync stage runs out of GPU
  memory.
- `options.face_pads`: four integers for Wav2Lip face padding; the default
  `[0, 24, 0, 0]` adds chin room.
- `options.background_focus`: per-aspect crop focus from `0.0` to `1.0`. Use
  `x` to retain the left/right part of the source and `y` for the top/bottom.
- `options.shadow_opacity`: contact shadow strength; `0.20` to `0.40` is normal.
- `options.shadow_blur`: contact shadow softness in panel pixels.
- `options.edge_feather`: alpha edge blur after mask cleanup; `0.8` to `1.6` is
  the useful range.

## Validation

Run:

```powershell
& $env:TALKING_VIDEO_PYTHON scripts/pipeline.py --project <project-dir> --stage validate
```

Do not start the expensive stages until validation passes.
