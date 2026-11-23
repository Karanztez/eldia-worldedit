"""Region editing commands (//set, //replace, //overlay, //walls, //faces, //smooth, //move, //stack, etc.)."""

from __future__ import annotations

from ..clipboard.clipboard import revolve_region
from ..core.command_parser import parse_flags
from ..core.masks import MaskContext, parse_mask
from ..core.patterns import PatternContext, parse_pattern
from ..core.regions import ConvexPolyhedralRegion
from ..core.types import AIR_SPEC, BlockSpec, resolve_direction
from ..world.generators import (
    op_center,
    op_curve,
    op_deform,
    op_faces,
    op_flora,
    op_forest,
    op_hollow,
    op_line,
    op_move,
    op_naturalize,
    op_overlay,
    op_replace,
    op_set,
    op_smooth,
    op_snowsmooth,
    op_stack,
    op_walls,
)
from . import CommandContext, CommandRouter, CommandSpec


def _pat_ctx(ctx: CommandContext, region: object, origin: object) -> PatternContext:
    cb = ctx.services.clipboards.get(ctx.actor.key)
    return PatternContext(
        world=ctx.actor.world,
        clipboard=cb,
        hand_block=ctx.actor.hand_block,
        origin=origin,  # type: ignore[arg-type]
        region=region,
    )


