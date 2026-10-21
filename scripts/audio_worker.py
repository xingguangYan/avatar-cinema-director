from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


SAMPLE_RATE = 24000


def synth_line(pipeline: Any, text: str, voice: str, speed: float) -> np.ndarray:
    pieces = []
    for _, _, audio in pipeline(
        text,
        voice=voice,
        speed=speed,
        split_pattern=r"(?<=[.!?])\s+",
    ):
        chunk = np.asarray(audio, dtype=np.float32).reshape(-1)
        if chunk.size:
            pieces.append(chunk)
    if not pieces:
        return np.zeros(int(SAMPLE_RATE * 0.3), dtype=np.float32)
    return np.concatenate(pieces)


def synth_edge_line(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    volume: str,
    ffmpeg: Path,
    work_dir: Path,
    index: int,
) -> np.ndarray:
    import edge_tts

    async def save_audio(path: Path) -> None:
        communicate = edge_tts.Communicate(
            text,
            voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
        )
        await communicate.save(str(path))

    work_dir.mkdir(parents=True, exist_ok=True)
    mp3 = work_dir / f"edge_{index:03d}.mp3"
    wav = work_dir / f"edge_{index:03d}.wav"
    asyncio.run(save_audio(mp3))
    subprocess.run(
        [
            str(ffmpeg),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(mp3),
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(wav),
        ],
        check=True,
    )
    audio, sample_rate = sf.read(wav, dtype="float32")
    if sample_rate != SAMPLE_RATE:
        raise RuntimeError(f"Unexpected Edge sample rate: {sample_rate}")
    return np.asarray(audio, dtype=np.float32).reshape(-1)


def convert_audio(ffmpeg: Path, source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(ffmpeg),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-ar",
            "48000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(target),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    args = parser.parse_args()

    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    from kokoro import KModel, KPipeline

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    audio_dir = Path(spec["audio_dir"])
    lines_dir = audio_dir / "lines"
    padded_dir = audio_dir / "padded"
    lines_dir.mkdir(parents=True, exist_ok=True)
    padded_dir.mkdir(parents=True, exist_ok=True)

    kokoro_root = Path(spec["kokoro_root"])
    model = KModel(
        config=str(kokoro_root / "config.json"),
        model=str(kokoro_root / "kokoro-v1_0.pth"),
    )
    options = spec.get("options", {})
    device_setting = str(
        options.get("compute_device", options.get("device", "auto"))
    ).lower()
    if device_setting == "auto":
        try:
            import torch

            kokoro_device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            kokoro_device = "cpu"
    elif device_setting in {"gpu", "cuda"} or device_setting.startswith(
        ("gpu:", "cuda:")
    ):
        kokoro_device = "cuda"
    else:
        kokoro_device = "cpu"
    characters = {item["id"]: item for item in spec["characters"]}
    pipelines = {}
    for item in spec["characters"]:
        if item.get("engine", "kokoro") == "kokoro":
            pipelines[item["id"]] = KPipeline(
                lang_code=str(item.get("lang_code", "a")),
                model=model,
                device=kokoro_device,
            )

    gap = float(options.get("gap_seconds", 0.50))
    lead = float(options.get("lead_silence_seconds", 0.14))
    tail = float(options.get("tail_silence_seconds", 0.30))

    cursor = 0.0
    events = []
    line_audio = []
    edge_work_dir = audio_dir / "edge_tmp"
    ffmpeg = Path(spec["ffmpeg"])
    for index, item in enumerate(spec["dialogue"]):
        character = characters[item["speaker_id"]]
        if character.get("engine", "kokoro") == "edge":
            audio = synth_edge_line(
                item["text"],
                character["voice"],
                str(character.get("rate", "+0%")),
                str(character.get("pitch", "+0Hz")),
                str(character.get("edge_volume", "+0%")),
                ffmpeg,
                edge_work_dir,
                index,
            )
        else:
            audio = synth_line(
                pipelines[character["id"]],
                item["text"],
                character["voice"],
                float(character.get("speed", 1.0)),
            )
        line_audio.append(audio)
        duration = audio.size / SAMPLE_RATE
        start = cursor + gap + lead
        end = start + duration
        events.append(
            {
                "index": index,
                "speaker_id": character["id"],
                "speaker": character["display_name"],
                "text": item["text"],
                "translation": item.get("translation", ""),
                "start": round(start, 4),
                "end": round(end, 4),
                "duration": round(duration, 4),
            }
        )
        cursor = end + tail

    total = max(cursor, 0.1)
    total_samples = int(round(total * SAMPLE_RATE))
    master = np.zeros(total_samples, dtype=np.float32)
    padded = {
        item["id"]: np.zeros(total_samples, dtype=np.float32)
        for item in spec["characters"]
    }
    for event, audio in zip(events, line_audio):
        start = int(round(event["start"] * SAMPLE_RATE))
        end = min(start + audio.size, total_samples)
        master[start:end] += audio[: end - start]
        padded[event["speaker_id"]][start:end] += audio[: end - start]
        sf.write(
            lines_dir / f"line_{event['index']:03d}_{event['speaker_id']}.wav",
            audio,
            SAMPLE_RATE,
            subtype="PCM_16",
        )

    master_24k = audio_dir / "dialogue_master_24k.wav"
    sf.write(
        master_24k,
        np.clip(master, -0.98, 0.98),
        SAMPLE_RATE,
        subtype="PCM_16",
    )
    convert_audio(ffmpeg, master_24k, audio_dir / "dialogue_master_48k.wav")

    for character in spec["characters"]:
        source = padded_dir / f"{character['id']}_24k.wav"
        sf.write(
            source,
            np.clip(padded[character["id"]], -0.98, 0.98),
            SAMPLE_RATE,
            subtype="PCM_16",
        )
        convert_audio(
            ffmpeg,
            source,
            padded_dir / f"{character['id']}_48k.wav",
        )

    timeline = {
        "total_duration": round(total, 4),
        "route": spec["route"],
        "characters": [
            {"id": item["id"], "display_name": item["display_name"]}
            for item in spec["characters"]
        ],
        "events": events,
    }
    (audio_dir / "timeline.json").write_text(
        json.dumps(timeline, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"AUDIO: {len(events)} lines, {total:.3f}s -> {audio_dir}")


if __name__ == "__main__":
    main()
