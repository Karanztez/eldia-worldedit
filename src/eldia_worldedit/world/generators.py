"""WorldEdit 3D voxel generators, terrain operators, splines, deform/g, trees, and entity utilities."""

from __future__ import annotations

import math
import random
from collections import Counter, deque
from contextlib import suppress

from ..core.masks import Mask, MaskContext
from ..core.math_expr import CompiledExpression, compile_expression
from ..core.patterns import Pattern, PatternContext
from ..core.regions import Region
from ..core.types import AIR_SPEC, LIQUID_BLOCKS, WATER_BLOCKS, BlockSpec, BlockVec3, resolve_direction
from .adapter import WorldAdapter
from .edit_session import EditSession

GRAVITY_BLOCKS: frozenset[str] = frozenset({
    "minecraft:sand",
    "minecraft:red_sand",
    "minecraft:gravel",
    "minecraft:anvil",
    "minecraft:chipped_anvil",
    "minecraft:damaged_anvil",
    "minecraft:dragon_egg",
    "minecraft:pointed_dripstone",
    "minecraft:white_concrete_powder",
    "minecraft:orange_concrete_powder",
    "minecraft:magenta_concrete_powder",
    "minecraft:light_blue_concrete_powder",
    "minecraft:yellow_concrete_powder",
    "minecraft:lime_concrete_powder",
    "minecraft:pink_concrete_powder",
    "minecraft:gray_concrete_powder",
    "minecraft:light_gray_concrete_powder",
    "minecraft:cyan_concrete_powder",
    "minecraft:purple_concrete_powder",
    "minecraft:blue_concrete_powder",
    "minecraft:brown_concrete_powder",
    "minecraft:green_concrete_powder",
    "minecraft:red_concrete_powder",
    "minecraft:black_concrete_powder",
})

PASSIVE_MOBS: frozenset[str] = frozenset({
    "minecraft:cow", "minecraft:pig", "minecraft:sheep", "minecraft:chicken", "minecraft:horse",
    "minecraft:donkey", "minecraft:mule", "minecraft:rabbit", "minecraft:fox", "minecraft:goat",
    "minecraft:frog", "minecraft:turtle", "minecraft:squid", "minecraft:glow_squid",
    "minecraft:cod", "minecraft:salmon", "minecraft:tropical_fish", "minecraft:pufferfish",
    "minecraft:axolotl", "minecraft:bee", "minecraft:bat", "minecraft:mooshroom", "minecraft:panda",
    "minecraft:sniffer", "minecraft:armadillo", "minecraft:camel", "minecraft:llama",
})

ANIMAL_MOBS: frozenset[str] = PASSIVE_MOBS

PET_MOBS: frozenset[str] = frozenset({"minecraft:wolf", "minecraft:cat", "minecraft:parrot"})

GOLEM_MOBS: frozenset[str] = frozenset({
    "minecraft:iron_golem", "minecraft:snow_golem", "minecraft:copper_golem",
})

AMBIENT_MOBS: frozenset[str] = frozenset({"minecraft:bat", "minecraft:firefly"})

NPC_MOBS: frozenset[str] = frozenset({
    "minecraft:villager", "minecraft:villager_v2", "minecraft:wandering_trader",
})

NON_LIVING_ENTITIES: frozenset[str] = frozenset({
    "minecraft:item",
    "minecraft:xp_orb",
    "minecraft:arrow",
    "minecraft:boat",
    "minecraft:chest_boat",
    "minecraft:minecart",
    "minecraft:chest_minecart",
    "minecraft:tnt_minecart",
    "minecraft:hopper_minecart",
    "minecraft:armor_stand",
    "minecraft:painting",
    "minecraft:item_frame",
    "minecraft:glow_item_frame",
    "minecraft:falling_block",
    "minecraft:tnt",
})

_DIRS_6 = (
    BlockVec3(1, 0, 0), BlockVec3(-1, 0, 0),
    BlockVec3(0, 1, 0), BlockVec3(0, -1, 0),
    BlockVec3(0, 0, 1), BlockVec3(0, 0, -1),
)
_DIRS_4H = (BlockVec3(1, 0, 0), BlockVec3(-1, 0, 0), BlockVec3(0, 0, 1), BlockVec3(0, 0, -1))


def _pat(
    pattern: Pattern,
    pos: BlockVec3,
    rng: random.Random,
    ctx: PatternContext,
) -> BlockSpec:
    return pattern.apply(pos, rng, ctx)


