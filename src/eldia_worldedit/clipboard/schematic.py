"""Pure-Python Sponge Schematic v2 (.schem gzipped NBT) and .wejson reader/writer."""

from __future__ import annotations

import gzip
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.types import AIR_SPEC, BlockSpec, BlockVec3, parse_block_spec
from .clipboard import Clipboard

_TAG_END = 0
_TAG_BYTE = 1
_TAG_SHORT = 2
_TAG_INT = 3
_TAG_LONG = 4
_TAG_FLOAT = 5
_TAG_DOUBLE = 6
_TAG_BYTE_ARRAY = 7
_TAG_STRING = 8
_TAG_LIST = 9
_TAG_COMPOUND = 10
_TAG_INT_ARRAY = 11
_TAG_LONG_ARRAY = 12


def _write_utf8(buf: bytearray, text: str) -> None:
    raw = text.encode("utf-8")
    buf.extend(struct.pack(">H", len(raw)))
    buf.extend(raw)


def _write_tag(buf: bytearray, tag_type: int, name: str | None, payload: Any) -> None:
    buf.append(tag_type)
    if name is not None:
        _write_utf8(buf, name)
    _write_payload(buf, tag_type, payload)


def _write_payload(buf: bytearray, tag_type: int, val: Any) -> None:
    if tag_type == _TAG_BYTE:
        buf.extend(struct.pack(">b", int(val)))
    elif tag_type == _TAG_SHORT:
        buf.extend(struct.pack(">h", int(val)))
    elif tag_type == _TAG_INT:
        buf.extend(struct.pack(">i", int(val)))
    elif tag_type == _TAG_LONG:
        buf.extend(struct.pack(">q", int(val)))
    elif tag_type == _TAG_FLOAT:
        buf.extend(struct.pack(">f", float(val)))
    elif tag_type == _TAG_DOUBLE:
        buf.extend(struct.pack(">d", float(val)))
    elif tag_type == _TAG_BYTE_ARRAY:
        raw = bytes(val)
        buf.extend(struct.pack(">i", len(raw)))
        buf.extend(raw)
    elif tag_type == _TAG_STRING:
        _write_utf8(buf, str(val))
    elif tag_type == _TAG_INT_ARRAY:
        arr = list(val)
        buf.extend(struct.pack(">i", len(arr)))
        for item in arr:
            buf.extend(struct.pack(">i", int(item)))
    elif tag_type == _TAG_LONG_ARRAY:
        arr = list(val)
        buf.extend(struct.pack(">i", len(arr)))
        for item in arr:
            buf.extend(struct.pack(">q", int(item)))
    elif tag_type == _TAG_LIST:
        elem_type, items = val
        buf.append(elem_type)
        buf.extend(struct.pack(">i", len(items)))
        for item in items:
            _write_payload(buf, elem_type, item)
    elif tag_type == _TAG_COMPOUND:
        for k, (child_type, child_val) in val.items():
            _write_tag(buf, child_type, k, child_val)
        buf.append(_TAG_END)


class _NbtReader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def read_u8(self) -> int:
        val = self.data[self.pos]
        self.pos += 1
        return val

    def read_fmt(self, fmt: str) -> Any:
        sz = struct.calcsize(fmt)
        res = struct.unpack_from(fmt, self.data, self.pos)[0]
        self.pos += sz
        return res

    def read_str(self) -> str:
        length = self.read_fmt(">H")
        raw = self.data[self.pos : self.pos + length]
        self.pos += length
        return raw.decode("utf-8", errors="replace")

    def read_payload(self, tag_type: int) -> Any:
        if tag_type == _TAG_BYTE:
            return self.read_fmt(">b")
        if tag_type == _TAG_SHORT:
            return self.read_fmt(">h")
        if tag_type == _TAG_INT:
            return self.read_fmt(">i")
        if tag_type == _TAG_LONG:
            return self.read_fmt(">q")
        if tag_type == _TAG_FLOAT:
            return self.read_fmt(">f")
        if tag_type == _TAG_DOUBLE:
            return self.read_fmt(">d")
        if tag_type == _TAG_BYTE_ARRAY:
            n = self.read_fmt(">i")
            raw = self.data[self.pos : self.pos + n]
            self.pos += n
            return raw
        if tag_type == _TAG_STRING:
            return self.read_str()
        if tag_type == _TAG_INT_ARRAY:
            n = self.read_fmt(">i")
            out = list(struct.unpack_from(f">{n}i", self.data, self.pos))
            self.pos += 4 * n
            return out
        if tag_type == _TAG_LONG_ARRAY:
            n = self.read_fmt(">i")
            out = list(struct.unpack_from(f">{n}q", self.data, self.pos))
            self.pos += 8 * n
            return out
        if tag_type == _TAG_LIST:
            elem_type = self.read_u8()
            n = self.read_fmt(">i")
            return [self.read_payload(elem_type) for _ in range(n)]
        if tag_type == _TAG_COMPOUND:
            comp: dict[str, Any] = {}
            while True:
                t = self.read_u8()
                if t == _TAG_END:
                    break
                name = self.read_str()
                comp[name] = self.read_payload(t)
            return comp
        raise ValueError(f"Unsupported NBT tag type: {tag_type}")

    def read_root(self) -> tuple[str, dict[str, Any]]:
        t = self.read_u8()
        if t != _TAG_COMPOUND:
            raise ValueError("NBT root must be a Compound tag.")
        name = self.read_str()
        return name, self.read_payload(_TAG_COMPOUND)


