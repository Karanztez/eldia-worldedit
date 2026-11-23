"""Tests for argument tokenizer, flag parser, block spec parsing, directions, and AST math expressions."""

import pytest

from eldia_worldedit.core.command_parser import parse_flags, split_top_level, tokenize_args
from eldia_worldedit.core.math_expr import ExpressionError, compile_expression, evaluate_expression
from eldia_worldedit.core.types import (
    BlockSpec,
    BlockVec3,
    flip_block_spec,
    normalize_block_id,
    parse_block_spec,
    resolve_direction,
    rotate_block_spec,
)


def test_tokenize_and_split_top_level():
    toks = tokenize_args('  -ae -m "stone, cobble"  "hello world" -15  ')
    assert toks == ["-ae", "-m", "stone, cobble", "hello world", "-15"]

    parts = split_top_level('50%oak_stairs[weirdo_direction=2,upside_down_bit=false],50%stone', ",")
    assert parts == ["50%oak_stairs[weirdo_direction=2,upside_down_bit=false]", "50%stone"]


def test_parse_flags_preserves_negative_numbers_and_combined_clusters():
    active, values, pos = parse_flags(
        ["-ae", "-m", "!air", "-10", "5", "--", "-not-a-flag"],
        value_flags={"m"},
        bool_flags={"a", "e", "o"},
    )
    assert active == {"a", "e"}
    assert values == {"m": "!air"}
    assert pos == ["-10", "5", "-not-a-flag"]

    with pytest.raises(ValueError):
        parse_flags(["-m"], value_flags={"m"})


def test_block_spec_parse_rotate_and_flip():
    assert normalize_block_id("1") == "minecraft:stone"
    assert normalize_block_id("Stone") == "minecraft:stone"
    spec = parse_block_spec("oak_stairs[weirdo_direction=0,upside_down_bit=true]")
    assert spec.block_type == "minecraft:oak_stairs"
    assert spec.states_dict == {"upside_down_bit": True, "weirdo_direction": 0}

    rot90 = rotate_block_spec(spec, 90)
    assert rot90.states_dict["weirdo_direction"] == 2
    flipped_y = flip_block_spec(spec, "y")
    assert flipped_y.states_dict["upside_down_bit"] is False
    flipped_x = flip_block_spec(BlockSpec("minecraft:chest", (("minecraft:cardinal_direction", "east"),)), "x")
    assert flipped_x.states_dict["minecraft:cardinal_direction"] == "west"


def test_resolve_direction_cardinal_and_relative():
    assert resolve_direction("north") == BlockVec3(0, 0, -1)
    assert resolve_direction("up") == BlockVec3(0, 1, 0)
    # Yaw 0 faces south (+Z); left looking down +Y is +X (east) -> wait left is (dz, 0, -dx)
    assert resolve_direction("me", yaw=0.0, pitch=0.0) == BlockVec3(0, 0, 1)
    assert resolve_direction("me", yaw=0.0, pitch=-60.0) == BlockVec3(0, 1, 0)
    assert resolve_direction("left", yaw=0.0, pitch=0.0) == BlockVec3(1, 0, 0)
    assert resolve_direction("right", yaw=0.0, pitch=0.0) == BlockVec3(-1, 0, 0)


def test_math_expression_operators_ternary_and_security():
    assert evaluate_expression("2^3 + abs(-4) + floor(2.9)") == pytest.approx(14.0)
    assert evaluate_expression("x > 0 && y <= 5 ? 10 : -1", {"x": 2.0, "y": 5.0}) == 10.0
    assert evaluate_expression("!(0) || 0") == 1.0
    assert evaluate_expression("1 / 0") == 0.0
    n = evaluate_expression("noise(0.5, 1.2, -0.3)")
    assert -1.0 <= n <= 1.0
    assert evaluate_expression("sin(pi / 2)") == pytest.approx(1.0)

    # Disallowed calls / attribute lookups must fail cleanly
    with pytest.raises(ExpressionError):
        compile_expression("__import__('os').system('echo hi')")
    with pytest.raises(ExpressionError):
        compile_expression("(1).__class__")
    # Overly deep AST blocked
    deep = "+".join(["1"] * 300)
    with pytest.raises(ExpressionError):
        compile_expression(deep)
