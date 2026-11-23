"""Procedural shape & terrain generation commands (//cyl, //sphere, //pyramid, //cone, //g, etc.)."""

from __future__ import annotations

from ..core.command_parser import parse_flags
from ..core.patterns import PatternContext, parse_pattern
from ..world.generators import (
    generate_cone,
    generate_cylinder,
    generate_pyramid,
    generate_sphere,
    op_biome_set,
    op_forest,
    op_generate,
    op_pumpkins,
)
from . import CommandContext, CommandRouter, CommandSpec


def _place_origin(ctx: CommandContext):
    sel = ctx.services.selections.get_selector(ctx.actor.key)
    return ctx.services.sessions.resolve_placement_origin(ctx.actor.key, ctx.actor.position, sel)


def _parse_radii(raw: str) -> tuple[float, float, float]:
    parts = [float(p.strip()) for p in raw.split(",")]
    if len(parts) == 1:
        return parts[0], parts[0], parts[0]
    if len(parts) == 2:
        return parts[0], parts[1], parts[0]
    return parts[0], parts[1], parts[2]


def _run_cyl(ctx: CommandContext, filled: bool) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"h"})
    if "h" in flags:
        filled = False
    if len(pos_args) < 2:
        raise ValueError("Usage: //cyl [-h] <pattern> <radius[,zradius]> [height]")
    origin = _place_origin(ctx)
    pctx = PatternContext(world=ctx.actor.world, clipboard=ctx.services.clipboards.get(ctx.actor.key), hand_block=ctx.actor.hand_block, origin=origin)
    pat = parse_pattern(pos_args[0], pctx)
    rx, r2, _ = _parse_radii(pos_args[1])
    rz = r2 if "," in pos_args[1] else rx
    height = int(pos_args[2]) if len(pos_args) >= 3 else 1
    session = ctx.create_edit_session("cyl", origin=origin)
    generate_cylinder(session, origin, pat, rx, rz, height=height, filled=filled, pat_ctx=pctx)
    ctx.commit_edit(session, f"Cylinder generated ({session.changes_count} block(s)).")


def _run_sphere(ctx: CommandContext, filled: bool) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"r", "h"})
    if "h" in flags:
        filled = False
    if len(pos_args) < 2:
        raise ValueError("Usage: //sphere [-rh] <pattern> <radius[,ry,rz]>")
    origin = _place_origin(ctx)
    pctx = PatternContext(world=ctx.actor.world, clipboard=ctx.services.clipboards.get(ctx.actor.key), hand_block=ctx.actor.hand_block, origin=origin)
    pat = parse_pattern(pos_args[0], pctx)
    rx, ry, rz = _parse_radii(pos_args[1])
    session = ctx.create_edit_session("sphere", origin=origin)
    generate_sphere(session, origin, pat, rx, ry, rz, filled=filled, raised="r" in flags, pat_ctx=pctx)
    ctx.commit_edit(session, f"Sphere generated ({session.changes_count} block(s)).")


def _run_pyramid(ctx: CommandContext, filled: bool) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"h"})
    if "h" in flags:
        filled = False
    if len(pos_args) < 2:
        raise ValueError("Usage: //pyramid [-h] <pattern> <size>")
    origin = _place_origin(ctx)
    pctx = PatternContext(world=ctx.actor.world, clipboard=ctx.services.clipboards.get(ctx.actor.key), hand_block=ctx.actor.hand_block, origin=origin)
    pat = parse_pattern(pos_args[0], pctx)
    size = int(pos_args[1])
    session = ctx.create_edit_session("pyramid", origin=origin)
    generate_pyramid(session, origin, pat, size=size, filled=filled, pat_ctx=pctx)
    ctx.commit_edit(session, f"Pyramid generated ({session.changes_count} block(s)).")


def _cmd_cone(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"h"})
    if len(pos_args) < 3:
        raise ValueError("Usage: //cone [-h] <pattern> <radius[,zradius]> <height> [thickness]")
    origin = _place_origin(ctx)
    pctx = PatternContext(world=ctx.actor.world, clipboard=ctx.services.clipboards.get(ctx.actor.key), hand_block=ctx.actor.hand_block, origin=origin)
    pat = parse_pattern(pos_args[0], pctx)
    rx, r2, _ = _parse_radii(pos_args[1])
    rz = r2 if "," in pos_args[1] else rx
    height = int(pos_args[2])
    thickness = float(pos_args[3]) if len(pos_args) >= 4 else 1.0
    session = ctx.create_edit_session("cone", origin=origin)
    generate_cone(session, origin, pat, rx, rz, height=height, filled="h" not in flags, thickness=thickness, pat_ctx=pctx)
    ctx.commit_edit(session, f"Cone generated ({session.changes_count} block(s)).")


