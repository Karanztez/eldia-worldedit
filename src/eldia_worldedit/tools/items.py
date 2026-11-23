"""WorldEdit bound item tools and Super Pickaxe executors."""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ..core.masks import Mask, MaskContext, parse_mask
from ..core.patterns import PatternContext, parse_pattern
from ..core.types import AIR_SPEC, BLOCK_CATEGORIES, BlockSpec, BlockVec3
from ..world.adapter import WorldAdapter
from ..world.edit_session import EditSession
from ..world.generators import generate_tree

TOOL_TYPES: tuple[str, ...] = (
    "selwand",
    "navwand",
    "info",
    "tree",
    "stacker",
    "repl",
    "cycler",
    "floodfill",
    "deltree",
    "farwand",
    "lrbuild",
)


@dataclass
class ToolConfig:
    """Tool binding attached to a specific item type in a player's ToolManager."""

    kind: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SuperPickaxeConfig:
    """Per-player Super Pickaxe toggle and mode state."""

    enabled: bool = False
    mode: str = "single"
    radius: int = 1
    drop_items: bool = True


_DIRS_6 = (
    BlockVec3(1, 0, 0), BlockVec3(-1, 0, 0),
    BlockVec3(0, 1, 0), BlockVec3(0, -1, 0),
    BlockVec3(0, 0, 1), BlockVec3(0, 0, -1),
)
_DIRS_26 = tuple(
    BlockVec3(dx, dy, dz)
    for dx in (-1, 0, 1)
    for dy in (-1, 0, 1)
    for dz in (-1, 0, 1)
    if (dx, dy, dz) != (0, 0, 0)
)
_LOG_TYPES = BLOCK_CATEGORIES["logs"]
_LEAF_TYPES = BLOCK_CATEGORIES["leaves"]
_CARDINAL_CYCLE = ("north", "east", "south", "west")


def _cycle_block_spec(spec: BlockSpec, target_prop_idx: int = 0) -> tuple[BlockSpec, str]:
    """Advance one state property on `spec` to the next logical Bedrock value."""
    if not spec.states:
        if "wool" in spec.block_type or "concrete" in spec.block_type or "terracotta" in spec.block_type:
            colors = (
                "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
                "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black",
            )
            for idx, col in enumerate(colors):
                prefix = f"minecraft:{col}_"
                if spec.block_type.startswith(prefix):
                    nxt_col = colors[(idx + 1) % len(colors)]
                    nxt_type = f"minecraft:{nxt_col}_{spec.block_type[len(prefix):]}"
                    return BlockSpec(nxt_type), f"color={nxt_col}"
        return spec, f"{spec.block_type} has no cyclable block states."

    items = list(spec.states)
    idx = target_prop_idx % len(items)
    key, val = items[idx]
    if isinstance(val, bool):
        nval: bool | int | str = not val
    elif isinstance(val, int):
        if key == "facing_direction":
            nval = (val + 1) % 6
        elif key == "weirdo_direction" or key == "direction":
            nval = (val + 1) % 4
        elif key == "height":
            nval = (val + 1) % 8
        else:
            nval = (val + 1) % 16
    elif key == "minecraft:cardinal_direction" and val in _CARDINAL_CYCLE:
        nval = _CARDINAL_CYCLE[(_CARDINAL_CYCLE.index(val) + 1) % 4]
    elif key == "pillar_axis":
        axes = ("y", "x", "z")
        nval = axes[(axes.index(val) + 1) % 3] if val in axes else "y"
    elif key == "minecraft:vertical_half":
        nval = "top" if val == "bottom" else "bottom"
    else:
        nval = val
    items[idx] = (key, nval)
    return BlockSpec(spec.block_type, tuple(sorted(items))), f"{key}={nval}"