def _cmd_set(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //set <pattern>")
    region = ctx.services.selections.get_region(ctx.actor.key)
    session = ctx.create_edit_session("set", origin=region.min_point)
    pat = parse_pattern(" ".join(ctx.tokens), _pat_ctx(ctx, region, region.min_point))
    op_set(session, region, pat, pat_ctx=_pat_ctx(ctx, region, region.min_point))
    ctx.commit_edit(session, f"Operation completed ({session.changes_count} block(s) affected).")


def _cmd_replace(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //replace [from-mask] <to-pattern>")
    region = ctx.services.selections.get_region(ctx.actor.key)
    session = ctx.create_edit_session("replace", origin=region.min_point)
    pctx = _pat_ctx(ctx, region, region.min_point)
    mctx = MaskContext(region=region, origin=region.min_point, hand_block=ctx.actor.hand_block)
    if len(ctx.tokens) == 1:
        from_mask = None
        to_pat = parse_pattern(ctx.tokens[0], pctx)
    else:
        to_pat = parse_pattern(ctx.tokens[-1], pctx)
        from_mask = parse_mask(" ".join(ctx.tokens[:-1]), mctx)
    op_replace(session, region, from_mask, to_pat, pat_ctx=pctx, mask_ctx=mctx)
    ctx.commit_edit(session, f"{session.changes_count} block(s) have been replaced.")


def _cmd_overlay(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //overlay <pattern>")
    region = ctx.services.selections.get_region(ctx.actor.key)
    session = ctx.create_edit_session("overlay", origin=region.min_point)
    pctx = _pat_ctx(ctx, region, region.min_point)
    pat = parse_pattern(" ".join(ctx.tokens), pctx)
    op_overlay(session, region, pat, pat_ctx=pctx)
    ctx.commit_edit(session, f"{session.changes_count} block(s) overlaid.")


def _cmd_walls(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //walls <pattern>")
    region = ctx.services.selections.get_region(ctx.actor.key)
    session = ctx.create_edit_session("walls", origin=region.min_point)
    pctx = _pat_ctx(ctx, region, region.min_point)
    pat = parse_pattern(" ".join(ctx.tokens), pctx)
    op_walls(session, region, pat, pat_ctx=pctx)
    ctx.commit_edit(session, f"{session.changes_count} wall block(s) updated.")


def _cmd_faces(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //faces <pattern>")
    region = ctx.services.selections.get_region(ctx.actor.key)
    session = ctx.create_edit_session("faces", origin=region.min_point)
    pctx = _pat_ctx(ctx, region, region.min_point)
    pat = parse_pattern(" ".join(ctx.tokens), pctx)
    op_faces(session, region, pat, pat_ctx=pctx)
    ctx.commit_edit(session, f"{session.changes_count} outline block(s) updated.")


def _cmd_center(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //center <pattern>")
    region = ctx.services.selections.get_region(ctx.actor.key)
    session = ctx.create_edit_session("center", origin=region.min_point)
    pctx = _pat_ctx(ctx, region, region.min_point)
    pat = parse_pattern(" ".join(ctx.tokens), pctx)
    op_center(session, region, pat, pat_ctx=pctx)
    ctx.commit_edit(session, f"{session.changes_count} center block(s) updated.")


def _cmd_smooth(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"n"})
    region = ctx.services.selections.get_region(ctx.actor.key)
    iters = int(pos_args[0]) if pos_args else 1
    mask = None
    mctx = MaskContext(region=region, origin=region.min_point, hand_block=ctx.actor.hand_block)
    if "n" in flags:
        mask = parse_mask("#existing,!leaves,!logs", mctx)
    elif len(pos_args) >= 2:
        mask = parse_mask(" ".join(pos_args[1:]), mctx)
    session = ctx.create_edit_session("smooth", origin=region.min_point)
    op_smooth(session, region, iterations=iters, mask=mask, mask_ctx=mctx)
    ctx.commit_edit(session, f"Smoothed region ({session.changes_count} blocks modified).")


def _cmd_snowsmooth(ctx: CommandContext) -> None:
    region = ctx.services.selections.get_region(ctx.actor.key)
    iters = int(ctx.tokens[0]) if ctx.tokens else 1
    snow_blocks = int(ctx.tokens[1]) if len(ctx.tokens) >= 2 else 1
    session = ctx.create_edit_session("snowsmooth", origin=region.min_point)
    op_snowsmooth(session, region, iterations=iters, snow_blocks=snow_blocks)
    ctx.commit_edit(session, f"Smoothed snow heightmap ({session.changes_count} blocks).")


def _cmd_move(ctx: CommandContext) -> None:
    flags, values, pos_args = parse_flags(ctx.tokens, value_flags={"m"}, bool_flags={"s", "a", "e", "b"})
    region = ctx.services.selections.get_region(ctx.actor.key)
    count = int(pos_args[0]) if pos_args else 1
    dir_tok = pos_args[1] if len(pos_args) >= 2 else None
    replace_pat = None
    if len(pos_args) >= 3:
        replace_pat = parse_pattern(pos_args[2], _pat_ctx(ctx, region, region.min_point))
    direction = resolve_direction(dir_tok, yaw=ctx.actor.yaw, pitch=ctx.actor.pitch)
    mask = parse_mask(values["m"], MaskContext(region=region, origin=region.min_point)) if "m" in values else None
    session = ctx.create_edit_session("move", origin=region.min_point)
    _, new_min, new_max = op_move(
        session,
        ctx.actor.world,
        region,
        direction,
        count=count,
        replace_pattern=replace_pat,
        ignore_air="a" in flags,
        move_entities="e" in flags,
        move_biomes="b" in flags,
        mask=mask,
        pat_ctx=_pat_ctx(ctx, region, region.min_point),
    )
    if "s" in flags:
        region.shift(direction * count)
    ctx.commit_edit(session, f"Moved {session.changes_count} block(s) to {new_min.format_short()} .. {new_max.format_short()}.")


def _cmd_stack(ctx: CommandContext) -> None:
    flags, values, pos_args = parse_flags(ctx.tokens, value_flags={"m"}, bool_flags={"s", "a", "e", "b"})
    region = ctx.services.selections.get_region(ctx.actor.key)
    count = int(pos_args[0]) if pos_args else 1
    dir_tok = pos_args[1] if len(pos_args) >= 2 else None
    direction = resolve_direction(dir_tok, yaw=ctx.actor.yaw, pitch=ctx.actor.pitch)
    mask = parse_mask(values["m"], MaskContext(region=region, origin=region.min_point)) if "m" in values else None
    session = ctx.create_edit_session("stack", origin=region.min_point)
    _, new_min, new_max = op_stack(
        session,
        ctx.actor.world,
        region,
        direction,
        count=count,
        ignore_air="a" in flags,
        stack_biomes="b" in flags,
        mask=mask,
    )
    if "s" in flags:
        dims = region.dimensions
        stride = direction
        region.shift(resolve_direction(dir_tok, yaw=ctx.actor.yaw, pitch=ctx.actor.pitch).min_with(stride) if False else type(dims)(direction.x * dims.x * count, direction.y * dims.y * count, direction.z * dims.z * count))
    ctx.commit_edit(session, f"Stacked {count} time(s) to {new_min.format_short()} .. {new_max.format_short()} ({session.changes_count} blocks updated).")


def _cmd_line(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"h"})
    if not pos_args:
        raise ValueError("Usage: //line [-h] <pattern> [thickness]")
    region = ctx.services.selections.get_region(ctx.actor.key)
    pat_str = pos_args[0]
    thickness = int(pos_args[1]) if len(pos_args) >= 2 else 0
    if hasattr(region, "pos1") and hasattr(region, "pos2"):
        p1, p2 = region.pos1, region.pos2
    else:
        p1, p2 = region.min_point, region.max_point
    session = ctx.create_edit_session("line", origin=p1)
    op_line(session, p1, p2, parse_pattern(pat_str, _pat_ctx(ctx, region, p1)), thickness=thickness, filled="h" not in flags)
    ctx.commit_edit(session, f"Line drawn ({session.changes_count} block(s)).")


def _cmd_curve(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"h"})
    if not pos_args:
        raise ValueError("Usage: //curve [-h] <pattern> [thickness]")
    region = ctx.services.selections.get_region(ctx.actor.key)
    if isinstance(region, ConvexPolyhedralRegion):
        verts = region.vertices
    elif hasattr(region, "pos1") and hasattr(region, "pos2"):
        verts = [region.pos1, region.pos2]
    else:
        verts = [region.min_point, region.center, region.max_point]
    pat_str = pos_args[0]
    thickness = int(pos_args[1]) if len(pos_args) >= 2 else 0
    session = ctx.create_edit_session("curve", origin=verts[0])
    op_curve(session, verts, parse_pattern(pat_str, _pat_ctx(ctx, region, verts[0])), thickness=thickness, filled="h" not in flags)
    ctx.commit_edit(session, f"Curve drawn ({session.changes_count} block(s)).")


def _cmd_hollow(ctx: CommandContext) -> None:
    region = ctx.services.selections.get_region(ctx.actor.key)
    thickness = int(ctx.tokens[0]) if ctx.tokens else 1
    pat = parse_pattern(ctx.tokens[1], _pat_ctx(ctx, region, region.min_point)) if len(ctx.tokens) >= 2 else None
    session = ctx.create_edit_session("hollow", origin=region.min_point)
    op_hollow(session, ctx.actor.world, region, thickness=thickness, pattern=pat)
    ctx.commit_edit(session, f"Hollowed region ({session.changes_count} block(s) replaced).")


def _cmd_deform(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"r", "o"})
    if not pos_args:
        raise ValueError("Usage: //deform [-ro] <expression>")
    region = ctx.services.selections.get_region(ctx.actor.key)
    expr = " ".join(pos_args)
    session = ctx.create_edit_session("deform", origin=region.center)
    op_deform(session, ctx.actor.world, region, expr, raw_coords="r" in flags, offset_mode="o" in flags, origin=region.center)
    ctx.commit_edit(session, f"Deformed region ({session.changes_count} block(s)).")


def _cmd_forest(ctx: CommandContext) -> None:
    region = ctx.services.selections.get_region(ctx.actor.key)
    tree_type = ctx.tokens[0] if ctx.tokens else "oak"
    density = float(ctx.tokens[1]) if len(ctx.tokens) >= 2 else 5.0
    session = ctx.create_edit_session("forest", origin=region.min_point)
    op_forest(session, ctx.actor.world, region, tree_type=tree_type, density=density)
    ctx.commit_edit(session, f"Planted forest ({session.changes_count} tree block(s)).")


def _cmd_flora(ctx: CommandContext) -> None:
    region = ctx.services.selections.get_region(ctx.actor.key)
    density = float(ctx.tokens[0]) if ctx.tokens else 10.0
    session = ctx.create_edit_session("flora", origin=region.min_point)
    op_flora(session, ctx.actor.world, region, density=density)
    ctx.commit_edit(session, f"Scattered flora ({session.changes_count} block(s)).")


def _cmd_naturalize(ctx: CommandContext) -> None:
    region = ctx.services.selections.get_region(ctx.actor.key)
    session = ctx.create_edit_session("naturalize", origin=region.min_point)
    op_naturalize(session, region)
    ctx.commit_edit(session, f"Naturalized terrain ({session.changes_count} block(s)).")


def _cmd_regen(ctx: CommandContext) -> None:
    region = ctx.services.selections.get_region(ctx.actor.key)
    session = ctx.create_edit_session("regen", origin=region.min_point)
    grass = BlockSpec("minecraft:grass_block")
    dirt = BlockSpec("minecraft:dirt")
    stone = BlockSpec("minecraft:stone")
    # Flat-chunk deterministic baseline regen over Bedrock surface level y=63
    for pos in region.iter_positions():
        if pos.y > 63:
            session.set_block(pos, AIR_SPEC)
        elif pos.y == 63:
            session.set_block(pos, grass)
        elif pos.y >= 60:
            session.set_block(pos, dirt)
        else:
            session.set_block(pos, stone)
    ctx.commit_edit(session, f"Regenerated region baseline ({session.changes_count} block(s)).")


def _cmd_revolve(ctx: CommandContext) -> None:
    flags, values, pos_args = parse_flags(ctx.tokens, value_flags={"m"}, bool_flags={"r"})
    if not pos_args:
        raise ValueError("Usage: //revolve [-r] [-m mask] <count> [start] [end] [height]")
    count = int(pos_args[0])
    start = float(pos_args[1]) if len(pos_args) >= 2 else 0.0
    end = float(pos_args[2]) if len(pos_args) >= 3 else 360.0
    height_diff = float(pos_args[3]) if len(pos_args) >= 4 else 0.0
    region = ctx.services.selections.get_region(ctx.actor.key)
    mask = parse_mask(values["m"]) if "m" in values else None
    session = ctx.create_edit_session("revolve", origin=ctx.actor.position)
    revolve_region(
        ctx.actor.world, session, region, ctx.actor.position,
        count=count, start_angle=start, end_angle=end, height_diff=height_diff, reverse="r" in flags, mask=mask,
    )
    ctx.commit_edit(session, f"Revolved {count} copies ({session.changes_count} block(s)).")


def register(router: CommandRouter) -> None:
    specs = [
        CommandSpec("set", (), "worldedit.region.set", "Set all blocks inside selection.", "//set <pattern>", "Region", _cmd_set),
        CommandSpec("replace", ("re", "rep"), "worldedit.region.replace", "Replace blocks in selection.", "//replace [from-mask] <to-pattern>", "Region", _cmd_replace),
        CommandSpec("overlay", (), "worldedit.region.overlay", "Place block layer atop surface.", "//overlay <pattern>", "Region", _cmd_overlay),
        CommandSpec("walls", (), "worldedit.region.walls", "Build walls around selection.", "//walls <pattern>", "Region", _cmd_walls),
        CommandSpec("faces", ("outline",), "worldedit.region.faces", "Build 6 faces around selection.", "//faces <pattern>", "Region", _cmd_faces),
        CommandSpec("center", ("middle",), "worldedit.region.center", "Set center block(s) of selection.", "//center <pattern>", "Region", _cmd_center),
        CommandSpec("smooth", (), "worldedit.region.smooth", "Smooth terrain heightmap.", "//smooth [-n] [iterations]", "Region", _cmd_smooth),
        CommandSpec("snowsmooth", (), "worldedit.region.snowsmooth", "Smooth snow layers.", "//snowsmooth [iterations] [blocks]", "Region", _cmd_snowsmooth),
        CommandSpec("move", (), "worldedit.region.move", "Move selection contents.", "//move [-saeb] [count] [dir] [replace]", "Region", _cmd_move),
        CommandSpec("stack", (), "worldedit.region.stack", "Repeat selection along a direction.", "//stack [-saeb] [count] [dir]", "Region", _cmd_stack),
        CommandSpec("line", (), "worldedit.region.line", "Draw straight 3D line between pos1 & pos2.", "//line [-h] <pattern> [thickness]", "Region", _cmd_line),
        CommandSpec("curve", (), "worldedit.region.curve", "Draw Catmull-Rom spline through vertices.", "//curve [-h] <pattern> [thickness]", "Region", _cmd_curve),
        CommandSpec("hollow", (), "worldedit.region.hollow", "Hollow solid shapes in selection.", "//hollow [thickness] [pattern]", "Region", _cmd_hollow),
        CommandSpec("deform", (), "worldedit.region.deform", "Deform blocks using math formula.", "//deform [-ro] <expression>", "Region", _cmd_deform),
        CommandSpec("forest", (), "worldedit.region.forest", "Plant trees in selection.", "//forest [type] [density]", "Region", _cmd_forest),
        CommandSpec("flora", (), "worldedit.region.flora", "Scatter flowers and grass in selection.", "//flora [density]", "Region", _cmd_flora),
        CommandSpec("naturalize", (), "worldedit.region.naturalize", "Cover selection in 1 grass, 3 dirt, stone.", "//naturalize", "Region", _cmd_naturalize),
        CommandSpec("regen", (), "worldedit.regen", "Reset region to clean overworld baseline.", "//regen", "Region", _cmd_regen),
        CommandSpec("revolve", (), "worldedit.region.revolve", "Revolve selection radially around player.", "//revolve [-r] <count> [start] [end] [dy]", "Region", _cmd_revolve),
    ]
    for s in specs:
        router.register(s)
