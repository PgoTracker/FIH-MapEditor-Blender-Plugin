"""Blender-independent .fihmap.zip validation and writing."""

import json
import os
import re
import tempfile
import zipfile


FORMAT_VERSION = 15
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,79}\Z")
MAX_ASSETS = 100
MAX_OBJ = 8 * 1024 * 1024
MAX_SCRIPT = 256 * 1024
MAX_PNG = 8 * 1024 * 1024
MAX_SOUND = 4 * 1024 * 1024
MAX_PACKAGE = 64 * 1024 * 1024


class ExportError(ValueError):
    pass


def asset_name(object_name):
    """Blender's .001 duplicate suffix denotes another instance of one asset."""
    base = re.sub(r"\.\d{3,}$", "", object_name)
    if not NAME.fullmatch(base):
        raise ExportError(
            f"Invalid object name {object_name!r}. Use letters, digits and '_' "
            "with a letter or '_' first (maximum 80 characters)."
        )
    return base


def validate_png(data, name):
    if len(data) > MAX_PNG or len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ExportError(f"{name}: texture must be a PNG of at most 8 MB")
    if data[8:16] != b"\x00\x00\x00\rIHDR":
        raise ExportError(f"{name}: PNG has no IHDR header")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if not (1 <= width <= 2048 and 1 <= height <= 2048):
        raise ExportError(f"{name}: texture must be at most 2048 x 2048")
    if data[24] != 8 or data[25] not in (2, 6) or data[26:29] != b"\0\0\0":
        raise ExportError(f"{name}: texture must be non-interlaced 8-bit RGB or RGBA PNG")


def validate_sound(data, extension, name):
    if not isinstance(data, bytes) or not (12 <= len(data) <= MAX_SOUND):
        raise ExportError(f"{name}: impact sound must be 12 bytes to 4 MB")
    wav = extension == ".wav" and data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    ogg = extension == ".ogg" and data[:4] == b"OggS"
    if not (wav or ogg):
        raise ExportError(f"{name}: impact sound must be WAV or Ogg")


def write_package(path, map_name, objects, assets, *, base_mode="Overlay", spawn=None,
                  goal=None, checkpoints=None):
    """assets maps names to dicts with obj bytes and optional png/cs bytes."""
    if not objects:
        raise ExportError("No mesh objects to export")
    if len(assets) > MAX_ASSETS:
        raise ExportError(f"A package can contain at most {MAX_ASSETS} unique assets")
    seen = set()
    entries = []
    for name, files in sorted(assets.items(), key=lambda item: item[0].lower()):
        if not NAME.fullmatch(name) or name.lower() in seen:
            raise ExportError(f"Invalid or duplicate asset name: {name}")
        seen.add(name.lower())
        obj = files.get("obj")
        png = files.get("png")
        script = files.get("cs")
        sound = files.get("sound")
        sound_ext = files.get("sound_ext")
        if not isinstance(obj, bytes) or not obj or len(obj) > MAX_OBJ:
            raise ExportError(f"{name}: OBJ must be 1 byte to 8 MB")
        entries.append((f"geometry/{name}.obj", obj))
        if png is not None:
            validate_png(png, name)
            entries.append((f"textures/{name}.png", png))
        if script is not None:
            if not isinstance(script, bytes) or len(script) > MAX_SCRIPT:
                raise ExportError(f"{name}: C# file exceeds 256 KB")
            try:
                script.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ExportError(f"{name}: C# file must be UTF-8") from exc
            entries.append((f"scripts/{name}.cs", script))
        if sound is not None:
            validate_sound(sound, sound_ext, name)
            entries.append((f"sounds/{name}{sound_ext}", sound))
    for item in objects:
        source = item.get("Source", "")
        if not source.startswith("package://") or source[10:].lower() not in seen:
            raise ExportError(f"Map object references missing asset: {source}")
    if base_mode not in ("Overlay", "Blank"):
        raise ExportError(f"Invalid base mode: {base_mode}")
    map_data = {
        "FormatVersion": FORMAT_VERSION,
        "Name": map_name,
        "BaseMode": base_mode,
        "Spawn": spawn,
        "Goal": goal,
        "Objects": objects,
        "Checkpoints": checkpoints if checkpoints is not None else [],
    }
    map_bytes = (json.dumps(map_data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if len(map_bytes) > MAX_OBJ:
        raise ExportError("Map JSON exceeds 8 MB")
    entries.insert(0, ("map.fihmap.json", map_bytes))
    if sum(len(value) for _, value in entries) > MAX_PACKAGE:
        raise ExportError("Package expands beyond 64 MB")
    dest = os.path.abspath(path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    fd, temp = tempfile.mkstemp(suffix=".tmp", dir=os.path.dirname(dest))
    os.close(fd)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name, data in entries:
                archive.writestr(name, data)
        if os.path.getsize(temp) > MAX_PACKAGE:
            raise ExportError("Package exceeds 64 MB")
        os.replace(temp, dest)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return dest
