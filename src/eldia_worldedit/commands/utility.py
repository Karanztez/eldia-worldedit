"""Utility commands (//fill, //fillr, //drain, //fixwater, //fixlava, //snow, //thaw, //green, //ex, //butcher, //calc)."""

from __future__ import annotations

from ..core.command_parser import parse_flags
from ..core.masks import MaskContext, parse_mask
from ..core.math_expr import ExpressionError, evaluate_expression
from ..core.patterns import PatternContext, parse_pattern
from ..world.generators import (
    op_butcher,
    op_drain,
    op_extinguish,
    op_fill,
    op_fillr,
    op_fix_liquid,
    op_green,
    op_remove_above,
    op_remove_below,
    op_remove_entities,
    op_remove_near,
    op_replace_near,
    op_snow,
    op_thaw,
)
from . import CommandContext, CommandRouter, CommandSpec


def _cmd_fill(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"u"})
    if len(pos_args) < 2:
        raise ValueError("Usage: //fill <pattern> <radius> [depth]")
    pctx = PatternContext(world=ctx.actor.world, hand_block=ctx.actor.hand_block, origin=ctx.actor.position)
    pat = parse_pattern(pos_args[0], pctx)
    radius = float(pos_args[1])
    depth = int(pos_args[2]) if len(pos_args) >= 3 else 1
    session = ctx.create_edit_session("fill")
    op_fill(session, ctx.actor.world, ctx.actor.position, pat, radius=radius, depth=depth, up="u" in flags, pat_ctx=pctx)
    ctx.commit_edit(session, ctx.t("util.fill", count=session.changes_count))


def _cmd_fillr(ctx: CommandContext) -> None:
    if len(ctx.tokens) < 2:
        raise ValueError("Usage: //fillr <pattern> <radius> [depth]")
    pctx = PatternContext(world=ctx.actor.world, hand_block=ctx.actor.hand_block, origin=ctx.actor.position)
    pat = parse_pattern(ctx.tokens[0], pctx)
    radius = float(ctx.tokens[1])
    depth = int(ctx.tokens[2]) if len(ctx.tokens) >= 3 else None
    session = ctx.create_edit_session("fillr")
    op_fillr(session, ctx.actor.world, ctx.actor.position, pat, radius=radius, depth=depth, pat_ctx=pctx)
    ctx.commit_edit(session, ctx.t("util.fillr", count=session.changes_count))


def _cmd_drain(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"w"})
    if not pos_args:
        raise ValueError("Usage: //drain [-w] <radius>")
    radius = float(pos_args[0])
    session = ctx.create_edit_session("drain")
    op_drain(session, ctx.actor.world, ctx.actor.position, radius=radius, waterlogged="w" in flags)
    ctx.commit_edit(session, ctx.t("util.drain", count=session.changes_count))


def _cmd_fixwater(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: /fixwater <radius>")
    radius = float(ctx.tokens[0])
    session = ctx.create_edit_session("fixwater")
    op_fix_liquid(session, ctx.actor.world, ctx.actor.position, radius=radius, liquid="water")
    ctx.commit_edit(session, ctx.t("util.fixwater", count=session.changes_count))


def _cmd_fixlava(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: /fixlava <radius>")
    radius = float(ctx.tokens[0])
    session = ctx.create_edit_session("fixlava")
    op_fix_liquid(session, ctx.actor.world, ctx.actor.position, radius=radius, liquid="lava")
    ctx.commit_edit(session, ctx.t("util.fixlava", count=session.changes_count))


def _cmd_removeabove(ctx: CommandContext) -> None:
    size = int(ctx.tokens[0]) if ctx.tokens else 10
    height = int(ctx.tokens[1]) if len(ctx.tokens) >= 2 else 256
    session = ctx.create_edit_session("removeabove")
    op_remove_above(session, ctx.actor.world, ctx.actor.position, size=size, height=height)
    ctx.commit_edit(session, ctx.t("util.removeabove", count=session.changes_count))


def _cmd_removebelow(ctx: CommandContext) -> None:
    size = int(ctx.tokens[0]) if ctx.tokens else 10
    height = int(ctx.tokens[1]) if len(ctx.tokens) >= 2 else 256
    session = ctx.create_edit_session("removebelow")
    op_remove_below(session, ctx.actor.world, ctx.actor.position, size=size, height=height)
    ctx.commit_edit(session, ctx.t("util.removebelow", count=session.changes_count))


def _cmd_removenear(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: /removenear <mask> [size]")
    size = 50
    if len(ctx.tokens) >= 2 and ctx.tokens[-1].isdigit():
        size = int(ctx.tokens[-1])
        mask_expr = " ".join(ctx.tokens[:-1])
    else:
        mask_expr = " ".join(ctx.tokens)
    mask = parse_mask(mask_expr, MaskContext(origin=ctx.actor.position, hand_block=ctx.actor.hand_block))
    session = ctx.create_edit_session("removenear")
    op_remove_near(session, ctx.actor.world, ctx.actor.position, mask=mask, size=size)
    ctx.commit_edit(session, ctx.t("util.removenear", count=session.changes_count))


def _cmd_replacenear(ctx: CommandContext) -> None:
    if len(ctx.tokens) < 2:
        raise ValueError("Usage: /replacenear <size> [from-mask] <to-pattern>")
    size = int(ctx.tokens[0])
    pctx = PatternContext(world=ctx.actor.world, hand_block=ctx.actor.hand_block, origin=ctx.actor.position)
    if len(ctx.tokens) == 2:
        from_mask = None
        to_pat = parse_pattern(ctx.tokens[1], pctx)
    else:
        from_mask = parse_mask(" ".join(ctx.tokens[1:-1]), MaskContext(origin=ctx.actor.position, hand_block=ctx.actor.hand_block))
        to_pat = parse_pattern(ctx.tokens[-1], pctx)
    session = ctx.create_edit_session("replacenear")
    op_replace_near(session, ctx.actor.world, ctx.actor.position, from_mask=from_mask, to_pattern=to_pat, size=size, pat_ctx=pctx)
    ctx.commit_edit(session, ctx.t("util.replacenear", count=session.changes_count))


def _cmd_snow(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"s"})
    radius = float(pos_args[0]) if pos_args else 10.0
    session = ctx.create_edit_session("snow")
    op_snow(session, ctx.actor.world, ctx.actor.position, radius=radius, stack="s" in flags)
    ctx.commit_edit(session, ctx.t("util.snow", count=session.changes_count))


def _cmd_thaw(ctx: CommandContext) -> None:
    radius = float(ctx.tokens[0]) if ctx.tokens else 10.0
    session = ctx.create_edit_session("thaw")
    op_thaw(session, ctx.actor.world, ctx.actor.position, radius=radius)
    ctx.commit_edit(session, ctx.t("util.thaw", count=session.changes_count))


def _cmd_green(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"f"})
    radius = float(pos_args[0]) if pos_args else 10.0
    session = ctx.create_edit_session("green")
    op_green(session, ctx.actor.world, ctx.actor.position, radius=radius, only_grass="f" in flags)
    ctx.commit_edit(session, ctx.t("util.green", count=session.changes_count))


def _cmd_extinguish(ctx: CommandContext) -> None:
    radius = float(ctx.tokens[0]) if ctx.tokens else 15.0
    session = ctx.create_edit_session("extinguish")
    op_extinguish(session, ctx.actor.world, ctx.actor.position, radius=radius)
    ctx.commit_edit(session, ctx.t("util.ex", count=session.changes_count))


def _cmd_butcher(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"p", "a", "n", "g", "b", "l", "r", "f"})
    radius = float(pos_args[0]) if pos_args else -1.0
    removed = op_butcher(ctx.actor.world, ctx.actor.position, radius=radius, flags=flags)
    ctx.actor.send_message(ctx.t("util.butcher", count=removed))


