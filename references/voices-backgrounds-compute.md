# Voices, Backgrounds, And Compute

Read this reference when choosing a voice, bundled background, caption size,
audio level, or compute backend.

## Voice Engines

### Kokoro Offline

The skill bundles 54 Kokoro voice embeddings under:

```text
assets/voices/kokoro/
```

Language coverage:

| Locale | Language | Voices |
|---|---|---:|
| `en-US` | American English | 20 |
| `en-GB` | British English | 8 |
| `zh-CN` | Mandarin Chinese | 8 |
| `ja-JP` | Japanese | 5 |
| `es-ES` | Spanish | 3 |
| `hi-IN` | Hindi | 4 |
| `pt-BR` | Brazilian Portuguese | 3 |
| `it-IT` | Italian | 2 |
| `fr-FR` | French | 1 |

Example:

```json
{
  "engine": "kokoro",
  "voice": "zf_xiaoxiao",
  "lang_code": "z",
  "speed": 0.96
}
```

Kokoro is offline after the model and voice pack are installed.

### Edge TTS Online

The generated catalog contains 322 Microsoft neural voices across 142 locales
and 75 language families.

Files:

```text
assets/voices/catalog.json
assets/voices/edge-voices.raw.json
assets/voices/samples/
```

Example:

```json
{
  "engine": "edge",
  "voice": "zh-CN-XiaoxiaoNeural",
  "rate": "+0%",
  "pitch": "+0Hz",
  "edge_volume": "+0%"
}
```

Edge voices require network access while the audio stage runs.

## Recommended Edge Voices

| Locale | Voice IDs |
|---|---|
| `zh-CN` | `zh-CN-XiaoxiaoNeural`, `zh-CN-YunxiNeural`, `zh-CN-YunjianNeural` |
| `zh-TW` | `zh-TW-HsiaoChenNeural`, `zh-TW-YunJheNeural` |
| `en-US` | `en-US-AvaMultilingualNeural`, `en-US-AndrewMultilingualNeural`, `en-US-EmmaMultilingualNeural`, `en-US-BrianMultilingualNeural` |
| `en-GB` | `en-GB-LibbyNeural`, `en-GB-RyanNeural` |
| `ja-JP` | `ja-JP-NanamiNeural`, `ja-JP-KeitaNeural` |
| `ko-KR` | `ko-KR-SunHiNeural`, `ko-KR-HyunsuMultilingualNeural` |
| `es-ES` | `es-ES-ElviraNeural`, `es-ES-AlvaroNeural` |
| `fr-FR` | `fr-FR-DeniseNeural`, `fr-FR-HenriNeural` |
| `de-DE` | `de-DE-AmalaNeural`, `de-DE-ConradNeural` |
| `it-IT` | `it-IT-ElsaNeural`, `it-IT-DiegoNeural` |
| `pt-BR` | `pt-BR-FranciscaNeural`, `pt-BR-AntonioNeural` |
| `ru-RU` | `ru-RU-SvetlanaNeural`, `ru-RU-DmitryNeural` |
| `ar-SA` | `ar-SA-ZariyahNeural`, `ar-SA-HamedNeural` |
| `hi-IN` | `hi-IN-SwaraNeural`, `hi-IN-MadhurNeural` |
| `tr-TR` | `tr-TR-EmelNeural`, `tr-TR-AhmetNeural` |
| `nl-NL` | `nl-NL-ColetteNeural`, `nl-NL-FennaNeural` |
| `pl-PL` | `pl-PL-ZofiaNeural`, `pl-PL-MarekNeural` |
| `id-ID` | `id-ID-GadisNeural`, `id-ID-ArdiNeural` |
| `vi-VN` | `vi-VN-HoaiMyNeural`, `vi-VN-NamMinhNeural` |
| `th-TH` | `th-TH-PremwadeeNeural`, `th-TH-NiwatNeural` |
| `uk-UA` | `uk-UA-PolinaNeural`, `uk-UA-OstapNeural` |
| `fa-IR` | `fa-IR-DilaraNeural`, `fa-IR-FaridNeural` |
| `he-IL` | `he-IL-HilaNeural`, `he-IL-AvriNeural` |
| `ms-MY` | `ms-MY-YasminNeural`, `ms-MY-OsmanNeural` |
| `sw-KE` | `sw-KE-ZuriNeural`, `sw-KE-RafikiNeural` |
| `fil-PH` | `fil-PH-BlessicaNeural`, `fil-PH-AngeloNeural` |
| `sv-SE` | `sv-SE-SofieNeural`, `sv-SE-MattiasNeural` |
| `da-DK` | `da-DK-ChristelNeural`, `da-DK-JeppeNeural` |
| `nb-NO` | `nb-NO-PernilleNeural`, `nb-NO-FinnNeural` |
| `fi-FI` | `fi-FI-NooraNeural`, `fi-FI-HarriNeural` |

