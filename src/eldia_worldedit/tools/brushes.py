"""WorldEdit terrain sculpting & painting brushes (22+ brush types + per-brush masks)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from ..clipboard.clipboard import Clipboard, paste_clipboard
from ..core.masks import IntersectionMask, Mask, MaskContext, parse_mask
from ..core.patterns import PatternContext, parse_pattern
from ..core.regions import CuboidRegion
from ..core.types import BlockSpec, BlockVec3
from ..world.adapter import WorldAdapter
from ..world.edit_session import EditSession
from ..world.generators import (
    generate_cone,
    generate_cylinder,
    generate_sphere,
    generate_tree,
    op_biome_set,
    op_butcher,
    op_deform,
    op_extinguish,
    op_flora,
    op_forest,
    op_gravity,
    op_morph,
    op_raise_lower,
    op_set,
    op_smooth,
    op_snow,
    op_snowsmooth,
    op_splatter,
)

BRUSH_TYPES: tuple[str, ...] = (
    "sphere",
    "cylinder",
    "splatter",
    "clipboard",
    "smooth",
    "snowsmooth",
    "extinguish",
    "gravity",
    "butcher",
    "heightmap",
    "deform",
    "set",
    "forest",
    "feature",
    "raise",
    "lower",
    "snow",
    "biome",
    "morph",
    "erode",
    "dilate",
    "cone",
    "apply",
    "paint",
)


@dataclass
class BrushConfig:
    """Mutable per-item brush settings stored on a player's ToolManager."""

    kind: str = "sphere"
    pattern: str = "stone"
    radius: float = 5.0
    height: int = 1
    hollow: bool = False
    mask: str | None = None
    trace_mask: str | None = None
    material_mask: str | None = None
    range_limit: float = 128.0
    iterations: int = 1
    density: float = 10.0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def size(self) -> float:
        return self.radius

    @size.setter
    def size(self, val: float) -> None:
        self.radius = max(0.0, float(val))


def _compose_mask(base: Mask | None, extra: Mask | None) -> Mask | None:
    if base is None:
        return extra
    if extra is None:
        return base
    return IntersectionMask([base, extra])


def _apply_heightmap(
    session: EditSession,
    world: WorldAdapter,
    center: BlockVec3,
    radius: float,
    height_scale: int,
    fill_spec: BlockSpec,
) -> int:
    """Apply cosine hill mound heightmap sculpt around `center`."""
    ir = max(1, math.ceil(radius))
    r_sq = radius * radius
    changed = 0
    for dx in range(-ir, ir + 1):
        for dz in range(-ir, ir + 1):
            d2 = dx * dx + dz * dz
            if d2 > r_sq:
                continue
            dist_ratio = math.sqrt(d2) / max(1.0, radius)
            bump = round(height_scale * 0.5 * (1.0 + math.cos(math.pi * dist_ratio)))
            if bump <= 0:
                continue
            x, z = center.x + dx, center.z + dz
            top_y = center.y
            for y in range(min(world.max_y, center.y + ir), max(world.min_y, center.y - ir) - 1, -1):
                if not world.get_block(BlockVec3(x, y, z)).is_air:
                    top_y = y
                    break
            for dy in range(1, bump + 1):
                p = BlockVec3(x, top_y + dy, z)
                if session.set_block(p, fill_spec):
                    changed += 1
    return changed


