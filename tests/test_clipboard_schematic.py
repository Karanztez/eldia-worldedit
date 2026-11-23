"""Tests for Clipboard copy/cut/paste/rotate/flip and Sponge v2/v3, .schematic, .mcstructure, .wejson I/O."""

import gzip
from pathlib import Path

import pytest

from eldia_worldedit.clipboard.schematic import (
    _TAG_BYTE_ARRAY,
    _TAG_COMPOUND,
    _TAG_INT,
    _TAG_INT_ARRAY,
    _TAG_SHORT,
    _encode_varints,
    _write_tag,
    load_schematic,
    save_schematic,
)
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


def test_schematic_all_formats_roundtrip(tmp_path: Path):
    services = WorldEditServices.create(tmp_path)
    router = CommandRouter(services)
    register_all_commands(router)
    actor = MockCommandActor(_position=BlockVec3(0, 64, 0))

    actor.world.set_block(BlockVec3(0, 64, 0), BlockSpec("minecraft:emerald_block"))
    actor.world.set_block(BlockVec3(1, 65, 1), BlockSpec("minecraft:oak_log", (("pillar_axis", "x"),)))
    router.dispatch_line(actor, "//pos1 0,64,0")
    router.dispatch_line(actor, "//pos2 1,65,1")
    router.dispatch_line(actor, "//copy")

    # 1. Sponge v2 .schem, Bedrock .mcstructure, and .wejson
    router.dispatch_line(actor, "//schem save tower_v2")
    router.dispatch_line(actor, "//schem save tower_mc mcstructure")
    router.dispatch_line(actor, "//schem save tower_json wejson")
    router.dispatch_line(actor, "//clearclipboard")

    router.dispatch_line(actor, "//schem list")
    assert any("tower_v2.schem" in m for m in actor.messages)
    assert any("tower_mc.mcstructure" in m for m in actor.messages)

    router.dispatch_line(actor, "//schem load tower_mc")
    actor.teleport(BlockVec3(40, 70, 40))
    router.dispatch_line(actor, "//paste")
    assert actor.world.get_block(BlockVec3(40, 70, 40)) == BlockSpec("minecraft:emerald_block")
    assert actor.world.get_block(BlockVec3(41, 71, 41)) == BlockSpec("minecraft:oak_log", (("pillar_axis", "x"),))

    router.dispatch_line(actor, "//schem load tower_v2")
    cb = services.clipboards.get(actor.key)
    assert cb is not None and cb.blocks[BlockVec3(0, 0, 0)] == BlockSpec("minecraft:emerald_block")

    # 2. Classic MCEdit .schematic (Blocks + Data bytes)
    legacy_root = {
        "Width": (_TAG_SHORT, 2),
        "Height": (_TAG_SHORT, 1),
        "Length": (_TAG_SHORT, 1),
        "Blocks": (_TAG_BYTE_ARRAY, bytes([35, 1])),
        "Data": (_TAG_BYTE_ARRAY, bytes([14, 1])),
    }
    raw_legacy = bytearray()
    _write_tag(raw_legacy, _TAG_COMPOUND, "Schematic", legacy_root, endian=">")
    (tmp_path / "legacy_test.schematic").write_bytes(gzip.compress(bytes(raw_legacy)))
    cb_legacy = load_schematic(tmp_path, "legacy_test")
    assert cb_legacy.blocks[BlockVec3(0, 0, 0)] == BlockSpec("minecraft:red_wool")
    assert cb_legacy.blocks[BlockVec3(1, 0, 0)] == BlockSpec("minecraft:granite")

    # 3. Sponge v3 .schem (nested Schematic + Blocks.Palette/Data)
    v3_inner = {
        "Version": (_TAG_INT, 3),
        "Width": (_TAG_SHORT, 2),
        "Height": (_TAG_SHORT, 1),
        "Length": (_TAG_SHORT, 1),
        "Offset": (_TAG_INT_ARRAY, [0, 0, 0]),
        "Blocks": (
            _TAG_COMPOUND,
            {
                "Palette": (_TAG_COMPOUND, {"minecraft:grass": (_TAG_INT, 0), "minecraft:diamond_block": (_TAG_INT, 1)}),
                "Data": (_TAG_BYTE_ARRAY, _encode_varints([0, 1])),
            },
        ),
    }
    raw_v3 = bytearray()
    _write_tag(raw_v3, _TAG_COMPOUND, "", {"Schematic": (_TAG_COMPOUND, v3_inner)}, endian=">")
    (tmp_path / "v3_test.schem").write_bytes(gzip.compress(bytes(raw_v3)))
    cb_v3 = load_schematic(tmp_path, "v3_test")
    assert cb_v3.blocks[BlockVec3(0, 0, 0)] == BlockSpec("minecraft:short_grass")
    assert cb_v3.blocks[BlockVec3(1, 0, 0)] == BlockSpec("minecraft:diamond_block")

    with pytest.raises(ValueError):
        save_schematic(cb, tmp_path, "../escape")
    with pytest.raises(FileNotFoundError):
        load_schematic(tmp_path, "nonexistent")
