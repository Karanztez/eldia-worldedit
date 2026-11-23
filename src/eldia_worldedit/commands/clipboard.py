"""Clipboard and Schematic commands (//copy, //cut, //paste, //rotate, //flip, //clearclipboard, //schem)."""

from __future__ import annotations

from ..clipboard.clipboard import copy_region, flip_clipboard, paste_clipboard, rotate_clipboard
from ..clipboard.schematic import SCHEMATIC_FORMATS
from ..core.command_parser import parse_flags
from ..core.masks import MaskContext, parse_mask
from ..core.types import AIR_SPEC, resolve_direction
from . import CommandContext, CommandRouter, CommandSpec


def _cmd_copy(ctx: CommandContext) -> None:
    flags, values, _ = parse_flags(ctx.tokens, value_flags={"m"}, bool_flags={"e", "b"})
    region = ctx.services.selections.get_region(ctx.actor.key)
    mctx = MaskContext(region=region, origin=ctx.actor.position, hand_block=ctx.actor.hand_block)
    mask = parse_mask(values["m"], mctx) if "m" in values else None
    cb = copy_region(
        ctx.actor.world,
        region,
        ctx.actor.position,
        mask=mask,
        mask_context=mctx,
        copy_entities="e" in flags,
        copy_biomes="b" in flags,
    )
    ctx.services.clipboards.set(ctx.actor.key, cb)
    ctx.actor.send_message(ctx.t("clip.copied", vol=cb.volume))


def _cmd_cut(ctx: CommandContext) -> None:
    flags, values, pos_args = parse_flags(ctx.tokens, value_flags={"m"}, bool_flags={"e", "b"})
    region = ctx.services.selections.get_region(ctx.actor.key)
    mctx = MaskContext(region=region, origin=ctx.actor.position, hand_block=ctx.actor.hand_block)
    mask = parse_mask(values["m"], mctx) if "m" in values else None
    cb = copy_region(
        ctx.actor.world,
        region,
        ctx.actor.position,
        mask=mask,
        mask_context=mctx,
        copy_entities="e" in flags,
        copy_biomes="b" in flags,
    )
    ctx.services.clipboards.set(ctx.actor.key, cb)

    from ..core.patterns import PatternContext, parse_pattern

    leave_pat = parse_pattern(pos_args[0], PatternContext(world=ctx.actor.world)) if pos_args else None
    session = ctx.create_edit_session("cut", origin=ctx.actor.position)
    for pos in region.iter_positions():
        if mask is not None and not mask.test(ctx.actor.world, pos, mctx):
            continue
        spec = leave_pat.apply(pos, mctx.rng, PatternContext(world=ctx.actor.world)) if leave_pat else AIR_SPEC
        session.set_block(pos, spec)
    ctx.commit_edit(session, ctx.t("clip.cut", count=session.changes_count))


def _cmd_paste(ctx: CommandContext) -> None:
    flags, values, _ = parse_flags(ctx.tokens, value_flags={"m"}, bool_flags={"a", "o", "s", "b", "e", "n"})
    cb = ctx.services.clipboards.get(ctx.actor.key)
    if cb is None:
        raise ValueError(ctx.t("clip.empty"))
    to_pos = cb.origin if "o" in flags else ctx.actor.position
    src_mask = parse_mask(values["m"]) if "m" in values else None
    session = ctx.create_edit_session("paste", origin=to_pos)
    changed, pmin, pmax = paste_clipboard(
        cb,
        session,
        to_pos,
        ignore_air="a" in flags,
        source_mask=src_mask,
        paste_biomes="b" in flags,
        select_only="n" in flags,
    )
    if "s" in flags or "n" in flags:
        sel = ctx.services.selections
        sel.set_mode(ctx.actor.key, "cuboid")
        sel.select_pos1(ctx.actor.key, pmin, lang=ctx.services.lang)
        sel.select_pos2(ctx.actor.key, pmax, lang=ctx.services.lang)
    ctx.commit_edit(session, ctx.t("clip.pasted", pos=to_pos.format_short(), count=changed))


def _cmd_rotate(ctx: CommandContext) -> None:
    cb = ctx.services.clipboards.get(ctx.actor.key)
    if cb is None:
        raise ValueError(ctx.t("clip.empty"))
    if not ctx.tokens:
        raise ValueError("Usage: //rotate <y-degrees> [x-degrees] [z-degrees]")
    ry = int(ctx.tokens[0])
    rx = int(ctx.tokens[1]) if len(ctx.tokens) >= 2 else 0
    rz = int(ctx.tokens[2]) if len(ctx.tokens) >= 3 else 0
    rotated = rotate_clipboard(cb, rot_y=ry, rot_x=rx, rot_z=rz)
    ctx.services.clipboards.set(ctx.actor.key, rotated)
    ctx.actor.send_message(ctx.t("clip.rotated", ry=ry, rx=rx, rz=rz))


