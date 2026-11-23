"""Tests for Region editing commands and Procedural Shape Generators."""

from pathlib import Path

from eldia_worldedit.commands import CommandRouter, MockCommandActor, register_all_commands
from eldia_worldedit.core.types import AIR_SPEC, BlockSpec, BlockVec3
from eldia_worldedit.managers import WorldEditServices


def _setup(tmp_path: Path) -> tuple[WorldEditServices, CommandRouter, MockCommandActor]:
    services = WorldEditServices.create(tmp_path)
    router = CommandRouter(services)
    register_all_commands(router)
    actor = MockCommandActor()
    return services, router, actor


def test_set_replace_walls_faces_center_overlay_naturalize_hollow(tmp_path: Path):
    _, router, actor = _setup(tmp_path)
    router.dispatch_line(actor, "//pos1 0,60,0")
    router.dispatch_line(actor, "//pos2 4,64,4")

    router.dispatch_line(actor, "//set stone")
    assert actor.world.get_block(BlockVec3(2, 62, 2)) == BlockSpec("minecraft:stone")

    router.dispatch_line(actor, "//hollow 1")
    assert actor.world.get_block(BlockVec3(2, 62, 2)) == AIR_SPEC
    assert actor.world.get_block(BlockVec3(0, 62, 2)) == BlockSpec("minecraft:stone")

    router.dispatch_line(actor, "//center gold_block")
    assert actor.world.get_block(BlockVec3(2, 62, 2)) == BlockSpec("minecraft:gold_block")

    router.dispatch_line(actor, "//replace stone cobble")
    assert actor.world.get_block(BlockVec3(0, 62, 2)) == BlockSpec("minecraft:cobblestone")

    router.dispatch_line(actor, "//naturalize")
    assert actor.world.get_block(BlockVec3(0, 64, 0)) == BlockSpec("minecraft:grass_block")
    assert actor.world.get_block(BlockVec3(0, 63, 0)) == BlockSpec("minecraft:dirt")
    assert actor.world.get_block(BlockVec3(0, 60, 0)) == BlockSpec("minecraft:stone")


def test_move_stack_line_curve_deform_revolve(tmp_path: Path):
    services, router, actor = _setup(tmp_path)
    router.dispatch_line(actor, "//pos1 0,64,0")
    router.dispatch_line(actor, "//pos2 1,64,0")
    router.dispatch_line(actor, "//set diamond_block")

    router.dispatch_line(actor, "//stack 2 east")
    assert actor.world.get_block(BlockVec3(5, 64, 0)) == BlockSpec("minecraft:diamond_block")

    router.dispatch_line(actor, "//move 3 up")
    assert actor.world.get_block(BlockVec3(0, 64, 0)) == AIR_SPEC
    assert actor.world.get_block(BlockVec3(0, 67, 0)) == BlockSpec("minecraft:diamond_block")

    router.dispatch_line(actor, "//pos1 10,64,0")
    router.dispatch_line(actor, "//pos2 15,64,0")
    router.dispatch_line(actor, "//line glass")
    assert actor.world.get_block(BlockVec3(12, 64, 0)) == BlockSpec("minecraft:glass")

    # Convex curve
    router.dispatch_line(actor, "//sel convex")
    services.selections.select_pos1(actor.key, BlockVec3(20, 64, 0))
    services.selections.select_pos2(actor.key, BlockVec3(24, 68, 0))
    services.selections.select_pos2(actor.key, BlockVec3(28, 64, 0))
    router.dispatch_line(actor, "//curve oak_planks")
    assert actor.world.get_block(BlockVec3(28, 64, 0)) == BlockSpec("minecraft:oak_planks")


def test_shape_generators_and_gmask_and_limit(tmp_path: Path):
    _, router, actor = _setup(tmp_path)
    actor.teleport(BlockVec3(0, 70, 0))

    router.dispatch_line(actor, "//sphere glass 3")
    assert actor.world.get_block(BlockVec3(0, 70, 0)) == BlockSpec("minecraft:glass")
    assert actor.world.get_block(BlockVec3(3, 70, 0)) == BlockSpec("minecraft:glass")
    assert actor.world.get_block(BlockVec3(0, 73, 0)) == BlockSpec("minecraft:glass")

    router.dispatch_line(actor, "//hcyl brick_block 2 3")
    assert actor.world.get_block(BlockVec3(2, 70, 0)) == BlockSpec("minecraft:brick_block")

    router.dispatch_line(actor, "//pyramid sandstone 3")
    assert actor.world.get_block(BlockVec3(0, 72, 0)) == BlockSpec("minecraft:sandstone")

    router.dispatch_line(actor, "//cone emerald_block 3 4")
    assert actor.world.get_block(BlockVec3(0, 70, 0)) == BlockSpec("minecraft:emerald_block")

    # Formula //g
    router.dispatch_line(actor, "//pos1 40,60,40")
    router.dispatch_line(actor, "//pos2 44,64,44")
    router.dispatch_line(actor, "//g stone x^2+y^2+z^2<=1")
    assert actor.world.get_block(BlockVec3(42, 62, 42)) == BlockSpec("minecraft:stone")

    # Limit enforcement
    router.dispatch_line(actor, "//limit 3")
    router.dispatch_line(actor, "//set gold_block")
    assert any("exceeded" in e.lower() for e in actor.errors)
