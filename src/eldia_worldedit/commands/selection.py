"""Selection commands (//pos1, //pos2, //hpos1, //hpos2, //chunk, //wand, //expand, //contract, etc.)."""

from __future__ import annotations

from ..core.command_parser import parse_flags
from ..core.masks import MaskContext, parse_mask
from ..core.regions import SELECTOR_TYPES
from ..core.types import BlockVec3, resolve_direction
from ..world.generators import op_count, op_distr
from ..world.navigation import raycast_block
from . import CommandContext, CommandRouter, CommandSpec


def _parse_xyz(raw: str) -> BlockVec3:
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 3:
        raise ValueError("Coordinates must be formatted as x,y,z.")
    return BlockVec3(int(parts[0]), int(parts[1]), int(parts[2]))


def _cmd_pos1(ctx: CommandContext) -> None:
    pos = _parse_xyz(ctx.tokens[0]) if ctx.tokens else ctx.actor.position
    msg = ctx.services.selections.select_pos1(ctx.actor.key, pos, lang=ctx.services.lang)
    ctx.actor.send_message(msg)


def _cmd_pos2(ctx: CommandContext) -> None:
    pos = _parse_xyz(ctx.tokens[0]) if ctx.tokens else ctx.actor.position
    msg = ctx.services.selections.select_pos2(ctx.actor.key, pos, lang=ctx.services.lang)
    ctx.actor.send_message(msg)


def _cmd_hpos1(ctx: CommandContext) -> None:
    ex, ey, ez = ctx.actor.eye_position
    hit = raycast_block(ctx.actor.world, ex, ey, ez, ctx.actor.yaw, ctx.actor.pitch, max_dist=128.0)
    if hit is None:
        raise ValueError(ctx.t("cmd.no_block_sight"))
    ctx.actor.send_message(ctx.services.selections.select_pos1(ctx.actor.key, hit, lang=ctx.services.lang))


def _cmd_hpos2(ctx: CommandContext) -> None:
    ex, ey, ez = ctx.actor.eye_position
    hit = raycast_block(ctx.actor.world, ex, ey, ez, ctx.actor.yaw, ctx.actor.pitch, max_dist=128.0)
    if hit is None:
        raise ValueError(ctx.t("cmd.no_block_sight"))
    ctx.actor.send_message(ctx.services.selections.select_pos2(ctx.actor.key, hit, lang=ctx.services.lang))


def _cmd_chunk(ctx: CommandContext) -> None:
    _flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"s", "c"})
    if pos_args:
        if "," in pos_args[0]:
            parts = pos_args[0].split(",")
            cx, cz = int(parts[0]), int(parts[1])
        else:
            cx, cz = ctx.actor.position.chunk_coords()
    else:
        cx, cz = ctx.actor.position.chunk_coords()
    x0, z0 = cx * 16, cz * 16
    lo = BlockVec3(x0, ctx.actor.world.min_y, z0)
    hi = BlockVec3(x0 + 15, ctx.actor.world.max_y, z0 + 15)
    sel = ctx.services.selections
    sel.set_mode(ctx.actor.key, "cuboid")
    sel.select_pos1(ctx.actor.key, lo, lang=ctx.services.lang)
    msg = sel.select_pos2(ctx.actor.key, hi, lang=ctx.services.lang)
    ctx.actor.send_message(ctx.t("sel.chunk", cx=cx, cz=cz, msg=msg))


def _cmd_wand(ctx: CommandContext) -> None:
    _flags, _, _ = parse_flags(ctx.tokens, bool_flags={"n"})
    sess = ctx.services.sessions.get(ctx.actor.key)
    item = sess.nav_wand_item if "n" in _flags else sess.wand_item
    if ctx.actor.give_item(item, 1):
        ctx.actor.send_message(ctx.t("sel.wand", item=item))
    else:
        ctx.actor.send_error(ctx.t("sel.wand_fail", item=item))


def _cmd_toggleeditwand(ctx: CommandContext) -> None:
    sess = ctx.services.sessions.get(ctx.actor.key)
    sess.wand_enabled = not sess.wand_enabled
    state = ctx.t("state.enabled" if sess.wand_enabled else "state.disabled")
    ctx.actor.send_message(ctx.t("sel.wand_toggle", state=state))


