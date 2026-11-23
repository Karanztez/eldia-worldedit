"""WorldEdit block mask DSL (!, comma union, space intersection, #existing, #solid, >, <, %, =expr)."""

from __future__ import annotations

import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .command_parser import split_top_level
from .math_expr import CompiledExpression, compile_expression
from .types import BLOCK_CATEGORIES, BlockSpec, BlockVec3, parse_block_spec

if TYPE_CHECKING:
    from ..world.adapter import WorldAdapter

_PERCENT_RE = re.compile(r"^%(\d+(?:\.\d+)?)$")


@dataclass
class MaskContext:
    """Runtime context passed into mask evaluations."""

    region: Any = None
    origin: BlockVec3 = field(default_factory=lambda: BlockVec3(0, 0, 0))
    hand_block: BlockSpec | None = None
    rng: random.Random = field(default_factory=random.Random)


class Mask(ABC):
    """Predicate matching world positions."""

    @abstractmethod
    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        """Return True if `pos` satisfies this mask."""


@dataclass(frozen=True)
class BlockMask(Mask):
    """Matches block type and any explicitly provided block states."""

    spec: BlockSpec

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        current = world.get_block(pos)
        if current.block_type != self.spec.block_type:
            return False
        if not self.spec.states:
            return True
        cur_states = current.states_dict
        return all(cur_states.get(k) == v for k, v in self.spec.states)


@dataclass(frozen=True)
class NegatedMask(Mask):
    """Inverts an inner mask (!mask)."""

    inner: Mask

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        return not self.inner.test(world, pos, context)


class UnionMask(Mask):
    """Matches if ANY child mask matches (comma-separated)."""

    def __init__(self, masks: list[Mask]) -> None:
        self.masks = masks

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        return any(m.test(world, pos, context) for m in self.masks)


class IntersectionMask(Mask):
    """Matches if ALL child masks match (space-separated)."""

    def __init__(self, masks: list[Mask]) -> None:
        self.masks = masks

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        return all(m.test(world, pos, context) for m in self.masks)


class ExistingMask(Mask):
    """Matches any non-air block (#existing)."""

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        return not world.get_block(pos).is_air


class AirMask(Mask):
    """Matches any air block (#air)."""

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        return world.get_block(pos).is_air


class SolidMask(Mask):
    """Matches any solid block (#solid)."""

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        return world.get_block(pos).is_solid


class LiquidMask(Mask):
    """Matches water or lava (#liquid)."""

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        return world.get_block(pos).is_liquid


class CategoryMask(Mask):
    """Matches any block belonging to a category (#wool, ##wool, #logs, etc.)."""

    def __init__(self, category: str) -> None:
        key = category.lower()
        if key not in BLOCK_CATEGORIES:
            raise ValueError(f"Unknown block category '#{category}'.")
        self.types = BLOCK_CATEGORIES[key]

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        return world.get_block(pos).block_type in self.types


@dataclass(frozen=True)
class OffsetMask(Mask):
    """Tests an inner mask at an offset relative to `pos` (e.g. >mask checks pos+(0,-1,0))."""

    inner: Mask
    offset: BlockVec3

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        return self.inner.test(world, pos + self.offset, context)


@dataclass(frozen=True)
class NoiseMask(Mask):
    """Matches randomly with probability `chance` in [0, 1] (%50 -> 0.5)."""

    chance: float

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        rng = context.rng if context is not None else random
        return rng.random() < self.chance


class RegionMask(Mask):
    """Matches positions inside the current player selection (#region / #sel)."""

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        if context is None or context.region is None:
            return False
        return bool(context.region.contains(pos))


class SurfaceMask(Mask):
    """Matches non-air blocks that have at least one air neighbor (#surface)."""

    _NEIGHBORS = (
        BlockVec3(1, 0, 0), BlockVec3(-1, 0, 0),
        BlockVec3(0, 1, 0), BlockVec3(0, -1, 0),
        BlockVec3(0, 0, 1), BlockVec3(0, 0, -1),
    )

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        if world.get_block(pos).is_air:
            return False
        return any(world.get_block(pos + d).is_air for d in self._NEIGHBORS)


