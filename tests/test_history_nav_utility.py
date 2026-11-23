"""Tests for Undo/Redo history, Navigation solvers, and Utility commands."""

from pathlib import Path

from eldia_worldedit.commands import CommandRouter, MockCommandActor, register_all_commands
from eldia_worldedit.core.types import AIR_SPEC, BlockSpec, BlockVec3
from eldia_worldedit.managers import WorldEditServices
from eldia_worldedit.world.adapter import ActorInfo


def test_history_undo_redo_and_clear(tmp_path: Path):
    services = WorldEditServices.create(tmp_path)
    router = CommandRouter(services)
    register_all_commands(router)
    actor = MockCommandActor()

    router.dispatch_line(actor, "//pos1 0,64,0")
    router.dispatch_line(actor, "//pos2 1,64,1")
    router.dispatch_line(actor, "//set stone")
    router.dispatch_line(actor, "//set gold_block")
    assert actor.world.get_block(BlockVec3(0, 64, 0)) == BlockSpec("minecraft:gold_block")

    router.dispatch_line(actor, "//undo")
    assert actor.world.get_block(BlockVec3(0, 64, 0)) == BlockSpec("minecraft:stone")

    router.dispatch_line(actor, "//undo")
    assert actor.world.get_block(BlockVec3(0, 64, 0)) == AIR_SPEC

    router.dispatch_line(actor, "//redo 2")
    assert actor.world.get_block(BlockVec3(0, 64, 0)) == BlockSpec("minecraft:gold_block")

    router.dispatch_line(actor, "//clearhistory")
    assert services.history.stats(actor.key) == (0, 0)


def test_navigation_commands(tmp_path: Path):
    services = WorldEditServices.create(tmp_path)
    router = CommandRouter(services)
    register_all_commands(router)
    actor = MockCommandActor(_position=BlockVec3(0, 64, 0), _yaw=0.0, _pitch=0.0)

    # Unstuck inside stone
    actor.world.set_block(BlockVec3(0, 64, 0), BlockSpec("minecraft:stone"))
    actor.world.set_block(BlockVec3(0, 65, 0), BlockSpec("minecraft:stone"))
    router.dispatch_line(actor, "/unstuck")
    assert actor.position.y >= 66

    # Ceiling & descend
    actor.teleport(BlockVec3(0, 64, 0))
    actor.world.set_block(BlockVec3(0, 64, 0), AIR_SPEC)
    actor.world.set_block(BlockVec3(0, 65, 0), AIR_SPEC)
    actor.world.set_block(BlockVec3(0, 63, 0), BlockSpec("minecraft:stone"))
    actor.world.set_block(BlockVec3(0, 72, 0), BlockSpec("minecraft:stone"))
    router.dispatch_line(actor, "/ceil")
    assert actor.position == BlockVec3(0, 70, 0)

    router.dispatch_line(actor, "/ascend")
    assert actor.position == BlockVec3(0, 73, 0)

    router.dispatch_line(actor, "/descend")
    assert actor.position == BlockVec3(0, 64, 0)

    # /thru a wall along +Z (yaw=0)
    actor.world.set_block(BlockVec3(0, 65, 3), BlockSpec("minecraft:stone"))
    actor.world.set_block(BlockVec3(0, 64, 3), BlockSpec("minecraft:stone"))
    router.dispatch_line(actor, "/thru")
    assert actor.position.z >= 4

    # /up with glass support
    actor.teleport(BlockVec3(5, 64, 5))
    router.dispatch_line(actor, "/up 6")
    assert actor.position == BlockVec3(5, 70, 5)
    assert actor.world.get_block(BlockVec3(5, 69, 5)) == BlockSpec("minecraft:glass")


def test_utility_fill_drain_snow_green_ex_butcher_calc(tmp_path: Path):
    services = WorldEditServices.create(tmp_path)
    router = CommandRouter(services)
    register_all_commands(router)
    actor = MockCommandActor(_position=BlockVec3(0, 64, 0))

    # Build small basin and test //fill + //drain
    for x in range(-2, 3):
        for z in range(-2, 3):
            actor.world.set_block(BlockVec3(x, 62, z), BlockSpec("minecraft:stone"))
            if abs(x) == 2 or abs(z) == 2:
                actor.world.set_block(BlockVec3(x, 63, z), BlockSpec("minecraft:stone"))
                actor.world.set_block(BlockVec3(x, 64, z), BlockSpec("minecraft:stone"))

    actor.teleport(BlockVec3(0, 63, 0))
    router.dispatch_line(actor, "//fill water 2 2")
    assert actor.world.get_block(BlockVec3(0, 63, 0)) == BlockSpec("minecraft:water")

    router.dispatch_line(actor, "//drain 4")
    assert actor.world.get_block(BlockVec3(0, 63, 0)) == AIR_SPEC

    # Extinguish, green, snow, thaw
    actor.world.set_block(BlockVec3(1, 63, 0), BlockSpec("minecraft:fire"))
    actor.world.set_block(BlockVec3(0, 63, 1), BlockSpec("minecraft:dirt"))
    router.dispatch_line(actor, "/ex 5")
    assert actor.world.get_block(BlockVec3(1, 63, 0)) == AIR_SPEC
    router.dispatch_line(actor, "/green 5")
    assert actor.world.get_block(BlockVec3(0, 63, 1)) == BlockSpec("minecraft:grass_block")
    router.dispatch_line(actor, "/snow 5")
    assert actor.world.get_block(BlockVec3(0, 64, 1)).block_type == "minecraft:snow_layer"
    router.dispatch_line(actor, "/thaw 5")
    assert actor.world.get_block(BlockVec3(0, 64, 1)) == AIR_SPEC

    # Butcher & /remove & //calc
    actor.world.entities.extend([
        ActorInfo(1, "minecraft:zombie", BlockVec3(1, 64, 1)),
        ActorInfo(2, "minecraft:cow", BlockVec3(2, 64, 2)),
        ActorInfo(3, "minecraft:item", BlockVec3(2, 64, 1)),
    ])
    router.dispatch_line(actor, "/butcher 10")
    assert [e.entity_type for e in actor.world.entities] == ["minecraft:cow", "minecraft:item"]
    router.dispatch_line(actor, "/remove items 10")
    assert [e.entity_type for e in actor.world.entities] == ["minecraft:cow"]
    router.dispatch_line(actor, "//calc 3^2 + 4^2")
    assert any("= 25" in m for m in actor.messages)
