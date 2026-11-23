"""History commands (//undo, //redo, //clearhistory)."""

from __future__ import annotations

from . import CommandContext, CommandRouter, CommandSpec


def _cmd_undo(ctx: CommandContext) -> None:
    steps_req = 1
    target_key = ctx.actor.key
    if ctx.tokens:
        try:
            steps_req = int(ctx.tokens[0])
            if len(ctx.tokens) >= 2:
                target_key = ctx.tokens[1]
        except ValueError:
            target_key = ctx.tokens[0]
            steps_req = int(ctx.tokens[1]) if len(ctx.tokens) >= 2 else 1

    fast = ctx.services.sessions.get(ctx.actor.key).fast_mode
    steps, blocks = ctx.services.history.undo(target_key, ctx.actor.resolve_world, count=steps_req, fast_mode=fast)
    if steps == 0:
        ctx.actor.send_error("Nothing left to undo.")
    else:
        ctx.actor.send_message(f"Undid {steps} edit(s) ({blocks} block(s) restored).")


def _cmd_redo(ctx: CommandContext) -> None:
    steps_req = 1
    target_key = ctx.actor.key
    if ctx.tokens:
        try:
            steps_req = int(ctx.tokens[0])
            if len(ctx.tokens) >= 2:
                target_key = ctx.tokens[1]
        except ValueError:
            target_key = ctx.tokens[0]
            steps_req = int(ctx.tokens[1]) if len(ctx.tokens) >= 2 else 1

    fast = ctx.services.sessions.get(ctx.actor.key).fast_mode
    steps, blocks = ctx.services.history.redo(target_key, ctx.actor.resolve_world, count=steps_req, fast_mode=fast)
    if steps == 0:
        ctx.actor.send_error("Nothing left to redo.")
    else:
        ctx.actor.send_message(f"Redid {steps} edit(s) ({blocks} block(s) applied).")


def _cmd_clearhistory(ctx: CommandContext) -> None:
    cnt = ctx.services.history.clear(ctx.actor.key)
    ctx.actor.send_message(f"Cleared {cnt} history entry/entries.")


def register(router: CommandRouter) -> None:
    specs = [
        CommandSpec("undo", (), "worldedit.history.undo", "Undo previous WorldEdit operations.", "//undo [count] [player]", "History", _cmd_undo, player_only=False),
        CommandSpec("redo", (), "worldedit.history.redo", "Redo previously undone edits.", "//redo [count] [player]", "History", _cmd_redo, player_only=False),
        CommandSpec("clearhistory", (), "worldedit.history.clear", "Clear your undo/redo stack.", "//clearhistory", "History", _cmd_clearhistory),
    ]
    for s in specs:
        router.register(s)