class ExposedMask(Mask):
    """Matches non-air blocks exposed directly to air above (#exposed)."""

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        if world.get_block(pos).is_air:
            return False
        return world.get_block(pos + BlockVec3(0, 1, 0)).is_air


class ExpressionMask(Mask):
    """Evaluates a boolean math expression with variables x, y, z, rx, ry, rz (=expr)."""

    def __init__(self, compiled: CompiledExpression) -> None:
        self.compiled = compiled

    def test(self, world: WorldAdapter, pos: BlockVec3, context: MaskContext | None = None) -> bool:
        origin = context.origin if context is not None else BlockVec3(0, 0, 0)
        env = {
            "x": float(pos.x),
            "y": float(pos.y),
            "z": float(pos.z),
            "rx": float(pos.x - origin.x),
            "ry": float(pos.y - origin.y),
            "rz": float(pos.z - origin.z),
        }
        return self.compiled.evaluate(env) != 0.0


def _parse_atom_mask(token: str, context: MaskContext | None) -> Mask:
    tok = token.strip()
    if not tok:
        raise ValueError("Empty mask token.")

    if tok.startswith("!"):
        return NegatedMask(_parse_atom_mask(tok[1:], context))
    if tok.startswith(">"):
        # WorldEdit >mask means "above <mask>", i.e., block below (y - 1) matches mask.
        return OffsetMask(_parse_atom_mask(tok[1:], context), BlockVec3(0, -1, 0))
    if tok.startswith("<"):
        # WorldEdit <mask means "below <mask>", i.e., block above (y + 1) matches mask.
        return OffsetMask(_parse_atom_mask(tok[1:], context), BlockVec3(0, 1, 0))
    if tok.startswith("="):
        return ExpressionMask(compile_expression(tok[1:]))

    m_pct = _PERCENT_RE.match(tok)
    if m_pct:
        pct = float(m_pct.group(1)) / 100.0
        return NoiseMask(max(0.0, min(1.0, pct)))

    low = tok.lower()
    if low == "#existing":
        return ExistingMask()
    if low == "#solid":
        return SolidMask()
    if low == "#air":
        return AirMask()
    if low in ("#liquid", "#liquids"):
        return LiquidMask()
    if low in ("#region", "#sel", "#selection"):
        return RegionMask()
    if low == "#surface":
        return SurfaceMask()
    if low == "#exposed":
        return ExposedMask()
    if low == "#hand":
        if context is None or context.hand_block is None:
            raise ValueError("Hold a block in your hand to use '#hand' mask.")
        return BlockMask(context.hand_block)
    if low.startswith("##"):
        return CategoryMask(low[2:])
    if low.startswith("#"):
        cat = low[1:]
        if cat in BLOCK_CATEGORIES:
            return CategoryMask(cat)
        raise ValueError(f"Unknown mask tag '{tok}'.")

    return BlockMask(parse_block_spec(tok))


def parse_mask(expr: str, context: MaskContext | None = None) -> Mask:
    """Parse a WorldEdit mask expression supporting ',', '!', '>', '<', '%', '=', and spaces."""
    text = expr.strip()
    if not text:
        raise ValueError("Mask cannot be empty.")

    # Split top-level spaces outside brackets/parens -> intersection of union terms
    space_terms = split_top_level(text, " ")
    if len(space_terms) > 1 and not text.startswith("="):
        return IntersectionMask([parse_mask(term, context) for term in space_terms])

    comma_terms = split_top_level(text, ",")
    if len(comma_terms) == 1:
        return _parse_atom_mask(comma_terms[0], context)
    return UnionMask([_parse_atom_mask(t, context) for t in comma_terms])