def execute_brush(
    brush: BrushConfig,
    world: WorldAdapter,
    session: EditSession,
    target: BlockVec3,
    clipboard: Clipboard | None = None,
    hand_block: BlockSpec | None = None,
    rng: random.Random | None = None,
) -> tuple[int, str]:
    """Execute `brush` centered at `target`, recording changes into `session`."""
    r = rng or random.Random()
    kind = brush.kind.lower()
    old_gmask = session.gmask
    old_ctx = session.mask_context
    ir = max(1, math.ceil(brush.radius))
    bounds = CuboidRegion(
        BlockVec3(target.x - ir, max(world.min_y, target.y - ir), target.z - ir),
        BlockVec3(target.x + ir, min(world.max_y, target.y + ir), target.z + ir),
    )

    try:
        mctx = old_ctx or MaskContext(region=bounds, origin=target, hand_block=hand_block, rng=r)
        if brush.mask:
            parsed_brush_mask = parse_mask(brush.mask, mctx)
            session.gmask = _compose_mask(old_gmask, parsed_brush_mask)
            session.mask_context = mctx

        pat_ctx = PatternContext(world=world, clipboard=clipboard, hand_block=hand_block, origin=target, region=bounds)

        if kind == "sphere":
            pat = parse_pattern(brush.pattern, pat_ctx)
            cnt = generate_sphere(session, target, pat, brush.radius, filled=not brush.hollow, rng=r, pat_ctx=pat_ctx)
            return cnt, f"Sphere brush applied ({cnt} blocks)."

        if kind in ("cylinder", "cyl"):
            pat = parse_pattern(brush.pattern, pat_ctx)
            cnt = generate_cylinder(
                session, target, pat, brush.radius, brush.radius, brush.height, filled=not brush.hollow, rng=r, pat_ctx=pat_ctx
            )
            return cnt, f"Cylinder brush applied ({cnt} blocks)."

        if kind == "cone":
            pat = parse_pattern(brush.pattern, pat_ctx)
            cnt = generate_cone(
                session, target, pat, brush.radius, brush.radius, max(2, brush.height), filled=not brush.hollow, rng=r, pat_ctx=pat_ctx
            )
            return cnt, f"Cone brush applied ({cnt} blocks)."

        if kind == "splatter":
            pat = parse_pattern(brush.pattern, pat_ctx)
            attempts = int(brush.extra.get("attempts", max(10, int(brush.radius * 4))))
            cnt = op_splatter(session, world, target, pat, brush.radius, attempts=attempts, rng=r, pat_ctx=pat_ctx)
            return cnt, f"Splatter brush applied ({cnt} blocks)."

        if kind == "clipboard":
            if clipboard is None:
                raise ValueError("Clipboard is empty for clipboard brush.")
            ignore_air = bool(brush.extra.get("ignore_air", False))
            use_origin = bool(brush.extra.get("use_origin", False))
            if use_origin:
                paste_at = target
            else:
                lo, hi = clipboard.min_point, clipboard.max_point
                center = BlockVec3((lo.x + hi.x) // 2, lo.y, (lo.z + hi.z) // 2)
                paste_at = target + (clipboard.origin - center)
            cnt, _, _ = paste_clipboard(clipboard, session, paste_at, ignore_air=ignore_air)
            return cnt, f"Clipboard brush pasted {cnt} blocks."

        if kind == "smooth":
            cnt = op_smooth(session, bounds, iterations=brush.iterations, mask=session.gmask, mask_ctx=mctx)
            return cnt, f"Smooth brush applied ({cnt} blocks)."

        if kind == "snowsmooth":
            snow_blocks = int(brush.extra.get("snow_blocks", 1))
            cnt = op_snowsmooth(session, bounds, iterations=brush.iterations, snow_blocks=snow_blocks)
            return cnt, f"Snow smooth brush applied ({cnt} blocks)."

        if kind in ("extinguish", "ex"):
            cnt = op_extinguish(session, world, target, brush.radius)
            return cnt, f"Extinguished {cnt} fire block(s)."

        if kind in ("gravity", "grav"):
            cnt = op_gravity(session, world, bounds, hard=bool(brush.extra.get("hard", False)))
            return cnt, f"Gravity brush settled {cnt} block(s)."

        if kind == "butcher":
            flags = set(brush.extra.get("flags", set()))
            cnt = op_butcher(world, target, radius=brush.radius, flags=flags)
            return cnt, f"Butcher brush removed {cnt} entity/entities."

        if kind in ("height", "heightmap"):
            pat = parse_pattern(brush.pattern, pat_ctx)
            spec = pat.apply(target, r, pat_ctx)
            cnt = _apply_heightmap(session, world, target, brush.radius, max(1, brush.height), spec)
            return cnt, f"Heightmap brush sculpted {cnt} block(s)."

        if kind == "deform":
            expr = str(brush.extra.get("expr", "y+=0.2*sin(x*3)"))
            cnt = op_deform(
                session, world, bounds, expr,
                raw_coords=bool(brush.extra.get("raw_coords", False)),
                offset_mode=bool(brush.extra.get("offset_mode", False)),
                origin=target,
            )
            return cnt, f"Deform brush updated {cnt} block(s)."

        if kind == "set":
            pat = parse_pattern(brush.pattern, pat_ctx)
            cnt = op_set(session, bounds, pat, rng=r, pat_ctx=pat_ctx)
            return cnt, f"Set brush updated {cnt} block(s)."

        if kind == "forest":
            tree_type = str(brush.extra.get("tree_type", "oak"))
            cnt = op_forest(session, world, bounds, tree_type=tree_type, density=brush.density, rng=r)
            return cnt, f"Forest brush grew {cnt} tree block(s)."

        if kind == "feature":
            tree_type = str(brush.extra.get("tree_type", "oak"))
            cnt = generate_tree(session, target + BlockVec3(0, 1, 0), tree_type=tree_type, rng=r)
            return cnt, f"Placed {tree_type} feature ({cnt} blocks)."

        if kind == "raise":
            cnt = op_raise_lower(session, world, target, brush.radius, max(1, abs(brush.height)))
            return cnt, f"Raised terrain ({cnt} blocks updated)."

        if kind == "lower":
            cnt = op_raise_lower(session, world, target, brush.radius, -max(1, abs(brush.height)))
            return cnt, f"Lowered terrain ({cnt} blocks updated)."

        if kind == "snow":
            cnt = op_snow(session, world, target, brush.radius, stack=bool(brush.extra.get("stack", False)))
            return cnt, f"Applied snow to {cnt} block(s)."

        if kind == "biome":
            biome_name = str(brush.extra.get("biome", "plains"))
            cnt = op_biome_set(world, bounds, biome_name)
            return cnt, f"Set biome '{biome_name}' across {cnt} positions."

        if kind == "morph":
            cnt = op_morph(
                session, world, target, brush.radius,
                erode_faces=int(brush.extra.get("erode_faces", 2)),
                erode_iters=int(brush.extra.get("erode_iters", 1)),
                fill_faces=int(brush.extra.get("fill_faces", 5)),
                fill_iters=int(brush.extra.get("fill_iters", 1)),
            )
            return cnt, f"Morph brush sculpted {cnt} block(s)."

        if kind == "erode":
            cnt = op_morph(session, world, target, brush.radius, erode_faces=2, erode_iters=brush.iterations, fill_faces=7, fill_iters=0)
            return cnt, f"Erode brush removed/sculpted {cnt} block(s)."

        if kind == "dilate":
            cnt = op_morph(session, world, target, brush.radius, erode_faces=7, erode_iters=0, fill_faces=2, fill_iters=brush.iterations)
            return cnt, f"Dilate brush filled {cnt} block(s)."

        if kind == "apply":
            pat = parse_pattern(brush.pattern, pat_ctx)
            shape = str(brush.extra.get("shape", "sphere")).lower()
            if shape in ("cyl", "cylinder"):
                cnt = generate_cylinder(session, target, pat, brush.radius, brush.radius, brush.height, filled=True, rng=r, pat_ctx=pat_ctx)
            elif shape in ("cube", "cuboid"):
                cnt = op_set(session, bounds, pat, rng=r, pat_ctx=pat_ctx)
            else:
                cnt = generate_sphere(session, target, pat, brush.radius, filled=True, rng=r, pat_ctx=pat_ctx)
            return cnt, f"Apply brush ({shape}) updated {cnt} block(s)."

        if kind == "paint":
            mode = str(brush.extra.get("paint_mode", "flora")).lower()
            if mode == "forest":
                tree_type = str(brush.extra.get("tree_type", "oak"))
                cnt = op_forest(session, world, bounds, tree_type=tree_type, density=brush.density, rng=r)
            else:
                cnt = op_flora(session, world, bounds, density=brush.density, rng=r)
            return cnt, f"Paint brush scattered {cnt} block(s)."

        raise ValueError(f"Unsupported brush type '{brush.kind}'.")
    finally:
        session.gmask = old_gmask
        session.mask_context = old_ctx
