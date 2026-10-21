from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np


DEFAULT_KOKORO_ROOT = Path(r"D:\闫星光\玩\uibro-dialogue\assets\kokoro")
DEFAULT_WAV2LIP_ROOT = Path(r"D:\闫星光\玩\wav2lip_local\Wav2Lip-master")
DEFAULT_AUDIO_PYTHON = Path(
    r"D:\闫星光\玩\freevideoai\.venv\Scripts\python.exe"
)
DEFAULT_FFMPEG = Path(
    r"D:\闫星光\玩\ffmpeg\bin\ffmpeg-9.0.2-full_build-shared\bin\ffmpeg.exe"
)
ASPECTS = {
    "16x9": (1920, 1080),
    "9x16": (1080, 1920),
}
SPEAKER_COLORS = ("E8B469", "7AC0E8")
PANEL_W = 768
PANEL_H = 1280


def env_path(name: str, default: Path | None = None) -> Path:
    value = os.environ.get(name)
    if value:
        return Path(value).expanduser()
    if default is None:
        raise RuntimeError(f"{name} is not configured")
    return default


def tool_paths() -> dict[str, Path]:
    ffmpeg = env_path("TALKING_VIDEO_FFMPEG", DEFAULT_FFMPEG)
    default_audio_python = (
        DEFAULT_AUDIO_PYTHON if DEFAULT_AUDIO_PYTHON.exists() else Path(sys.executable)
    )
    return {
        "python": Path(os.environ.get("TALKING_VIDEO_PYTHON", sys.executable)),
        "audio_python": Path(
            os.environ.get("TALKING_VIDEO_AUDIO_PYTHON", default_audio_python)
        ),
        "kokoro": env_path("TALKING_VIDEO_KOKORO_ROOT", DEFAULT_KOKORO_ROOT),
        "wav2lip": env_path("TALKING_VIDEO_WAV2LIP_ROOT", DEFAULT_WAV2LIP_ROOT),
        "checkpoint": env_path(
            "TALKING_VIDEO_WAV2LIP_CHECKPOINT",
            DEFAULT_WAV2LIP_ROOT / "checkpoints" / "wav2lip_gan.pth",
        ),
        "ffmpeg": ffmpeg,
        "ffprobe": ffmpeg.with_name("ffprobe.exe" if os.name == "nt" else "ffprobe"),
    }


def compute_device(project: dict[str, Any]) -> str:
    value = str(
        project["options"].get(
            "compute_device",
            project["options"].get("device", "auto"),
        )
    ).lower()
    if value == "auto" or value == "cpu":
        return value
    if value in {"gpu", "cuda"}:
        return "cuda:0"
    if value.startswith("gpu:"):
        return "cuda:" + value.split(":", 1)[1]
    return value


def video_encoder_modes(project: dict[str, Any]) -> list[str]:
    configured = str(project["options"].get("video_encoder", "auto")).lower()
    if configured == "auto":
        if compute_device(project) == "cpu":
            return ["cpu"]
        return ["nvidia", "cpu"]
    if configured in {"gpu", "nvidia", "cuda"}:
        return ["nvidia"]
    return ["cpu"]


def slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def read_image(path: Path) -> np.ndarray:
    raw = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Unreadable image: {path}")
    return image


def write_png(path: Path, image: np.ndarray) -> None:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"Unable to encode image: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer.tofile(str(path))


def crop_background(
    image: np.ndarray,
    target_width: int,
    target_height: int,
    focus_x: float,
    focus_y: float,
) -> np.ndarray:
    height, width = image.shape[:2]
    scale = max(target_width / width, target_height / height)
    resized_width = max(target_width, int(math.ceil(width * scale)))
    resized_height = max(target_height, int(math.ceil(height * scale)))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    resized = cv2.resize(
        image,
        (resized_width, resized_height),
        interpolation=interpolation,
    )

    focus_x = min(1.0, max(0.0, float(focus_x)))
    focus_y = min(1.0, max(0.0, float(focus_y)))
    max_x = max(0, resized_width - target_width)
    max_y = max(0, resized_height - target_height)
    x0 = int(round(max_x * focus_x))
    y0 = int(round(max_y * focus_y))
    return resized[y0 : y0 + target_height, x0 : x0 + target_width]


def build_backgrounds(project: dict[str, Any]) -> None:
    background_dir = project["project_dir"] / "work" / "backgrounds"
    background_dir.mkdir(parents=True, exist_ok=True)
    focus_options = project["options"].get("background_focus", {})
    if not isinstance(focus_options, dict):
        raise RuntimeError("options.background_focus must be an object")

    for aspect in project["outputs"]:
        source = project["backgrounds"].get(aspect) or project["backgrounds"].get(
            "default"
        )
        target_width, target_height = ASPECTS[aspect]
        focus = focus_options.get(aspect, {})
        if not isinstance(focus, dict):
            focus = {}
        cropped = crop_background(
            read_image(source),
            target_width,
            target_height,
            float(focus.get("x", 0.5)),
            float(focus.get("y", 0.5)),
        )
        write_png(background_dir / f"{aspect}.png", cropped)
        print(
            f"BACKGROUND: {aspect} {cropped.shape[1]}x{cropped.shape[0]} "
            f"focus=({float(focus.get('x', 0.5)):.2f},"
            f"{float(focus.get('y', 0.5)):.2f})"
        )


