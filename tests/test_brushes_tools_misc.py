"""Tests for Brushes, Bound Tools, Super Pickaxe, Snapshots, CraftScripts, and Endstone Plugin metadata."""

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

    # Bind and test floodfill, cycler, deltree, super pickaxe
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

    # Super pickaxe recursive mode
    router.dispatch_line(actor, "//sp recursive 2")
    sp = services.tools.get_super_pickaxe(actor.key)
    for x in range(30, 33):
        actor.world.set_block(BlockVec3(x, 64, 30), BlockSpec("minecraft:obsidian"))
    spsess = services.create_edit_session(actor.key, actor.world)
    broken = execute_super_pickaxe(sp, actor.world, spsess, BlockVec3(30, 64, 30))
    spsess.commit()
    assert broken == 3 and actor.world.get_block(BlockVec3(32, 64, 30)) == AIR_SPEC


def test_snapshots_and_craftscripts_and_biomes(tmp_path: Path):
    services = WorldEditServices.create(tmp_path)
    router = CommandRouter(services)
    register_all_commands(router)
    actor = MockCommandActor()

    # Snapshots
    actor.world.set_block(BlockVec3(0, 64, 0), BlockSpec("minecraft:gold_block"))
    router.dispatch_line(actor, "//pos1 0,64,0")
    router.dispatch_line(actor, "//pos2 1,64,1")
    router.dispatch_line(actor, "//snap save base1")
    router.dispatch_line(actor, "//set air")
    assert actor.world.get_block(BlockVec3(0, 64, 0)) == AIR_SPEC
    router.dispatch_line(actor, "//restore")
    assert actor.world.get_block(BlockVec3(0, 64, 0)) == BlockSpec("minecraft:gold_block")

    # CraftScripts + /.s repeat
    script_file = services.scripts.craftscripts_dir / "pillar.wescript"
    services.scripts.craftscripts_dir.mkdir(parents=True, exist_ok=True)
    script_file.write_text("//pos1 5,64,5\n//pos2 5,67,5\n//set $0\n", encoding="utf-8")
    router.dispatch_line(actor, "/cs pillar diamond_block")
    assert actor.world.get_block(BlockVec3(5, 67, 5)) == BlockSpec("minecraft:diamond_block")
    router.dispatch_line(actor, "/.s emerald_block")
    assert actor.world.get_block(BlockVec3(5, 67, 5)) == BlockSpec("minecraft:emerald_block")

    # Biomes & searchitem
    router.dispatch_line(actor, "//setbiome cherry_grove")
    assert actor.world.get_biome(BlockVec3(5, 64, 5)) == "cherry_grove"
    router.dispatch_line(actor, "/searchitem amethyst")
    assert any("amethyst_block" in m for m in actor.messages)


def test_endstone_plugin_annotations_commands_and_rewrites():
    # 1. Verify NO @event_handler uses stringified annotations
    for _, method in inspect.getmembers(WorldEditPlugin, predicate=inspect.isfunction):
        if getattr(method, "_is_event_handler", False) or method.__name__.startswith("on_") and method.__name__ not in ("on_load", "on_enable", "on_disable", "on_command"):
            sig = inspect.signature(method)
            for pname, param in sig.parameters.items():
                if pname == "self":
                    continue
                assert isinstance(param.annotation, type) and issubclass(param.annotation, Event), (
                    f"{method.__name__} parameter {pname} annotation must be real Event subclass, got {param.annotation!r}"
                )

    # 2. Verify zero vanilla BDS command collisions and valid Endstone usage grammar
    cmds = WorldEditPlugin.commands
    assert "worldedit" in cmds and "pos1" in cmds and "brush" in cmds
    for cname, meta in cmds.items():
        assert cname not in VANILLA_COMMANDS, f"Plugin registered vanilla BDS command '{cname}'"
        for alias in meta.get("aliases", []):
            assert alias not in VANILLA_COMMANDS, f"Alias '{alias}' collides with vanilla BDS command"
        for usage in meta["usages"]:
            assert not ("[" in usage and "<" in usage), f"Invalid nested Endstone usage syntax: {usage}"

    # 3. Verify // & shorthand rewrites
    assert rewrite_double_slash_command("//") == "/we sp toggle"
    assert rewrite_double_slash_command("//set stone") == "/we set stone"
    assert rewrite_double_slash_command("//fill water 3") == "/we fill water 3"
    assert rewrite_double_slash_command("/.s gold_block") == "/we .s gold_block"
    assert rewrite_double_slash_command("/;") == "/we sel"
    assert rewrite_double_slash_command("/!") == "/we unstuck"
    assert rewrite_double_slash_command("/,") == "/we sp toggle"
    assert rewrite_double_slash_command("/pos1") is None
