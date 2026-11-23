"""Pure-Python Sponge v2/v3 (.schem), MCEdit (.schematic), Bedrock (.mcstructure), and .wejson I/O."""

from __future__ import annotations

import gzip
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.types import AIR_SPEC, LEGACY_BLOCK_IDS, BlockSpec, BlockVec3, StateValue, parse_block_spec
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

_JAVA_TO_BEDROCK_ALIASES: dict[str, str] = {
    "minecraft:grass": "minecraft:short_grass",
    "minecraft:short_grass": "minecraft:short_grass",
    "minecraft:wall_torch": "minecraft:torch",
    "minecraft:soul_wall_torch": "minecraft:soul_torch",
    "minecraft:redstone_wall_torch": "minecraft:redstone_torch",
    "minecraft:waterlily": "minecraft:waterlily",
    "minecraft:lily_pad": "minecraft:waterlily",
    "minecraft:terracotta": "minecraft:hardened_clay",
    "minecraft:cobweb": "minecraft:web",
    "minecraft:snow_block": "minecraft:snow",
    "minecraft:snow": "minecraft:snow_layer",
    "minecraft:bricks": "minecraft:brick_block",
    "minecraft:nether_bricks": "minecraft:nether_brick",
    "minecraft:red_nether_bricks": "minecraft:red_nether_brick",
    "minecraft:stone_brick_stairs": "minecraft:stone_brick_stairs",
    "minecraft:oak_sign": "minecraft:standing_sign",
    "minecraft:oak_wall_sign": "minecraft:wall_sign",
    "minecraft:end_stone_bricks": "minecraft:end_bricks",
    "minecraft:melon": "minecraft:melon_block",
    "minecraft:carved_pumpkin": "minecraft:carved_pumpkin",
    "minecraft:jack_o_lantern": "minecraft:lit_pumpkin",
    "minecraft:rooted_dirt": "minecraft:dirt_with_roots",
}

_LEGACY_COLOR_ORDER = (
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black",
)
_LEGACY_WOOD_ORDER = ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak")
_LEGACY_STONE_VARIANTS = {
    0: "minecraft:stone",
    1: "minecraft:granite",
    2: "minecraft:polished_granite",
    3: "minecraft:diorite",
    4: "minecraft:polished_diorite",
    5: "minecraft:andesite",
    6: "minecraft:polished_andesite",
}


def _legacy_id_data_to_spec(block_id: int, data: int) -> BlockSpec:
    if block_id == 0:
        return AIR_SPEC
    if block_id == 1:
        return BlockSpec(_LEGACY_STONE_VARIANTS.get(data & 0x07, "minecraft:stone"))
    if block_id == 5:
        wood = _LEGACY_WOOD_ORDER[min(len(_LEGACY_WOOD_ORDER) - 1, data & 0x07)]
        return BlockSpec(f"minecraft:{wood}_planks")
    if block_id == 17:
        wood = _LEGACY_WOOD_ORDER[min(3, data & 0x03)]
        return BlockSpec(f"minecraft:{wood}_log")
    if block_id == 162:
        wood = "acacia" if (data & 0x01) == 0 else "dark_oak"
        return BlockSpec(f"minecraft:{wood}_log")
    if block_id == 18:
        wood = _LEGACY_WOOD_ORDER[min(3, data & 0x03)]
        return BlockSpec(f"minecraft:{wood}_leaves")
    if block_id == 35:
        color = _LEGACY_COLOR_ORDER[data & 0x0F]
        return BlockSpec(f"minecraft:{color}_wool")
    if block_id == 95:
        color = _LEGACY_COLOR_ORDER[data & 0x0F]
        return BlockSpec(f"minecraft:{color}_stained_glass")
    if block_id == 159:
        color = _LEGACY_COLOR_ORDER[data & 0x0F]
        return BlockSpec(f"minecraft:{color}_terracotta")
    if block_id == 251:
        color = _LEGACY_COLOR_ORDER[data & 0x0F]
        return BlockSpec(f"minecraft:{color}_concrete")
    if block_id == 252:
        color = _LEGACY_COLOR_ORDER[data & 0x0F]
        return BlockSpec(f"minecraft:{color}_concrete_powder")
    if block_id == 98:
        variants = ("minecraft:stone_bricks", "minecraft:mossy_stone_bricks", "minecraft:cracked_stone_bricks", "minecraft:chiseled_stone_bricks")
        return BlockSpec(variants[data & 0x03])
    btype = LEGACY_BLOCK_IDS.get(str(block_id), "minecraft:stone")
    return BlockSpec(btype)