def _encode_varints(indices: list[int]) -> bytes:
    out = bytearray()
    for val in indices:
        v = val
        while True:
            byte = v & 0x7F
            v >>= 7
            if v != 0:
                out.append(byte | 0x80)
            else:
                out.append(byte)
                break
    return bytes(out)


def _decode_varints(raw: bytes, expected: int) -> list[int]:
    out: list[int] = []
    i = 0
    n = len(raw)
    while i < n and len(out) < expected:
        val = 0
        shift = 0
        while True:
            b = raw[i]
            i += 1
            val |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        out.append(val)
    return out


@dataclass(frozen=True)
class SchematicEntry:
    """Metadata summary for a saved schematic file."""

    name: str
    path: Path
    fmt: str
    size_bytes: int
    modified_ts: float


SCHEMATIC_FORMATS: tuple[str, ...] = ("schem", "sponge", "wejson")


def sanitize_schematic_name(name: str) -> str:
    clean = name.strip()
    if not clean or "/" in clean or "\\" in clean or ".." in clean:
        raise ValueError(f"Invalid schematic name '{name}'.")
    return clean


def _resolve_save_path(directory: Path, name: str, fmt: str) -> tuple[Path, str]:
    clean = sanitize_schematic_name(name)
    norm_fmt = fmt.lower()
    if norm_fmt == "sponge":
        norm_fmt = "schem"
    if norm_fmt not in ("schem", "wejson"):
        raise ValueError(f"Unsupported schematic format '{fmt}'. Expected: schem, wejson.")
    ext = f".{norm_fmt}"
    if clean.lower().endswith(".schem"):
        return directory / clean, "schem"
    if clean.lower().endswith(".wejson"):
        return directory / clean, "wejson"
    return directory / f"{clean}{ext}", norm_fmt