def _cmd_expand(ctx: CommandContext) -> None:
    region = ctx.services.selections.get_region(ctx.actor.key)
    if not ctx.tokens:
        raise ValueError("Usage: //expand <amount|vert> [reverse-amount] [direction]")
    if ctx.tokens[0].lower() in ("vert", "v"):
        lo = BlockVec3(region.min_point.x, ctx.actor.world.min_y, region.min_point.z)
        hi = BlockVec3(region.max_point.x, ctx.actor.world.max_y, region.max_point.z)
        if hasattr(region, "pos1") and hasattr(region, "pos2"):
            region.pos1 = lo
            region.pos2 = hi
        else:
            region.expand(BlockVec3(0, ctx.actor.world.min_y - region.min_point.y, 0))
            region.expand(BlockVec3(0, ctx.actor.world.max_y - region.max_point.y, 0))
        ctx.actor.send_message(ctx.t("sel.expand_vert", vol=region.volume))
        return

    amount = int(ctx.tokens[0])
    reverse_amt = 0
    dir_token: str | None = None
    if len(ctx.tokens) >= 2:
        try:
            reverse_amt = int(ctx.tokens[1])
            dir_token = ctx.tokens[2] if len(ctx.tokens) >= 3 else None
        except ValueError:
            dir_token = ctx.tokens[1]
    direction = resolve_direction(dir_token, yaw=ctx.actor.yaw, pitch=ctx.actor.pitch)
    before = region.volume
    region.expand(direction * amount)
    if reverse_amt:
        region.expand((-direction) * reverse_amt)
    after = region.volume
    ctx.actor.send_message(ctx.t("sel.expand", after=after, delta=after - before))


def _cmd_contract(ctx: CommandContext) -> None:
    region = ctx.services.selections.get_region(ctx.actor.key)
    if not ctx.tokens:
        raise ValueError("Usage: //contract <amount> [reverse-amount] [direction]")
    amount = int(ctx.tokens[0])
    reverse_amt = 0
    dir_token: str | None = None
    if len(ctx.tokens) >= 2:
        try:
            reverse_amt = int(ctx.tokens[1])
            dir_token = ctx.tokens[2] if len(ctx.tokens) >= 3 else None
        except ValueError:
            dir_token = ctx.tokens[1]
    direction = resolve_direction(dir_token, yaw=ctx.actor.yaw, pitch=ctx.actor.pitch)
    before = region.volume
    region.contract(direction * amount)
    if reverse_amt:
        region.contract((-direction) * reverse_amt)
    after = region.volume
    ctx.actor.send_message(ctx.t("sel.contract", after=after, delta=after - before))


def _cmd_outset(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"h", "v"})
    if not pos_args:
        raise ValueError("Usage: //outset [-hv] <amount>")
    amount = int(pos_args[0])
    region = ctx.services.selections.get_region(ctx.actor.key)
    region.outset(amount, h_only="h" in flags, v_only="v" in flags)
    ctx.actor.send_message(ctx.t("sel.outset", amount=amount, vol=region.volume))


def _cmd_inset(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"h", "v"})
    if not pos_args:
        raise ValueError("Usage: //inset [-hv] <amount>")
    amount = int(pos_args[0])
    region = ctx.services.selections.get_region(ctx.actor.key)
    region.inset(amount, h_only="h" in flags, v_only="v" in flags)
    ctx.actor.send_message(ctx.t("sel.inset", amount=amount, vol=region.volume))