def _normalize_loaded_spec(spec: BlockSpec) -> BlockSpec:
    mapped = _JAVA_TO_BEDROCK_ALIASES.get(spec.block_type)
    if mapped is None or mapped == spec.block_type:
        return spec
    return BlockSpec(mapped, spec.states)


def _write_utf8(buf: bytearray, text: str, endian: str = ">") -> None:
    raw = text.encode("utf-8")
    buf.extend(struct.pack(f"{endian}H", len(raw)))
    buf.extend(raw)


def _write_tag(buf: bytearray, tag_type: int, name: str | None, payload: Any, endian: str = ">") -> None:
    buf.append(tag_type)
    if name is not None:
        _write_utf8(buf, name, endian=endian)
    _write_payload(buf, tag_type, payload, endian=endian)


def _write_payload(buf: bytearray, tag_type: int, val: Any, endian: str = ">") -> None:
    if tag_type == _TAG_BYTE:
        buf.extend(struct.pack(f"{endian}b", int(val)))
    elif tag_type == _TAG_SHORT:
        buf.extend(struct.pack(f"{endian}h", int(val)))
    elif tag_type == _TAG_INT:
        buf.extend(struct.pack(f"{endian}i", int(val)))
    elif tag_type == _TAG_LONG:
        buf.extend(struct.pack(f"{endian}q", int(val)))
    elif tag_type == _TAG_FLOAT:
        buf.extend(struct.pack(f"{endian}f", float(val)))
    elif tag_type == _TAG_DOUBLE:
        buf.extend(struct.pack(f"{endian}d", float(val)))
    elif tag_type == _TAG_BYTE_ARRAY:
        raw = bytes(val)
        buf.extend(struct.pack(f"{endian}i", len(raw)))
        buf.extend(raw)
    elif tag_type == _TAG_STRING:
        _write_utf8(buf, str(val), endian=endian)
    elif tag_type == _TAG_INT_ARRAY:
        arr = list(val)
        buf.extend(struct.pack(f"{endian}i", len(arr)))
        for item in arr:
            buf.extend(struct.pack(f"{endian}i", int(item)))
    elif tag_type == _TAG_LONG_ARRAY:
        arr = list(val)
        buf.extend(struct.pack(f"{endian}i", len(arr)))
        for item in arr:
            buf.extend(struct.pack(f"{endian}q", int(item)))
    elif tag_type == _TAG_LIST:
        elem_type, items = val
        buf.append(elem_type)
        buf.extend(struct.pack(f"{endian}i", len(items)))
        for item in items:
            _write_payload(buf, elem_type, item, endian=endian)
    elif tag_type == _TAG_COMPOUND:
        for k, (child_type, child_val) in val.items():
            _write_tag(buf, child_type, k, child_val, endian=endian)
        buf.append(_TAG_END)


