"""Clipboard operations: copy, cut, paste, rotate, flip, and revolve."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.masks import Mask, MaskContext
from ..core.regions import Region
from ..core.types import (
    AIR_SPEC,
    BlockSpec,
    BlockVec3,
    flip_block_spec,
    rotate_block_spec,
)
from ..world.adapter import WorldAdapter
from ..world.edit_session import EditSession


@dataclass
class Clipboard:
    """In-memory 3D schematic buffer centered around `origin`."""

    origin: BlockVec3
    min_point: BlockVec3
    max_point: BlockVec3
    blocks: dict[BlockVec3, BlockSpec] = field(default_factory=dict)
    biomes: dict[BlockVec3, str] = field(default_factory=dict)
    entities: list[dict[str, object]] = field(default_factory=list)

    @property
    def dimensions(self) -> BlockVec3:
        return BlockVec3(
            self.max_point.x - self.min_point.x + 1,
            self.max_point.y - self.min_point.y + 1,
            self.max_point.z - self.min_point.z + 1,
        )

    @property
    def volume(self) -> int:
        dims = self.dimensions
        return dims.x * dims.y * dims.z


def copy_region(
    world: WorldAdapter,
    region: Region,
    origin: BlockVec3,
    mask: Mask | None = None,
    mask_context: MaskContext | None = None,
    copy_entities: bool = False,
    copy_biomes: bool = False,
) -> Clipboard:
    """Copy all blocks (and optional biomes/entities) from `region` into a Clipboard."""
    blocks: dict[BlockVec3, BlockSpec] = {}
    biomes: dict[BlockVec3, str] = {}
    for pos in region.iter_positions():
        if mask is not None and not mask.test(world, pos, mask_context):
            blocks[pos] = AIR_SPEC
        else:
            blocks[pos] = world.get_block(pos)
        if copy_biomes:
            biomes[pos] = world.get_biome(pos)

    entities: list[dict[str, object]] = []
    if copy_entities:
        for ent in world.get_entities():
            if ent.entity_type != "minecraft:player" and region.contains(ent.pos):
                rel = ent.pos - origin
                entities.append({
                    "type": ent.entity_type,
                    "offset": (rel.x, rel.y, rel.z),
                    "name": ent.name,
                })

    return Clipboard(
        origin=origin,
        min_point=region.min_point,
        max_point=region.max_point,
        blocks=blocks,
        biomes=biomes,
        entities=entities,
    )


def _rotate_rel(v: BlockVec3, rx: int, ry: int, rz: int) -> BlockVec3:
    x, y, z = v.x, v.y, v.z
    # Y rotation (clockwise looking down +Y in Minecraft: +X -> +Z -> -X -> -Z)
    for _ in range((ry // 90) % 4):
        x, z = -z, x
    # X rotation
    for _ in range((rx // 90) % 4):
        y, z = -z, y
    # Z rotation
    for _ in range((rz // 90) % 4):
        x, y = -y, x
    return BlockVec3(x, y, z)


def rotate_clipboard(cb: Clipboard, rot_y: int = 0, rot_x: int = 0, rot_z: int = 0) -> Clipboard:
    """Return a rotated copy of `cb` around its origin in 90-degree increments."""
    new_blocks: dict[BlockVec3, BlockSpec] = {}
    new_biomes: dict[BlockVec3, str] = {}
    coords: list[BlockVec3] = []

    for pos, spec in cb.blocks.items():
        rel = pos - cb.origin
        nrel = _rotate_rel(rel, rot_x, rot_y, rot_z)
        npos = cb.origin + nrel
        new_blocks[npos] = rotate_block_spec(spec, rot_y)
        coords.append(npos)

    for pos, bio in cb.biomes.items():
        nrel = _rotate_rel(pos - cb.origin, rot_x, rot_y, rot_z)
        new_biomes[cb.origin + nrel] = bio

    if coords:
        lo = BlockVec3(min(p.x for p in coords), min(p.y for p in coords), min(p.z for p in coords))
        hi = BlockVec3(max(p.x for p in coords), max(p.y for p in coords), max(p.z for p in coords))
    else:
        lo, hi = cb.min_point, cb.max_point

    new_entities = []
    for ent in cb.entities:
        ox, oy, oz = ent["offset"]  # type: ignore[misc]
        nrel = _rotate_rel(BlockVec3(int(ox), int(oy), int(oz)), rot_x, rot_y, rot_z)
        new_entities.append({**ent, "offset": (nrel.x, nrel.y, nrel.z)})

    return Clipboard(
        origin=cb.origin,
        min_point=lo,
        max_point=hi,
        blocks=new_blocks,
        biomes=new_biomes,
        entities=new_entities,
    )


def flip_clipboard(cb: Clipboard, direction: BlockVec3) -> Clipboard:
    """Mirror `cb` around its origin along the dominant axis of `direction`."""
    ax, ay, az = abs(direction.x), abs(direction.y), abs(direction.z)
    if ay >= ax and ay >= az:
        axis = "y"
    elif ax >= az:
        axis = "x"
    else:
        axis = "z"

    def _mirror(p: BlockVec3) -> BlockVec3:
        rel = p - cb.origin
        if axis == "x":
            rel = BlockVec3(-rel.x, rel.y, rel.z)
        elif axis == "y":
            rel = BlockVec3(rel.x, -rel.y, rel.z)
        else:
            rel = BlockVec3(rel.x, rel.y, -rel.z)
        return cb.origin + rel

    new_blocks: dict[BlockVec3, BlockSpec] = {}
    coords: list[BlockVec3] = []
    for pos, spec in cb.blocks.items():
        np = _mirror(pos)
        new_blocks[np] = flip_block_spec(spec, axis)
        coords.append(np)

    new_biomes = {_mirror(pos): bio for pos, bio in cb.biomes.items()}
    if coords:
        lo = BlockVec3(min(p.x for p in coords), min(p.y for p in coords), min(p.z for p in coords))
        hi = BlockVec3(max(p.x for p in coords), max(p.y for p in coords), max(p.z for p in coords))
    else:
        lo, hi = cb.min_point, cb.max_point

    return Clipboard(
        origin=cb.origin,
        min_point=lo,
        max_point=hi,
        blocks=new_blocks,
        biomes=new_biomes,
        entities=list(cb.entities),
    )


def paste_clipboard(
    cb: Clipboard,
    session: EditSession,
    to: BlockVec3,
    ignore_air: bool = False,
    include_structure_void: bool = False,
    source_mask: Mask | None = None,
    paste_biomes: bool = False,
    select_only: bool = False,
) -> tuple[int, BlockVec3, BlockVec3]:
    """Paste `cb` at `to` returning (blocks_changed, pasted_min, pasted_max)."""
    offset = to - cb.origin
    pasted_min = cb.min_point + offset
    pasted_max = cb.max_point + offset

    if select_only:
        return 0, pasted_min, pasted_max

    changed = 0
    for pos, spec in cb.blocks.items():
        if ignore_air and spec.is_air:
            continue
        if not include_structure_void and spec.block_type == "minecraft:structure_void":
            continue
        if source_mask is not None and not source_mask.test(session.world, pos):
            continue
        dest = pos + offset
        if session.set_block(dest, spec):
            changed += 1

    if paste_biomes and cb.biomes:
        for pos, bio in cb.biomes.items():
            session.world.set_biome(pos + offset, bio)

    return changed, pasted_min, pasted_max


def revolve_region(
    world: WorldAdapter,
    session: EditSession,
    region: Region,
    origin: BlockVec3,
    count: int,
    start_angle: float = 0.0,
    end_angle: float = 360.0,
    height_diff: float = 0.0,
    reverse: bool = False,
    mask: Mask | None = None,
) -> int:
    """Copy `region` radially `count` times around `origin` in the XZ plane."""
    import math

    if count <= 0:
        raise ValueError("Revolution count must be positive.")
    cb = copy_region(world, region, origin, mask=mask)
    changed = 0
    span = end_angle - start_angle
    if reverse:
        span = -span

    for step in range(1, count + 1):
        t = step / count
        deg = start_angle + span * t
        rad = math.radians(deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        dy_shift = round(height_diff * t)
        snap_rot = (round(deg / 90.0) * 90) % 360

        for pos, spec in cb.blocks.items():
            if spec.is_air:
                continue
            rel = pos - origin
            rx = round(rel.x * cos_a - rel.z * sin_a)
            rz = round(rel.x * sin_a + rel.z * cos_a)
            dest = BlockVec3(origin.x + rx, origin.y + rel.y + dy_shift, origin.z + rz)
            if session.set_block(dest, rotate_block_spec(spec, snap_rot)):
                changed += 1
    return changed