def _cmd_remove_entities(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: /remove <type|all|items|arrows|boats|minecarts> [radius]")
    etype = ctx.tokens[0]
    radius = float(ctx.tokens[1]) if len(ctx.tokens) >= 2 else -1.0
    removed = op_remove_entities(ctx.actor.world, ctx.actor.position, entity_type=etype, radius=radius)
    ctx.actor.send_message(ctx.t("util.remove_ent", count=removed, etype=etype))


def _cmd_calc(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //calc <expression>")
    expr = " ".join(ctx.tokens)
    try:
        val = evaluate_expression(expr)
    except ExpressionError as exc:
        raise ValueError(str(exc)) from exc
    if abs(val - round(val)) < 1e-12:
        ctx.actor.send_message(f"= {round(val)}")
    else:
        ctx.actor.send_message(f"= {val:g}")


def register(router: CommandRouter) -> None:
    specs = [
        CommandSpec("fill", (), "worldedit.fill", "Fill a pit downward with a pattern.", "//fill [-u] <pattern> <radius> [depth]", "Utility", _cmd_fill),
        CommandSpec("fillr", (), "worldedit.fill.recursive", "Fill recursively through air.", "//fillr <pattern> <radius> [depth]", "Utility", _cmd_fillr),
        CommandSpec("drain", (), "worldedit.drain", "Drain nearby connected water/lava pools.", "//drain [-w] <radius>", "Utility", _cmd_drain),
        CommandSpec("fixwater", (), "worldedit.fixwater", "Level nearby water pools.", "/fixwater <radius>", "Utility", _cmd_fixwater),
        CommandSpec("fixlava", (), "worldedit.fixlava", "Level nearby lava pools.", "/fixlava <radius>", "Utility", _cmd_fixlava),
        CommandSpec("removeabove", (), "worldedit.removeabove", "Remove blocks above your position.", "/removeabove [size] [height]", "Utility", _cmd_removeabove),
        CommandSpec("removebelow", (), "worldedit.removebelow", "Remove blocks below your position.", "/removebelow [size] [height]", "Utility", _cmd_removebelow),
        CommandSpec("removenear", (), "worldedit.removenear", "Remove matching blocks nearby.", "/removenear <mask> [size]", "Utility", _cmd_removenear),
        CommandSpec("replacenear", (), "worldedit.replacenear", "Replace matching blocks nearby.", "/replacenear <size> [from] <to>", "Utility", _cmd_replacenear),
        CommandSpec("snow", (), "worldedit.snow", "Simulate snow fall around you.", "/snow [-s] [radius]", "Utility", _cmd_snow),
        CommandSpec("thaw", (), "worldedit.thaw", "Remove snow and melt ice around you.", "/thaw [radius]", "Utility", _cmd_thaw),
        CommandSpec("green", (), "worldedit.green", "Turn nearby exposed dirt into grass.", "/green [-f] [radius]", "Utility", _cmd_green),
        CommandSpec("extinguish", ("ex",), "worldedit.extinguish", "Put out fire around you.", "/extinguish [radius]", "Utility", _cmd_extinguish),
        CommandSpec("butcher", (), "worldedit.butcher", "Kill nearby mobs with type flags.", "/butcher [-pangbf] [radius]", "Utility", _cmd_butcher),
        CommandSpec("remove", ("rem",), "worldedit.remove", "Remove entities by type.", "/remove <type> [radius]", "Utility", _cmd_remove_entities),
        CommandSpec("calc", ("eval",), "worldedit.calc", "Evaluate a math expression.", "//calc <expression>", "Utility", _cmd_calc, player_only=False),
    ]
    for s in specs:
        router.register(s)
