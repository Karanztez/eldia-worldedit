"""Tests for Brushes, Bound Tools, Super Pickaxe, Config/Thai i18n, Debounce, Snapshots, and Endstone Plugin."""

import inspect
from pathlib import Path

from endstone.event import Event

from eldia_worldedit.commands import (
    VANILLA_COMMANDS,
    CommandRouter,
    MockCommandActor,
    register_all_commands,
    rewrite_double_slash_command,
)
from eldia_worldedit.core.types import AIR_SPEC, BlockSpec, BlockVec3
from eldia_worldedit.managers import WorldEditServices
from eldia_worldedit.plugin import WorldEditPlugin
from eldia_worldedit.tools.brushes import execute_brush
from eldia_worldedit.tools.items import execute_super_pickaxe, execute_tool


def test_brushes_tools_and_super_pickaxe(tmp_path: Path):
    services = WorldEditServices.create(tmp_path)
    router = CommandRouter(services)
    register_all_commands(router)
    actor = MockCommandActor(_hand_item="minecraft:arrow")

    # Bind & configure sphere brush
    router.dispatch_line(actor, "//br sphere stone 2")
    router.dispatch_line(actor, "/mat granite")
    router.dispatch_line(actor, "/size 3")
    router.dispatch_line(actor, "/mask air")
    brush = services.tools.get_brush(actor.key, "minecraft:arrow")
    assert brush is not None and brush.radius == 3.0 and brush.pattern == "granite"

    session = services.create_edit_session(actor.key, actor.world, origin=BlockVec3(0, 64, 0))
    cnt, _ = execute_brush(brush, actor.world, session, BlockVec3(0, 64, 0))
    session.commit()
    assert cnt > 0 and actor.world.get_block(BlockVec3(0, 64, 0)) == BlockSpec("minecraft:granite")

    # Bind and test cycler & super pickaxe
    actor._hand_item = "minecraft:blaze_rod"
    router.dispatch_line(actor, "/tool cycler")
    stair_pos = BlockVec3(20, 64, 20)
    actor.world.set_block(stair_pos, BlockSpec("minecraft:oak_stairs", (("weirdo_direction", 0),)))
    tool = services.tools.get_tool(actor.key, "minecraft:blaze_rod")
    assert tool is not None
    tsess = services.create_edit_session(actor.key, actor.world, origin=stair_pos)
    execute_tool(tool, actor.world, tsess, stair_pos, is_left_click=False)
    tsess.commit()
    assert actor.world.get_block(stair_pos).states_dict["weirdo_direction"] == 1

    router.dispatch_line(actor, "//sp recursive 2")
    sp = services.tools.get_super_pickaxe(actor.key)
    for x in range(30, 33):
        actor.world.set_block(BlockVec3(x, 64, 30), BlockSpec("minecraft:obsidian"))
    spsess = services.create_edit_session(actor.key, actor.world)
    broken = execute_super_pickaxe(sp, actor.world, spsess, BlockVec3(30, 64, 30))
    spsess.commit()
    assert broken == 3 and actor.world.get_block(BlockVec3(32, 64, 30)) == AIR_SPEC


def test_config_thai_lang_and_debounce(tmp_path: Path):
    services = WorldEditServices.create(tmp_path)
    cfg_file = tmp_path / "config.yml"
    assert cfg_file.is_file()
    assert (tmp_path / "schematics").is_dir()
    assert (tmp_path / "snapshots").is_dir()
    assert (tmp_path / "craftscripts").is_dir()
    assert services.config.config.prefix == "[EWE]"
    assert services.config.config.language == "en"

    router = CommandRouter(services)
    register_all_commands(router)
    actor = MockCommandActor()

    # Switch to Thai via /ewe lang th and persist to config.yml
    router.dispatch_line(actor, "/ewe lang th")
    assert services.lang.language == "th"
    assert 'language: "th"' in cfg_file.read_text(encoding="utf-8")

    # Test Thai selection, set, and undo messages
    router.dispatch_line(actor, "//pos1 0,64,0")
    assert any("ตั้งจุดที่ 1" in m for m in actor.messages)
    router.dispatch_line(actor, "//pos2 1,64,1")
    assert any("ตั้งจุดที่ 2" in m for m in actor.messages)
    router.dispatch_line(actor, "//set stone")
    assert any("แก้ไขพื้นที่เรียบร้อยแล้ว" in m for m in actor.messages)
    router.dispatch_line(actor, "//undo")
    assert any("ย้อนกลับ" in m for m in actor.messages)

    # Test /ewe reload reads edited config.yml
    cfg_file.write_text('language: "en"\nprefix: "[EWE]"\nmax_history: 30\ndefault_limit: 500000\n', encoding="utf-8")
    router.dispatch_line(actor, "/ewe reload")
    assert services.lang.language == "en"

    # Test right-click & duplicate position debounce (prevents BDS second-click spam)
    tman = services.tools
    pos = BlockVec3(292, 62, 79)
    assert tman.should_debounce_right_click(actor.key, now_ms=1000.0) is False
    assert tman.should_debounce_right_click(actor.key, now_ms=1100.0) is True
    assert tman.should_debounce_right_click(actor.key, now_ms=1400.0) is False

    assert tman.should_suppress_repeat_pos(actor.key, "pos2", pos, now_ms=1000.0) is False
    assert tman.should_suppress_repeat_pos(actor.key, "pos2", pos, now_ms=1450.0) is True
    assert tman.should_suppress_repeat_pos(actor.key, "pos2", pos, now_ms=2500.0) is False
    assert tman.should_suppress_repeat_pos(actor.key, "pos2", BlockVec3(293, 62, 79), now_ms=2550.0) is False