class _NbtReader:
    def __init__(self, data: bytes, little_endian: bool = False) -> None:
        self.data = data
        self.pos = 0
        self.endian = "<" if little_endian else ">"

    def read_u8(self) -> int:
        val = self.data[self.pos]
        self.pos += 1
        return val

    def read_fmt(self, fmt: str) -> Any:
        full_fmt = f"{self.endian}{fmt}"
        sz = struct.calcsize(full_fmt)
        res = struct.unpack_from(full_fmt, self.data, self.pos)[0]
        self.pos += sz
        return res

    def read_str(self) -> str:
        length = self.read_fmt("H")
        raw = self.data[self.pos : self.pos + length]
        self.pos += length
        return raw.decode("utf-8", errors="replace")

    def read_payload(self, tag_type: int) -> Any:
        if tag_type == _TAG_BYTE:
            return self.read_fmt("b")
        if tag_type == _TAG_SHORT:
            return self.read_fmt("h")
        if tag_type == _TAG_INT:
            return self.read_fmt("i")
        if tag_type == _TAG_LONG:
            return self.read_fmt("q")
        if tag_type == _TAG_FLOAT:
            return self.read_fmt("f")
        if tag_type == _TAG_DOUBLE:
            return self.read_fmt("d")
        if tag_type == _TAG_BYTE_ARRAY:
            n = self.read_fmt("i")
            raw = self.data[self.pos : self.pos + n]
            self.pos += n
            return raw
        if tag_type == _TAG_STRING:
            return self.read_str()
        if tag_type == _TAG_INT_ARRAY:
            n = self.read_fmt("i")
            if n == 0:
                return []
            out = list(struct.unpack_from(f"{self.endian}{n}i", self.data, self.pos))
            self.pos += 4 * n
            return out
        if tag_type == _TAG_LONG_ARRAY:
            n = self.read_fmt("i")
            if n == 0:
                return []
            out = list(struct.unpack_from(f"{self.endian}{n}q", self.data, self.pos))
            self.pos += 8 * n
            return out
        if tag_type == _TAG_LIST:
            elem_type = self.read_u8()
            n = self.read_fmt("i")
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


SCHEMATIC_FORMATS: tuple[str, ...] = ("schem", "sponge", "schematic", "mcstructure", "wejson")


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
    if norm_fmt not in ("schem", "mcstructure", "wejson"):
        raise ValueError(f"Unsupported schematic format '{fmt}'. Expected: schem, mcstructure, wejson.")
    ext = f".{norm_fmt}"
    for known_ext in (".schem", ".mcstructure", ".wejson"):
        if clean.lower().endswith(known_ext):
            return directory / clean, known_ext.lstrip(".")
    return directory / f"{clean}{ext}", norm_fmt


def _state_val_to_nbt(val: StateValue) -> tuple[int, Any]:
    if isinstance(val, bool):
        return (_TAG_BYTE, 1 if val else 0)
    if isinstance(val, int):
        return (_TAG_INT, val)
    return (_TAG_STRING, str(val))


def save_schematic(
    clipboard: Clipboard,
    directory: Path,
    name: str,
    fmt: str = "schem",
    overwrite: bool = False,
) -> Path:
    """Save a Clipboard to disk in Sponge .schem, Bedrock .mcstructure, or .wejson format."""
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

    if norm_fmt == "mcstructure":
        palette_map_mc: dict[BlockSpec, int] = {}
        palette_entries: list[dict[str, Any]] = []
        layer0: list[int] = []
        total_vox = w * h * length
        # Bedrock .mcstructure indexes (x * H + y) * L + z
        for x in range(w):
            for y in range(h):
                for z in range(length):
                    spec = clipboard.blocks.get(BlockVec3(lo.x + x, lo.y + y, lo.z + z), AIR_SPEC)
                    if spec.is_air and spec.block_type == "minecraft:air":
                        layer0.append(-1)
                        continue
                    idx = palette_map_mc.get(spec)
                    if idx is None:
                        idx = len(palette_entries)
                        palette_map_mc[spec] = idx
                        nbt_states = {k: _state_val_to_nbt(v) for k, v in spec.states}
                        palette_entries.append({
                            "name": (_TAG_STRING, spec.block_type),
                            "states": (_TAG_COMPOUND, nbt_states),
                            "version": (_TAG_INT, 18168865),
                        })
                    layer0.append(idx)
        layer1 = [-1] * total_vox
        root = {
            "format_version": (_TAG_INT, 1),
            "size": (_TAG_LIST, (_TAG_INT, [w, h, length])),
            "structure_world_origin": (_TAG_LIST, (_TAG_INT, [we_offset.x, we_offset.y, we_offset.z])),
            "structure": (
                _TAG_COMPOUND,
                {
                    "block_indices": (
                        _TAG_LIST,
                        (_TAG_LIST, [(_TAG_INT, layer0), (_TAG_INT, layer1)]),
                    ),
                    "entities": (_TAG_LIST, (_TAG_COMPOUND, [])),
                    "palette": (
                        _TAG_COMPOUND,
                        {
                            "default": (
                                _TAG_COMPOUND,
                                {
                                    "block_palette": (_TAG_LIST, (_TAG_COMPOUND, palette_entries)),
                                    "block_position_data": (_TAG_COMPOUND, {}),
                                },
                            )
                        },
                    ),
                },
            ),
        }
        raw_buf = bytearray()
        _write_tag(raw_buf, _TAG_COMPOUND, "", root, endian="<")
        path.write_bytes(bytes(raw_buf))
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
    _write_tag(raw_buf, _TAG_COMPOUND, "Schematic", root, endian=">")
    path.write_bytes(gzip.compress(bytes(raw_buf)))
    return path