def execute_tool(
    tool: ToolConfig,
    world: WorldAdapter,
    session: EditSession,
    target: BlockVec3,
    face_normal: BlockVec3 | None = None,
    is_left_click: bool = False,
    hand_block: BlockSpec | None = None,
    rng: random.Random | None = None,
) -> tuple[int, list[str]]:
    """Run a bound WorldEdit tool against `target`."""
    r = rng or random.Random()
    normal = face_normal or BlockVec3(0, 1, 0)
    kind = tool.kind.lower()

    if kind == "info":
        spec = world.get_block(target)
        biome = world.get_biome(target)
        chunk = target.chunk_coords()
        return 0, [
            f"@{target.format_short()} | chunk {chunk} | biome: {biome}",
            f"Block: {spec.to_string()} (solid={spec.is_solid}, liquid={spec.is_liquid})",
        ]

    if kind == "tree":
        tree_type = str(tool.params.get("tree_type", "oak"))
        spawn_at = target + BlockVec3(0, 1, 0)
        cnt = generate_tree(session, spawn_at, tree_type=tree_type, rng=r)
        return cnt, [f"Generated {tree_type} tree ({cnt} blocks)."]

    if kind == "stacker":
        max_range = max(1, int(tool.params.get("max_range", 8)))
        mask_expr = tool.params.get("mask")
        stop_mask: Mask | None = parse_mask(str(mask_expr), MaskContext(origin=target)) if mask_expr else None
        base_spec = world.get_block(target)
        placed = 0
        for step in range(1, max_range + 1):
            nxt = target + (normal * step)
            if nxt.y < world.min_y or nxt.y > world.max_y:
                break
            if stop_mask is not None:
                if not stop_mask.test(world, nxt):
                    break
            elif not world.get_block(nxt).is_air:
                break
            if session.set_block(nxt, base_spec):
                placed += 1
        return placed, [f"Stacked {placed} block(s)."]

    if kind == "repl":
        if is_left_click:
            spec = world.get_block(target)
            tool.params["pattern"] = spec.to_string()
            return 0, [f"Replacer pattern set to {spec.to_string()}."]
        pat_str = str(tool.params.get("pattern", "stone"))
        ctx = PatternContext(world=world, hand_block=hand_block, origin=target)
        pat = parse_pattern(pat_str, ctx)
        changed = 1 if session.set_block(target, pat.apply(target, r, ctx)) else 0
        return changed, [f"Replaced block with {pat_str}."] if changed else []

    if kind == "cycler":
        spec = world.get_block(target)
        if is_left_click:
            if not spec.states:
                return 0, [f"{spec.block_type} has no block state properties."]
            idx = (int(tool.params.get("prop_index", 0)) + 1) % len(spec.states)
            tool.params["prop_index"] = idx
            prop_name = spec.states[idx][0]
            return 0, [f"Selected cycler property: {prop_name}."]
        prop_idx = int(tool.params.get("prop_index", 0))
        new_spec, desc = _cycle_block_spec(spec, prop_idx)
        if new_spec == spec:
            return 0, [desc]
        changed = 1 if session.set_block(target, new_spec) else 0
        return changed, [f"Cycled {desc}."]

    if kind == "floodfill":
        max_range = max(1, int(tool.params.get("range", 10)))
        pat_str = str(tool.params.get("pattern", "stone"))
        ctx = PatternContext(world=world, hand_block=hand_block, origin=target)
        pat = parse_pattern(pat_str, ctx)
        origin_spec = world.get_block(target)
        if origin_spec.is_air:
            return 0, ["Target a non-air block to flood fill."]
        queue: deque[BlockVec3] = deque([target])
        visited: set[BlockVec3] = {target}
        changed = 0
        while queue:
            cur = queue.popleft()
            if session.set_block(cur, pat.apply(cur, r, ctx)):
                changed += 1
            for d in _DIRS_6:
                nxt = cur + d
                if nxt in visited:
                    continue
                if (
                    abs(nxt.x - target.x) <= max_range
                    and abs(nxt.y - target.y) <= max_range
                    and abs(nxt.z - target.z) <= max_range
                    and world.get_block(nxt).block_type == origin_spec.block_type
                ):
                    visited.add(nxt)
                    queue.append(nxt)
        return changed, [f"Flood filled {changed} block(s)."]

    if kind == "deltree":
        origin_spec = world.get_block(target)
        if origin_spec.block_type not in (_LOG_TYPES | _LEAF_TYPES):
            return 0, ["Target a tree log or leaf block."]
        queue = deque([target])
        visited = {target}
        changed = 0
        limit_dist = 32
        while queue:
            cur = queue.popleft()
            if session.set_block(cur, AIR_SPEC):
                changed += 1
            for d in _DIRS_26:
                nxt = cur + d
                if nxt in visited:
                    continue
                if nxt.distance(target) > limit_dist:
                    continue
                if world.get_block(nxt).block_type in (_LOG_TYPES | _LEAF_TYPES):
                    visited.add(nxt)
                    queue.append(nxt)
        return changed, [f"Removed tree ({changed} blocks)."]

    if kind == "lrbuild":
        key = "left_pattern" if is_left_click else "right_pattern"
        pat_str = str(tool.params.get(key, "stone"))
        ctx = PatternContext(world=world, hand_block=hand_block, origin=target)
        pat = parse_pattern(pat_str, ctx)
        place_at = target + normal
        changed = 1 if session.set_block(place_at, pat.apply(place_at, r, ctx)) else 0
        return changed, [f"Built {pat_str} at {place_at.format_short()}."] if changed else []

    return 0, [f"No action defined for tool '{tool.kind}'."]


def execute_super_pickaxe(
    cfg: SuperPickaxeConfig,
    world: WorldAdapter,
    session: EditSession,
    target: BlockVec3,
) -> int:
    """Apply Super Pickaxe break behavior ('single', 'area', or 'recursive') around `target`."""
    if not cfg.enabled:
        return 0
    origin_spec = world.get_block(target)
    if origin_spec.is_air or origin_spec.block_type == "minecraft:bedrock":
        return 0

    mode = cfg.mode.lower()
    radius = max(0, min(5, cfg.radius))

    if mode == "single":
        return 1 if session.set_block(target, AIR_SPEC) else 0

    if mode == "area":
        changed = 0
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    p = BlockVec3(target.x + dx, target.y + dy, target.z + dz)
                    spec = world.get_block(p)
                    if not spec.is_air and spec.block_type != "minecraft:bedrock" and session.set_block(p, AIR_SPEC):
                        changed += 1
        return changed

    if mode in ("recursive", "recur"):
        queue: deque[BlockVec3] = deque([target])
        visited: set[BlockVec3] = {target}
        changed = 0
        while queue:
            cur = queue.popleft()
            if session.set_block(cur, AIR_SPEC):
                changed += 1
            for d in _DIRS_6:
                nxt = cur + d
                if nxt in visited:
                    continue
                if (
                    abs(nxt.x - target.x) <= radius
                    and abs(nxt.y - target.y) <= radius
                    and abs(nxt.z - target.z) <= radius
                    and world.get_block(nxt).block_type == origin_spec.block_type
                ):
                    visited.add(nxt)
                    queue.append(nxt)
        return changed

    return 1 if session.set_block(target, AIR_SPEC) else 0
