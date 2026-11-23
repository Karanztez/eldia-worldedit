"""Tests for all 7 Region/Selector types and selection commands."""

from pathlib import Path

from eldia_worldedit.commands import CommandRouter, MockCommandActor, register_all_commands
from eldia_worldedit.core.regions import create_selector
from eldia_worldedit.core.types import BlockSpec, BlockVec3
from eldia_worldedit.managers import WorldEditServices


def test_all_seven_region_selectors():
    # 1. Cuboid
    cub = create_selector("cuboid")
    cub.select_primary(BlockVec3(0, 0, 0))
    cub.select_secondary(BlockVec3(2, 2, 2))
    assert cub.get_region().volume == 27

    # 2. Extend
    ext = create_selector("extend")
    ext.select_primary(BlockVec3(0, 0, 0))
    ext.select_secondary(BlockVec3(3, 1, 2))
    ext.select_secondary(BlockVec3(-1, 4, 0))
    reg = ext.get_region()
    assert reg.min_point == BlockVec3(-1, 0, 0)
    assert reg.max_point == BlockVec3(3, 4, 2)

    # 3. Ellipsoid & 4. Sphere
    sph = create_selector("sphere")
    sph.select_primary(BlockVec3(10, 10, 10))
    sph.select_secondary(BlockVec3(13, 10, 10))
    assert sph.get_region().contains(BlockVec3(12, 10, 10))
    assert not sph.get_region().contains(BlockVec3(14, 14, 14))

    # 5. Cylinder
    cyl = create_selector("cyl")
    cyl.select_primary(BlockVec3(0, 10, 0))
    cyl.select_secondary(BlockVec3(2, 14, 2))
    creg = cyl.get_region()
    assert creg.min_point.y == 10 and creg.max_point.y == 14
    assert creg.contains(BlockVec3(0, 12, 0))

    # 6. Polygonal 2D
    poly = create_selector("poly")
    poly.select_primary(BlockVec3(0, 64, 0))
    poly.select_secondary(BlockVec3(4, 65, 0))
    assert not poly.is_defined()
    poly.select_secondary(BlockVec3(4, 64, 4))
    assert poly.is_defined()
    assert poly.get_region().contains(BlockVec3(2, 64, 1))

    # 7. Convex Polyhedral
    cvx = create_selector("convex")
    cvx.select_primary(BlockVec3(0, 0, 0))
    cvx.select_secondary(BlockVec3(4, 0, 0))
    cvx.select_secondary(BlockVec3(0, 0, 4))
    cvx.select_secondary(BlockVec3(0, 4, 0))
    assert cvx.is_defined()
    assert cvx.get_region().contains(BlockVec3(1, 1, 1))
    assert not cvx.get_region().contains(BlockVec3(3, 3, 3))


def test_selection_commands_flow(tmp_path: Path):
    services = WorldEditServices.create(tmp_path)
    router = CommandRouter(services)
    register_all_commands(router)
    actor = MockCommandActor()
    actor.world.set_block(BlockVec3(1, 64, 1), BlockSpec("minecraft:stone"))

    assert router.dispatch_line(actor, "//pos1 0,64,0")
    assert router.dispatch_line(actor, "//pos2 2,64,2")
    assert router.dispatch_line(actor, "//size")
    assert any("9 blocks" in m for m in actor.messages)

    assert router.dispatch_line(actor, "//count stone")
    assert any("1 matching" in m for m in actor.messages)

    assert router.dispatch_line(actor, "//expand 1 up")
    assert services.selections.get_region(actor.key).volume == 18

    assert router.dispatch_line(actor, "//contract 1 down")
    assert services.selections.get_region(actor.key).volume == 9

    assert router.dispatch_line(actor, "//shift 5 east")
    assert services.selections.get_region(actor.key).min_point == BlockVec3(5, 64, 0)

    assert router.dispatch_line(actor, "//drawsel")
    pts = services.selections.get_outline_points(actor.key)
    assert len(pts) > 10

    assert router.dispatch_line(actor, "//wand")
    assert actor.given_items == [("minecraft:wooden_axe", 1)]