def save_schematic(
    clipboard: Clipboard,
    directory: Path,
    name: str,
    fmt: str = "schem",
    overwrite: bool = False,
) -> Path:
    """Save a Clipboard to disk in Sponge .schem (gzipped NBT) or .wejson format."""
    path, norm_fmt = _resolve_save_path(directory, name, fmt)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Schematic '{path.name}' already exists (pass -f to overwrite).")
    directory.mkdir(parents=True, exist_ok=True)

    lo, hi = clipboard.min_point, clipboard.max_point
    w = hi.x - lo.x + 1
    h = hi.y - lo.y + 1
    length = hi.z - lo.z + 1
    we_offset = lo - clipboard.origin

    if norm_fmt == "wejson":
        palette_idx: dict[str, int] = {}
        palette_list: list[str] = []
        encoded_blocks: list[list[int]] = []
        for pos, spec in clipboard.blocks.items():
            key = spec.to_string()
            if key not in palette_idx:
                palette_idx[key] = len(palette_list)
                palette_list.append(key)
            rel = pos - lo
            encoded_blocks.append([rel.x, rel.y, rel.z, palette_idx[key]])
        payload = {
            "version": 1,
            "dimensions": [w, h, length],
            "offset": [we_offset.x, we_offset.y, we_offset.z],
            "palette": palette_list,
            "blocks": encoded_blocks,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    # Sponge Schematic v2 (.schem)
    palette_map: dict[str, int] = {"minecraft:air": 0}
    block_indices: list[int] = []
    for y in range(h):
        for z in range(length):
            for x in range(w):
                spec = clipboard.blocks.get(BlockVec3(lo.x + x, lo.y + y, lo.z + z), AIR_SPEC)
                key = spec.to_string()
                idx = palette_map.get(key)
                if idx is None:
                    idx = len(palette_map)
                    palette_map[key] = idx
                block_indices.append(idx)

    nbt_palette = {k: (_TAG_INT, v) for k, v in palette_map.items()}
    root = {
        "Version": (_TAG_INT, 2),
        "DataVersion": (_TAG_INT, 3955),
        "Width": (_TAG_SHORT, w),
        "Height": (_TAG_SHORT, h),
        "Length": (_TAG_SHORT, length),
        "PaletteMax": (_TAG_INT, len(palette_map)),
        "Palette": (_TAG_COMPOUND, nbt_palette),
        "BlockData": (_TAG_BYTE_ARRAY, _encode_varints(block_indices)),
        "Offset": (_TAG_INT_ARRAY, [we_offset.x, we_offset.y, we_offset.z]),
        "Metadata": (
            _TAG_COMPOUND,
            {
                "WEOffsetX": (_TAG_INT, we_offset.x),
                "WEOffsetY": (_TAG_INT, we_offset.y),
                "WEOffsetZ": (_TAG_INT, we_offset.z),
            },
        ),
    }
    raw_buf = bytearray()
    _write_tag(raw_buf, _TAG_COMPOUND, "Schematic", root)
    path.write_bytes(gzip.compress(bytes(raw_buf)))
    return path


def _find_schematic_file(directory: Path, name: str) -> Path:
    clean = sanitize_schematic_name(name)
    candidates = [directory / clean]
    for ext in (".schem", ".schematic", ".wejson"):
        candidates.append(directory / f"{clean}{ext}")
    for cand in candidates:
        if cand.is_file():
            return cand
    raise FileNotFoundError(f"Schematic '{clean}' not found in {directory}.")


def load_schematic(directory: Path, name: str) -> Clipboard:
    """Load a .schem, .schematic, or .wejson file into a Clipboard."""
    path = _find_schematic_file(directory, name)
    if path.suffix.lower() == ".wejson":
        raw = json.loads(path.read_text(encoding="utf-8"))
        w, h, length = raw["dimensions"]
        ox, oy, oz = raw.get("offset", [0, 0, 0])
        palette = [parse_block_spec(item) for item in raw["palette"]]
        origin = BlockVec3(0, 0, 0)
        lo = BlockVec3(int(ox), int(oy), int(oz))
        hi = BlockVec3(lo.x + int(w) - 1, lo.y + int(h) - 1, lo.z + int(length) - 1)
        blocks: dict[BlockVec3, BlockSpec] = {}
        for rx, ry, rz, pidx in raw["blocks"]:
            blocks[BlockVec3(lo.x + int(rx), lo.y + int(ry), lo.z + int(rz))] = palette[int(pidx)]
        return Clipboard(origin=origin, min_point=lo, max_point=hi, blocks=blocks)

    raw_bytes = path.read_bytes()
    if raw_bytes[:2] == b"\x1f\x8b":
        raw_bytes = gzip.decompress(raw_bytes)
    _, root = _NbtReader(raw_bytes).read_root()
    # Handle Sponge v3 wrapper if nested under "Schematic"
    if "Schematic" in root and isinstance(root["Schematic"], dict):
        root = root["Schematic"]

    w = int(root["Width"])
    h = int(root["Height"])
    length = int(root["Length"])
    meta = root.get("Metadata", {})
    if "WEOffsetX" in meta:
        off_vec = BlockVec3(int(meta["WEOffsetX"]), int(meta["WEOffsetY"]), int(meta["WEOffsetZ"]))
    elif "Offset" in root and len(root["Offset"]) == 3:
        off_vec = BlockVec3(int(root["Offset"][0]), int(root["Offset"][1]), int(root["Offset"][2]))
    else:
        off_vec = BlockVec3(0, 0, 0)

    rev_palette: dict[int, BlockSpec] = {}
    for bstr, idx in root["Palette"].items():
        rev_palette[int(idx)] = parse_block_spec(str(bstr))

    indices = _decode_varints(bytes(root["BlockData"]), w * h * length)
    lo = off_vec
    hi = BlockVec3(lo.x + w - 1, lo.y + h - 1, lo.z + length - 1)
    blocks = {}
    i = 0
    for y in range(h):
        for z in range(length):
            for x in range(w):
                if i < len(indices):
                    spec = rev_palette.get(indices[i], AIR_SPEC)
                    blocks[BlockVec3(lo.x + x, lo.y + y, lo.z + z)] = spec
                i += 1

    return Clipboard(origin=BlockVec3(0, 0, 0), min_point=lo, max_point=hi, blocks=blocks)


def list_schematics(directory: Path, sort: str = "name") -> list[SchematicEntry]:
    """List available schematic files in `directory`."""
    if not directory.exists():
        return []
    entries: list[SchematicEntry] = []
    for p in directory.iterdir():
        if p.is_file() and p.suffix.lower() in (".schem", ".schematic", ".wejson"):
            stat = p.stat()
            entries.append(
                SchematicEntry(
                    name=p.stem,
                    path=p,
                    fmt=p.suffix.lstrip(".").lower(),
                    size_bytes=stat.st_size,
                    modified_ts=stat.st_mtime,
                )
            )
    if sort == "oldest":
        entries.sort(key=lambda e: e.modified_ts)
    elif sort == "newest":
        entries.sort(key=lambda e: e.modified_ts, reverse=True)
    else:
        entries.sort(key=lambda e: e.name.lower())
    return entries


def delete_schematic(directory: Path, name: str) -> Path:
    """Delete a schematic file by name."""
    path = _find_schematic_file(directory, name)
    path.unlink()
    return path