def _cmd_generate(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"h", "r", "o", "c"})
    if len(pos_args) < 2:
        raise ValueError("Usage: //g [-hroc] <pattern> <expression>")
    region = ctx.services.selections.get_region(ctx.actor.key)
    origin = _place_origin(ctx)
    pctx = PatternContext(world=ctx.actor.world, clipboard=ctx.services.clipboards.get(ctx.actor.key), hand_block=ctx.actor.hand_block, origin=origin, region=region)
    pat = parse_pattern(pos_args[0], pctx)
    expr = " ".join(pos_args[1:])
    session = ctx.create_edit_session("generate", origin=origin)
    op_generate(
        session, region, pat, expr,
        hollow="h" in flags, raw_coords="r" in flags, offset_mode="o" in flags, origin=region.center if "c" in flags else origin, pat_ctx=pctx,
    )
    ctx.commit_edit(session, f"Generated {session.changes_count} block(s) from formula.")


def _cmd_forestgen(ctx: CommandContext) -> None:
    size = int(ctx.tokens[0]) if ctx.tokens else 10
    tree_type = ctx.tokens[1] if len(ctx.tokens) >= 2 else "oak"
    density = float(ctx.tokens[2]) if len(ctx.tokens) >= 3 else 5.0
    origin = _place_origin(ctx)
    from ..core.regions import CuboidRegion
    from ..core.types import BlockVec3

    box = CuboidRegion(
        origin - BlockVec3(size, 5, size),
        origin + BlockVec3(size, 5, size),
    )
    session = ctx.create_edit_session("forestgen", origin=origin)
    op_forest(session, ctx.actor.world, box, tree_type=tree_type, density=density)
    ctx.commit_edit(session, f"Generated {session.changes_count} forest block(s).")


def _cmd_pumpkins(ctx: CommandContext) -> None:
    size = int(ctx.tokens[0]) if ctx.tokens else 10
    origin = _place_origin(ctx)
    session = ctx.create_edit_session("pumpkins", origin=origin)
    op_pumpkins(session, ctx.actor.world, origin, size=size)
    ctx.commit_edit(session, f"Generated pumpkin patch ({session.changes_count} block(s)).")


def _cmd_generatebiome(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //generatebiome <biome> [expression]")
    region = ctx.services.selections.get_region(ctx.actor.key)
    biome_name = ctx.tokens[0]
    cnt = op_biome_set(ctx.actor.world, region, biome_name)
    ctx.actor.send_message(f"Applied biome '{biome_name}' across {cnt} block column(s).")


def register(router: CommandRouter) -> None:
    specs = [
        CommandSpec("cyl", (), "worldedit.generation.cylinder", "Generate a solid cylinder.", "//cyl [-h] <pattern> <radius> [height]", "Generation", lambda c: _run_cyl(c, True)),
        CommandSpec("hcyl", (), "worldedit.generation.cylinder", "Generate a hollow cylinder.", "//hcyl <pattern> <radius> [height]", "Generation", lambda c: _run_cyl(c, False)),
        CommandSpec("sphere", (), "worldedit.generation.sphere", "Generate a solid sphere/ellipsoid.", "//sphere [-rh] <pattern> <radius>", "Generation", lambda c: _run_sphere(c, True)),
        CommandSpec("hsphere", (), "worldedit.generation.sphere", "Generate a hollow sphere/ellipsoid.", "//hsphere [-r] <pattern> <radius>", "Generation", lambda c: _run_sphere(c, False)),
        CommandSpec("pyramid", (), "worldedit.generation.pyramid", "Generate a solid pyramid.", "//pyramid [-h] <pattern> <size>", "Generation", lambda c: _run_pyramid(c, True)),
        CommandSpec("hpyramid", (), "worldedit.generation.pyramid", "Generate a hollow pyramid.", "//hpyramid <pattern> <size>", "Generation", lambda c: _run_pyramid(c, False)),
        CommandSpec("cone", (), "worldedit.generation.cone", "Generate a cone.", "//cone [-h] <pattern> <radius> <height> [thickness]", "Generation", _cmd_cone),
        CommandSpec("g", ("gen", "generate"), "worldedit.generation.shape", "Generate shape from math formula.", "//g [-hroc] <pattern> <expression>", "Generation", _cmd_generate),
        CommandSpec("forestgen", (), "worldedit.generation.forest", "Generate forest around you.", "/forestgen [size] [type] [density]", "Generation", _cmd_forestgen),
        CommandSpec("pumpkins", (), "worldedit.generation.pumpkins", "Generate a pumpkin patch.", "/pumpkins [size]", "Generation", _cmd_pumpkins),
        CommandSpec("generatebiome", (), "worldedit.generation.biome", "Generate biome across selection.", "//generatebiome <biome>", "Generation", _cmd_generatebiome),
    ]
    for s in specs:
        router.register(s)