def _cmd_flip(ctx: CommandContext) -> None:
    cb = ctx.services.clipboards.get(ctx.actor.key)
    if cb is None:
        raise ValueError(ctx.t("clip.empty"))
    dir_tok = ctx.tokens[0] if ctx.tokens else None
    direction = resolve_direction(dir_tok, yaw=ctx.actor.yaw, pitch=ctx.actor.pitch)
    flipped = flip_clipboard(cb, direction)
    ctx.services.clipboards.set(ctx.actor.key, flipped)
    ctx.actor.send_message(ctx.t("clip.flipped", dir=direction.format_short()))


def _cmd_clearclipboard(ctx: CommandContext) -> None:
    ctx.services.clipboards.clear(ctx.actor.key)
    ctx.actor.send_message(ctx.t("clip.cleared"))


def _cmd_schem(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //schem <save|load|list|delete|formats> ...")
    sub = ctx.tokens[0].lower()
    rest = ctx.tokens[1:]
    cman = ctx.services.clipboards

    if sub in ("formats", "listformats"):
        ctx.actor.send_message(ctx.t("schem.formats", formats=", ".join(SCHEMATIC_FORMATS)))
        return

    if sub == "list":
        flags, _, _ = parse_flags(rest, bool_flags={"d", "n", "o"})
        sort_mode = "oldest" if "o" in flags else ("newest" if ("d" in flags or "n" in flags) else "name")
        entries = cman.list_files(sort=sort_mode)
        if not entries:
            ctx.actor.send_message(ctx.t("schem.none"))
            return
        ctx.actor.send_message(ctx.t("schem.list", count=len(entries)))
        for e in entries:
            ctx.actor.send_message(f"  - {e.name}.{e.fmt} ({e.size_bytes} bytes)")
        return

    if sub == "save":
        flags, _, pos_args = parse_flags(rest, bool_flags={"f"})
        if not pos_args:
            raise ValueError("Usage: //schem save [-f] <filename> [schem|mcstructure|wejson]")
        name = pos_args[0]
        fmt = pos_args[1] if len(pos_args) >= 2 else "schem"
        path = cman.save_to_disk(ctx.actor.key, name, fmt=fmt, overwrite="f" in flags)
        ctx.actor.send_message(ctx.t("schem.saved", name=path.name))
        return

    if sub == "load":
        if not rest:
            raise ValueError("Usage: //schem load <filename>")
        cb = cman.load_from_disk(ctx.actor.key, rest[0])
        d = cb.dimensions
        ctx.actor.send_message(ctx.t("schem.loaded", name=rest[0], dx=d.x, dy=d.y, dz=d.z))
        return

    if sub in ("delete", "rm"):
        if not rest:
            raise ValueError("Usage: //schem delete <filename>")
        removed = cman.delete_file(rest[0])
        ctx.actor.send_message(ctx.t("schem.deleted", name=removed.name))
        return

    raise ValueError(f"Unknown schematic subcommand '{sub}'. Use save, load, list, delete, or formats.")


def register(router: CommandRouter) -> None:
    specs = [
        CommandSpec("copy", (), "worldedit.clipboard.copy", "Copy selection to clipboard.", "//copy [-eb] [-m mask]", "Clipboard", _cmd_copy),
        CommandSpec("cut", (), "worldedit.clipboard.cut", "Cut selection into clipboard.", "//cut [-eb] [-m mask] [leave]", "Clipboard", _cmd_cut),
        CommandSpec("paste", (), "worldedit.clipboard.paste", "Paste clipboard contents.", "//paste [-aosben] [-m mask]", "Clipboard", _cmd_paste),
        CommandSpec("rotate", (), "worldedit.clipboard.rotate", "Rotate clipboard in 90-degree increments.", "//rotate <y> [x] [z]", "Clipboard", _cmd_rotate),
        CommandSpec("flip", (), "worldedit.clipboard.flip", "Mirror clipboard along a direction.", "//flip [direction]", "Clipboard", _cmd_flip),
        CommandSpec("clearclipboard", (), "worldedit.clipboard.clear", "Clear your active clipboard.", "//clearclipboard", "Clipboard", _cmd_clearclipboard),
        CommandSpec("schem", ("schematic",), "worldedit.schematic", "Manage saved schematic files.", "//schem <save|load|list|delete|formats>", "Clipboard", _cmd_schem, player_only=False),
    ]
    for s in specs:
        router.register(s)