def _cmd_shift(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //shift <amount> [direction]")
    amount = int(ctx.tokens[0])
    dir_tok = ctx.tokens[1] if len(ctx.tokens) >= 2 else None
    direction = resolve_direction(dir_tok, yaw=ctx.actor.yaw, pitch=ctx.actor.pitch)
    region = ctx.services.selections.get_region(ctx.actor.key)
    region.shift(direction * amount)
    ctx.actor.send_message(
        ctx.t("sel.shift", lo=region.min_point.format_short(), hi=region.max_point.format_short())
    )


def _cmd_size(ctx: CommandContext) -> None:
    # Support /size <num> as brush size shortcut when numeric argument is provided
    if ctx.tokens and not ctx.tokens[0].startswith("-"):
        try:
            new_radius = float(ctx.tokens[0])
            item = ctx.actor.hand_item
            brush = ctx.services.tools.get_brush(ctx.actor.key, item) if item else None
            if brush is not None:
                brush.size = new_radius
                ctx.actor.send_message(f"Brush size set to {new_radius:g}.")
                return
        except ValueError:
            pass

    flags, _, _ = parse_flags(ctx.tokens, bool_flags={"c"})
    if "c" in flags:
        cb = ctx.services.clipboards.get(ctx.actor.key)
        if cb is None:
            raise ValueError(ctx.t("clip.empty"))
        d = cb.dimensions
        ctx.actor.send_message(ctx.t("sel.size_clip", vol=cb.volume, dx=d.x, dy=d.y, dz=d.z))
        return

    region = ctx.services.selections.get_region(ctx.actor.key)
    d = region.dimensions
    ctx.actor.send_message(
        ctx.t(
            "sel.size",
            vol=region.volume,
            dx=d.x,
            dy=d.y,
            dz=d.z,
            lo=region.min_point.format_short(),
            hi=region.max_point.format_short(),
        )
    )


def _cmd_count(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //count <mask>")
    region = ctx.services.selections.get_region(ctx.actor.key)
    mask = parse_mask(" ".join(ctx.tokens), MaskContext(region=region, origin=region.min_point, hand_block=ctx.actor.hand_block))
    total = op_count(ctx.actor.world, region, mask)
    ctx.actor.send_message(ctx.t("sel.count", total=total))


def _cmd_distr(ctx: CommandContext) -> None:
    flags, _, _ = parse_flags(ctx.tokens, bool_flags={"c", "d"})
    region = ctx.services.selections.get_region(ctx.actor.key)
    total, rows = op_distr(ctx.actor.world, region, include_air=("d" not in flags))
    ctx.actor.send_message(ctx.t("sel.distr_hdr", total=total))
    for name, cnt, pct in rows[:12]:
        ctx.actor.send_message(f"  {cnt} ({pct:.2f}%) - {name}")


def _cmd_sel(ctx: CommandContext) -> None:
    if not ctx.tokens:
        ctx.services.selections.clear(ctx.actor.key)
        ctx.actor.send_message(ctx.t("sel.cleared"))
        return
    mode = ctx.tokens[0].lower()
    if mode not in SELECTOR_TYPES:
        valid = ", ".join(sorted(SELECTOR_TYPES))
        raise ValueError(f"Unknown selector type '{mode}'. Choose from: {valid}.")
    ctx.services.selections.set_mode(ctx.actor.key, mode)
    ctx.actor.send_message(ctx.t("sel.mode", mode=mode))


def _cmd_drawsel(ctx: CommandContext) -> None:
    sess = ctx.services.sessions.get(ctx.actor.key)
    sess.drawsel_enabled = not sess.drawsel_enabled
    state = ctx.t("state.enabled" if sess.drawsel_enabled else "state.disabled")
    ctx.actor.send_message(ctx.t("sel.drawsel", state=state))


def _cmd_toggleplace(ctx: CommandContext) -> None:
    sess = ctx.services.sessions.get(ctx.actor.key)
    sess.place_mode = "player" if sess.place_mode == "pos1" else "pos1"
    label = ctx.t("sel.place_player" if sess.place_mode == "player" else "sel.place_pos1")
    ctx.actor.send_message(ctx.t("sel.place", label=label))


def register(router: CommandRouter) -> None:
    specs = [
        CommandSpec("pos1", ("1",), "worldedit.selection.pos", "Set selection position #1.", "//pos1 [x,y,z]", "Selection", _cmd_pos1),
        CommandSpec("pos2", ("2",), "worldedit.selection.pos", "Set selection position #2.", "//pos2 [x,y,z]", "Selection", _cmd_pos2),
        CommandSpec("hpos1", (), "worldedit.selection.hpos", "Set position #1 at target block.", "//hpos1", "Selection", _cmd_hpos1),
        CommandSpec("hpos2", (), "worldedit.selection.hpos", "Set position #2 at target block.", "//hpos2", "Selection", _cmd_hpos2),
        CommandSpec("chunk", (), "worldedit.selection.chunk", "Select the chunk you are standing in.", "//chunk [x,z]", "Selection", _cmd_chunk),
        CommandSpec("wand", (), "worldedit.wand", "Give yourself the selection wand.", "//wand [-n]", "Selection", _cmd_wand),
        CommandSpec("toggleeditwand", ("tew",), "worldedit.wand.toggle", "Toggle edit wand mode.", "//toggleeditwand", "Selection", _cmd_toggleeditwand),
        CommandSpec("expand", (), "worldedit.selection.expand", "Expand selection region.", "//expand <amount|vert> [dir]", "Selection", _cmd_expand),
        CommandSpec("contract", (), "worldedit.selection.contract", "Contract selection region.", "//contract <amount> [dir]", "Selection", _cmd_contract),
        CommandSpec("outset", (), "worldedit.selection.outset", "Outset selection evenly.", "//outset [-hv] <amount>", "Selection", _cmd_outset),
        CommandSpec("inset", (), "worldedit.selection.inset", "Inset selection evenly.", "//inset [-hv] <amount>", "Selection", _cmd_inset),
        CommandSpec("shift", (), "worldedit.selection.shift", "Shift selection bounding box.", "//shift <amount> [dir]", "Selection", _cmd_shift),
        CommandSpec("size", (), "worldedit.selection.size", "Show selection or clipboard size.", "//size [-c]", "Selection", _cmd_size),
        CommandSpec("count", (), "worldedit.analysis.count", "Count blocks matching a mask.", "//count <mask>", "Selection", _cmd_count),
        CommandSpec("distr", (), "worldedit.analysis.distr", "Show block distribution in selection.", "//distr [-d]", "Selection", _cmd_distr),
        CommandSpec("sel", ("desel", "deselect", ";"), "worldedit.selection.clear", "Clear selection or switch mode.", "//sel [cuboid|extend|ellipsoid|sphere|cyl|poly|convex]", "Selection", _cmd_sel),
        CommandSpec("drawsel", (), "worldedit.selection.draw", "Toggle selection wireframe particles.", "//drawsel", "Selection", _cmd_drawsel),
        CommandSpec("toggleplace", (), "worldedit.toggleplace", "Toggle placement between pos1 and player.", "/toggleplace", "Selection", _cmd_toggleplace),
    ]
    for s in specs:
        router.register(s)
