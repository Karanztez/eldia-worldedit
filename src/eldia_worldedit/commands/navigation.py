"""Navigation commands (/unstuck, /ascend, /descend, /ceil, /thru, /jumpto, /up)."""

from __future__ import annotations

from ..core.command_parser import parse_flags
from ..world.navigation import (
    find_ascend_pos,
    find_ceiling_pos,
    find_descend_pos,
    find_jumpto_pos,
    find_thru_pos,
    find_unstuck_pos,
    find_up_pos,
)
from . import CommandContext, CommandRouter, CommandSpec


def _cmd_unstuck(ctx: CommandContext) -> None:
    dest = find_unstuck_pos(ctx.actor.world, ctx.actor.position)
    ctx.actor.teleport(dest)
    ctx.actor.send_message(ctx.t("nav.unstuck", pos=dest.format_short()))


def _cmd_ascend(ctx: CommandContext) -> None:
    levels = int(ctx.tokens[0]) if ctx.tokens else 1
    dest = find_ascend_pos(ctx.actor.world, ctx.actor.position, levels=levels)
    if dest is None:
        raise ValueError("No free floor found above you.")
    ctx.actor.teleport(dest)
    ctx.actor.send_message(ctx.t("nav.ascend", levels=levels, pos=dest.format_short()))


def _cmd_descend(ctx: CommandContext) -> None:
    levels = int(ctx.tokens[0]) if ctx.tokens else 1
    dest = find_descend_pos(ctx.actor.world, ctx.actor.position, levels=levels)
    if dest is None:
        raise ValueError("No free room found below you.")
    ctx.actor.teleport(dest)
    ctx.actor.send_message(ctx.t("nav.descend", levels=levels, pos=dest.format_short()))


def _cmd_ceil(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"f", "g"})
    clearance = int(pos_args[0]) if pos_args else 0
    dest = find_ceiling_pos(ctx.actor.world, ctx.actor.position, clearance=clearance)
    if dest is None:
        raise ValueError("No ceiling found above you.")
    if "g" in flags:
        session = ctx.create_edit_session("ceil")
        from ..core.types import BlockSpec, BlockVec3

        below = dest - BlockVec3(0, 1, 0)
        if ctx.actor.world.get_block(below).is_air:
            session.set_block(below, BlockSpec("minecraft:glass"))
            ctx.commit_edit(session)
    ctx.actor.teleport(dest)
    ctx.actor.send_message(ctx.t("nav.ceil", pos=dest.format_short()))


def _cmd_thru(ctx: CommandContext) -> None:
    ex, ey, ez = ctx.actor.eye_position
    dest = find_thru_pos(ctx.actor.world, ex, ey, ez, ctx.actor.yaw, ctx.actor.pitch)
    if dest is None:
        raise ValueError("No free space found through the obstacle you are looking at.")
    ctx.actor.teleport(dest)
    ctx.actor.send_message(ctx.t("nav.thru", pos=dest.format_short()))


def _cmd_jumpto(ctx: CommandContext) -> None:
    ex, ey, ez = ctx.actor.eye_position
    dest = find_jumpto_pos(ctx.actor.world, ex, ey, ez, ctx.actor.yaw, ctx.actor.pitch)
    if dest is None:
        raise ValueError(ctx.t("cmd.no_block_sight"))
    ctx.actor.teleport(dest)
    ctx.actor.send_message(ctx.t("nav.jumpto", pos=dest.format_short()))


def _cmd_up(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"f", "g"})
    if not pos_args:
        raise ValueError("Usage: /up <distance>")
    dist = int(pos_args[0])
    session = ctx.create_edit_session("up")
    dest = find_up_pos(ctx.actor.world, session, ctx.actor.position, distance=dist, place_glass="f" not in flags)
    ctx.commit_edit(session)
    ctx.actor.teleport(dest)
    ctx.actor.send_message(ctx.t("nav.up", dist=dist, pos=dest.format_short()))


def register(router: CommandRouter) -> None:
    specs = [
        CommandSpec("unstuck", ("!",), "worldedit.navigation.unstuck", "Escape from inside solid blocks.", "/unstuck", "Navigation", _cmd_unstuck),
        CommandSpec("ascend", ("asc",), "worldedit.navigation.ascend", "Go up one or more floors.", "/ascend [levels]", "Navigation", _cmd_ascend),
        CommandSpec("descend", ("desc",), "worldedit.navigation.descend", "Go down one or more floors.", "/descend [levels]", "Navigation", _cmd_descend),
        CommandSpec("ceil", (), "worldedit.navigation.ceiling", "Teleport beneath the ceiling.", "/ceil [-g] [clearance]", "Navigation", _cmd_ceil),
        CommandSpec("thru", (), "worldedit.navigation.thru.command", "Pass through wall you are looking at.", "/thru", "Navigation", _cmd_thru),
        CommandSpec("jumpto", ("j",), "worldedit.navigation.jumpto.command", "Teleport onto the block in view.", "/jumpto", "Navigation", _cmd_jumpto),
        CommandSpec("up", (), "worldedit.navigation.up", "Rise straight up with optional glass.", "/up [-f] <distance>", "Navigation", _cmd_up),
    ]
    for s in specs:
        router.register(s)