def resolve_path(project_dir: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else project_dir / path


def load_project(project_arg: str) -> dict[str, Any]:
    project_path = Path(project_arg).expanduser().resolve()
    manifest_path = project_path / "project.json" if project_path.is_dir() else project_path
    if not manifest_path.exists():
        raise RuntimeError(f"Missing manifest: {manifest_path}")
    project_dir = manifest_path.parent
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    route = str(raw.get("route", "")).lower()
    if route not in {"single", "two"}:
        raise RuntimeError("route must be 'single' or 'two'")

    characters = []
    for index, item in enumerate(raw.get("characters", [])):
        display_name = str(item.get("display_name") or item.get("name") or "").strip()
        if not display_name:
            raise RuntimeError(f"characters[{index}] is missing display_name")
        character_id = str(
            item.get("id") or slugify(display_name, f"character-{index + 1}")
        )
        engine = str(item.get("engine", "kokoro")).lower()
        if engine not in {"kokoro", "edge"}:
            raise RuntimeError(
                f"Character {display_name} engine must be kokoro or edge"
            )
        voice_value = str(item.get("voice") or "").strip()
        if not voice_value:
            raise RuntimeError(f"Character {display_name} is missing voice")
        if engine == "kokoro":
            project_voice = resolve_path(project_dir, voice_value)
            installed_voice = (
                Path(__file__).resolve().parents[1]
                / "assets"
                / "voices"
                / "kokoro"
                / (voice_value if voice_value.endswith(".pt") else f"{voice_value}.pt")
            )
            kokoro_voice = tool_paths()["kokoro"] / "voices" / (
                voice_value if voice_value.endswith(".pt") else f"{voice_value}.pt"
            )
            if project_voice.exists():
                voice_path: Path | str = project_voice
            elif installed_voice.exists():
                voice_path = installed_voice
            elif kokoro_voice.exists():
                voice_path = kokoro_voice
            else:
                voice_path = project_voice
        else:
            voice_path = voice_value
        characters.append(
            {
                "id": character_id,
                "display_name": display_name,
                "photo": resolve_path(project_dir, str(item.get("photo", ""))),
                "engine": engine,
                "voice": voice_path,
                "gender": str(item.get("gender", "")).strip().lower(),
                "lang_code": str(item.get("lang_code", "a")),
                "speed": float(item.get("speed", 1.0)),
                "rate": str(item.get("rate", "+0%")),
                "pitch": str(item.get("pitch", "+0Hz")),
                "edge_volume": str(item.get("edge_volume", "+0%")),
            }
        )

    background_value = raw.get("backgrounds", {})
    if isinstance(background_value, str):
        background_value = {"default": background_value}
    backgrounds = {
        str(key): resolve_path(project_dir, str(value))
        for key, value in background_value.items()
    }

    speakers: dict[str, str] = {}
    for character in characters:
        speakers[character["id"].casefold()] = character["id"]
        speakers[character["display_name"].casefold()] = character["id"]

    dialogue = []
    for index, item in enumerate(raw.get("dialogue", [])):
        speaker_key = str(item.get("speaker", "")).strip().casefold()
        if speaker_key not in speakers:
            raise RuntimeError(
                f"dialogue[{index}] speaker does not match a character: {speaker_key}"
            )
        text = re.sub(r"\s+", " ", str(item.get("text", ""))).strip()
        if not text:
            raise RuntimeError(f"dialogue[{index}] is empty")
        translation = re.sub(
            r"\s+",
            " ",
            str(item.get("translation", item.get("subtitle", ""))),
        ).strip()
        dialogue.append(
            {
                "speaker_id": speakers[speaker_key],
                "text": text,
                "translation": translation,
            }
        )

    outputs = [str(item) for item in raw.get("outputs", ["16x9", "9x16"])]
    options = dict(raw.get("options", {}))
    return {
        "project_dir": project_dir,
        "manifest_path": manifest_path,
        "route": route,
        "title": str(raw.get("title") or project_dir.name),
        "subtitle": str(raw.get("subtitle") or ""),
        "characters": characters,
        "backgrounds": backgrounds,
        "dialogue": dialogue,
        "outputs": outputs,
        "options": options,
    }


def normalize_gender(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"f", "female", "woman", "girl"}:
        return "female"
    if normalized in {"m", "male", "man", "boy"}:
        return "male"
    return ""


def infer_voice_gender(character: dict[str, Any]) -> str:
    if character["engine"] == "kokoro":
        stem = Path(character["voice"]).stem
        if len(stem) >= 2 and stem[1] in {"f", "m"}:
            return "female" if stem[1] == "f" else "male"
        return ""

    catalog_path = (
        Path(__file__).resolve().parents[1] / "assets" / "voices" / "catalog.json"
    )
    if not catalog_path.exists():
        return ""
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    voice_id = str(character["voice"]).casefold()
    for item in catalog.get("edge", []):
        if str(item.get("id", "")).casefold() == voice_id:
            return normalize_gender(item.get("gender", ""))
    return ""


def validate_project(project: dict[str, Any]) -> None:
    route = project["route"]
    characters = project["characters"]
    expected_count = 1 if route == "single" else 2
    if len(characters) != expected_count:
        raise RuntimeError(
            f"{route} route requires exactly {expected_count} character(s)"
        )
    if not project["dialogue"]:
        raise RuntimeError("dialogue must contain at least one line")
    if not project["outputs"]:
        raise RuntimeError("outputs must contain 16x9 and/or 9x16")
    if any(aspect not in ASPECTS for aspect in project["outputs"]):
        raise RuntimeError(f"Unsupported output aspect: {project['outputs']}")

    paths = tool_paths()
    for key in (
        "python",
        "audio_python",
        "wav2lip",
        "checkpoint",
        "ffmpeg",
        "ffprobe",
    ):
        if not paths[key].exists():
            raise RuntimeError(f"Missing {key}: {paths[key]}")
    if not (paths["kokoro"] / "config.json").exists():
        raise RuntimeError(f"Missing Kokoro config under {paths['kokoro']}")

    ids = [character["id"] for character in characters]
    if len(set(ids)) != len(ids):
        raise RuntimeError("Character ids must be unique")
    for character in characters:
        if not character["photo"].exists():
            raise RuntimeError(f"Missing character photo: {character['photo']}")
        if character["engine"] == "kokoro":
            if not Path(character["voice"]).exists():
                raise RuntimeError(f"Missing Kokoro voice: {character['voice']}")
        elif not str(character["voice"]).strip():
            raise RuntimeError(f"Missing Edge voice id: {character['display_name']}")
        declared_gender = normalize_gender(character.get("gender", ""))
        inferred_gender = infer_voice_gender(character)
        if declared_gender and inferred_gender and declared_gender != inferred_gender:
            raise RuntimeError(
                f"Voice gender mismatch for {character['display_name']}: "
                f"declared {declared_gender}, inferred {inferred_gender}"
            )
        image = read_image(character["photo"])
        min_side = min(image.shape[:2])
        if min_side < 512:
            raise RuntimeError(
                f"Character photo is too small ({image.shape[1]}x{image.shape[0]}): "
                f"{character['photo']}"
            )
        if min_side < 768:
            print(f"WARNING: low-resolution character photo: {character['photo']}")

    if route == "two":
        voices = {
            f"{character['engine']}:{str(character['voice']).casefold()}"
            for character in characters
        }
        if len(voices) == 1:
            print("WARNING: both characters use the same voice file")

    for aspect in project["outputs"]:
        background = project["backgrounds"].get(aspect) or project["backgrounds"].get(
            "default"
        )
        if background is None:
            raise RuntimeError(f"No background configured for {aspect}")
        if not background.exists():
            raise RuntimeError(f"Missing background: {background}")
        image = read_image(background)
        target_w, target_h = ASPECTS[aspect]
        if image.shape[1] < target_w * 0.5 or image.shape[0] < target_h * 0.5:
            print(f"WARNING: low-resolution background for {aspect}: {background}")

    focus_options = project["options"].get("background_focus", {})
    if not isinstance(focus_options, dict):
        raise RuntimeError("options.background_focus must be an object")
    for aspect, focus in focus_options.items():
        if aspect not in ASPECTS:
            raise RuntimeError(f"Unsupported background_focus aspect: {aspect}")
        if not isinstance(focus, dict):
            raise RuntimeError(f"background_focus.{aspect} must be an object")
        for key in ("x", "y"):
            value = float(focus.get(key, 0.5))
            if value < 0.0 or value > 1.0:
                raise RuntimeError(f"background_focus.{aspect}.{key} must be 0..1")

    bgm_value = str(project["options"].get("bgm") or "").strip()
    if bgm_value:
        bgm = resolve_path(project["project_dir"], bgm_value)
        if not bgm.exists():
            raise RuntimeError(f"Missing background music: {bgm}")

    device = compute_device(project)
    if device not in {"auto", "cpu"}:
        match = re.fullmatch(r"cuda:(\d+)", device)
        if match is None:
            raise RuntimeError(
                "compute_device must be auto, cpu, gpu:N, or cuda:N"
            )
        if int(match.group(1)) < 0:
            raise RuntimeError("compute_device GPU index must be non-negative")

    video_encoder = str(project["options"].get("video_encoder", "auto")).lower()
    if video_encoder not in {"auto", "cpu", "gpu", "nvidia", "cuda"}:
        raise RuntimeError(
            "video_encoder must be auto, cpu, gpu, nvidia, or cuda"
        )

    voice_volume = float(project["options"].get("voice_volume", 1.0))
    bgm_volume = float(project["options"].get("bgm_volume", 0.075))
    if not 0.0 <= voice_volume <= 3.0:
        raise RuntimeError("voice_volume must be between 0.0 and 3.0")
    if not 0.0 <= bgm_volume <= 1.0:
        raise RuntimeError("bgm_volume must be between 0.0 and 1.0")
    translation_scale = float(
        project["options"].get("caption_translation_scale", 0.78)
    )
    if not 0.5 <= translation_scale <= 1.2:
        raise RuntimeError("caption_translation_scale must be between 0.5 and 1.2")

    color_adjustments = project["options"].get("character_color_adjustments", {})
    if not isinstance(color_adjustments, dict):
        raise RuntimeError("character_color_adjustments must be an object")
    character_ids = {item["id"] for item in characters}
    for character_id, adjustment in color_adjustments.items():
        if character_id not in character_ids:
            raise RuntimeError(
                f"character_color_adjustments has unknown id: {character_id}"
            )
        if not isinstance(adjustment, dict):
            raise RuntimeError(
                f"character_color_adjustments.{character_id} must be an object"
            )
        brightness = float(adjustment.get("brightness", -0.006))
        contrast = float(adjustment.get("contrast", 1.012))
        saturation = float(adjustment.get("saturation", 0.98))
        if not -0.3 <= brightness <= 0.3:
            raise RuntimeError("character brightness must be between -0.3 and 0.3")
        if not 0.5 <= contrast <= 2.0:
            raise RuntimeError("character contrast must be between 0.5 and 2.0")
        if not 0.0 <= saturation <= 2.0:
            raise RuntimeError("character saturation must be between 0.0 and 2.0")

    for aspect in project["outputs"]:
        font_size = int(
            project["options"].get(
                f"caption_font_size_{aspect}",
                42 if aspect == "16x9" else 46,
            )
        )
        margin_v = int(
            project["options"].get(
                f"caption_margin_v_{aspect}",
                70 if aspect == "16x9" else 180,
            )
        )
        if font_size < 16 or font_size > 120:
            raise RuntimeError(f"caption_font_size_{aspect} must be 16..120")
        if margin_v < 0 or margin_v > ASPECTS[aspect][1] // 2:
            raise RuntimeError(f"caption_margin_v_{aspect} is out of range")

    print(
        f"VALID: route={route} characters={len(characters)} "
        f"lines={len(project['dialogue'])} outputs={','.join(project['outputs'])}"
    )


def build_audio(project: dict[str, Any]) -> None:
    paths = tool_paths()
    project_dir = project["project_dir"]
    audio_dir = project_dir / "work" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    spec = {
        "audio_dir": str(audio_dir),
        "kokoro_root": str(paths["kokoro"]),
        "ffmpeg": str(paths["ffmpeg"]),
        "route": project["route"],
        "characters": [
            {
                "id": item["id"],
                "display_name": item["display_name"],
                "voice": str(item["voice"]),
                "engine": item["engine"],
                "lang_code": item["lang_code"],
                "speed": item["speed"],
                "rate": item["rate"],
                "pitch": item["pitch"],
                "edge_volume": item["edge_volume"],
            }
            for item in project["characters"]
        ],
        "dialogue": [
            {
                "speaker_id": item["speaker_id"],
                "text": item["text"],
                "translation": item["translation"],
            }
            for item in project["dialogue"]
        ],
        "options": project["options"],
    }
    spec_path = audio_dir / "audio_spec.json"
    spec_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    worker = Path(__file__).with_name("audio_worker.py")
    environment = os.environ.copy()
    device = compute_device(project)
    if device == "cpu":
        environment["CUDA_VISIBLE_DEVICES"] = ""
    else:
        match = re.fullmatch(r"cuda:(\d+)", device)
        if match is not None:
            environment["CUDA_VISIBLE_DEVICES"] = match.group(1)
    subprocess.run(
        [str(paths["audio_python"]), str(worker), "--spec", str(spec_path)],
        env=environment,
        check=True,
    )
    if not (audio_dir / "timeline.json").exists():
        raise RuntimeError("Audio worker did not produce timeline.json")


def remove_background(image_rgb: np.ndarray) -> np.ndarray:
    from rembg import new_session, remove

    session = new_session(model_name="u2net_human_seg")
    rgba = remove(image_rgb, session=session)
    coverage = float((rgba[..., 3] > 10).mean())
    if coverage < 0.02 or coverage > 0.98:
        raise RuntimeError(f"Suspicious alpha coverage: {coverage:.3f}")
    return rgba


def cutout_bbox(rgba: np.ndarray) -> tuple[int, int, int, int]:
    alpha = rgba[..., 3]
    rows = np.any(alpha > 20, axis=1)
    cols = np.any(alpha > 20, axis=0)
    if not rows.any() or not cols.any():
        raise RuntimeError("Background removal returned an empty mask")
    return (
        int(np.argmax(cols)),
        int(np.argmax(rows)),
        int(len(cols) - np.argmax(cols[::-1])),
        int(len(rows) - np.argmax(rows[::-1])),
    )


def build_panel(rgba: np.ndarray, fallback: tuple[int, int, int]) -> tuple[np.ndarray, np.ndarray]:
    x0, y0, x1, y1 = cutout_bbox(rgba)
    crop = rgba[y0:y1, x0:x1]
    height, width = crop.shape[:2]
    scale = min(PANEL_W / width, PANEL_H / height) * 0.92
    new_w = max(1, int(width * scale))
    new_h = max(1, int(height * scale))
    resized = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_AREA)

    panel = np.empty((PANEL_H, PANEL_W, 3), dtype=np.uint8)
    panel[..., 0], panel[..., 1], panel[..., 2] = fallback
    mask = np.zeros((PANEL_H, PANEL_W), dtype=np.uint8)
    px = (PANEL_W - new_w) // 2
    py = (PANEL_H - new_h) // 4
    panel[py : py + new_h, px : px + new_w] = resized[..., :3]
    mask[py : py + new_h, px : px + new_w] = resized[..., 3]
    feather = cv2.GaussianBlur(mask, (0, 0), 1.1)
    blend = (
        panel.astype(np.float32) * feather[..., None] / 255.0
        + np.array(fallback, dtype=np.float32) * (1.0 - feather[..., None] / 255.0)
    )
    return np.clip(blend, 0, 255).astype(np.uint8), feather


