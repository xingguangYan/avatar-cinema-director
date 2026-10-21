from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
VOICE_DIR = SKILL_ROOT / "assets" / "voices"
KOKORO_DIR = VOICE_DIR / "kokoro"
SAMPLE_DIR = VOICE_DIR / "samples"
KOKORO_API = "https://hf-mirror.com/api/models/hexgrad/Kokoro-82M/tree/main/voices"
KOKORO_DOWNLOAD = "https://hf-mirror.com/hexgrad/Kokoro-82M/resolve/main/{path}"

KOKORO_LOCALES = {
    "a": ("en-US", "American English"),
    "b": ("en-GB", "British English"),
    "e": ("es-ES", "Spanish"),
    "f": ("fr-FR", "French"),
    "h": ("hi-IN", "Hindi"),
    "i": ("it-IT", "Italian"),
    "j": ("ja-JP", "Japanese"),
    "p": ("pt-BR", "Brazilian Portuguese"),
    "z": ("zh-CN", "Mandarin Chinese"),
}

SAMPLE_TEXTS = {
    "ar-SA": "مرحبًا، هذه عينة صوتية.",
    "bn-IN": "নমস্কার, এটি একটি কণ্ঠ নমুনা।",
    "cs-CZ": "Dobrý den, toto je ukázka hlasu.",
    "da-DK": "Hej, dette er en stemmeprøve.",
    "de-DE": "Hallo, dies ist eine Sprachprobe.",
    "el-GR": "Γεια σας, αυτό είναι ένα δείγμα φωνής.",
    "en-GB": "Hello, this is a voice preview.",
    "en-US": "Hello, this is a voice preview.",
    "es-ES": "Hola, esta es una muestra de voz.",
    "fa-IR": "سلام، این یک نمونه صدا است.",
    "fil-PH": "Kumusta, ito ay isang sample ng boses.",
    "fi-FI": "Hei, tämä on ääninäyte.",
    "fr-FR": "Bonjour, ceci est un exemple de voix.",
    "he-IL": "שלום, זו דוגמת קול.",
    "hi-IN": "नमस्ते, यह आवाज़ का एक नमूना है।",
    "hu-HU": "Hello, ez egy hangminta.",
    "id-ID": "Halo, ini adalah contoh suara.",
    "it-IT": "Ciao, questo è un esempio vocale.",
    "ja-JP": "こんにちは、これは音声のサンプルです。",
    "ko-KR": "안녕하세요. 음성 샘플입니다.",
    "ms-MY": "Helo, ini contoh suara.",
    "nb-NO": "Hei, dette er en stemmeprøve.",
    "nl-NL": "Hallo, dit is een stemvoorbeeld.",
    "pl-PL": "Cześć, to jest próbka głosu.",
    "pt-BR": "Olá, esta é uma amostra de voz.",
    "pt-PT": "Olá, esta é uma amostra de voz.",
    "ro-RO": "Bună, acesta este un eșantion vocal.",
    "ru-RU": "Здравствуйте, это пример голоса.",
    "sv-SE": "Hej, detta är ett röstprov.",
    "sw-KE": "Habari, hii ni sampuli ya sauti.",
    "ta-IN": "வணக்கம், இது ஒரு குரல் மாதிரி.",
    "te-IN": "నమస్కారం, ఇది ఒక వాయిస్ నమూనా.",
    "th-TH": "สวัสดี นี่คือตัวอย่างเสียง",
    "tr-TR": "Merhaba, bu bir ses örneği.",
    "uk-UA": "Вітаю, це приклад голосу.",
    "ur-PK": "سلام، یہ آواز کا نمونہ ہے۔",
    "vi-VN": "Xin chào, đây là một mẫu giọng nói.",
    "zh-CN": "你好，这是一段语音试听。",
    "zh-TW": "你好，這是一段語音試聽。",
}

DOUBLE_SAMPLE_LOCALES = {
    "en-US",
    "en-GB",
    "zh-CN",
    "ja-JP",
    "ko-KR",
    "es-ES",
    "fr-FR",
    "de-DE",
    "it-IT",
    "pt-BR",
    "ru-RU",
    "ar-SA",
    "hi-IN",
}


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "Codex"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def download_kokoro(force: bool = False) -> list[dict[str, Any]]:
    KOKORO_DIR.mkdir(parents=True, exist_ok=True)
    items = fetch_json(KOKORO_API)
    voices = []
    for item in items:
        path = str(item.get("path", ""))
        if not path.startswith("voices/") or not path.endswith(".pt"):
            continue
        filename = Path(path).name
        target = KOKORO_DIR / filename
        expected_size = int(item.get("size", 0))
        if force or not target.exists() or (
            expected_size and target.stat().st_size != expected_size
        ):
            url = KOKORO_DOWNLOAD.format(path=path)
            print(f"download {filename}")
            urllib.request.urlretrieve(url, target)
            time.sleep(0.8)
        prefix = filename[0]
        locale, language = KOKORO_LOCALES[prefix]
        voices.append(
            {
                "id": filename.removesuffix(".pt"),
                "engine": "kokoro",
                "locale": locale,
                "language": language,
                "gender": "female" if filename[1] == "f" else "male",
                "offline": True,
                "file": f"kokoro/{filename}",
                "source": url_for_source(path),
            }
        )
    return sorted(voices, key=lambda item: item["id"])