def _find_schematic_file(directory: Path, name: str) -> Path:
    clean = sanitize_schematic_name(name)
    candidates = [directory / clean]
    for ext in (".schem", ".schematic", ".mcstructure", ".wejson"):
        candidates.append(directory / f"{clean}{ext}")
    for cand in candidates:
        if cand.is_file():
            return cand
    raise FileNotFoundError(f"Schematic '{clean}' not found in {directory}.")


def _load_mcstructure(raw_bytes: bytes) -> Clipboard:
    _, root = _NbtReader(raw_bytes, little_endian=True).read_root()
    size = root["size"]
    w, h, length = int(size[0]), int(size[1]), int(size[2])
    orig_list = root.get("structure_world_origin", [0, 0, 0])
    lo = BlockVec3(int(orig_list[0]), int(orig_list[1]), int(orig_list[2]))
    hi = BlockVec3(lo.x + w - 1, lo.y + h - 1, lo.z + length - 1)

    struct_tag = root["structure"]
    indices = struct_tag["block_indices"][0]
    raw_palette = struct_tag["palette"]["default"]["block_palette"]

    parsed_palette: list[BlockSpec] = []
    for entry in raw_palette:
        bname = str(entry["name"])
        raw_states = entry.get("states", {})
        state_items: list[tuple[str, StateValue]] = []
        for sk, sv in raw_states.items():
            if isinstance(sv, (bool, int, str)):
                state_items.append((str(sk), sv))
        state_items.sort(key=lambda pair: pair[0])
        parsed_palette.append(BlockSpec(bname, tuple(state_items)))

    blocks: dict[BlockVec3, BlockSpec] = {}
    i = 0
    for x in range(w):
        for y in range(h):
            for z in range(length):
                if i < len(indices):
                    pidx = int(indices[i])
                    spec = AIR_SPEC if pidx < 0 or pidx >= len(parsed_palette) else parsed_palette[pidx]
                    blocks[BlockVec3(lo.x + x, lo.y + y, lo.z + z)] = spec
                i += 1
    return Clipboard(origin=BlockVec3(0, 0, 0), min_point=lo, max_point=hi, blocks=blocks)