def build_contact_shadow(
    mask: np.ndarray,
    opacity: float,
    blur_sigma: float,
) -> np.ndarray:
    visible = np.where(mask > 16)
    if len(visible[0]) == 0:
        raise RuntimeError("Cannot create a contact shadow from an empty mask")
    y0, y1 = int(visible[0].min()), int(visible[0].max())
    x0, x1 = int(visible[1].min()), int(visible[1].max())
    center_x = (x0 + x1) // 2
    center_y = min(PANEL_H - 2, max(2, y1 - 3))
    axis_x = max(48, int((x1 - x0) * 0.34))
    axis_y = max(10, int((y1 - y0) * 0.017))

    shadow = np.zeros((PANEL_H, PANEL_W, 4), dtype=np.uint8)
    alpha = int(round(255 * min(0.7, max(0.05, opacity))))
    cv2.ellipse(
        shadow,
        (center_x, center_y),
        (axis_x, axis_y),
        0,
        0,
        360,
        (0, 0, 0, alpha),
        thickness=-1,
        lineType=cv2.LINE_AA,
    )
    return cv2.GaussianBlur(
        shadow,
        (0, 0),
        sigmaX=max(1.0, blur_sigma),
        sigmaY=max(1.0, blur_sigma * 0.55),
    )


def build_panels(project: dict[str, Any]) -> None:
    panel_dir = project["project_dir"] / "work" / "panels"
    panel_dir.mkdir(parents=True, exist_ok=True)
    fallback = tuple(project["options"].get("panel_fallback", [48, 34, 26]))
    shadow_opacity = float(project["options"].get("shadow_opacity", 0.30))
    shadow_blur = float(project["options"].get("shadow_blur", 16.0))
    for character in project["characters"]:
        image_bgr = read_image(character["photo"])
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        rgba = remove_background(image_rgb)
        panel, mask = build_panel(rgba, fallback)
        write_png(panel_dir / f"{character['id']}_panel.png", panel)
        write_png(panel_dir / f"{character['id']}_mask.png", mask)
        write_png(
            panel_dir / f"{character['id']}_cutout.png",
            cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA),
        )
        write_png(
            panel_dir / f"{character['id']}_shadow.png",
            build_contact_shadow(mask, shadow_opacity, shadow_blur),
        )
        print(f"PANEL: {character['display_name']} -> {panel_dir}")