The full catalog contains many more voices and locales.

## Refresh Voice Assets

Use the Kokoro/Edge audio interpreter:

```powershell
& $env:TALKING_VIDEO_AUDIO_PYTHON scripts/voice_pack.py
```

Generate or refresh the local Edge preview samples:

```powershell
& $env:TALKING_VIDEO_AUDIO_PYTHON scripts/voice_pack.py --samples
```

Force all Kokoro voices to download again:

```powershell
& $env:TALKING_VIDEO_AUDIO_PYTHON scripts/voice_pack.py --force-kokoro
```

The Edge samples are intentionally excluded from the public git repository.

## Bundled Background Pack

Eight complete scene sets are included in both aspects:

```text
assets/backgrounds/<id>_16x9.jpg
assets/backgrounds/<id>_9x16.jpg
```

Available IDs:

| ID | Mood |
|---|---|
| `warm-tavern` | Warm, intimate, amber |
| `daylight-cafe` | Bright, relaxed, daytime |
| `modern-office` | Clean, professional, neutral |
| `creative-studio` | Contemporary, editorial, bright |
| `library-lounge` | Scholarly, quiet, warm wood |
| `rooftop-evening` | Urban, cinematic, blue hour |
| `tea-house` | Calm, Asian-inspired, natural |
| `city-night` | Night, energetic, high contrast |

Recommended focus values are stored in:

```text
assets/backgrounds/catalog.json
```

## Caption Size

Set exact pixel sizes per aspect:

```json
{
  "caption_font_size_16x9": 42,
  "caption_font_size_9x16": 46,
  "caption_margin_v_16x9": 70,
  "caption_margin_v_9x16": 180,
  "caption_wrap_16x9": 58,
  "caption_wrap_9x16": 46
}
```

Add bilingual subtitles without changing what is spoken:

```json
{
  "speaker": "Host",
  "text": "你好，欢迎来到今天的节目。",
  "translation": "Hello and welcome to today's program."
}
```

`caption_translation_scale` controls the secondary caption size. The default is
`0.78`.

Safe ranges:

- Font size: `16` to `120`.
- Bottom margin: `0` to half the output height.

## Audio Levels

Voice is normalized before these gains are applied:

```json
{
  "voice_volume": 1.06,
  "bgm_volume": 0.075,
  "limiter_limit": 0.95
}
```

Guidance:

- `voice_volume`: normally `0.9` to `1.2`.
- `bgm_volume`: normally `0.03` to `0.10`.
- `limiter_limit`: keep at `0.95` unless there is a specific delivery target.

## CPU And GPU

### Compute Device

```json
"compute_device": "auto"
```

Accepted values:

| Value | Behavior |
|---|---|
| `auto` | Use CUDA when available, otherwise CPU |
| `cpu` | Force Kokoro and Wav2Lip to CPU |
| `gpu:0` | Use the first NVIDIA GPU |
| `gpu:1` | Use the second NVIDIA GPU |
| `cuda:0` | Same as `gpu:0` |
| `cuda:1` | Same as `gpu:1` |

GPU selection is applied with `CUDA_VISIBLE_DEVICES`.

### Video Encoder

```json
"video_encoder": "auto"
```

Accepted values:

| Value | Behavior |
|---|---|
| `auto` | Try NVIDIA NVENC, then fall back to CPU x264; CPU-only compute skips NVENC |
| `nvidia` | Require NVENC and fail if unavailable |
| `gpu` | Alias for NVENC |
| `cuda` | Alias for NVENC |
| `cpu` | Use `libx264` |

The fallback is recorded in the render log.
