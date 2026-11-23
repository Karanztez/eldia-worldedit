"""General, Biome, Chunk, Snapshot, Scripting, and Global Session commands (/we, //gmask, //fast, //limit, //snap, /cs)."""

from __future__ import annotations

from ..core.command_parser import parse_flags
from ..core.masks import MaskContext, parse_mask
from ..core.types import KNOWN_BEDROCK_BIOMES, KNOWN_BEDROCK_BLOCKS
from ..world.generators import op_biome_set
from ..world.navigation import raycast_block
from . import CommandContext, CommandRouter, CommandSpec


def _cmd_worldedit(ctx: CommandContext) -> None:
    if not ctx.tokens:
        specs = ctx.router.all_specs()
        ctx.actor.send_message(ctx.t("gen.info", count=len(specs)))
        return

    sub = ctx.tokens[0].lower()
    rest = ctx.tokens[1:]

    if sub in ("version", "ver"):
        ctx.actor.send_message(ctx.t("gen.version"))
        return

    if sub == "lang":
        if not rest:
            ctx.actor.send_message(f"Current language: {ctx.services.lang.language} (en / th)")
            return
        new_lang = ctx.services.lang.set_language(rest[0])
        ctx.services.config.config.language = new_lang
        ctx.services.config.save()
        ctx.actor.send_message(ctx.t("gen.lang_set", lang=new_lang))
        return

    if sub in ("gui", "ui"):
        ctx.require_player()
        if ctx.actor.raw_player is None:
            raise ValueError("Interactive Bedrock Forms require a live Endstone player.")
        sess = ctx.services.sessions.get(ctx.actor.key)
        summary = f"Limit: {sess.block_change_limit} | Fast: {sess.fast_mode} | Wand: {sess.wand_enabled}"
        ctx.services.ui.open_main_menu(ctx.actor.raw_player, summary, lang=ctx.services.lang)
        return

    if sub == "cui":
        ctx.require_player()
        sess = ctx.services.sessions.get(ctx.actor.key)
        sess.drawsel_enabled = not sess.drawsel_enabled
        state = ctx.t("state.enabled" if sess.drawsel_enabled else "state.disabled")
        ctx.actor.send_message(ctx.t("sel.drawsel", state=state))
        return

    if sub == "reload":
        cfg = ctx.services.reload_config()
        ctx.actor.send_message(ctx.t("gen.reloaded", lang=cfg.language, prefix=cfg.prefix))
        return

    if sub == "report":
        undo_d, redo_d = ctx.services.history.stats(ctx.actor.key)
        sess = ctx.services.sessions.get(ctx.actor.key)
        ctx.actor.send_message(
            f"[Report] World: {ctx.actor.world.name} | History: undo={undo_d}, redo={redo_d} | Limit: {sess.block_change_limit}"
        )
        return

    if sub == "tz":
        ctx.actor.send_message("Server timezone: UTC (configure via host environment).")
        return

    if sub in ("help", "commands"):
        all_specs = ctx.router.all_specs()
        if rest and not rest[0].isdigit():
            query = rest[0].lower().lstrip("/")
            found = ctx.router.find(query)
            if found is not None:
                aliases = ", ".join(found.aliases) if found.aliases else "none"
                ctx.actor.send_message(f"{found.usage} - {found.description} (aliases: {aliases})")
                return
            matches = [s for s in all_specs if query in s.name or query in s.description.lower()][:10]
            for s in matches:
                ctx.actor.send_message(f"  {s.usage} - {s.description}")
            return
        page = max(1, int(rest[0])) if rest and rest[0].isdigit() else 1
        per_page = 10
        pages = max(1, (len(all_specs) + per_page - 1) // per_page)
        page = min(page, pages)
        chunk = all_specs[(page - 1) * per_page : page * per_page]
        ctx.actor.send_message(f"--- Eldia WorldEdit Help (Page {page}/{pages}) ---")
        for s in chunk:
            ctx.actor.send_message(f"  {s.usage} - {s.description}")
        return

    if ctx.router.find(sub) is not None:
        ctx.router.dispatch(ctx.actor, sub, " ".join(rest), scheduler=ctx.scheduler, plugin=ctx.plugin)
        return

    raise ValueError(f"Unknown subcommand '{sub}'. Try /ewe help.")


def _cmd_gmask(ctx: CommandContext) -> None:
    sess = ctx.services.sessions.get(ctx.actor.key)
    if not ctx.tokens:
        sess.gmask_expr = None
        ctx.actor.send_message(ctx.t("gen.gmask_clear"))
        return
    expr = " ".join(ctx.tokens)
    parse_mask(expr, MaskContext(origin=ctx.actor.position, hand_block=ctx.actor.hand_block))
    sess.gmask_expr = expr
    ctx.actor.send_message(ctx.t("gen.gmask_set", expr=expr))


def _cmd_gtransform(ctx: CommandContext) -> None:
    sess = ctx.services.sessions.get(ctx.actor.key)
    if not ctx.tokens:
        sess.gtransform_expr = None
        ctx.actor.send_message("Global clipboard transform cleared.")
        return
    sess.gtransform_expr = " ".join(ctx.tokens)
    ctx.actor.send_message(f"Global transform set to: {sess.gtransform_expr}")


def _cmd_fast(ctx: CommandContext) -> None:
    sess = ctx.services.sessions.get(ctx.actor.key)
    sess.fast_mode = not sess.fast_mode
    state = ctx.t("state.enabled" if sess.fast_mode else "state.disabled")
    ctx.actor.send_message(ctx.t("gen.fast", state=state))


def _cmd_perf(ctx: CommandContext) -> None:
    sess = ctx.services.sessions.get(ctx.actor.key)
    if not ctx.tokens:
        modes = ("none", "multi_stage", "bottom_up")
        idx = (modes.index(sess.reorder_mode) + 1) % len(modes) if sess.reorder_mode in modes else 0
        sess.reorder_mode = modes[idx]
    else:
        mode = ctx.tokens[0].lower()
        alias = {"off": "none", "none": "none", "on": "multi_stage", "multi": "multi_stage", "multi_stage": "multi_stage", "bottom": "bottom_up", "bottom_up": "bottom_up"}
        if mode not in alias:
            raise ValueError("Usage: //perf [none|multi_stage|bottom_up]")
        sess.reorder_mode = alias[mode]
    ctx.actor.send_message(f"Placement reorder mode set to '{sess.reorder_mode}'.")


def _cmd_limit(ctx: CommandContext) -> None:
    if not ctx.tokens:
        sess = ctx.services.sessions.get(ctx.actor.key)
        ctx.actor.send_message(f"Current block change limit: {sess.block_change_limit}")
        return
    val = int(ctx.tokens[0])
    applied = ctx.services.sessions.set_limit(ctx.actor.key, val)
    ctx.actor.send_message(ctx.t("gen.limit", limit=applied))


def _cmd_timeout(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //timeout <milliseconds>")
    sess = ctx.services.sessions.get(ctx.actor.key)
    sess.timeout_ms = max(100, int(ctx.tokens[0]))
    ctx.actor.send_message(f"Operation timeout set to {sess.timeout_ms}ms.")


def _cmd_searchitem(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: /searchitem <query>")
    q = " ".join(ctx.tokens).strip().lower()
    matches = [b for b in KNOWN_BEDROCK_BLOCKS if q in b][:15]
    if not matches:
        ctx.actor.send_message(f"No blocks found matching '{q}'.")
        return
    ctx.actor.send_message(f"Matches for '{q}' ({len(matches)} shown):")
    for m in matches:
        ctx.actor.send_message(f"  - {m}")


def _cmd_biomeinfo(ctx: CommandContext) -> None:
    flags, _, _ = parse_flags(ctx.tokens, bool_flags={"p", "t"})
    if "t" in flags:
        ex, ey, ez = ctx.actor.eye_position
        pos = raycast_block(ctx.actor.world, ex, ey, ez, ctx.actor.yaw, ctx.actor.pitch) or ctx.actor.position
    else:
        pos = ctx.actor.position
    biome = ctx.actor.world.get_biome(pos)
    ctx.actor.send_message(f"Biome at {pos.format_short()}: {biome}")


def _cmd_biomelist(ctx: CommandContext) -> None:
    page = max(1, int(ctx.tokens[0])) if ctx.tokens and ctx.tokens[0].isdigit() else 1
    per_page = 12
    pages = max(1, (len(KNOWN_BEDROCK_BIOMES) + per_page - 1) // per_page)
    page = min(page, pages)
    items = KNOWN_BEDROCK_BIOMES[(page - 1) * per_page : page * per_page]
    ctx.actor.send_message(f"--- Biomes (Page {page}/{pages}) ---")
    ctx.actor.send_message(", ".join(items))


def _cmd_setbiome(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"p"})
    if not pos_args:
        raise ValueError("Usage: //setbiome [-p] <biome>")
    biome_name = pos_args[0].lower()
    if "p" in flags:
        ctx.actor.world.set_biome(ctx.actor.position, biome_name)
        ctx.actor.send_message(f"Set biome at {ctx.actor.position.format_short()} to '{biome_name}'.")
        return
    region = ctx.services.selections.get_region(ctx.actor.key)
    cnt = op_biome_set(ctx.actor.world, region, biome_name)
    ctx.actor.send_message(ctx.t("gen.biome_set", biome=biome_name, count=cnt))


def _cmd_chunkinfo(ctx: CommandContext) -> None:
    cx, cz = ctx.actor.position.chunk_coords()
    ctx.actor.send_message(
        f"Chunk ({cx}, {cz}) | Block origin ({cx * 16}, {cz * 16}) .. ({cx * 16 + 15}, {cz * 16 + 15})"
    )


def _cmd_listchunks(ctx: CommandContext) -> None:
    chunks = ctx.actor.world.get_loaded_chunks()
    ctx.actor.send_message(f"Loaded chunks ({len(chunks)}): {', '.join(f'({c[0]},{c[1]})' for c in chunks[:15])}")


def _cmd_delchunks(ctx: CommandContext) -> None:
    ctx.actor.send_message("Chunk pruning queued cleanly (non-destructive dry summary on live BDS).")


def _cmd_snapshot(ctx: CommandContext) -> None:
    if not ctx.tokens:
        raise ValueError("Usage: //snap <save|list|use|sel|before|after> ...")
    sub = ctx.tokens[0].lower()
    rest = ctx.tokens[1:]
    sman = ctx.services.snapshots

    if sub == "save":
        flags, _, pos_args = parse_flags(rest, bool_flags={"f"})
        region = ctx.services.selections.get_region(ctx.actor.key)
        name = pos_args[0] if pos_args else f"snap_{int(__import__('time').time())}"
        entry = sman.save_snapshot(name, ctx.actor.world, region, overwrite="f" in flags)
        sman.select_snapshot(ctx.actor.key, entry.name)
        ctx.actor.send_message(ctx.t("snap.saved", name=entry.name, vol=region.volume))
        return

    if sub == "list":
        snaps = sman.list_snapshots()
        if not snaps:
            ctx.actor.send_message("No snapshots stored.")
            return
        ctx.actor.send_message(f"Snapshots ({len(snaps)}):")
        for idx, s in enumerate(snaps[:10], start=1):
            ctx.actor.send_message(f"  {idx}. {s.name} ({s.dimension})")
        return

    if sub == "use":
        if not rest:
            raise ValueError("Usage: //snap use <name|latest>")
        chosen = sman.select_snapshot(ctx.actor.key, rest[0])
        ctx.actor.send_message(f"Now using snapshot '{chosen.name}'.")
        return

    if sub == "sel":
        if not rest:
            raise ValueError("Usage: //snap sel <index>")
        snaps = sman.list_snapshots()
        idx = int(rest[0]) - 1
        if not (0 <= idx < len(snaps)):
            raise ValueError("Snapshot index out of range.")
        chosen = sman.select_snapshot(ctx.actor.key, snaps[idx].name)
        ctx.actor.send_message(f"Selected snapshot #{idx + 1}: {chosen.name}")
        return

    if sub in ("before", "after"):
        if not rest:
            raise ValueError(f"Usage: //snap {sub} <unix_timestamp>")
        ts = float(rest[0])
        chosen = sman.select_by_time(ctx.actor.key, ts, before=(sub == "before"))
        ctx.actor.send_message(f"Selected snapshot '{chosen.name}'.")
        return

    raise ValueError(f"Unknown snapshot subcommand '{sub}'.")


def _cmd_restore(ctx: CommandContext) -> None:
    flags, _, pos_args = parse_flags(ctx.tokens, bool_flags={"a"})
    region = ctx.services.selections.get_region(ctx.actor.key)
    snap_name = pos_args[0] if pos_args else None
    session = ctx.create_edit_session("restore")
    used_name, changed = ctx.services.snapshots.restore_region(
        ctx.actor.key, session, region, snapshot_name=snap_name, only_air="a" in flags
    )
    ctx.commit_edit(session, ctx.t("snap.restored", count=changed, name=used_name))


def _cmd_cs(ctx: CommandContext) -> None:
    if not ctx.tokens:
        scripts = ctx.services.scripts.list_scripts()
        ctx.actor.send_message(
            f"Available CraftScripts ({len(scripts)}): {', '.join(scripts) or 'none'}"
        )
        return
    filename = ctx.tokens[0]
    script_args = ctx.tokens[1:]
    lines = ctx.services.scripts.load_script_lines(filename, script_args)
    ctx.services.scripts.record_last_script(ctx.actor.key, filename, script_args)
    ran = 0
    for line in lines:
        if ctx.router.dispatch_line(ctx.actor, line, scheduler=ctx.scheduler, plugin=ctx.plugin):
            ran += 1
    ctx.actor.send_message(f"Executed CraftScript '{filename}' ({ran} step(s)).")


def _cmd_repeat_script(ctx: CommandContext) -> None:
    last_script = ctx.services.scripts.get_last_script(ctx.actor.key)
    if ctx.tokens and last_script is not None:
        filename, _ = last_script
        lines = ctx.services.scripts.load_script_lines(filename, ctx.tokens)
        ran = 0
        for line in lines:
            if ctx.router.dispatch_line(ctx.actor, line, scheduler=ctx.scheduler, plugin=ctx.plugin):
                ran += 1
        ctx.actor.send_message(f"Re-ran CraftScript '{filename}' ({ran} step(s)).")
        return

    last_cmd = ctx.services.scripts.get_last_command(ctx.actor.key)
    if not last_cmd:
        raise ValueError("No previous script or command recorded to repeat (/.s).")
    ctx.router.dispatch_line(ctx.actor, last_cmd, scheduler=ctx.scheduler, plugin=ctx.plugin)


def register(router: CommandRouter) -> None:
    specs = [
        CommandSpec("worldedit", ("ewe", "we"), "worldedit.help", "Eldia WorldEdit info, GUI, lang, help, and router.", "/ewe <version|help|gui|lang|reload|cui|report>", "General", _cmd_worldedit, player_only=False),
        CommandSpec("gmask", (), "worldedit.global-mask", "Set global edit mask.", "//gmask [mask]", "General", _cmd_gmask),
        CommandSpec("gtransform", (), "worldedit.global-transform", "Set global clipboard transform.", "//gtransform [transform]", "General", _cmd_gtransform),
        CommandSpec("fast", (), "worldedit.fast", "Toggle fast mode (disables physics updates).", "//fast", "General", _cmd_fast),
        CommandSpec("perf", ("reorder",), "worldedit.perf", "Set placement reorder strategy.", "//perf [none|multi_stage|bottom_up]", "General", _cmd_perf),
        CommandSpec("limit", (), "worldedit.limit", "Set per-edit block change limit.", "//limit [count]", "General", _cmd_limit),
        CommandSpec("timeout", (), "worldedit.timeout", "Set per-edit timeout in milliseconds.", "//timeout <ms>", "General", _cmd_timeout),
        CommandSpec("searchitem", ("search",), "worldedit.searchitem", "Search Bedrock block IDs.", "/searchitem <query>", "General", _cmd_searchitem, player_only=False),
        CommandSpec("biomeinfo", (), "worldedit.biome.info", "Inspect biome at your location.", "/biomeinfo [-pt]", "Biome", _cmd_biomeinfo),
        CommandSpec("biomelist", (), "worldedit.biome.list", "List known Bedrock biomes.", "/biomelist [page]", "Biome", _cmd_biomelist, player_only=False),
        CommandSpec("setbiome", (), "worldedit.biome.set", "Set biome in selection.", "//setbiome [-p] <biome>", "Biome", _cmd_setbiome),
        CommandSpec("chunkinfo", (), "worldedit.chunkinfo", "Show chunk coordinates.", "/chunkinfo", "Chunk", _cmd_chunkinfo),
        CommandSpec("listchunks", (), "worldedit.listchunks", "List loaded chunks in world.", "/listchunks", "Chunk", _cmd_listchunks, player_only=False),
        CommandSpec("delchunks", (), "worldedit.delchunks", "Chunk pruning placeholder summary.", "/delchunks", "Chunk", _cmd_delchunks, player_only=False),
        CommandSpec("snapshot", ("snap",), "worldedit.snapshots", "Save, list, and pick backup snapshots.", "//snap <save|list|use|sel|before|after>", "Snapshot", _cmd_snapshot, player_only=False),
        CommandSpec("restore", (), "worldedit.snapshots.restore", "Restore selection from selected snapshot.", "//restore [-a] [name]", "Snapshot", _cmd_restore),
        CommandSpec("cs", (), "worldedit.scripting.execute", "Run a CraftScript macro file.", "/cs <file> [args...]", "Scripting", _cmd_cs),
        CommandSpec(".s", (), "worldedit.scripting.execute", "Repeat last CraftScript or WorldEdit command.", "/.s [args...]", "Scripting", _cmd_repeat_script),
    ]
    for s in specs:
        router.register(s)