def ascii_stage_root(project_dir: Path) -> Path:
    configured = os.environ.get("TALKING_VIDEO_ASCII_ROOT")
    candidates = []
    if configured:
        candidates.append(Path(configured))
    if os.name == "nt":
        candidates.append(Path(r"C:\talking_video_work"))
    else:
        candidates.append(Path("/tmp/talking-video-work"))

    for candidate in candidates:
        try:
            str(candidate).encode("ascii")
        except UnicodeEncodeError:
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        key = hashlib.sha1(str(project_dir).encode("utf-8")).hexdigest()[:12]
        return candidate / key
    raise RuntimeError(
        "Set TALKING_VIDEO_ASCII_ROOT to a writable ASCII-only directory"
    )


def run_wav2lip(project: dict[str, Any], character: dict[str, Any], force: bool) -> Path:
    paths = tool_paths()
    project_dir = project["project_dir"]
    panel = project_dir / "work" / "panels" / f"{character['id']}_panel.png"
    audio = project_dir / "work" / "audio" / "padded" / f"{character['id']}_48k.wav"
    output = project_dir / "work" / "talk" / f"{character['id']}_talk.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not force:
        print(f"TALK: reuse {output}")
        return output
    if not panel.exists() or not audio.exists():
        raise RuntimeError("Run the audio and panels stages before talk")

    stage = ascii_stage_root(project_dir)
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True, exist_ok=True)
    face = stage / "face.png"
    voice = stage / "voice.wav"
    staged_output = stage / "talk.mp4"
    shutil.copy2(panel, face)
    shutil.copy2(audio, voice)

    pads = project["options"].get("face_pads", [0, 24, 0, 0])
    batch_size = int(project["options"].get("wav2lip_batch_size", 96))
    device = compute_device(project)
    command = [
        str(paths["python"]),
        str(paths["wav2lip"] / "inference.py"),
        "--checkpoint_path",
        str(paths["checkpoint"]),
        "--face",
        str(face),
        "--audio",
        str(voice),
        "--outfile",
        str(staged_output),
        "--static",
        "True",
        "--fps",
        "30",
        "--wav2lip_batch_size",
        str(batch_size),
        "--face_det_batch_size",
        "1",
        "--pads",
        *[str(item) for item in pads],
    ]
    log_path = output.with_suffix(".log")
    environment = os.environ.copy()
    if device == "cpu":
        environment["CUDA_VISIBLE_DEVICES"] = ""
    else:
        match = re.fullmatch(r"cuda:(\d+)", device)
        if match is not None:
            environment["CUDA_VISIBLE_DEVICES"] = match.group(1)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(paths["wav2lip"]), environment.get("PYTHONPATH", "")]
    )
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.run(
            command,
            cwd=paths["wav2lip"],
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if process.returncode != 0 or not staged_output.exists():
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
        raise RuntimeError(
            f"Wav2Lip failed for {character['display_name']}:\n" + "\n".join(tail)
        )
    shutil.copy2(staged_output, output)
    shutil.rmtree(stage, ignore_errors=True)
    print(f"TALK: {character['display_name']} -> {output}")
    return output


def build_talk(project: dict[str, Any], force: bool) -> None:
    for character in project["characters"]:
        run_wav2lip(project, character, force)


def ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def wrap_caption(text: str, limit: int) -> str:
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    if cjk_count >= 4:
        max_chars = max(10, int(limit * 0.5))
        punctuation = set("，。！？；：、,.!?;:—")
        lines = []
        current = ""
        for char in text:
            current += char
            if len(current) >= max_chars and char in punctuation:
                lines.append(current.strip())
                current = ""
            elif len(current) >= max_chars + 4:
                split_at = max(
                    (index + 1 for index, item in enumerate(current[:-1]) if item in punctuation),
                    default=-1,
                )
                if split_at > 0:
                    lines.append(current[:split_at].strip())
                    current = current[split_at:]
                else:
                    lines.append(current.strip())
                    current = ""
        if current.strip():
            lines.append(current.strip())
        return r"\N".join(line for line in lines if line)

    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > limit:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return r"\N".join(lines)


def build_captions(
    project: dict[str, Any],
    timeline: dict[str, Any],
    width: int,
    height: int,
    font_size: int,
    margin_v: int,
    wrap_limit: int,
    output: Path,
) -> Path:
    font = str(project["options"].get("caption_font", "Arial"))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H60000000,-1,0,0,0,100,100,0,0,1,3,1,2,90,90,{margin_v},1
Style: Label,{font},{max(font_size - 14, 18)},&H00F3E6CE,&H00F3E6CE,&H66000000,&H00000000,-1,0,0,0,100,100,4,0,1,1.5,0,8,120,120,86,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    total = float(timeline["total_duration"])
    label_end = min(5.0, max(1.0, total - 1.0))
    subtitle = project["subtitle"].upper()
    label_text = project["title"].upper()
    if subtitle:
        label_text += rf"\N{{\fs14\c&HBFD5E1&}}{subtitle}"
    lines.append(
        f"Dialogue: 0,{ass_time(0.7)},{ass_time(label_end)},Label,,0,0,0,,"
        rf"{{\fad(300,400)}}{label_text}" + "\n"
    )

    character_index = {
        character["id"]: index for index, character in enumerate(project["characters"])
    }
    translation_scale = float(
        project["options"].get("caption_translation_scale", 0.78)
    )
    translation_size = max(18, int(round(font_size * translation_scale)))
    for event in timeline["events"]:
        color = SPEAKER_COLORS[character_index[event["speaker_id"]] % len(SPEAKER_COLORS)]
        text = (
            wrap_caption(event["text"], wrap_limit)
            .replace("\\", r"\\")
            .replace("{", r"\{")
            .replace("}", r"\}")
        )
        translation = event.get("translation", "")
        secondary = ""
        if translation:
            translated_text = (
                wrap_caption(translation, max(24, int(wrap_limit * 1.08)))
                .replace("\\", r"\\")
                .replace("{", r"\{")
                .replace("}", r"\}")
            )
            secondary = (
                rf"\N{{\fs{translation_size}\c&HEAE2D9&}}"
                f"{translated_text}"
            )
        lines.append(
            f"Dialogue: 0,{ass_time(event['start'])},{ass_time(event['end'])},"
            f"Caption,,0,0,0,,{{\\fad(130,130)}}{{\\c&H{color}&}}"
            f"{event['speaker'].upper()}{{\\c&HFFFFFF&}} {text}{secondary}\n"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(lines), encoding="utf-8-sig")
    return output


def person_chain(
    video_index: int,
    mask_index: int,
    shadow_index: int,
    index: int,
    width: int,
    height: int,
    edge_feather: float,
    contrast: float,
    saturation: float,
    brightness: float,
) -> str:
    return (
        f"[{video_index}:v]format=rgba,"
        f"eq=contrast={contrast:.3f}:saturation={saturation:.3f}:"
        f"brightness={brightness:.3f}[rv{index}];"
        f"[{mask_index}:v]format=gray,"
        "curves=all='0/0 0.04/0 0.08/1 1/1',"
        f"gblur=sigma={max(0.2, edge_feather):.2f}[rm{index}];"
        f"[rv{index}][rm{index}]alphamerge[ra{index}];"
        f"[ra{index}]scale={width}:{height}:flags=lanczos[rs{index}];"
        f"[{shadow_index}:v]format=rgba,"
        f"scale={width}:{height}:flags=lanczos[rsh{index}];"
    )


def aspect_layout(project: dict[str, Any], aspect: str) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    width, height = ASPECTS[aspect]
    count = len(project["characters"])
    if count == 1:
        if aspect == "16x9":
            panel_w, panel_h = 648, 1080
            return width, height, [((width - panel_w) // 2, 0, panel_w, panel_h)]
        panel_w, panel_h = 720, 1200
        return width, height, [((width - panel_w) // 2, 80, panel_w, panel_h)]

    if aspect == "16x9":
        panel_w, panel_h = 648, 1080
        return width, height, [
            (276, 0, panel_w, panel_h),
            (width - panel_w - 56, 0, panel_w, panel_h),
        ]
    panel_w, panel_h = 528, 880
    first_x = (width - panel_w) // 2
    return width, height, [
        (first_x, 36, panel_w, panel_h),
        (first_x + 14, 992, panel_w, panel_h),
    ]


def build_filter_graph(
    project: dict[str, Any],
    aspect: str,
    timeline: dict[str, Any],
    caption_name: str,
    audio_index: int,
    bgm_index: int | None,
) -> str:
    width, height, layout = aspect_layout(project, aspect)
    fps = int(project["options"].get("fps", 30))
    frames = max(1, math.ceil(float(timeline["total_duration"]) * fps))
    graph = (
        "[0:v]"
        "eq=contrast=1.02:saturation=1.10:brightness=0.006,"
        f"zoompan=z='min(1.0+0.06*on/{frames},1.06)':"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={width}x{height}:fps={fps},format=rgba[bg];"
    )
    edge_feather = float(project["options"].get("edge_feather", 1.15))
    color_adjustments = project["options"].get("character_color_adjustments", {})
    if not isinstance(color_adjustments, dict):
        color_adjustments = {}
    for index, (_, _, panel_w, panel_h) in enumerate(layout):
        character = project["characters"][index]
        adjustment = color_adjustments.get(character["id"], {})
        if not isinstance(adjustment, dict):
            adjustment = {}
        graph += person_chain(
            1 + index * 3,
            2 + index * 3,
            3 + index * 3,
            index,
            panel_w,
            panel_h,
            edge_feather,
            float(adjustment.get("contrast", 1.012)),
            float(adjustment.get("saturation", 0.98)),
            float(adjustment.get("brightness", -0.006)),
        )

    current = "bg"
    for index, (base_x, base_y, _, _) in enumerate(layout):
        phase = 1.1 + index * 0.8
        sway_x = 5.0 + index * 1.5
        sway_y = 2.6 + index * 0.8
        shadow_label = f"rshadow{index}"
        next_label = f"rvout{index}"
        position = (
            f"x='{base_x}+{sway_x}*sin(2*PI*t/6.3+{phase})':"
            f"y='{base_y}+{sway_y}*sin(2*PI*t/5.1+{phase})':"
            "eval=frame:format=auto:shortest=1"
        )
        graph += (
            f"[{current}][rsh{index}]overlay={position}[{shadow_label}];"
            f"[{shadow_label}][rs{index}]overlay={position}[{next_label}];"
        )
        current = next_label

    fade_start = max(0.0, float(timeline["total_duration"]) - 1.2)
    voice_volume = float(project["options"].get("voice_volume", 1.0))
    bgm_volume = float(project["options"].get("bgm_volume", 0.075))
    limiter_limit = float(project["options"].get("limiter_limit", 0.95))
    graph += (
        f"[{current}]eq=contrast=1.03:saturation=1.06:brightness=0.004,"
        "unsharp=5:5:0.30:5:5:0.0,vignette=PI/4.6,"
        f"subtitles={caption_name},format=yuv420p,"
        f"fade=t=in:st=0:d=0.7,fade=t=out:st={fade_start:.3f}:d=1.2[vout];"
        f"[{audio_index}:a]aresample=48000,"
        "aformat=sample_fmts=fltp:channel_layouts=stereo,"
        "highpass=f=72,lowpass=f=13500,"
        "equalizer=f=210:t=q:w=0.8:g=1.0,"
        "acompressor=threshold=0.14:ratio=2.4:attack=18:release=240,"
        f"loudnorm=I=-16:TP=-1.5:LRA=8,volume={voice_volume:.3f}[voice];"
    )
    if bgm_index is None:
        graph += f"[voice]alimiter=limit={limiter_limit:.3f}[aout]"
    else:
        graph += (
            f"[{bgm_index}:a]aresample=48000,"
            "aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"volume={bgm_volume:.3f},afade=t=in:st=0:d=2.2,"
            f"afade=t=out:st={max(0.0, float(timeline['total_duration']) - 3.2):.3f}:"
            "d=3.2[bgm];"
            "[voice][bgm]amix=inputs=2:duration=first:dropout_transition=0:"
            f"normalize=0,alimiter=limit={limiter_limit:.3f}[aout]"
        )
    return graph


def verify_output(
    output: Path,
    expected_duration: float,
    expected_width: int,
    expected_height: int,
) -> None:
    paths = tool_paths()
    probe = subprocess.run(
        [
            str(paths["ffprobe"]),
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(probe.stdout)
    duration = float(data["format"]["duration"])
    if abs(duration - expected_duration) > 1.0:
        raise RuntimeError(f"Unexpected output duration: {duration:.3f}s")
    streams = data.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if video is None or audio is None:
        raise RuntimeError(f"Missing video or audio stream: {output}")
    if int(video["width"]) != expected_width or int(video["height"]) != expected_height:
        raise RuntimeError(f"Unexpected dimensions: {video['width']}x{video['height']}")
    subprocess.run(
        [str(paths["ffmpeg"]), "-v", "error", "-i", str(output), "-f", "null", "-"],
        check=True,
    )
    print(f"VERIFIED: {output} ({duration:.3f}s)")


def render_project(project: dict[str, Any], force: bool) -> None:
    paths = tool_paths()
    project_dir = project["project_dir"]
    timeline_path = project_dir / "work" / "audio" / "timeline.json"
    if not timeline_path.exists():
        raise RuntimeError("Run the audio stage before render")
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    master = project_dir / "work" / "audio" / "dialogue_master_48k.wav"
    talk_paths = [
        project_dir / "work" / "talk" / f"{character['id']}_talk.mp4"
        for character in project["characters"]
    ]
    if any(not path.exists() for path in talk_paths):
        raise RuntimeError("Run the talk stage before render")
    cropped_backgrounds = {
        aspect: project_dir / "work" / "backgrounds" / f"{aspect}.png"
        for aspect in project["outputs"]
    }
    if any(not path.exists() for path in cropped_backgrounds.values()):
        build_backgrounds(project)

    title_slug = project["options"].get("output_name") or slugify(
        project["title"], "talking-video"
    )
    output_dir = project_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    bgm_value = str(project["options"].get("bgm") or "").strip()
    bgm = resolve_path(project_dir, bgm_value) if bgm_value else None
    for aspect in project["outputs"]:
        width, height = ASPECTS[aspect]
        caption_dir = project_dir / "work" / "render" / aspect
        font_size = int(
            project["options"].get(
                f"caption_font_size_{aspect}",
                42 if aspect == "16x9" else 46,
            )
        )
        margin_v = int(
            project["options"].get(
                f"caption_margin_v_{aspect}",
                70 if aspect == "16x9" else 180,
            )
        )
        wrap_limit = int(
            project["options"].get(
                f"caption_wrap_{aspect}",
                58 if aspect == "16x9" else 46,
            )
        )
        caption = build_captions(
            project,
            timeline,
            width,
            height,
            font_size,
            margin_v,
            wrap_limit,
            caption_dir / "captions.ass",
        )
        output = output_dir / f"{title_slug}_{aspect}.mp4"
        if output.exists() and not force:
            verify_output(output, float(timeline["total_duration"]), width, height)
            print(f"RENDER: reuse {output}")
            continue

        background = cropped_backgrounds[aspect]
        command = [
            str(paths["ffmpeg"]),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-framerate",
            "30",
            "-i",
            str(background),
        ]
        for character, talk in zip(project["characters"], talk_paths):
            mask = project_dir / "work" / "panels" / f"{character['id']}_mask.png"
            shadow = project_dir / "work" / "panels" / f"{character['id']}_shadow.png"
            if not shadow.exists():
                raise RuntimeError("Run the panels stage to create contact shadows")
            command += [
                "-i",
                str(talk),
                "-loop",
                "1",
                "-framerate",
                "30",
                "-i",
                str(mask),
                "-loop",
                "1",
                "-framerate",
                "30",
                "-i",
                str(shadow),
            ]
        audio_index = 1 + len(project["characters"]) * 3
        command += ["-i", str(master)]
        bgm_index = None
        if bgm is not None:
            bgm_index = audio_index + 1
            command += ["-stream_loop", "-1", "-i", str(bgm)]
        graph = build_filter_graph(
            project,
            aspect,
            timeline,
            caption.name,
            audio_index,
            bgm_index,
        )
        command += [
            "-filter_complex",
            graph,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-t",
            f"{float(timeline['total_duration']):.3f}",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            "-metadata",
            f"title={project['title']}",
        ]
        log_path = output.with_suffix(".render.log")
        modes = video_encoder_modes(project)
        render_environment = os.environ.copy()
        render_device = compute_device(project)
        if render_device.startswith("cuda:"):
            render_environment["CUDA_VISIBLE_DEVICES"] = render_device.split(":", 1)[1]
        succeeded = False
        for mode_index, mode in enumerate(modes):
            encoder_command = command.copy()
            if mode == "nvidia":
                encoder_args = [
                    "-c:v",
                    "h264_nvenc",
                    "-preset",
                    "p5",
                    "-tune",
                    "hq",
                    "-rc",
                    "vbr",
                    "-cq",
                    "20",
                    "-b:v",
                    "8M",
                    "-maxrate",
                    "12M",
                    "-bufsize",
                    "16M",
                    "-spatial-aq",
                    "1",
                ]
            else:
                encoder_args = [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                ]
            encoder_command += encoder_args + [
                "-profile:v",
                "high",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "30",
                "-metadata",
                "comment=Generated by avatar-cinema-director",
                "-metadata",
                f"encoder_mode={mode}",
                str(output),
            ]
            log_mode = "w" if mode_index == 0 else "a"
            with log_path.open(log_mode, encoding="utf-8", errors="replace") as log:
                if mode_index > 0:
                    log.write(f"\n[avatar-cinema-director] fallback encoder={mode}\n")
                process = subprocess.run(
                    encoder_command,
                    cwd=caption_dir,
                    env=render_environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
            if process.returncode == 0:
                succeeded = True
                break
        if not succeeded:
            tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
            raise RuntimeError(f"Render failed:\n" + "\n".join(tail))
        verify_output(output, float(timeline["total_duration"]), width, height)


def main() -> None:
    parser = argparse.ArgumentParser(description="Single/dual talking video pipeline")
    parser.add_argument("--project", required=True, help="Project directory or project.json")
    parser.add_argument(
        "--stage",
        choices=[
            "validate",
            "audio",
            "backgrounds",
            "panels",
            "talk",
            "render",
            "all",
        ],
        default="all",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    project = load_project(args.project)
    validate_project(project)
    if args.stage == "validate":
        return
    if args.stage in {"audio", "all"}:
        build_audio(project)
    if args.stage in {"backgrounds", "all"}:
        build_backgrounds(project)
    if args.stage in {"panels", "all"}:
        build_panels(project)
    if args.stage in {"talk", "all"}:
        build_talk(project, args.force)
    if args.stage in {"render", "all"}:
        render_project(project, args.force)


if __name__ == "__main__":
    main()
