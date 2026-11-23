"""3D DDA voxel raycasting and WorldEdit navigation solvers (unstuck, ascend, descend, ceil, thru, jumpto, up)."""

from __future__ import annotations

import math

from ..core.types import AIR_SPEC, BlockVec3
from .adapter import WorldAdapter
from .edit_session import EditSession


def yaw_pitch_to_vector(yaw: float, pitch: float) -> tuple[float, float, float]:
    """Convert Minecraft Bedrock yaw/pitch degrees to a normalized look unit vector."""
    yaw_rad = math.radians(yaw)
    pitch_rad = math.radians(pitch)
    cos_p = math.cos(pitch_rad)
    vx = -math.sin(yaw_rad) * cos_p
    vy = -math.sin(pitch_rad)
    vz = math.cos(yaw_rad) * cos_p
    return (vx, vy, vz)


def raycast_block(
    world: WorldAdapter,
    eye_x: float,
    eye_y: float,
    eye_z: float,
    yaw: float,
    pitch: float,
    max_dist: float = 128.0,
    stop_before: bool = False,
) -> BlockVec3 | None:
    """Cast a ray via 3D Amanatides-Woo DDA until hitting the first non-air block."""
    dx, dy, dz = yaw_pitch_to_vector(yaw, pitch)
    norm = math.sqrt(dx * dx + dy * dy + dz * dz)
    if norm < 1e-9:
        return None
    dx, dy, dz = dx / norm, dy / norm, dz / norm

    x = math.floor(eye_x)
    y = math.floor(eye_y)
    z = math.floor(eye_z)

    step_x = 1 if dx > 0 else (-1 if dx < 0 else 0)
    step_y = 1 if dy > 0 else (-1 if dy < 0 else 0)
    step_z = 1 if dz > 0 else (-1 if dz < 0 else 0)

    t_delta_x = abs(1.0 / dx) if abs(dx) > 1e-9 else float("inf")
    t_delta_y = abs(1.0 / dy) if abs(dy) > 1e-9 else float("inf")
    t_delta_z = abs(1.0 / dz) if abs(dz) > 1e-9 else float("inf")

    t_max_x = ((x + 1 - eye_x) / dx) if dx > 0 else (((eye_x - x) / -dx) if dx < 0 else float("inf"))
    t_max_y = ((y + 1 - eye_y) / dy) if dy > 0 else (((eye_y - y) / -dy) if dy < 0 else float("inf"))
    t_max_z = ((z + 1 - eye_z) / dz) if dz > 0 else (((eye_z - z) / -dz) if dz < 0 else float("inf"))

    prev: BlockVec3 | None = None
    t_cur = 0.0
    while t_cur <= max_dist:
        cur = BlockVec3(x, y, z)
        if world.min_y <= cur.y <= world.max_y and not world.get_block(cur).is_air:
            return prev if (stop_before and prev is not None) else cur
        prev = cur
        if t_max_x < t_max_y:
            if t_max_x < t_max_z:
                x += step_x
                t_cur = t_max_x
                t_max_x += t_delta_x
            else:
                z += step_z
                t_cur = t_max_z
                t_max_z += t_delta_z
        else:
            if t_max_y < t_max_z:
                y += step_y
                t_cur = t_max_y
                t_max_y += t_delta_y
            else:
                z += step_z
                t_cur = t_max_z
                t_max_z += t_delta_z
    return None


def _is_standable_space(world: WorldAdapter, feet: BlockVec3) -> bool:
    head = feet + BlockVec3(0, 1, 0)
    if feet.y < world.min_y or head.y > world.max_y:
        return False
    return not world.get_block(feet).is_solid and not world.get_block(head).is_solid


def find_unstuck_pos(world: WorldAdapter, pos: BlockVec3) -> BlockVec3:
    """Move upward from `pos` until two free non-solid blocks exist."""
    for y in range(max(world.min_y, pos.y), world.max_y):
        cand = BlockVec3(pos.x, y, pos.z)
        if _is_standable_space(world, cand):
            return cand
    return BlockVec3(pos.x, world.max_y + 1, pos.z)


