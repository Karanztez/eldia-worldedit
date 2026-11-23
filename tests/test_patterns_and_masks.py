"""Tests for WorldEdit pattern DSL and mask DSL."""

import random

from eldia_worldedit.clipboard.clipboard import Clipboard
from eldia_worldedit.core.masks import MaskContext, parse_mask
from eldia_worldedit.core.patterns import PatternContext, parse_pattern
from eldia_worldedit.core.regions import CuboidRegion
from eldia_worldedit.core.types import BlockSpec, BlockVec3
from eldia_worldedit.world.adapter import InMemoryWorldAdapter


def test_patterns_single_weighted_category_hand_clipboard_states():
    world = InMemoryWorldAdapter()
    world.set_block(BlockVec3(1, 64, 1), BlockSpec("minecraft:oak_stairs", (("weirdo_direction", 0),)))

    rng = random.Random(42)
    ctx = PatternContext(
        world=world,
        hand_block=BlockSpec("minecraft:diamond_block"),
        clipboard=Clipboard(
            origin=BlockVec3(0, 0, 0),
            min_point=BlockVec3(0, 0, 0),
            max_point=BlockVec3(1, 0, 0),
            blocks={BlockVec3(0, 0, 0): BlockSpec("minecraft:gold_block"), BlockVec3(1, 0, 0): BlockSpec("minecraft:iron_block")},
        ),
        origin=BlockVec3(10, 64, 10),
    )

    assert parse_pattern("stone").apply(BlockVec3(0, 0, 0), rng, ctx) == BlockSpec("minecraft:stone")
    assert parse_pattern("#hand", ctx).apply(BlockVec3(0, 0, 0), rng, ctx) == BlockSpec("minecraft:diamond_block")
    assert parse_pattern("#clipboard", ctx).apply(BlockVec3(11, 64, 10), rng, ctx) == BlockSpec("minecraft:iron_block")

    wool = parse_pattern("##wool").apply(BlockVec3(0, 0, 0), rng, ctx)
    assert wool.block_type.endswith("_wool")

    mix = parse_pattern("75%stone,25%cobblestone")
    picks = [mix.apply(BlockVec3(i, 0, 0), rng, ctx).block_type for i in range(400)]
    assert picks.count("minecraft:stone") > picks.count("minecraft:cobblestone")

    state_pat = parse_pattern("^[upside_down_bit=true]")
    updated = state_pat.apply(BlockVec3(1, 64, 1), rng, ctx)
    assert updated.block_type == "minecraft:oak_stairs"
    assert updated.states_dict == {"upside_down_bit": True, "weirdo_direction": 0}


def test_masks_negation_offsets_surface_region_noise_expr_and_combinators():
    world = InMemoryWorldAdapter()
    world.set_block(BlockVec3(0, 64, 0), BlockSpec("minecraft:grass_block"))
    world.set_block(BlockVec3(0, 65, 0), BlockSpec("minecraft:stone"))
    world.set_block(BlockVec3(0, 63, 0), BlockSpec("minecraft:stone"))
    world.set_block(BlockVec3(1, 64, 0), BlockSpec("minecraft:water"))

    reg = CuboidRegion(BlockVec3(0, 63, 0), BlockVec3(0, 66, 0))
    mctx = MaskContext(region=reg, origin=BlockVec3(0, 64, 0), rng=random.Random(7))

    assert parse_mask("!air").test(world, BlockVec3(0, 65, 0), mctx)
    assert not parse_mask("!air").test(world, BlockVec3(5, 65, 5), mctx)
    assert parse_mask("#existing").test(world, BlockVec3(0, 64, 0), mctx)
    assert parse_mask("#liquid").test(world, BlockVec3(1, 64, 0), mctx)
    assert parse_mask(">grass_block").test(world, BlockVec3(0, 65, 0), mctx)
    assert parse_mask("<stone").test(world, BlockVec3(0, 64, 0), mctx)
    assert parse_mask("#exposed").test(world, BlockVec3(0, 65, 0), mctx)
    assert not parse_mask("#exposed").test(world, BlockVec3(0, 64, 0), mctx)
    assert parse_mask("#surface").test(world, BlockVec3(0, 64, 0), mctx)
    assert parse_mask("#region").test(world, BlockVec3(0, 65, 0), mctx)
    assert not parse_mask("#region").test(world, BlockVec3(1, 64, 0), mctx)
    assert parse_mask("stone,grass_block").test(world, BlockVec3(0, 64, 0), mctx)
    assert parse_mask("#solid #region").test(world, BlockVec3(0, 65, 0), mctx)
    assert parse_mask("=rx^2+ry^2<5").test(world, BlockVec3(1, 65, 0), mctx)
    assert not parse_mask("=rx^2+ry^2<5").test(world, BlockVec3(3, 65, 0), mctx)