def load_schematic(directory: Path, name: str) -> Clipboard:
    """Load a .schem (v2/v3), .schematic, .mcstructure, or .wejson file into a Clipboard."""
    path = _find_schematic_file(directory, name)
    if path.suffix.lower() == ".wejson":
        raw = json.loads(path.read_text(encoding="utf-8"))
        w, h, length = raw["dimensions"]
        ox, oy, oz = raw.get("offset", [0, 0, 0])
        palette = [_normalize_loaded_spec(parse_block_spec(item)) for item in raw["palette"]]
        origin = BlockVec3(0, 0, 0)
        lo = BlockVec3(int(ox), int(oy), int(oz))
        hi = BlockVec3(lo.x + int(w) - 1, lo.y + int(h) - 1, lo.z + int(length) - 1)
        blocks: dict[BlockVec3, BlockSpec] = {}
        for rx, ry, rz, pidx in raw["blocks"]:
            blocks[BlockVec3(lo.x + int(rx), lo.y + int(ry), lo.z + int(rz))] = palette[int(pidx)]
        return Clipboard(origin=origin, min_point=lo, max_point=hi, blocks=blocks)

    raw_bytes = path.read_bytes()
    if path.suffix.lower() == ".mcstructure":
        return _load_mcstructure(raw_bytes)

    if raw_bytes[:2] == b"\x1f\x8b":
        raw_bytes = gzip.decompress(raw_bytes)

    _, root = _NbtReader(raw_bytes, little_endian=False).read_root()
    if "Schematic" in root and isinstance(root["Schematic"], dict):
        root = root["Schematic"]

    w = int(root["Width"])
    h = int(root["Height"])
    length = int(root["Length"])

    # Classic MCEdit / WorldEdit 6 .schematic (Width/Height/Length + Blocks + Data)
    if "Blocks" in root and isinstance(root["Blocks"], (bytes, bytearray)):
        block_ids = root["Blocks"]
        data_vals = root.get("Data", b"")
        add_blocks = root.get("AddBlocks", b"")
        ox = int(root.get("WEOffsetX", 0))
        oy = int(root.get("WEOffsetY", 0))
        oz = int(root.get("WEOffsetZ", 0))
        lo = BlockVec3(ox, oy, oz)
        hi = BlockVec3(lo.x + w - 1, lo.y + h - 1, lo.z + length - 1)
        blocks = {}
        i = 0
        for y in range(h):
            for z in range(length):
                for x in range(w):
                    if i < len(block_ids):
                        low_id = block_ids[i] & 0xFF
                        high_id = 0
                        if add_blocks and (i >> 1) < len(add_blocks):
                            b = add_blocks[i >> 1]
                            high_id = (b & 0x0F) if (i % 2 == 0) else ((b >> 4) & 0x0F)
                        full_id = (high_id << 8) | low_id
                        bdata = (data_vals[i] & 0x0F) if i < len(data_vals) else 0
                        spec = _normalize_loaded_spec(_legacy_id_data_to_spec(full_id, bdata))
                        blocks[BlockVec3(lo.x + x, lo.y + y, lo.z + z)] = spec
                    i += 1
        return Clipboard(origin=BlockVec3(0, 0, 0), min_point=lo, max_point=hi, blocks=blocks)

    # Sponge Schematic v3 (Blocks: {Palette, Data}) or Sponge v2 (Palette, BlockData)
    meta = root.get("Metadata", {})
    if "WEOffsetX" in meta:
        off_vec = BlockVec3(int(meta["WEOffsetX"]), int(meta["WEOffsetY"]), int(meta["WEOffsetZ"]))
    elif "Offset" in root and len(root["Offset"]) == 3:
        off_vec = BlockVec3(int(root["Offset"][0]), int(root["Offset"][1]), int(root["Offset"][2]))
    else:
        off_vec = BlockVec3(0, 0, 0)

    if "Blocks" in root and isinstance(root["Blocks"], dict):
        blocks_tag = root["Blocks"]
        raw_pal = blocks_tag["Palette"]
        raw_data = blocks_tag["Data"]
    else:
        raw_pal = root["Palette"]
        raw_data = root["BlockData"]

    rev_palette: dict[int, BlockSpec] = {}
    for bstr, idx in raw_pal.items():
        rev_palette[int(idx)] = _normalize_loaded_spec(parse_block_spec(str(bstr)))

    indices = _decode_varints(bytes(raw_data), w * h * length)
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
        if p.is_file() and p.suffix.lower() in (".schem", ".schematic", ".mcstructure", ".wejson"):
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
