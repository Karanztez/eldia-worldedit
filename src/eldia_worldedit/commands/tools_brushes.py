"""Brush, item tool, and Super Pickaxe commands (//br, //tool, //sp, /none, /mask, /mat, /range, /size)."""

from __future__ import annotations

from ..core.command_parser import parse_flags
from ..tools.brushes import BrushConfig
from ..tools.items import ToolConfig
from . import CommandContext, CommandRouter, CommandSpec


def _require_hand_item(ctx: CommandContext) -> str:
    item = ctx.actor.hand_item
    if not item or item == "minecraft:air":
        raise ValueError(ctx.t("cmd.hold_item"))
    return item


def _cmd_brush(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //br <sphere|cyl|cone|splatter|smooth|snowsmooth|clipboard|gravity|extinguish|butcher|height|deform|set|forest|feature|raise|lower|snow|biome|morph|erode|dilate|apply|paint|none> ...")
    sub = ctx.tokens[0].lower()
    rest = ctx.tokens[1:]
    item = _require_hand_item(ctx)

    if sub in ("none", "unbind"):
        removed = ctx.services.tools.unbind(ctx.actor.key, item)
        ctx.actor.send_message(f"Unbound brush from {item}." if removed else f"No brush bound on {item}.")
        return

    if sub == "mask":
        brush = ctx.services.tools.get_brush(ctx.actor.key, item)
        if brush is None:
            raise ValueError("Hold a bound brush to set its mask.")
        brush.mask = " ".join(rest) if rest else None
        ctx.actor.send_message("Brush mask cleared." if brush.mask is None else f"Brush mask set to: {brush.mask}")
        return

    if sub in ("mat", "material"):
        brush = ctx.services.tools.get_brush(ctx.actor.key, item)
        if brush is None or not rest:
            raise ValueError("Hold a bound brush and specify a pattern.")
        brush.pattern = " ".join(rest)
        ctx.actor.send_message(f"Brush material set to: {brush.pattern}")
        return

    if sub == "size":
        brush = ctx.services.tools.get_brush(ctx.actor.key, item)
        if brush is None or not rest:
            raise ValueError("Hold a bound brush and specify a radius.")
        brush.size = float(rest[0])
        ctx.actor.send_message(f"Brush radius set to {brush.radius:g}.")
        return

    if sub == "range":
        brush = ctx.services.tools.get_brush(ctx.actor.key, item)
        if brush is None or not rest:
            raise ValueError("Hold a bound brush and specify a max range.")
        brush.range_limit = max(1.0, float(rest[0]))
        ctx.actor.send_message(f"Brush range set to {brush.range_limit:g}.")
        return

    flags, _, pos_args = parse_flags(rest, bool_flags={"h", "a", "o", "e", "r", "p", "n", "g", "b", "f", "s"})

    if sub in ("s", "sphere"):
        pat = pos_args[0] if pos_args else "stone"
        rad = float(pos_args[1]) if len(pos_args) >= 2 else 3.0
        cfg = BrushConfig(kind="sphere", pattern=pat, radius=rad, hollow="h" in flags)
    elif sub in ("c", "cyl", "cylinder"):
        pat = pos_args[0] if pos_args else "stone"
        rad = float(pos_args[1]) if len(pos_args) >= 2 else 3.0
        h = int(pos_args[2]) if len(pos_args) >= 3 else 1
        cfg = BrushConfig(kind="cylinder", pattern=pat, radius=rad, height=h, hollow="h" in flags)
    elif sub == "cone":
        pat = pos_args[0] if pos_args else "stone"
        rad = float(pos_args[1]) if len(pos_args) >= 2 else 4.0
        h = int(pos_args[2]) if len(pos_args) >= 3 else 5
        cfg = BrushConfig(kind="cone", pattern=pat, radius=rad, height=h, hollow="h" in flags)
    elif sub == "splatter":
        pat = pos_args[0] if pos_args else "stone"
        rad = float(pos_args[1]) if len(pos_args) >= 2 else 4.0
        cfg = BrushConfig(kind="splatter", pattern=pat, radius=rad)
    elif sub in ("clipboard", "copy"):
        cfg = BrushConfig(
            kind="clipboard",
            radius=5.0,
            extra={"ignore_air": "a" in flags, "use_origin": "o" in flags},
        )
    elif sub == "smooth":
        rad = float(pos_args[0]) if pos_args else 3.0
        iters = int(pos_args[1]) if len(pos_args) >= 2 else 1
        cfg = BrushConfig(kind="smooth", radius=rad, iterations=iters)
    elif sub == "snowsmooth":
        rad = float(pos_args[0]) if pos_args else 3.0
        iters = int(pos_args[1]) if len(pos_args) >= 2 else 1
        snow_blocks = int(pos_args[2]) if len(pos_args) >= 3 else 1
        cfg = BrushConfig(kind="snowsmooth", radius=rad, iterations=iters, extra={"snow_blocks": snow_blocks})
    elif sub in ("ex", "extinguish"):
        rad = float(pos_args[0]) if pos_args else 5.0
        cfg = BrushConfig(kind="extinguish", radius=rad)
    elif sub in ("grav", "gravity"):
        rad = float(pos_args[0]) if pos_args else 5.0
        cfg = BrushConfig(kind="gravity", radius=rad, extra={"hard": "h" in flags})
    elif sub == "butcher":
        rad = float(pos_args[0]) if pos_args else 8.0
        cfg = BrushConfig(kind="butcher", radius=rad, extra={"flags": flags})
    elif sub in ("height", "heightmap"):
        rad = float(pos_args[0]) if pos_args else 5.0
        scale = int(float(pos_args[1])) if len(pos_args) >= 2 else 4
        pat = pos_args[2] if len(pos_args) >= 3 else "grass_block"
        cfg = BrushConfig(kind="heightmap", pattern=pat, radius=rad, height=scale)
    elif sub == "deform":
        rad = float(pos_args[0]) if pos_args else 5.0
        expr = " ".join(pos_args[1:]) if len(pos_args) >= 2 else "y+=0.2*sin(x*3)"
        cfg = BrushConfig(
            kind="deform", radius=rad,
            extra={"expr": expr, "raw_coords": "r" in flags, "offset_mode": "o" in flags},
        )
    elif sub == "set":
        pat = pos_args[0] if pos_args else "stone"
        rad = float(pos_args[1]) if len(pos_args) >= 2 else 3.0
        cfg = BrushConfig(kind="set", pattern=pat, radius=rad)
    elif sub == "forest":
        rad = float(pos_args[0]) if pos_args else 6.0
        tree_type = pos_args[1] if len(pos_args) >= 2 else "oak"
        density = float(pos_args[2]) if len(pos_args) >= 3 else 8.0
        cfg = BrushConfig(kind="forest", radius=rad, density=density, extra={"tree_type": tree_type})
    elif sub == "feature":
        tree_type = pos_args[0] if pos_args else "oak"
        cfg = BrushConfig(kind="feature", radius=1.0, extra={"tree_type": tree_type})
    elif sub == "raise":
        rad = float(pos_args[0]) if pos_args else 5.0
        h = int(pos_args[1]) if len(pos_args) >= 2 else 2
        cfg = BrushConfig(kind="raise", radius=rad, height=h)
    elif sub == "lower":
        rad = float(pos_args[0]) if pos_args else 5.0
        h = int(pos_args[1]) if len(pos_args) >= 2 else 2
        cfg = BrushConfig(kind="lower", radius=rad, height=h)
    elif sub == "snow":
        rad = float(pos_args[0]) if pos_args else 5.0
        cfg = BrushConfig(kind="snow", radius=rad, extra={"stack": "s" in flags})
    elif sub == "biome":
        rad = float(pos_args[0]) if pos_args else 5.0
        biome_name = pos_args[1] if len(pos_args) >= 2 else "plains"
        cfg = BrushConfig(kind="biome", radius=rad, extra={"biome": biome_name})
    elif sub == "morph":
        rad = float(pos_args[0]) if pos_args else 4.0
        cfg = BrushConfig(kind="morph", radius=rad)
    elif sub == "erode":
        rad = float(pos_args[0]) if pos_args else 4.0
        iters = int(pos_args[1]) if len(pos_args) >= 2 else 1
        cfg = BrushConfig(kind="erode", radius=rad, iterations=iters)
    elif sub == "dilate":
        rad = float(pos_args[0]) if pos_args else 4.0
        iters = int(pos_args[1]) if len(pos_args) >= 2 else 1
        cfg = BrushConfig(kind="dilate", radius=rad, iterations=iters)
    elif sub == "apply":
        shape = pos_args[0] if pos_args else "sphere"
        pat = pos_args[1] if len(pos_args) >= 2 else "stone"
        rad = float(pos_args[2]) if len(pos_args) >= 3 else 4.0
        cfg = BrushConfig(kind="apply", pattern=pat, radius=rad, extra={"shape": shape})
    elif sub == "paint":
        rad = float(pos_args[0]) if pos_args else 5.0
        density = float(pos_args[1]) if len(pos_args) >= 2 else 15.0
        mode = pos_args[2] if len(pos_args) >= 3 else "flora"
        cfg = BrushConfig(kind="paint", radius=rad, density=density, extra={"paint_mode": mode})
    else:
        raise ValueError(f"Unknown brush type '{sub}'.")

    ctx.services.tools.bind_brush(ctx.actor.key, item, cfg)
    ctx.actor.send_message(
        ctx.t("tool.brush_bound", kind=cfg.kind, radius=f"{cfg.radius:g}", pattern=cfg.pattern, item=item)
    )


def _bind_tool_kind(ctx: CommandContext, kind: str, params: dict | None = None) -> None:
    item = _require_hand_item(ctx)
    ctx.services.tools.bind_tool(ctx.actor.key, item, ToolConfig(kind=kind, params=params or {}))
    ctx.actor.send_message(ctx.t("tool.bound", kind=kind, item=item))


def _cmd_tool(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: /tool <selwand|navwand|info|tree|stack|repl|cycler|floodfill|deltree|farwand|lrbuild|none|unbindall> ...")
    sub = ctx.tokens[0].lower()
    rest = ctx.tokens[1:]
    if sub in ("none", "unbind"):
        item = _require_hand_item(ctx)
        removed = ctx.services.tools.unbind(ctx.actor.key, item)
        ctx.actor.send_message(ctx.t("tool.unbound", item=item) if removed else f"No tool bound on {item}.")
        return
    if sub == "unbindall":
        cnt = ctx.services.tools.unbind_all(ctx.actor.key)
        ctx.actor.send_message(ctx.t("tool.unbound_all", count=cnt))
        return
    if sub == "selwand":
        _bind_tool_kind(ctx, "selwand")
    elif sub == "navwand":
        _bind_tool_kind(ctx, "navwand")
    elif sub == "info":
        _bind_tool_kind(ctx, "info")
    elif sub == "tree":
        _bind_tool_kind(ctx, "tree", {"tree_type": rest[0] if rest else "oak"})
    elif sub in ("stack", "stacker"):
        max_r = int(rest[0]) if rest else 8
        mask_str = " ".join(rest[1:]) if len(rest) >= 2 else None
        _bind_tool_kind(ctx, "stacker", {"max_range": max_r, "mask": mask_str})
    elif sub == "repl":
        if not rest:
            raise ValueError("Usage: /tool repl <pattern>")
        _bind_tool_kind(ctx, "repl", {"pattern": " ".join(rest)})
    elif sub == "cycler":
        _bind_tool_kind(ctx, "cycler", {"prop_index": 0})
    elif sub in ("flood", "floodfill"):
        max_r = int(rest[0]) if rest else 10
        pat = " ".join(rest[1:]) if len(rest) >= 2 else "stone"
        _bind_tool_kind(ctx, "floodfill", {"range": max_r, "pattern": pat})
    elif sub == "deltree":
        _bind_tool_kind(ctx, "deltree")
    elif sub == "farwand":
        _bind_tool_kind(ctx, "farwand")
    elif sub == "lrbuild":
        if len(rest) < 2:
            raise ValueError("Usage: /tool lrbuild <left-pattern> <right-pattern>")
        _bind_tool_kind(ctx, "lrbuild", {"left_pattern": rest[0], "right_pattern": rest[1]})
    else:
        raise ValueError(f"Unknown tool type '{sub}'.")


def _cmd_superpickaxe(ctx: CommandContext) -> None:
    cfg = ctx.services.tools.get_super_pickaxe(ctx.actor.key)
    if not ctx.tokens or ctx.tokens[0].lower() == "toggle":
        cfg.enabled = not cfg.enabled
        state = ctx.t("state.enabled" if cfg.enabled else "state.disabled")
        ctx.actor.send_message(ctx.t("tool.sp_toggle", state=state, mode=cfg.mode))
        return
    sub = ctx.tokens[0].lower()
    if sub == "single":
        cfg.enabled = True
        cfg.mode = "single"
        ctx.actor.send_message(ctx.t("tool.sp_mode", mode="single"))
        return
    if sub == "area":
        cfg.enabled = True
        cfg.mode = "area"
        cfg.radius = max(1, min(5, int(ctx.tokens[1]) if len(ctx.tokens) >= 2 else 1))
        ctx.actor.send_message(ctx.t("tool.sp_mode", mode=f"area (r={cfg.radius})"))
        return
    if sub in ("recur", "recursive"):
        cfg.enabled = True
        cfg.mode = "recursive"
        cfg.radius = max(1, min(5, int(ctx.tokens[1]) if len(ctx.tokens) >= 2 else 3))
        ctx.actor.send_message(ctx.t("tool.sp_mode", mode=f"recursive (r={cfg.radius})"))
        return
    raise ValueError("Usage: //sp <toggle|single|area <r>|recursive <r>>")


def _cmd_none(ctx: CommandContext) -> None:
    item = _require_hand_item(ctx)
    removed = ctx.services.tools.unbind(ctx.actor.key, item)
    ctx.actor.send_message(ctx.t("tool.unbound", item=item) if removed else f"Nothing bound on {item}.")


def _cmd_mat(ctx: CommandContext) -> None:
    item = _require_hand_item(ctx)
    brush = ctx.services.tools.get_brush(ctx.actor.key, item)
    if brush is None or not ctx.tokens:
        raise ValueError("Hold a bound brush and pass a pattern: /mat <pattern>")
    brush.pattern = " ".join(ctx.tokens)
    ctx.actor.send_message(f"Brush material set to {brush.pattern}.")


def _cmd_range(ctx: CommandContext) -> None:
    item = _require_hand_item(ctx)
    brush = ctx.services.tools.get_brush(ctx.actor.key, item)
    if brush is None or not ctx.tokens:
        raise ValueError("Hold a bound brush and pass a range: /range <blocks>")
    brush.range_limit = max(1.0, float(ctx.tokens[0]))
    ctx.actor.send_message(f"Brush range set to {brush.range_limit:g}.")


def _cmd_mask(ctx: CommandContext) -> None:
    item = _require_hand_item(ctx)
    brush = ctx.services.tools.get_brush(ctx.actor.key, item)
    if brush is None:
        raise ValueError("Hold a bound brush to set its mask.")
    brush.mask = " ".join(ctx.tokens) if ctx.tokens else None
    ctx.actor.send_message("Brush mask cleared." if brush.mask is None else f"Brush mask set to: {brush.mask}")


def _cmd_smask(ctx: CommandContext) -> None:
    item = _require_hand_item(ctx)
    brush = ctx.services.tools.get_brush(ctx.actor.key, item)
    if brush is None:
        raise ValueError("Hold a bound brush to set its source mask.")
    brush.extra["source_mask"] = " ".join(ctx.tokens) if ctx.tokens else None
    ctx.actor.send_message("Brush source mask updated.")


def _cmd_tracemask(ctx: CommandContext) -> None:
    item = _require_hand_item(ctx)
    brush = ctx.services.tools.get_brush(ctx.actor.key, item)
    if brush is None:
        raise ValueError("Hold a bound brush to set its trace mask.")
    brush.trace_mask = " ".join(ctx.tokens) if ctx.tokens else None
    ctx.actor.send_message("Brush trace mask updated.")


def register(router: CommandRouter) -> None:
    specs = [
        CommandSpec("brush", ("br",), "worldedit.brush", "Bind or configure a terrain brush.", "//br <type> ...", "Brushes", _cmd_brush),
        CommandSpec("tool", (), "worldedit.tool", "Bind or unbind an item tool.", "/tool <type> ...", "Tools", _cmd_tool),
        CommandSpec("superpickaxe", ("sp", "togglepickaxe", ","), "worldedit.superpickaxe", "Toggle or configure Super Pickaxe.", "//sp [single|area|recursive] [radius]", "Tools", _cmd_superpickaxe),
        CommandSpec("none", (), "worldedit.tool.none", "Unbind brush or tool from held item.", "/none", "Tools", _cmd_none),
        CommandSpec("info", (), "worldedit.tool.info", "Bind block inspection tool.", "/info", "Tools", lambda c: _bind_tool_kind(c, "info")),
        CommandSpec("tree", (), "worldedit.tool.tree", "Bind tree generator tool.", "/tree [type]", "Tools", lambda c: _bind_tool_kind(c, "tree", {"tree_type": c.tokens[0] if c.tokens else "oak"})),
        CommandSpec("repl", (), "worldedit.tool.replacer", "Bind block replacer tool.", "/repl <pattern>", "Tools", lambda c: _bind_tool_kind(c, "repl", {"pattern": " ".join(c.tokens) if c.tokens else "stone"})),
        CommandSpec("cycler", (), "worldedit.tool.data-cycler", "Bind block state cycler tool.", "/cycler", "Tools", lambda c: _bind_tool_kind(c, "cycler", {"prop_index": 0})),
        CommandSpec("stacker", (), "worldedit.tool.stacker", "Bind block stacker tool.", "/stacker [range] [mask]", "Tools", lambda c: _bind_tool_kind(c, "stacker", {"max_range": int(c.tokens[0]) if c.tokens else 8})),
        CommandSpec("floodfill", ("flood",), "worldedit.tool.flood-fill", "Bind 3D flood-fill tool.", "/floodfill [range] [pattern]", "Tools", lambda c: _bind_tool_kind(c, "floodfill", {"range": int(c.tokens[0]) if c.tokens else 10, "pattern": c.tokens[1] if len(c.tokens) >= 2 else "stone"})),
        CommandSpec("deltree", (), "worldedit.tool.deltree", "Bind floating-tree remover tool.", "/deltree", "Tools", lambda c: _bind_tool_kind(c, "deltree")),
        CommandSpec("farwand", (), "worldedit.tool.farwand", "Bind long-range selection wand.", "/farwand", "Tools", lambda c: _bind_tool_kind(c, "farwand")),
        CommandSpec("lrbuild", (), "worldedit.tool.lrbuild", "Bind long-range block builder tool.", "/lrbuild <left> <right>", "Tools", lambda c: _bind_tool_kind(c, "lrbuild", {"left_pattern": c.tokens[0] if len(c.tokens) >= 2 else "stone", "right_pattern": c.tokens[1] if len(c.tokens) >= 2 else "air"})),
        CommandSpec("mat", ("material",), "worldedit.brush.options.material", "Set held brush material pattern.", "/mat <pattern>", "Brushes", _cmd_mat),
        CommandSpec("range", (), "worldedit.brush.options.range", "Set held brush max raycast range.", "/range <blocks>", "Brushes", _cmd_range),
        CommandSpec("mask", (), "worldedit.brush.options.mask", "Set held brush destination mask.", "/mask [mask]", "Brushes", _cmd_mask),
        CommandSpec("smask", (), "worldedit.brush.options.mask", "Set held brush source mask.", "/smask [mask]", "Brushes", _cmd_smask),
        CommandSpec("tracemask", (), "worldedit.brush.options.tracemask", "Set held brush raycast trace mask.", "/tracemask [mask]", "Brushes", _cmd_tracemask),
    ]
    for s in specs:
        router.register(s)