def op_set(
    session: EditSession,
    region: Region,
    pattern: Pattern,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Fill every position in `region` with `pattern`."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=session.world, origin=region.min_point, region=region)
    changed = 0
    for pos in region.iter_positions():
        if session.set_block(pos, _pat(pattern, pos, r, ctx)):
            changed += 1
    return changed


def op_replace(
    session: EditSession,
    region: Region,
    from_mask: Mask | None,
    pattern: Pattern,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
    mask_ctx: MaskContext | None = None,
) -> int:
    """Replace matching blocks in `region` (or all non-air blocks if `from_mask` is None)."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=session.world, origin=region.min_point, region=region)
    mctx = mask_ctx or MaskContext(region=region, origin=region.min_point, rng=r)
    changed = 0
    for pos in region.iter_positions():
        if from_mask is None:
            if session.get_block(pos).is_air:
                continue
        else:
            if not from_mask.test(session.world, pos, mctx):
                continue
        if session.set_block(pos, _pat(pattern, pos, r, ctx)):
            changed += 1
    return changed


def op_walls(
    session: EditSession,
    region: Region,
    pattern: Pattern,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Build vertical perimeter walls around `region`."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=session.world, origin=region.min_point, region=region)
    changed = 0
    for pos in region.iter_walls():
        if session.set_block(pos, _pat(pattern, pos, r, ctx)):
            changed += 1
    return changed


def op_faces(
    session: EditSession,
    region: Region,
    pattern: Pattern,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Build the outer 6 faces / outline shell of `region`."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=session.world, origin=region.min_point, region=region)
    changed = 0
    for pos in region.iter_faces():
        if session.set_block(pos, _pat(pattern, pos, r, ctx)):
            changed += 1
    return changed


def op_center(
    session: EditSession,
    region: Region,
    pattern: Pattern,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Place `pattern` at the middle 1-to-8 center block(s) of `region`."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=session.world, origin=region.min_point, region=region)
    lo, hi = region.min_point, region.max_point

    def _mids(a: int, b: int) -> tuple[int, ...]:
        s = a + b
        if s % 2 == 0:
            return (s // 2,)
        m = math.floor(s / 2.0)
        return (m, m + 1)

    changed = 0
    for x in _mids(lo.x, hi.x):
        for y in _mids(lo.y, hi.y):
            for z in _mids(lo.z, hi.z):
                pos = BlockVec3(x, y, z)
                if session.set_block(pos, _pat(pattern, pos, r, ctx)):
                    changed += 1
    return changed


def op_overlay(
    session: EditSession,
    region: Region,
    pattern: Pattern,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Place a single layer of `pattern` atop the highest non-air block in each column."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=session.world, origin=region.min_point, region=region)
    lo, hi = region.min_point, region.max_point
    changed = 0
    for x in range(lo.x, hi.x + 1):
        for z in range(lo.z, hi.z + 1):
            for y in range(hi.y, lo.y - 1, -1):
                cur = BlockVec3(x, y, z)
                if not region.contains(cur):
                    continue
                if not session.get_block(cur).is_air:
                    target = BlockVec3(x, y + 1, z)
                    if session.get_block(target).is_air and session.set_block(
                        target, _pat(pattern, target, r, ctx)
                    ):
                        changed += 1
                    break
    return changed


def op_naturalize(session: EditSession, region: Region) -> int:
    """Convert non-air surface layers to 1 grass_block, 3 dirt, and deeper stone."""
    lo, hi = region.min_point, region.max_point
    grass = BlockSpec("minecraft:grass_block")
    dirt = BlockSpec("minecraft:dirt")
    stone = BlockSpec("minecraft:stone")
    changed = 0
    for x in range(lo.x, hi.x + 1):
        for z in range(lo.z, hi.z + 1):
            depth = 0
            for y in range(hi.y, lo.y - 1, -1):
                pos = BlockVec3(x, y, z)
                if not region.contains(pos):
                    continue
                if session.get_block(pos).is_air:
                    depth = 0
                    continue
                if depth == 0:
                    spec = grass
                elif depth <= 3:
                    spec = dirt
                else:
                    spec = stone
                if session.set_block(pos, spec):
                    changed += 1
                depth += 1
    return changed


def generate_cylinder(
    session: EditSession,
    origin: BlockVec3,
    pattern: Pattern,
    rx: float,
    rz: float,
    height: int = 1,
    filled: bool = True,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Generate a vertical cylinder or hollow tube at `origin`."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=session.world, origin=origin)
    if height == 0:
        return 0
    y0, y1 = (origin.y, origin.y + height - 1) if height > 0 else (origin.y + height + 1, origin.y)
    irx, irz = math.ceil(rx), math.ceil(rz)
    denom_x = max(0.5, rx + 0.5)
    denom_z = max(0.5, rz + 0.5)

    def _inside(dx: int, dz: int) -> bool:
        return (dx / denom_x) ** 2 + (dz / denom_z) ** 2 <= 1.0

    changed = 0
    for dx in range(-irx, irx + 1):
        for dz in range(-irz, irz + 1):
            if not _inside(dx, dz):
                continue
            if not filled and (
                _inside(dx + 1, dz) and _inside(dx - 1, dz) and _inside(dx, dz + 1) and _inside(dx, dz - 1)
            ):
                continue
            for y in range(y0, y1 + 1):
                pos = BlockVec3(origin.x + dx, y, origin.z + dz)
                if session.set_block(pos, _pat(pattern, pos, r, ctx)):
                    changed += 1
    return changed


def generate_sphere(
    session: EditSession,
    origin: BlockVec3,
    pattern: Pattern,
    rx: float,
    ry: float | None = None,
    rz: float | None = None,
    filled: bool = True,
    raised: bool = False,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Generate a 3D sphere or ellipsoid at `origin` (optionally raised by ry)."""
    r = rng or random.Random()
    ery = rx if ry is None else ry
    erz = rx if rz is None else rz
    center = origin + BlockVec3(0, math.ceil(ery), 0) if raised else origin
    ctx = pat_ctx or PatternContext(world=session.world, origin=center)
    irx, iry, irz = math.ceil(rx), math.ceil(ery), math.ceil(erz)
    dx_d = max(0.5, rx + 0.5)
    dy_d = max(0.5, ery + 0.5)
    dz_d = max(0.5, erz + 0.5)

    def _inside(dx: int, dy: int, dz: int) -> bool:
        return (dx / dx_d) ** 2 + (dy / dy_d) ** 2 + (dz / dz_d) ** 2 <= 1.0

    changed = 0
    for dx in range(-irx, irx + 1):
        for dy in range(-iry, iry + 1):
            for dz in range(-irz, irz + 1):
                if not _inside(dx, dy, dz):
                    continue
                if not filled and (
                    _inside(dx + 1, dy, dz)
                    and _inside(dx - 1, dy, dz)
                    and _inside(dx, dy + 1, dz)
                    and _inside(dx, dy - 1, dz)
                    and _inside(dx, dy, dz + 1)
                    and _inside(dx, dy, dz - 1)
                ):
                    continue
                pos = BlockVec3(center.x + dx, center.y + dy, center.z + dz)
                if session.set_block(pos, _pat(pattern, pos, r, ctx)):
                    changed += 1
    return changed


def generate_cone(
    session: EditSession,
    origin: BlockVec3,
    pattern: Pattern,
    rx: float,
    rz: float,
    height: int,
    filled: bool = True,
    thickness: float = 1.0,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Generate an elliptical cone anchored at `origin`."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=session.world, origin=origin)
    if height == 0:
        return 0
    abs_h = abs(height)
    sign_y = 1 if height > 0 else -1
    changed = 0
    for layer in range(abs_h):
        scale = 1.0 if abs_h == 1 else max(0.0, 1.0 - (layer / abs_h))
        cur_rx = rx * scale
        cur_rz = rz * scale
        irx = math.ceil(cur_rx)
        irz = math.ceil(cur_rz)
        y = origin.y + sign_y * layer
        dx_d = max(0.5, cur_rx + 0.5)
        dz_d = max(0.5, cur_rz + 0.5)
        inner_rx = max(0.0, cur_rx - max(1.0, thickness))
        inner_rz = max(0.0, cur_rz - max(1.0, thickness))
        for dx in range(-irx, irx + 1):
            for dz in range(-irz, irz + 1):
                dist = (dx / dx_d) ** 2 + (dz / dz_d) ** 2
                if dist > 1.0:
                    continue
                if not filled and layer > 0 and layer < abs_h - 1 and inner_rx > 0 and inner_rz > 0:
                    in_dist = (dx / (inner_rx + 0.5)) ** 2 + (dz / (inner_rz + 0.5)) ** 2
                    if in_dist <= 1.0:
                        continue
                pos = BlockVec3(origin.x + dx, y, origin.z + dz)
                if session.set_block(pos, _pat(pattern, pos, r, ctx)):
                    changed += 1
    return changed


def generate_pyramid(
    session: EditSession,
    origin: BlockVec3,
    pattern: Pattern,
    size: int,
    filled: bool = True,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Generate a step pyramid of height `size` centered at `origin`."""
    if size <= 0:
        return 0
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=session.world, origin=origin)
    changed = 0
    for level in range(size):
        hw = size - 1 - level
        y = origin.y + level
        for dx in range(-hw, hw + 1):
            for dz in range(-hw, hw + 1):
                if not filled and abs(dx) < hw and abs(dz) < hw:
                    continue
                pos = BlockVec3(origin.x + dx, y, origin.z + dz)
                if session.set_block(pos, _pat(pattern, pos, r, ctx)):
                    changed += 1
    return changed


def op_smooth(
    session: EditSession,
    region: Region,
    iterations: int = 1,
    mask: Mask | None = None,
    mask_ctx: MaskContext | None = None,
) -> int:
    """Smooth terrain heightmap inside `region` across XZ columns."""
    lo, hi = region.min_point, region.max_point
    w = hi.x - lo.x + 1
    length = hi.z - lo.z + 1

    # Capture initial height & material palette per column inside region
    heights: list[list[float]] = [[float(lo.y - 1) for _ in range(length)] for _ in range(w)]
    top_specs: list[list[BlockSpec]] = [[BlockSpec("minecraft:grass_block") for _ in range(length)] for _ in range(w)]
    fill_specs: list[list[BlockSpec]] = [[BlockSpec("minecraft:stone") for _ in range(length)] for _ in range(w)]

    for ix in range(w):
        wx = lo.x + ix
        for iz in range(length):
            wz = lo.z + iz
            col_top: int | None = None
            for y in range(hi.y, lo.y - 1, -1):
                p = BlockVec3(wx, y, wz)
                spec = session.get_block(p)
                if not spec.is_air and (mask is None or mask.test(session.world, p, mask_ctx)):
                    col_top = y
                    top_specs[ix][iz] = spec
                    below = session.get_block(BlockVec3(wx, max(lo.y, y - 1), wz))
                    if not below.is_air:
                        fill_specs[ix][iz] = below
                    else:
                        fill_specs[ix][iz] = spec
                    break
            if col_top is not None:
                heights[ix][iz] = float(col_top)
            else:
                heights[ix][iz] = float(lo.y - 1)

    for _ in range(max(1, iterations)):
        next_h = [list(row) for row in heights]
        for ix in range(w):
            for iz in range(length):
                total = 0.0
                cnt = 0
                for dx in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        nx, nz = ix + dx, iz + dz
                        if 0 <= nx < w and 0 <= nz < length:
                            weight = 2 if (dx == 0 and dz == 0) else 1
                            total += heights[nx][nz] * weight
                            cnt += weight
                next_h[ix][iz] = total / max(1, cnt)
        heights = next_h

    changed = 0
    for ix in range(w):
        wx = lo.x + ix
        for iz in range(length):
            wz = lo.z + iz
            target_y = round(heights[ix][iz])
            for y in range(lo.y, hi.y + 1):
                pos = BlockVec3(wx, y, wz)
                if not region.contains(pos):
                    continue
                if y > target_y:
                    spec = AIR_SPEC
                elif y == target_y:
                    spec = top_specs[ix][iz]
                else:
                    spec = fill_specs[ix][iz]
                if session.set_block(pos, spec):
                    changed += 1
    return changed


def op_snowsmooth(
    session: EditSession,
    region: Region,
    iterations: int = 1,
    snow_blocks: int = 1,
) -> int:
    """Smooth snow heightmap using bedrock snow_layer heights."""
    lo, hi = region.min_point, region.max_point
    w = hi.x - lo.x + 1
    length = hi.z - lo.z + 1
    sub_heights: list[list[float]] = [[0.0 for _ in range(length)] for _ in range(w)]
    bases: list[list[int]] = [[lo.y - 1 for _ in range(length)] for _ in range(w)]

    for ix in range(w):
        wx = lo.x + ix
        for iz in range(length):
            wz = lo.z + iz
            base_y = lo.y - 1
            extra = 0.0
            for y in range(hi.y, lo.y - 1, -1):
                spec = session.get_block(BlockVec3(wx, y, wz))
                if spec.block_type == "minecraft:snow_layer":
                    layer_val = int(spec.states_dict.get("height", 0))
                    extra = (layer_val + 1) / 8.0
                    base_y = y - 1
                    break
                if spec.block_type == "minecraft:snow":
                    extra = 1.0
                    base_y = y - 1
                    break
                if not spec.is_air:
                    base_y = y
                    break
            bases[ix][iz] = base_y
            sub_heights[ix][iz] = base_y + extra

    for _ in range(max(1, iterations)):
        nxt = [list(r) for r in sub_heights]
        for ix in range(w):
            for iz in range(length):
                acc = 0.0
                cnt = 0
                for dx in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        nx, nz = ix + dx, iz + dz
                        if 0 <= nx < w and 0 <= nz < length:
                            acc += sub_heights[nx][nz]
                            cnt += 1
                nxt[ix][iz] = acc / max(1, cnt)
        sub_heights = nxt

    changed = 0
    for ix in range(w):
        wx = lo.x + ix
        for iz in range(length):
            wz = lo.z + iz
            h_val = sub_heights[ix][iz]
            base = bases[ix][iz]
            diff = h_val - base
            if diff <= 0.05:
                continue
            full_layers = math.floor(diff)
            frac = diff - full_layers
            snow_h = min(7, max(0, round(frac * 8) - 1))
            for k in range(max(0, full_layers)):
                p = BlockVec3(wx, base + 1 + k, wz)
                if p.y <= hi.y and session.set_block(p, BlockSpec("minecraft:snow")):
                    changed += 1
            if frac > 0.05 and snow_blocks >= 0:
                p_top = BlockVec3(wx, base + 1 + max(0, full_layers), wz)
                if p_top.y <= hi.y and session.set_block(
                    p_top, BlockSpec("minecraft:snow_layer", (("height", snow_h),))
                ):
                    changed += 1
    return changed


def op_move(
    session: EditSession,
    world: WorldAdapter,
    region: Region,
    direction: BlockVec3,
    count: int = 1,
    replace_pattern: Pattern | None = None,
    ignore_air: bool = False,
    move_entities: bool = False,
    move_biomes: bool = False,
    mask: Mask | None = None,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> tuple[int, BlockVec3, BlockVec3]:
    """Move blocks in `region` by `direction * count`, returning (changed, new_min, new_max)."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=world, origin=region.min_point, region=region)
    shift_vec = direction * count
    snapshot: list[tuple[BlockVec3, BlockSpec, str]] = []

    for pos in region.iter_positions():
        spec = world.get_block(pos)
        if mask is not None and not mask.test(world, pos):
            continue
        biome = world.get_biome(pos) if move_biomes else ""
        snapshot.append((pos, spec, biome))

    changed = 0
    for pos, _, _ in snapshot:
        fill_spec = _pat(replace_pattern, pos, r, ctx) if replace_pattern is not None else AIR_SPEC
        if session.set_block(pos, fill_spec):
            changed += 1

    for pos, spec, biome in snapshot:
        if ignore_air and spec.is_air:
            continue
        dest = pos + shift_vec
        if session.set_block(dest, spec):
            changed += 1
        if move_biomes and biome:
            world.set_biome(dest, biome)

    if move_entities:
        for ent in world.get_entities():
            if ent.entity_type != "minecraft:player" and region.contains(ent.pos) and ent.raw_actor is not None:
                with suppress(AttributeError, RuntimeError, TypeError, ValueError):
                    loc = ent.raw_actor.location
                    loc.x += shift_vec.x
                    loc.y += shift_vec.y
                    loc.z += shift_vec.z
                    ent.raw_actor.teleport(loc)

    return changed, region.min_point + shift_vec, region.max_point + shift_vec


def op_stack(
    session: EditSession,
    world: WorldAdapter,
    region: Region,
    direction: BlockVec3,
    count: int = 1,
    ignore_air: bool = False,
    stack_biomes: bool = False,
    mask: Mask | None = None,
) -> tuple[int, BlockVec3, BlockVec3]:
    """Repeat `region` `count` times along `direction`, returning (changed, last_min, last_max)."""
    if count <= 0:
        return 0, region.min_point, region.max_point
    dims = region.dimensions
    stride = BlockVec3(direction.x * dims.x, direction.y * dims.y, direction.z * dims.z)
    snapshot: list[tuple[BlockVec3, BlockSpec, str]] = []
    for pos in region.iter_positions():
        if mask is not None and not mask.test(world, pos):
            continue
        snapshot.append((pos, world.get_block(pos), world.get_biome(pos) if stack_biomes else ""))

    changed = 0
    last_shift = BlockVec3(0, 0, 0)
    for step in range(1, count + 1):
        shift_vec = stride * step
        last_shift = shift_vec
        for pos, spec, biome in snapshot:
            if ignore_air and spec.is_air:
                continue
            dest = pos + shift_vec
            if session.set_block(dest, spec):
                changed += 1
            if stack_biomes and biome:
                world.set_biome(dest, biome)

    return changed, region.min_point + last_shift, region.max_point + last_shift


def _bresenham_3d(a: BlockVec3, b: BlockVec3) -> list[BlockVec3]:
    pts: list[BlockVec3] = []
    x1, y1, z1 = a.x, a.y, a.z
    x2, y2, z2 = b.x, b.y, b.z
    dx, dy, dz = abs(x2 - x1), abs(y2 - y1), abs(z2 - z1)
    xs = 1 if x2 > x1 else -1
    ys = 1 if y2 > y1 else -1
    zs = 1 if z2 > z1 else -1
    pts.append(BlockVec3(x1, y1, z1))

    if dx >= dy and dx >= dz:
        p1, p2 = 2 * dy - dx, 2 * dz - dx
        while x1 != x2:
            x1 += xs
            if p1 >= 0:
                y1 += ys
                p1 -= 2 * dx
            if p2 >= 0:
                z1 += zs
                p2 -= 2 * dx
            p1 += 2 * dy
            p2 += 2 * dz
            pts.append(BlockVec3(x1, y1, z1))
    elif dy >= dx and dy >= dz:
        p1, p2 = 2 * dx - dy, 2 * dz - dy
        while y1 != y2:
            y1 += ys
            if p1 >= 0:
                x1 += xs
                p1 -= 2 * dy
            if p2 >= 0:
                z1 += zs
                p2 -= 2 * dy
            p1 += 2 * dx
            p2 += 2 * dz
            pts.append(BlockVec3(x1, y1, z1))
    else:
        p1, p2 = 2 * dy - dz, 2 * dx - dz
        while z1 != z2:
            z1 += zs
            if p1 >= 0:
                y1 += ys
                p1 -= 2 * dz
            if p2 >= 0:
                x1 += xs
                p2 -= 2 * dz
            p1 += 2 * dy
            p2 += 2 * dx
            pts.append(BlockVec3(x1, y1, z1))
    return pts


def op_line(
    session: EditSession,
    pos1: BlockVec3,
    pos2: BlockVec3,
    pattern: Pattern,
    thickness: int = 0,
    filled: bool = True,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Draw a straight 3D line between `pos1` and `pos2` with optional spherical `thickness`."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=session.world, origin=pos1)
    core_pts = _bresenham_3d(pos1, pos2)
    if thickness <= 0:
        targets = set(core_pts)
    else:
        targets = set()
        r_sq = (thickness + 0.5) ** 2
        inner_sq = max(0.0, (thickness - 0.5) ** 2) if not filled else -1.0
        for c in core_pts:
            for dx in range(-thickness, thickness + 1):
                for dy in range(-thickness, thickness + 1):
                    for dz in range(-thickness, thickness + 1):
                        d2 = dx * dx + dy * dy + dz * dz
                        if inner_sq < d2 <= r_sq:
                            targets.add(BlockVec3(c.x + dx, c.y + dy, c.z + dz))

    changed = 0
    for p in targets:
        if session.set_block(p, _pat(pattern, p, r, ctx)):
            changed += 1
    return changed


def _catmull_rom(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * t
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
    )


def op_curve(
    session: EditSession,
    vertices: list[BlockVec3],
    pattern: Pattern,
    thickness: int = 0,
    filled: bool = True,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Draw a smooth Catmull-Rom spline through ordered control vertices."""
    if len(vertices) < 2:
        raise ValueError("Need at least 2 points to draw a curve.")
    if len(vertices) == 2:
        return op_line(session, vertices[0], vertices[1], pattern, thickness, filled, rng, pat_ctx)

    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=session.world, origin=vertices[0])
    padded = [vertices[0], *vertices, vertices[-1]]
    spine: list[BlockVec3] = []
    for i in range(1, len(padded) - 2):
        a, b, c, d = padded[i - 1], padded[i], padded[i + 1], padded[i + 2]
        steps = max(16, int(b.distance(c) * 4))
        for s in range(steps + 1):
            t = s / steps
            px = round(_catmull_rom(a.x, b.x, c.x, d.x, t))
            py = round(_catmull_rom(a.y, b.y, c.y, d.y, t))
            pz = round(_catmull_rom(a.z, b.z, c.z, d.z, t))
            pt = BlockVec3(px, py, pz)
            if not spine or spine[-1] != pt:
                spine.append(pt)

    targets: set[BlockVec3] = set()
    if thickness <= 0:
        targets.update(spine)
    else:
        r_sq = (thickness + 0.5) ** 2
        inner_sq = max(0.0, (thickness - 0.5) ** 2) if not filled else -1.0
        for c in spine:
            for dx in range(-thickness, thickness + 1):
                for dy in range(-thickness, thickness + 1):
                    for dz in range(-thickness, thickness + 1):
                        d2 = dx * dx + dy * dy + dz * dz
                        if inner_sq < d2 <= r_sq:
                            targets.add(BlockVec3(c.x + dx, c.y + dy, c.z + dz))

    changed = 0
    for p in targets:
        if session.set_block(p, _pat(pattern, p, r, ctx)):
            changed += 1
    return changed


def op_hollow(
    session: EditSession,
    world: WorldAdapter,
    region: Region,
    thickness: int = 1,
    pattern: Pattern | None = None,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Hollow out solid structures in `region` leaving a shell of `thickness` blocks."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=world, origin=region.min_point, region=region)
    t = max(1, thickness)
    non_air: set[BlockVec3] = {
        pos for pos in region.iter_positions() if not world.get_block(pos).is_air
    }
    if not non_air:
        return 0

    shell: set[BlockVec3] = set()
    queue: deque[tuple[BlockVec3, int]] = deque()
    for pos in non_air:
        if any((pos + d) not in non_air and world.get_block(pos + d).is_air for d in _DIRS_6) or (
            (
                pos.x in (region.min_point.x, region.max_point.x)
                or pos.y in (region.min_point.y, region.max_point.y)
                or pos.z in (region.min_point.z, region.max_point.z)
            )
            and any(not region.contains(pos + d) and world.get_block(pos + d).is_air for d in _DIRS_6)
        ):
            shell.add(pos)
            queue.append((pos, 1))

    while queue:
        cur, dist = queue.popleft()
        if dist >= t:
            continue
        for d in _DIRS_6:
            nxt = cur + d
            if nxt in non_air and nxt not in shell:
                shell.add(nxt)
                queue.append((nxt, dist + 1))

    changed = 0
    for pos in non_air - shell:
        spec = _pat(pattern, pos, r, ctx) if pattern is not None else AIR_SPEC
        if session.set_block(pos, spec):
            changed += 1
    return changed


def _parse_expr_statements(expr_str: str) -> list[tuple[str | None, CompiledExpression]]:
    """Parse semicolon-separated assignments like 'y=y+0.2*sin(x)' or 'y+=0.5' or bare condition."""
    parts = [p.strip() for p in expr_str.split(";") if p.strip()]
    if not parts:
        raise ValueError("Expression cannot be empty.")
    out: list[tuple[str | None, CompiledExpression]] = []
    for part in parts:
        matched_op = False
        for op_tok in ("+=", "-=", "*=", "/="):
            if op_tok in part:
                lhs, rhs = part.split(op_tok, 1)
                target = lhs.strip()
                math_op = op_tok[0]
                compiled = compile_expression(f"({target}) {math_op} ({rhs.strip()})")
                out.append((target, compiled))
                matched_op = True
                break
        if matched_op:
            continue
        if "=" in part and not any(tok in part for tok in ("==", "!=", "<=", ">=")):
            lhs, rhs = part.split("=", 1)
            target = lhs.strip()
            out.append((target, compile_expression(rhs.strip())))
        else:
            out.append((None, compile_expression(part)))
    return out


def _region_norm_params(region: Region, raw_coords: bool, origin: BlockVec3) -> tuple[float, float, float, float, float, float]:
    lo, hi = region.min_point, region.max_point
    if raw_coords:
        return 0.0, 0.0, 0.0, 1.0, 1.0, 1.0
    cx = (lo.x + hi.x) / 2.0
    cy = (lo.y + hi.y) / 2.0
    cz = (lo.z + hi.z) / 2.0
    hx = max(0.5, (hi.x - lo.x) / 2.0)
    hy = max(0.5, (hi.y - lo.y) / 2.0)
    hz = max(0.5, (hi.z - lo.z) / 2.0)
    return cx, cy, cz, hx, hy, hz


def op_generate(
    session: EditSession,
    region: Region,
    pattern: Pattern,
    expr_str: str,
    hollow: bool = False,
    raw_coords: bool = False,
    offset_mode: bool = False,
    origin: BlockVec3 | None = None,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Evaluate a WorldEdit shape formula (`//g`) across `region` and place blocks where true."""
    r = rng or random.Random()
    orig = origin or region.center
    ctx = pat_ctx or PatternContext(world=session.world, origin=orig, region=region)
    stmts = _parse_expr_statements(expr_str)
    cx, cy, cz, hx, hy, hz = _region_norm_params(region, raw_coords, orig)

    def _matches(pos: BlockVec3) -> bool:
        if raw_coords:
            vx, vy, vz = float(pos.x), float(pos.y), float(pos.z)
        elif offset_mode:
            vx = float(pos.x - orig.x)
            vy = float(pos.y - orig.y)
            vz = float(pos.z - orig.z)
        else:
            vx = (pos.x - cx) / hx
            vy = (pos.y - cy) / hy
            vz = (pos.z - cz) / hz
        env: dict[str, float] = {
            "x": vx, "y": vy, "z": vz,
            "rx": float(pos.x - orig.x), "ry": float(pos.y - orig.y), "rz": float(pos.z - orig.z),
            "type": 0.0, "data": 0.0,
        }
        last_val = 0.0
        for target, compiled in stmts:
            last_val = compiled.evaluate(env)
            if target is not None:
                env[target] = last_val
        return (env.get("type", 0.0) != 0.0) if any(t == "type" for t, _ in stmts) else (last_val != 0.0)

    active: set[BlockVec3] = {pos for pos in region.iter_positions() if _matches(pos)}
    if hollow and active:
        shell: set[BlockVec3] = set()
        for pos in active:
            if not all((pos + d) in active for d in _DIRS_6):
                shell.add(pos)
        active = shell

    changed = 0
    for pos in active:
        if session.set_block(pos, _pat(pattern, pos, r, ctx)):
            changed += 1
    return changed


def op_deform(
    session: EditSession,
    world: WorldAdapter,
    region: Region,
    expr_str: str,
    raw_coords: bool = False,
    offset_mode: bool = False,
    origin: BlockVec3 | None = None,
) -> int:
    """Deform existing blocks in `region` by mapping each block position back to source coordinates."""
    orig = origin or region.center
    stmts = _parse_expr_statements(expr_str)
    cx, cy, cz, hx, hy, hz = _region_norm_params(region, raw_coords, orig)

    sampled: dict[BlockVec3, BlockSpec] = {}
    for pos in region.iter_positions():
        if raw_coords:
            vx, vy, vz = float(pos.x), float(pos.y), float(pos.z)
        elif offset_mode:
            vx = float(pos.x - orig.x)
            vy = float(pos.y - orig.y)
            vz = float(pos.z - orig.z)
        else:
            vx = (pos.x - cx) / hx
            vy = (pos.y - cy) / hy
            vz = (pos.z - cz) / hz
        env: dict[str, float] = {"x": vx, "y": vy, "z": vz}
        for target, compiled in stmts:
            val = compiled.evaluate(env)
            if target is not None:
                env[target] = val
        sx = env["x"] if raw_coords else (orig.x + env["x"] if offset_mode else cx + env["x"] * hx)
        sy = env["y"] if raw_coords else (orig.y + env["y"] if offset_mode else cy + env["y"] * hy)
        sz = env["z"] if raw_coords else (orig.z + env["z"] if offset_mode else cz + env["z"] * hz)
        src_pos = BlockVec3(round(sx), round(sy), round(sz))
        sampled[pos] = world.get_block(src_pos)

    changed = 0
    for pos, spec in sampled.items():
        if session.set_block(pos, spec):
            changed += 1
    return changed


TREE_TYPES: dict[str, tuple[str, str, int, int]] = {
    "oak": ("minecraft:oak_log", "minecraft:oak_leaves", 4, 2),
    "tree": ("minecraft:oak_log", "minecraft:oak_leaves", 4, 2),
    "big": ("minecraft:oak_log", "minecraft:oak_leaves", 7, 3),
    "big_tree": ("minecraft:oak_log", "minecraft:oak_leaves", 7, 3),
    "big_oak": ("minecraft:oak_log", "minecraft:oak_leaves", 7, 3),
    "birch": ("minecraft:birch_log", "minecraft:birch_leaves", 5, 2),
    "tall_birch": ("minecraft:birch_log", "minecraft:birch_leaves", 8, 2),
    "spruce": ("minecraft:spruce_log", "minecraft:spruce_leaves", 7, 2),
    "pine": ("minecraft:spruce_log", "minecraft:spruce_leaves", 7, 2),
    "redwood": ("minecraft:spruce_log", "minecraft:spruce_leaves", 9, 3),
    "tall_redwood": ("minecraft:spruce_log", "minecraft:spruce_leaves", 12, 3),
    "jungle": ("minecraft:jungle_log", "minecraft:jungle_leaves", 9, 3),
    "small_jungle": ("minecraft:jungle_log", "minecraft:jungle_leaves", 5, 2),
    "jungle_bush": ("minecraft:jungle_log", "minecraft:oak_leaves", 1, 2),
    "acacia": ("minecraft:acacia_log", "minecraft:acacia_leaves", 5, 2),
    "dark_oak": ("minecraft:dark_oak_log", "minecraft:dark_oak_leaves", 6, 3),
    "cherry": ("minecraft:cherry_log", "minecraft:cherry_leaves", 5, 3),
    "mangrove": ("minecraft:mangrove_log", "minecraft:mangrove_leaves", 6, 3),
    "azalea": ("minecraft:oak_log", "minecraft:azalea_leaves", 4, 2),
    "crimson": ("minecraft:crimson_stem", "minecraft:nether_wart_block", 6, 2),
    "crimson_fungus": ("minecraft:crimson_stem", "minecraft:nether_wart_block", 6, 2),
    "warped": ("minecraft:warped_stem", "minecraft:warped_wart_block", 6, 2),
    "warped_fungus": ("minecraft:warped_stem", "minecraft:warped_wart_block", 6, 2),
    "brown_mushroom": ("minecraft:mushroom_stem", "minecraft:brown_mushroom_block", 5, 2),
    "red_mushroom": ("minecraft:mushroom_stem", "minecraft:red_mushroom_block", 5, 2),
}


def generate_tree(
    session: EditSession,
    pos: BlockVec3,
    tree_type: str = "oak",
    rng: random.Random | None = None,
) -> int:
    """Generate a Bedrock tree of `tree_type` rooted at `pos`."""
    r = rng or random.Random()
    key = tree_type.strip().lower().replace(" ", "_")
    if key not in TREE_TYPES:
        raise ValueError(f"Unknown tree type '{tree_type}'.")
    log_id, leaf_id, base_h, radius = TREE_TYPES[key]
    log_spec = BlockSpec(log_id)
    leaf_spec = BlockSpec(leaf_id)
    height = max(2, base_h + r.randint(-1, 1))
    changed = 0

    for dy in range(height):
        p = BlockVec3(pos.x, pos.y + dy, pos.z)
        if session.set_block(p, log_spec):
            changed += 1

    canopy_start = max(1, height - radius - 1)
    for dy in range(canopy_start, height + 2):
        progress = dy - canopy_start
        layer_r = max(1, radius - (progress // 2))
        for dx in range(-layer_r, layer_r + 1):
            for dz in range(-layer_r, layer_r + 1):
                if dx == 0 and dz == 0 and dy < height:
                    continue
                if abs(dx) == layer_r and abs(dz) == layer_r and (dy == height + 1 or r.random() < 0.45):
                    continue
                lp = BlockVec3(pos.x + dx, pos.y + dy, pos.z + dz)
                if session.get_block(lp).is_air and session.set_block(lp, leaf_spec):
                    changed += 1
    return changed


def op_forest(
    session: EditSession,
    world: WorldAdapter,
    region: Region,
    tree_type: str = "oak",
    density: float = 5.0,
    rng: random.Random | None = None,
) -> int:
    """Plant trees on valid soil surfaces inside `region` at `density` percent."""
    r = rng or random.Random()
    lo, hi = region.min_point, region.max_point
    prob = max(0.0, min(100.0, density)) / 100.0
    soils = {
        "minecraft:grass_block", "minecraft:dirt", "minecraft:podzol", "minecraft:mycelium",
        "minecraft:coarse_dirt", "minecraft:rooted_dirt", "minecraft:moss_block",
        "minecraft:crimson_nylium", "minecraft:warped_nylium", "minecraft:netherrack",
    }
    changed = 0
    for x in range(lo.x, hi.x + 1):
        for z in range(lo.z, hi.z + 1):
            if r.random() >= prob:
                continue
            for y in range(hi.y, lo.y - 1, -1):
                ground = BlockVec3(x, y, z)
                above = BlockVec3(x, y + 1, z)
                if not region.contains(ground):
                    continue
                if world.get_block(ground).block_type in soils and world.get_block(above).is_air:
                    changed += generate_tree(session, above, tree_type, rng=r)
                    break
    return changed


def op_flora(
    session: EditSession,
    world: WorldAdapter,
    region: Region,
    density: float = 10.0,
    rng: random.Random | None = None,
) -> int:
    """Scatter grass, ferns, flowers, or cacti/deadbushes across surfaces in `region`."""
    r = rng or random.Random()
    lo, hi = region.min_point, region.max_point
    prob = max(0.0, min(100.0, density)) / 100.0
    grass_flora = (
        BlockSpec("minecraft:short_grass"),
        BlockSpec("minecraft:short_grass"),
        BlockSpec("minecraft:fern"),
        BlockSpec("minecraft:dandelion"),
        BlockSpec("minecraft:poppy"),
        BlockSpec("minecraft:cornflower"),
    )
    desert_flora = (BlockSpec("minecraft:deadbush"), BlockSpec("minecraft:cactus"))
    changed = 0
    for x in range(lo.x, hi.x + 1):
        for z in range(lo.z, hi.z + 1):
            if r.random() >= prob:
                continue
            for y in range(hi.y, lo.y - 1, -1):
                ground = BlockVec3(x, y, z)
                above = BlockVec3(x, y + 1, z)
                if not region.contains(ground):
                    continue
                gtype = world.get_block(ground).block_type
                if not world.get_block(above).is_air:
                    continue
                if gtype in ("minecraft:grass_block", "minecraft:dirt", "minecraft:moss_block"):
                    if session.set_block(above, r.choice(grass_flora)):
                        changed += 1
                    break
                if gtype in ("minecraft:sand", "minecraft:red_sand"):
                    if session.set_block(above, r.choice(desert_flora)):
                        changed += 1
                    break
    return changed


def op_pumpkins(
    session: EditSession,
    world: WorldAdapter,
    center: BlockVec3,
    size: int = 10,
    rng: random.Random | None = None,
) -> int:
    """Generate a natural pumpkin patch with oak leaves around `center`."""
    r = rng or random.Random()
    pumpkin = BlockSpec("minecraft:pumpkin")
    leaves = BlockSpec("minecraft:oak_leaves")
    changed = 0
    attempts = max(4, size * 2)
    for _ in range(attempts):
        dx = r.randint(-size, size)
        dz = r.randint(-size, size)
        if dx * dx + dz * dz > size * size:
            continue
        x, z = center.x + dx, center.z + dz
        for y in range(center.y + 4, center.y - 5, -1):
            ground = world.get_block(BlockVec3(x, y, z)).block_type
            above = BlockVec3(x, y + 1, z)
            if ground in ("minecraft:grass_block", "minecraft:dirt") and world.get_block(above).is_air:
                spec = pumpkin if r.random() < 0.7 else leaves
                if session.set_block(above, spec):
                    changed += 1
                break
    return changed


def op_fill(
    session: EditSession,
    world: WorldAdapter,
    start: BlockVec3,
    pattern: Pattern,
    radius: float,
    depth: int = 1,
    up: bool = False,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Flood-fill air cavities horizontally and downward (or upward) starting from `start`."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=world, origin=start)
    r_sq = radius * radius
    step_y = 1 if up else -1
    max_d = max(1, depth)
    queue: deque[BlockVec3] = deque([start])
    visited: set[BlockVec3] = {start}
    changed = 0

    while queue:
        cur = queue.popleft()
        if not world.get_block(cur).is_air:
            continue
        if session.set_block(cur, _pat(pattern, cur, r, ctx)):
            changed += 1
        neighbors = [*_DIRS_4H, BlockVec3(0, step_y, 0)]
        for d in neighbors:
            nxt = cur + d
            if nxt in visited:
                continue
            dx = nxt.x - start.x
            dz = nxt.z - start.z
            dy = abs(nxt.y - start.y)
            if dx * dx + dz * dz <= r_sq and dy < max_d and world.min_y <= nxt.y <= world.max_y:
                visited.add(nxt)
                queue.append(nxt)
    return changed


def op_fillr(
    session: EditSession,
    world: WorldAdapter,
    start: BlockVec3,
    pattern: Pattern,
    radius: float,
    depth: int | None = None,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Recursive 3D downward flood-fill through air within `radius` (and optional `depth`)."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=world, origin=start)
    r_sq = radius * radius
    queue: deque[BlockVec3] = deque([start])
    visited: set[BlockVec3] = {start}
    changed = 0
    while queue:
        cur = queue.popleft()
        if not world.get_block(cur).is_air:
            continue
        if session.set_block(cur, _pat(pattern, cur, r, ctx)):
            changed += 1
        for d in (*_DIRS_4H, BlockVec3(0, -1, 0)):
            nxt = cur + d
            if nxt in visited:
                continue
            if nxt.y < world.min_y or nxt.y > world.max_y:
                continue
            dx = nxt.x - start.x
            dz = nxt.z - start.z
            if dx * dx + dz * dz > r_sq:
                continue
            if depth is not None and abs(nxt.y - start.y) >= depth:
                continue
            visited.add(nxt)
            queue.append(nxt)
    return changed


def op_drain(
    session: EditSession,
    world: WorldAdapter,
    center: BlockVec3,
    radius: float,
    waterlogged: bool = False,
) -> int:
    """Drain connected water and lava bodies within spherical `radius`."""
    r_sq = radius * radius
    ir = math.ceil(radius)
    seeds: list[BlockVec3] = []
    for dx in range(-ir, ir + 1):
        for dy in range(-ir, ir + 1):
            for dz in range(-ir, ir + 1):
                if dx * dx + dy * dy + dz * dz <= r_sq:
                    p = BlockVec3(center.x + dx, center.y + dy, center.z + dz)
                    if world.get_block(p).block_type in LIQUID_BLOCKS:
                        seeds.append(p)
                        break
            if seeds:
                break
        if seeds:
            break

    queue: deque[BlockVec3] = deque(seeds)
    visited: set[BlockVec3] = set(seeds)
    changed = 0
    while queue:
        cur = queue.popleft()
        spec = world.get_block(cur)
        if spec.block_type not in LIQUID_BLOCKS and not waterlogged:
            continue
        if spec.block_type in LIQUID_BLOCKS and session.set_block(cur, AIR_SPEC):
            changed += 1
        for d in _DIRS_6:
            nxt = cur + d
            if nxt in visited:
                continue
            if center.distance_sq(nxt) <= r_sq and world.get_block(nxt).block_type in LIQUID_BLOCKS:
                visited.add(nxt)
                queue.append(nxt)
    return changed


def op_fix_liquid(
    session: EditSession,
    world: WorldAdapter,
    center: BlockVec3,
    radius: float,
    liquid: str = "water",
) -> int:
    """Level connected liquid bodies by filling flowing blocks and air pockets at or below source height."""
    if liquid == "lava":
        matches = {"minecraft:lava", "minecraft:flowing_lava"}
        fill_spec = BlockSpec("minecraft:lava")
    else:
        matches = {"minecraft:water", "minecraft:flowing_water"}
        fill_spec = BlockSpec("minecraft:water")

    r_sq = radius * radius
    ir = math.ceil(radius)
    start_blocks: list[BlockVec3] = []
    for dx in range(-ir, ir + 1):
        for dy in range(-ir, ir + 1):
            for dz in range(-ir, ir + 1):
                p = BlockVec3(center.x + dx, center.y + dy, center.z + dz)
                if dx * dx + dy * dy + dz * dz <= r_sq and world.get_block(p).block_type in matches:
                    start_blocks.append(p)

    if not start_blocks:
        return 0
    top_y = max(p.y for p in start_blocks)
    queue: deque[BlockVec3] = deque(start_blocks)
    visited: set[BlockVec3] = set(start_blocks)
    changed = 0
    while queue:
        cur = queue.popleft()
        cur_spec = world.get_block(cur)
        if cur_spec.block_type in matches or (cur_spec.is_air and cur.y <= top_y):
            if cur_spec != fill_spec and session.set_block(cur, fill_spec):
                changed += 1
            for d in (*_DIRS_4H, BlockVec3(0, -1, 0)):
                nxt = cur + d
                if nxt in visited or nxt.y > top_y or nxt.y < world.min_y:
                    continue
                if center.distance_sq(nxt) <= r_sq:
                    nxt_spec = world.get_block(nxt)
                    if nxt_spec.block_type in matches or nxt_spec.is_air:
                        visited.add(nxt)
                        queue.append(nxt)
    return changed


def op_remove_above(session: EditSession, world: WorldAdapter, center: BlockVec3, size: int, height: int) -> int:
    changed = 0
    top_y = min(world.max_y, center.y + max(0, height - 1))
    for dx in range(-size, size + 1):
        for dz in range(-size, size + 1):
            for y in range(center.y, top_y + 1):
                p = BlockVec3(center.x + dx, y, center.z + dz)
                if not world.get_block(p).is_air and session.set_block(p, AIR_SPEC):
                    changed += 1
    return changed


def op_remove_below(session: EditSession, world: WorldAdapter, center: BlockVec3, size: int, height: int) -> int:
    changed = 0
    bot_y = max(world.min_y, center.y - max(0, height - 1))
    for dx in range(-size, size + 1):
        for dz in range(-size, size + 1):
            for y in range(center.y, bot_y - 1, -1):
                p = BlockVec3(center.x + dx, y, center.z + dz)
                if not world.get_block(p).is_air and session.set_block(p, AIR_SPEC):
                    changed += 1
    return changed


def op_remove_near(session: EditSession, world: WorldAdapter, center: BlockVec3, mask: Mask, size: int) -> int:
    changed = 0
    for dx in range(-size, size + 1):
        for dy in range(-size, size + 1):
            for dz in range(-size, size + 1):
                p = BlockVec3(center.x + dx, center.y + dy, center.z + dz)
                if mask.test(world, p) and session.set_block(p, AIR_SPEC):
                    changed += 1
    return changed


def op_replace_near(
    session: EditSession,
    world: WorldAdapter,
    center: BlockVec3,
    from_mask: Mask | None,
    to_pattern: Pattern,
    size: int,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=world, origin=center)
    changed = 0
    for dx in range(-size, size + 1):
        for dy in range(-size, size + 1):
            for dz in range(-size, size + 1):
                p = BlockVec3(center.x + dx, center.y + dy, center.z + dz)
                if from_mask is None:
                    if world.get_block(p).is_air:
                        continue
                elif not from_mask.test(world, p):
                    continue
                if session.set_block(p, _pat(to_pattern, p, r, ctx)):
                    changed += 1
    return changed


def op_snow(session: EditSession, world: WorldAdapter, center: BlockVec3, radius: float, stack: bool = False) -> int:
    ir = math.ceil(radius)
    r_sq = radius * radius
    changed = 0
    ice = BlockSpec("minecraft:ice")
    for dx in range(-ir, ir + 1):
        for dz in range(-ir, ir + 1):
            if dx * dx + dz * dz > r_sq:
                continue
            x, z = center.x + dx, center.z + dz
            for y in range(min(world.max_y, center.y + ir), max(world.min_y, center.y - ir) - 1, -1):
                p = BlockVec3(x, y, z)
                spec = world.get_block(p)
                if spec.is_air:
                    continue
                if spec.block_type in WATER_BLOCKS:
                    if session.set_block(p, ice):
                        changed += 1
                    break
                if spec.block_type == "minecraft:snow_layer" and stack:
                    h = int(spec.states_dict.get("height", 0))
                    nxt_spec = BlockSpec("minecraft:snow") if h >= 7 else BlockSpec("minecraft:snow_layer", (("height", h + 1),))
                    if session.set_block(p, nxt_spec):
                        changed += 1
                    break
                if spec.is_solid:
                    above = BlockVec3(x, y + 1, z)
                    if world.get_block(above).is_air and session.set_block(above, BlockSpec("minecraft:snow_layer", (("height", 0),))):
                        changed += 1
                    break
    return changed


def op_thaw(session: EditSession, world: WorldAdapter, center: BlockVec3, radius: float) -> int:
    ir = math.ceil(radius)
    r_sq = radius * radius
    changed = 0
    water = BlockSpec("minecraft:water")
    for dx in range(-ir, ir + 1):
        for dy in range(-ir, ir + 1):
            for dz in range(-ir, ir + 1):
                if dx * dx + dy * dy + dz * dz > r_sq:
                    continue
                p = BlockVec3(center.x + dx, center.y + dy, center.z + dz)
                btype = world.get_block(p).block_type
                if btype in ("minecraft:snow_layer", "minecraft:snow"):
                    if session.set_block(p, AIR_SPEC):
                        changed += 1
                elif btype == "minecraft:ice" and session.set_block(p, water):
                    changed += 1
    return changed


def op_green(session: EditSession, world: WorldAdapter, center: BlockVec3, radius: float, only_grass: bool = False) -> int:
    ir = math.ceil(radius)
    r_sq = radius * radius
    changed = 0
    grass = BlockSpec("minecraft:grass_block")
    targets = {"minecraft:dirt"} if only_grass else {"minecraft:dirt", "minecraft:coarse_dirt", "minecraft:rooted_dirt"}
    for dx in range(-ir, ir + 1):
        for dy in range(-ir, ir + 1):
            for dz in range(-ir, ir + 1):
                if dx * dx + dy * dy + dz * dz > r_sq:
                    continue
                p = BlockVec3(center.x + dx, center.y + dy, center.z + dz)
                if (
                    world.get_block(p).block_type in targets
                    and world.get_block(p + BlockVec3(0, 1, 0)).is_air
                    and session.set_block(p, grass)
                ):
                    changed += 1
    return changed


def op_extinguish(session: EditSession, world: WorldAdapter, center: BlockVec3, radius: float) -> int:
    ir = math.ceil(radius)
    r_sq = radius * radius
    changed = 0
    for dx in range(-ir, ir + 1):
        for dy in range(-ir, ir + 1):
            for dz in range(-ir, ir + 1):
                if dx * dx + dy * dy + dz * dz > r_sq:
                    continue
                p = BlockVec3(center.x + dx, center.y + dy, center.z + dz)
                if world.get_block(p).block_type in ("minecraft:fire", "minecraft:soul_fire") and session.set_block(
                    p, AIR_SPEC
                ):
                    changed += 1
    return changed


def op_morph(
    session: EditSession,
    world: WorldAdapter,
    center: BlockVec3,
    radius: float,
    erode_faces: int = 2,
    erode_iters: int = 1,
    fill_faces: int = 5,
    fill_iters: int = 1,
) -> int:
    """Cellular automata erode + dilate sculpt operation."""
    ir = math.ceil(radius)
    r_sq = radius * radius
    bounds = [
        BlockVec3(center.x + dx, center.y + dy, center.z + dz)
        for dx in range(-ir, ir + 1)
        for dy in range(-ir, ir + 1)
        for dz in range(-ir, ir + 1)
        if dx * dx + dy * dy + dz * dz <= r_sq and world.min_y <= center.y + dy <= world.max_y
    ]
    state: dict[BlockVec3, BlockSpec] = {p: world.get_block(p) for p in bounds}

    for _ in range(max(0, erode_iters)):
        nxt = dict(state)
        for p in bounds:
            if state[p].is_air:
                continue
            air_neighbors = sum(
                1 for d in _DIRS_6 if (state[p + d].is_air if (p + d) in state else world.get_block(p + d).is_air)
            )
            if air_neighbors >= erode_faces:
                nxt[p] = AIR_SPEC
        state = nxt

    for _ in range(max(0, fill_iters)):
        nxt = dict(state)
        for p in bounds:
            if not state[p].is_air:
                continue
            solid_specs = [
                (state[p + d] if (p + d) in state else world.get_block(p + d))
                for d in _DIRS_6
            ]
            non_air = [s for s in solid_specs if not s.is_air]
            if len(non_air) >= fill_faces:
                nxt[p] = Counter(non_air).most_common(1)[0][0]
        state = nxt

    changed = 0
    for p, spec in state.items():
        if session.set_block(p, spec):
            changed += 1
    return changed


def op_gravity(session: EditSession, world: WorldAdapter, region: Region, hard: bool = False) -> int:
    """Apply gravity inside `region`: drop loose blocks (or all non-air when `hard=True`)."""
    lo, hi = region.min_point, region.max_point
    changed = 0
    for x in range(lo.x, hi.x + 1):
        for z in range(lo.z, hi.z + 1):
            floor_y = lo.y
            for y in range(lo.y, hi.y + 1):
                p = BlockVec3(x, y, z)
                if not region.contains(p):
                    continue
                spec = session.get_block(p)
                if spec.is_air:
                    continue
                falls = hard or spec.block_type in GRAVITY_BLOCKS
                if not falls:
                    floor_y = y + 1
                    continue
                if y > floor_y:
                    # Drop down while leaving floor_y updated
                    session.set_block(p, AIR_SPEC)
                    if session.set_block(BlockVec3(x, floor_y, z), spec):
                        changed += 1
                    changed += 1
                floor_y += 1
    return changed


def op_splatter(
    session: EditSession,
    world: WorldAdapter,
    center: BlockVec3,
    pattern: Pattern,
    radius: float,
    attempts: int = 20,
    rng: random.Random | None = None,
    pat_ctx: PatternContext | None = None,
) -> int:
    """Place irregular organic scatter splatters around `center` within `radius`."""
    r = rng or random.Random()
    ctx = pat_ctx or PatternContext(world=world, origin=center)
    ir = max(1, math.ceil(radius))
    changed = 0
    for _ in range(max(1, attempts)):
        dx = r.randint(-ir, ir)
        dy = r.randint(-ir, ir)
        dz = r.randint(-ir, ir)
        if dx * dx + dy * dy + dz * dz > radius * radius:
            continue
        blob_r = max(0, int(radius * r.uniform(0.15, 0.45)))
        seed = BlockVec3(center.x + dx, center.y + dy, center.z + dz)
        for bx in range(-blob_r, blob_r + 1):
            for by in range(-blob_r, blob_r + 1):
                for bz in range(-blob_r, blob_r + 1):
                    if bx * bx + by * by + bz * bz <= (blob_r + 0.5) ** 2 and r.random() < 0.75:
                        p = BlockVec3(seed.x + bx, seed.y + by, seed.z + bz)
                        if session.set_block(p, _pat(pattern, p, r, ctx)):
                            changed += 1
    return changed


def op_raise_lower(
    session: EditSession,
    world: WorldAdapter,
    center: BlockVec3,
    radius: float,
    delta_y: int,
) -> int:
    """Raise (`delta_y > 0`) or lower (`delta_y < 0`) terrain columns within horizontal `radius`."""
    if delta_y == 0:
        return 0
    ir = math.ceil(radius)
    r_sq = radius * radius
    changed = 0
    min_y = max(world.min_y, center.y - ir - abs(delta_y))
    max_y = min(world.max_y, center.y + ir + abs(delta_y))

    for dx in range(-ir, ir + 1):
        for dz in range(-ir, ir + 1):
            d2 = dx * dx + dz * dz
            if d2 > r_sq:
                continue
            falloff = 1.0 - (math.sqrt(d2) / max(1.0, radius))
            shift = round(delta_y * max(0.25, falloff))
            if shift == 0:
                continue
            x, z = center.x + dx, center.z + dz
            col = {y: world.get_block(BlockVec3(x, y, z)) for y in range(min_y, max_y + 1)}
            for y in range(min_y, max_y + 1):
                src_y = y - shift
                spec = col.get(src_y, AIR_SPEC)
                if src_y < min_y and shift > 0:
                    spec = col.get(min_y, BlockSpec("minecraft:stone"))
                if session.set_block(BlockVec3(x, y, z), spec):
                    changed += 1
    return changed


def op_biome_set(world: WorldAdapter, region: Region, biome_name: str) -> int:
    changed = 0
    target = biome_name.strip().lower()
    for pos in region.iter_positions():
        if world.set_biome(pos, target):
            changed += 1
    return changed


def op_distr(world: WorldAdapter, region: Region, include_air: bool = True) -> tuple[int, list[tuple[str, int, float]]]:
    """Compute block distribution histogram across `region`."""
    counts: Counter[str] = Counter()
    total = 0
    for pos in region.iter_positions():
        spec = world.get_block(pos)
        if not include_air and spec.is_air:
            continue
        counts[spec.to_string()] += 1
        total += 1
    rows = [
        (name, cnt, (cnt / total * 100.0) if total else 0.0)
        for name, cnt in counts.most_common()
    ]
    return total, rows


def op_count(world: WorldAdapter, region: Region, mask: Mask, mask_ctx: MaskContext | None = None) -> int:
    return sum(1 for pos in region.iter_positions() if mask.test(world, pos, mask_ctx))


def op_butcher(
    world: WorldAdapter,
    center: BlockVec3,
    radius: float = -1.0,
    flags: set[str] | None = None,
) -> int:
    """Kill entities within `radius` (-1 = all loaded) filtered by WorldEdit butcher flags (-p/-a/-n/-g/-b/-f)."""
    active = flags or set()
    kill_all = "f" in active
    kill_pets = kill_all or "p" in active
    kill_animals = kill_all or "a" in active
    kill_npcs = kill_all or "n" in active
    kill_golems = kill_all or "g" in active
    kill_ambient = kill_all or "b" in active

    removed = 0
    for ent in world.get_entities():
        if ent.entity_type == "minecraft:player" or ent.entity_type in NON_LIVING_ENTITIES:
            continue
        if radius >= 0 and ent.pos.distance(center) > radius:
            continue
        et = ent.entity_type
        if et in PET_MOBS and not kill_pets:
            continue
        if et in ANIMAL_MOBS and not kill_animals:
            continue
        if et in NPC_MOBS and not kill_npcs:
            continue
        if et in GOLEM_MOBS and not kill_golems:
            continue
        if et in AMBIENT_MOBS and not kill_ambient:
            continue
        if world.remove_entity(ent):
            removed += 1
    return removed


def op_remove_entities(
    world: WorldAdapter,
    center: BlockVec3,
    entity_type: str,
    radius: float = -1.0,
) -> int:
    target = entity_type.strip().lower()
    if ":" not in target and target not in ("all", "items", "arrows", "boats", "minecarts", "tnt", "xp"):
        target = f"minecraft:{target}"
    alias_map = {
        "items": {"minecraft:item"},
        "arrows": {"minecraft:arrow"},
        "boats": {"minecraft:boat", "minecraft:chest_boat"},
        "minecarts": {"minecraft:minecart", "minecraft:chest_minecart", "minecraft:tnt_minecart", "minecraft:hopper_minecart"},
        "tnt": {"minecraft:tnt"},
        "xp": {"minecraft:xp_orb"},
    }
    allowed = alias_map.get(target, {target})
    removed = 0
    for ent in world.get_entities():
        if ent.entity_type == "minecraft:player":
            continue
        if radius >= 0 and ent.pos.distance(center) > radius:
            continue
        if (target == "all" or ent.entity_type in allowed) and world.remove_entity(ent):
            removed += 1
    return removed


def compute_shift_vector(
    direction_token: str | None,
    count: int,
    yaw: float = 0.0,
    pitch: float = 0.0,
) -> BlockVec3:
    return resolve_direction(direction_token, yaw=yaw, pitch=pitch) * count
