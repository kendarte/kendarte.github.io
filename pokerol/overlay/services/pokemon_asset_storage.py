"""Persistent Fakemon visual-asset storage shared by the public creator and POKEROL.

Files live under POKEROL_ASSET_ROOT/pokemon/<species_id>/ and JSON stores only
public URLs. No database blobs or data URLs are written here.
"""

import os
import re
from pathlib import Path
from uuid import uuid4

ASSET_ROOT = Path(os.environ.get("POKEROL_ASSET_ROOT", "/data/pokerol_assets"))
PUBLIC_PREFIX = "/pokerol-assets/pokemon/"
MAX_ASSET_BYTES = 20 * 1024 * 1024
SPECIES_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
VISUAL_SLOTS = {
    "battle_front",
    "battle_back",
    "shot_neutral",
    "shot_attack_physical",
    "shot_attack_special",
    "shot_charge",
    "shot_hit",
    "shot_defend",
    "shot_dodge",
    "shot_ko",
    "portrait",
    "icon",
}
VIDEO_SLOTS = {
    "shot_neutral",
    "shot_attack_physical",
    "shot_attack_special",
    "shot_charge",
    "shot_hit",
    "shot_defend",
    "shot_dodge",
    "shot_ko",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".webm"}


def clean_species_id(value):
    value = str(value or "").strip()
    if not SPECIES_RE.fullmatch(value):
        raise ValueError("species_id inválido")
    return value


def clean_slot(value):
    value = str(value or "").strip().lower()
    if value not in VISUAL_SLOTS:
        raise ValueError("slot visual inválido")
    return value


def _ensure_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o755)
    except OSError:
        pass
    return path


def species_dir(species_id):
    species_id = clean_species_id(species_id)
    root = _ensure_dir(ASSET_ROOT / "pokemon")
    folder = (root / species_id).resolve()
    folder.relative_to(root.resolve())
    return _ensure_dir(folder)


def _header(file_obj, size=32):
    position = None
    try:
        position = file_obj.tell()
    except Exception:
        pass
    data = file_obj.read(size)
    try:
        file_obj.seek(0 if position is None else position)
    except Exception:
        pass
    return bytes(data or b"")


def _valid_signature(ext, header):
    ext = ext.lower()
    if ext == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if ext == ".webp":
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    if ext == ".mp4":
        return len(header) >= 12 and b"ftyp" in header[:32]
    if ext == ".webm":
        return header.startswith(b"\x1aE\xdf\xa3")
    return False


def validate_upload(upload, slot, media_kind):
    slot = clean_slot(slot)
    media_kind = str(media_kind or "image").strip().lower()
    if media_kind not in {"image", "video"}:
        raise ValueError("tipo de media inválido")
    if media_kind == "video" and slot not in VIDEO_SLOTS:
        raise ValueError("ese slot no admite video")
    size = int(getattr(upload, "size", 0) or 0)
    if size <= 0 or size > MAX_ASSET_BYTES:
        raise ValueError("archivo vacío o mayor de 20 MB")
    ext = Path(str(getattr(upload, "name", "") or "")).suffix.lower()
    allowed = VIDEO_EXTENSIONS if media_kind == "video" else IMAGE_EXTENSIONS
    if ext not in allowed:
        raise ValueError("formato no permitido")
    if not _valid_signature(ext, _header(upload)):
        raise ValueError("firma de archivo inválida")
    return slot, media_kind, ext


def _remove_slot_family(folder, slot, media_kind):
    extensions = VIDEO_EXTENSIONS if media_kind == "video" else IMAGE_EXTENSIONS
    prefixes = (f"{slot}.", f"{slot}-")
    for candidate in folder.iterdir():
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in extensions:
            continue
        if candidate.name.startswith(prefixes):
            try:
                candidate.unlink()
            except OSError:
                pass


def save_upload(upload, species_id, slot, media_kind="image"):
    species_id = clean_species_id(species_id)
    slot, media_kind, ext = validate_upload(upload, slot, media_kind)
    folder = species_dir(species_id)
    # Nginx intentionally serves persistent assets as immutable. Give every
    # replacement a fresh URL so browsers can never reuse an old slot image.
    filename = f"{slot}-{uuid4().hex[:12]}{ext}"
    final_path = folder / filename
    temp_path = folder / f".{slot}.{os.getpid()}.{uuid4().hex[:8]}.part"
    with temp_path.open("wb") as handle:
        chunks = getattr(upload, "chunks", None)
        if callable(chunks):
            for chunk in chunks():
                handle.write(chunk)
        else:
            upload.seek(0)
            handle.write(upload.read())
    temp_path.replace(final_path)
    try:
        final_path.chmod(0o644)
    except OSError:
        pass
    _remove_slot_family_except(folder, slot, media_kind, final_path)
    return f"{PUBLIC_PREFIX}{species_id}/{final_path.name}"


def _remove_slot_family_except(folder, slot, media_kind, keep):
    extensions = VIDEO_EXTENSIONS if media_kind == "video" else IMAGE_EXTENSIONS
    prefixes = (f"{slot}.", f"{slot}-")
    for candidate in folder.iterdir():
        if candidate == keep or not candidate.is_file():
            continue
        if candidate.suffix.lower() in extensions and candidate.name.startswith(prefixes):
            try:
                candidate.unlink()
            except OSError:
                pass


def clear_slot(species_id, slot, media_kind=None):
    species_id = clean_species_id(species_id)
    slot = clean_slot(slot)
    folder = species_dir(species_id)
    kinds = [str(media_kind).lower()] if media_kind else ["image", "video"]
    before = {path for path in folder.iterdir() if path.is_file()}
    for kind in kinds:
        if kind == "video" and slot not in VIDEO_SLOTS:
            continue
        if kind not in {"image", "video"}:
            raise ValueError("tipo de media inválido")
        _remove_slot_family(folder, slot, kind)
    after = {path for path in folder.iterdir() if path.is_file()}
    return len(before - after)
