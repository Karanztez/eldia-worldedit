"""Tests for Clipboard copy/cut/paste/rotate/flip and Sponge .schem / .wejson persistence."""

from pathlib import Path

import pytest

from eldia_worldedit.clipboard.schematic import load_schematic, save_schematic
from eldia_worldedit.commands import CommandRouter, MockCommandActor, register_all_commands
from eldia_worldedit.core.types import AIR_SPEC, BlockSpec, BlockVec3
from eldia_worldedit.managers import WorldEditServices


def test_clipboard_copy_rotate_flip_cut_paste(tmp_path: Path):
    services = WorldEditServices.create(tmp_path)
    router = CommandRouter(services)
    register_all_commands(router)
    actor = MockCommandActor(_position=BlockVec3(0, 64, 0))

    stairs = BlockSpec("minecraft:oak_stairs", (("weirdo_direction", 0), ("upside_down_bit", False)))
    actor.world.set_block(BlockVec3(1, 64, 0), stairs)
    actor.world.set_block(BlockVec3(2, 64, 0), BlockSpec("minecraft:diamond_block"))

    router.dispatch_line(actor, "//pos1 1,64,0")
    router.dispatch_line(actor, "//pos2 2,64,0")
    router.dispatch_line(actor, "//copy")

    router.dispatch_line(actor, "//rotate 90")
    actor.teleport(BlockVec3(10, 64, 10))
    router.dispatch_line(actor, "//paste")
    # (1, 0, 0) rotated 90 deg CW around Y -> (0, 0, 1) relative to origin
    pasted_stair = actor.world.get_block(BlockVec3(10, 64, 11))
    assert pasted_stair.block_type == "minecraft:oak_stairs"
    assert pasted_stair.states_dict["weirdo_direction"] == 2
    assert actor.world.get_block(BlockVec3(10, 64, 12)) == BlockSpec("minecraft:diamond_block")

    router.dispatch_line(actor, "//flip north")
    actor.teleport(BlockVec3(20, 64, 20))
    router.dispatch_line(actor, "//paste -a")
    assert actor.world.get_block(BlockVec3(20, 64, 19)).block_type == "minecraft:oak_stairs"

    router.dispatch_line(actor, "//pos1 1,64,0")
    router.dispatch_line(actor, "//pos2 2,64,0")
    router.dispatch_line(actor, "//cut")
    assert actor.world.get_block(BlockVec3(2, 64, 0)) == AIR_SPEC

    router.dispatch_line(actor, "//clearclipboard")
    assert services.clipboards.get(actor.key) is None


def test_schematic_nbt_and_wejson_roundtrip(tmp_path: Path):
    services = WorldEditServices.create(tmp_path)
    router = CommandRouter(services)
    register_all_commands(router)
    actor = MockCommandActor(_position=BlockVec3(0, 64, 0))

    actor.world.set_block(BlockVec3(0, 64, 0), BlockSpec("minecraft:emerald_block"))
    actor.world.set_block(BlockVec3(1, 65, 1), BlockSpec("minecraft:oak_log", (("pillar_axis", "x"),)))
    router.dispatch_line(actor, "//pos1 0,64,0")
    router.dispatch_line(actor, "//pos2 1,65,1")
    router.dispatch_line(actor, "//copy")

    # Save Sponge v2 .schem
    router.dispatch_line(actor, "//schem save tower_test")
    router.dispatch_line(actor, "//schem save tower_json wejson")
    router.dispatch_line(actor, "//clearclipboard")

    router.dispatch_line(actor, "//schem list")
    assert any("tower_test.schem" in m for m in actor.messages)

    router.dispatch_line(actor, "//schem load tower_test")
    actor.teleport(BlockVec3(30, 70, 30))
    router.dispatch_line(actor, "//paste")
    assert actor.world.get_block(BlockVec3(30, 70, 30)) == BlockSpec("minecraft:emerald_block")
    assert actor.world.get_block(BlockVec3(31, 71, 31)) == BlockSpec("minecraft:oak_log", (("pillar_axis", "x"),))

    router.dispatch_line(actor, "//schem load tower_json")
    cb = services.clipboards.get(actor.key)
    assert cb is not None and cb.blocks[BlockVec3(0, 0, 0)] == BlockSpec("minecraft:emerald_block")

    # Path traversal safety check
    with pytest.raises(ValueError):
        save_schematic(cb, tmp_path, "../escape")
    with pytest.raises(FileNotFoundError):
        load_schematic(tmp_path, "nonexistent")