def find_ascend_pos(world: WorldAdapter, pos: BlockVec3, levels: int = 1) -> BlockVec3 | None:
    """Ascend upward past `levels` solid ceiling layers to the next free standing space."""
    if levels <= 0:
        return pos
    y = pos.y + 1
    found_levels = 0
    in_solid = False
    while y < world.max_y:
        cand = BlockVec3(pos.x, y, pos.z)
        solid = world.get_block(cand).is_solid
        if solid:
            in_solid = True
        elif in_solid and _is_standable_space(world, cand):
            found_levels += 1
            in_solid = False
            if found_levels >= levels:
                return cand
        y += 1
    return None


def find_descend_pos(world: WorldAdapter, pos: BlockVec3, levels: int = 1) -> BlockVec3 | None:
    """Descend downward past `levels` solid floors to a safe standing floor."""
    if levels <= 0:
        return pos
    y = pos.y - 1
    found_levels = 0
    while y > world.min_y + 2:
        cand = BlockVec3(pos.x, y, pos.z)
        below = BlockVec3(pos.x, y - 1, pos.z)
        if world.get_block(below).is_solid and _is_standable_space(world, cand):
            found_levels += 1
            if found_levels >= levels:
                return cand
        y -= 1
    return None


def find_ceiling_pos(world: WorldAdapter, pos: BlockVec3, clearance: int = 0) -> BlockVec3 | None:
    """Move straight up below the next ceiling block with `clearance` free gap above head."""
    for y in range(pos.y + 2, world.max_y + 1):
        ceiling_cand = BlockVec3(pos.x, y, pos.z)
        if world.get_block(ceiling_cand).is_solid:
            feet_y = max(pos.y, y - 2 - max(0, clearance))
            return BlockVec3(pos.x, feet_y, pos.z)
    return None


def find_thru_pos(
    world: WorldAdapter,
    eye_x: float,
    eye_y: float,
    eye_z: float,
    yaw: float,
    pitch: float,
    max_dist: float = 64.0,
) -> BlockVec3 | None:
    """Trace along look vector through a wall until the first safe 2-block gap on the other side."""
    dx, dy, dz = yaw_pitch_to_vector(yaw, pitch)
    entered_wall = False
    t = 0.5
    while t <= max_dist:
        cand = BlockVec3(
            math.floor(eye_x + dx * t),
            math.floor(eye_y + dy * t) - 1,
            math.floor(eye_z + dz * t),
        )
        feet_solid = world.get_block(cand).is_solid or world.get_block(cand + BlockVec3(0, 1, 0)).is_solid
        if feet_solid:
            entered_wall = True
        elif entered_wall and _is_standable_space(world, cand):
            return cand
        t += 0.5
    return None


def find_jumpto_pos(
    world: WorldAdapter,
    eye_x: float,
    eye_y: float,
    eye_z: float,
    yaw: float,
    pitch: float,
    max_dist: float = 128.0,
) -> BlockVec3 | None:
    """Find safe standing block on top of the targeted block."""
    hit = raycast_block(world, eye_x, eye_y, eye_z, yaw, pitch, max_dist=max_dist, stop_before=False)
    if hit is None:
        return None
    for offset in range(1, 5):
        cand = BlockVec3(hit.x, hit.y + offset, hit.z)
        if _is_standable_space(world, cand):
            return cand
    return BlockVec3(hit.x, hit.y + 1, hit.z)


def find_up_pos(
    world: WorldAdapter,
    session: EditSession,
    pos: BlockVec3,
    distance: int,
    place_glass: bool = True,
) -> BlockVec3:
    """Teleport `distance` blocks upward and optionally place a glass block beneath feet."""
    target_y = max(world.min_y + 1, min(world.max_y, pos.y + distance))
    dest = BlockVec3(pos.x, target_y, pos.z)
    if place_glass:
        from ..core.types import BlockSpec

        support = BlockVec3(dest.x, dest.y - 1, dest.z)
        if world.get_block(support).is_air:
            session.set_block(support, BlockSpec("minecraft:glass"))
    # Clear feet/head if needed
    for dy in (0, 1):
        p = dest + BlockVec3(0, dy, 0)
        if world.get_block(p).is_solid:
            session.set_block(p, AIR_SPEC)
    return dest