def url_for_source(path: str) -> str:
    return KOKORO_DOWNLOAD.format(path=path)


async def refresh_edge() -> list[dict[str, Any]]:
    import edge_tts

    voices = await edge_tts.list_voices()
    return sorted(voices, key=lambda item: item["ShortName"])


def choose_sample_voices(
    voices: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected = []
    by_locale: dict[str, list[dict[str, Any]]] = {}
    for voice in voices:
        by_locale.setdefault(voice["Locale"], []).append(voice)
    for locale in SAMPLE_TEXTS:
        candidates = by_locale.get(locale, [])
        if not candidates:
            continue
        selected_for_locale = 0
        genders = ["Female", "Male"] if locale in DOUBLE_SAMPLE_LOCALES else ["Female"]
        for gender in genders:
            match = next((item for item in candidates if item["Gender"] == gender), None)
            if match is None and selected_for_locale == 0:
                match = candidates[0]
            if match is not None:
                selected.append(match)
                selected_for_locale += 1
    unique = {item["ShortName"]: item for item in selected}
    return sorted(unique.values(), key=lambda item: item["ShortName"])


async def generate_samples(voices: list[dict[str, Any]], force: bool = False) -> None:
    import edge_tts

    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    for index, voice in enumerate(choose_sample_voices(voices), start=1):
        locale = voice["Locale"]
        text = SAMPLE_TEXTS[locale]
        target = SAMPLE_DIR / f"{voice['ShortName']}.mp3"
        if target.exists() and not force:
            print(f"sample {index}: reuse {target.name}")
            continue
        print(f"sample {index}: {voice['ShortName']}")
        last_error = None
        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(
                    text,
                    voice["ShortName"],
                    rate="+0%",
                    volume="+0%",
                    pitch="+0Hz",
                )
                await communicate.save(str(target))
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(2 + attempt * 3)
        if last_error is not None:
            raise RuntimeError(f"Sample failed for {voice['ShortName']}: {last_error}")
        await asyncio.sleep(0.25)


def build_catalog(
    kokoro_voices: list[dict[str, Any]],
    edge_raw: list[dict[str, Any]],
) -> dict[str, Any]:
    edge_voices = []
    for voice in edge_raw:
        locale = str(voice["Locale"])
        sample = SAMPLE_DIR / f"{voice['ShortName']}.mp3"
        edge_voices.append(
            {
                "id": voice["ShortName"],
                "engine": "edge",
                "locale": locale,
                "language_code": locale.split("-")[0],
                "gender": str(voice.get("Gender", "")).lower(),
                "friendly_name": voice.get("FriendlyName", ""),
                "offline": False,
                "sample": (
                    f"samples/{sample.name}" if sample.exists() else None
                ),
                "sample_text": SAMPLE_TEXTS.get(locale),
                "voice_tag": voice.get("VoiceTag", {}),
            }
        )
    locale_count = len({item["locale"] for item in kokoro_voices + edge_voices})
    language_count = len(
        {
            item["locale"].split("-")[0]
            for item in kokoro_voices + edge_voices
        }
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "kokoro_offline_voices": len(kokoro_voices),
            "edge_online_voices": len(edge_voices),
            "total_voices": len(kokoro_voices) + len(edge_voices),
            "locales": locale_count,
            "language_families": language_count,
            "samples": len(list(SAMPLE_DIR.glob("*.mp3"))),
        },
        "kokoro": kokoro_voices,
        "edge": edge_voices,
    }


async def main_async(args: argparse.Namespace) -> None:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    (VOICE_DIR / "edge-voices.raw.json").write_text(
        json.dumps(await refresh_edge(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    edge_raw = json.loads(
        (VOICE_DIR / "edge-voices.raw.json").read_text(encoding="utf-8")
    )

    if args.samples:
        await generate_samples(edge_raw, force=args.force_samples)

    kokoro_voices = download_kokoro(force=args.force_kokoro)
    catalog = build_catalog(kokoro_voices, edge_raw)
    (VOICE_DIR / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(catalog["counts"], ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh voice catalogs and samples")
    parser.add_argument("--samples", action="store_true")
    parser.add_argument("--force-samples", action="store_true")
    parser.add_argument("--force-kokoro", action="store_true")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