def test_snapshots_and_craftscripts_and_biomes(tmp_path: Path):
    services = WorldEditServices.create(tmp_path)
    router = CommandRouter(services)
    register_all_commands(router)
    actor = MockCommandActor()

    actor.world.set_block(BlockVec3(0, 64, 0), BlockSpec("minecraft:gold_block"))
    router.dispatch_line(actor, "//pos1 0,64,0")
    router.dispatch_line(actor, "//pos2 1,64,1")
    router.dispatch_line(actor, "//snap save base1")
    router.dispatch_line(actor, "//set air")
    assert actor.world.get_block(BlockVec3(0, 64, 0)) == AIR_SPEC
    router.dispatch_line(actor, "//restore")
    assert actor.world.get_block(BlockVec3(0, 64, 0)) == BlockSpec("minecraft:gold_block")

    script_file = services.scripts.craftscripts_dir / "pillar.wescript"
    services.scripts.craftscripts_dir.mkdir(parents=True, exist_ok=True)
    script_file.write_text("//pos1 5,64,5\n//pos2 5,67,5\n//set $0\n", encoding="utf-8")
    router.dispatch_line(actor, "/cs pillar diamond_block")
    assert actor.world.get_block(BlockVec3(5, 67, 5)) == BlockSpec("minecraft:diamond_block")
    router.dispatch_line(actor, "/.s emerald_block")
    assert actor.world.get_block(BlockVec3(5, 67, 5)) == BlockSpec("minecraft:emerald_block")

    router.dispatch_line(actor, "//setbiome cherry_grove")
    assert actor.world.get_biome(BlockVec3(5, 64, 5)) == "cherry_grove"
    router.dispatch_line(actor, "/searchitem amethyst")
    assert any("amethyst_block" in m for m in actor.messages)


def test_endstone_plugin_annotations_commands_and_rewrites():
    for _, method in inspect.getmembers(WorldEditPlugin, predicate=inspect.isfunction):
        if getattr(method, "_is_event_handler", False) or method.__name__.startswith("on_") and method.__name__ not in ("on_load", "on_enable", "on_disable", "on_command"):
            sig = inspect.signature(method)
            for pname, param in sig.parameters.items():
                if pname == "self":
                    continue
                assert isinstance(param.annotation, type) and issubclass(param.annotation, Event), (
                    f"{method.__name__} parameter {pname} annotation must be real Event subclass, got {param.annotation!r}"
                )

    cmds = WorldEditPlugin.commands
    assert "worldedit" in cmds and "pos1" in cmds and "brush" in cmds
    assert "ewe" in cmds["worldedit"].get("aliases", [])
    for cname, meta in cmds.items():
        assert cname not in VANILLA_COMMANDS, f"Plugin registered vanilla BDS command '{cname}'"
        for alias in meta.get("aliases", []):
            assert alias not in VANILLA_COMMANDS, f"Alias '{alias}' collides with vanilla BDS command"
        for usage in meta["usages"]:
            assert not ("[" in usage and "<" in usage), f"Invalid nested Endstone usage syntax: {usage}"

    assert rewrite_double_slash_command("//") == "/ewe sp toggle"
    assert rewrite_double_slash_command("//set stone") == "/ewe set stone"
    assert rewrite_double_slash_command("//fill water 3") == "/ewe fill water 3"
    assert rewrite_double_slash_command("/.s gold_block") == "/ewe .s gold_block"
    assert rewrite_double_slash_command("/;") == "/ewe sel"
    assert rewrite_double_slash_command("/!") == "/ewe unstuck"
    assert rewrite_double_slash_command("/,") == "/ewe sp toggle"
    assert rewrite_double_slash_command("/pos1") is None
