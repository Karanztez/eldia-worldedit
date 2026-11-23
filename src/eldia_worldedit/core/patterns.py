"""WorldEdit block pattern DSL and evaluators (50%stone,dirt, #clipboard, #hand, ##wool, ^states)."""

from __future__ import annotations

import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .command_parser import split_top_level
from .types import (
    AIR_SPEC,
    BLOCK_CATEGORIES,
    BlockSpec,
    BlockVec3,
    parse_block_spec,
)

if TYPE_CHECKING:
    from ..clipboard.clipboard import Clipboard
    from ..world.adapter import WorldAdapter

_WEIGHT_RE = re.compile(r"^(\d+(?:\.\d+)?)%(.+)$")


@dataclass
class PatternContext:
    """Runtime context supplied when evaluating contextual patterns."""

    world: WorldAdapter | None = None
    clipboard: Clipboard | None = None
    hand_block: BlockSpec | None = None
    origin: BlockVec3 = field(default_factory=lambda: BlockVec3(0, 0, 0))
    region: Any = None


class Pattern(ABC):
    """Produces a BlockSpec for a target world coordinate."""

    @abstractmethod
    def apply(self, pos: BlockVec3, rng: random.Random, context: PatternContext) -> BlockSpec:
        """Evaluate the pattern at `pos`."""


@dataclass(frozen=True)
class BlockPattern(Pattern):
    """Constant single-block pattern."""

    spec: BlockSpec

    def apply(self, pos: BlockVec3, rng: random.Random, context: PatternContext) -> BlockSpec:
        return self.spec


class RandomPattern(Pattern):
    """Weighted random selection over child patterns."""

    def __init__(self, entries: list[tuple[float, Pattern]]) -> None:
        if not entries:
            raise ValueError("RandomPattern requires at least one entry.")
        self.entries = entries
        self._cumulative: list[float] = []
        total = 0.0
        for weight, _ in entries:
            if weight < 0:
                raise ValueError("Pattern weights must be non-negative.")
            total += weight
            self._cumulative.append(total)
        if total <= 0:
            raise ValueError("Total pattern weight must be positive.")
        self.total_weight = total

    def apply(self, pos: BlockVec3, rng: random.Random, context: PatternContext) -> BlockSpec:
        pick = rng.random() * self.total_weight
        for bound, (_, pat) in zip(self._cumulative, self.entries, strict=True):
            if pick <= bound:
                return pat.apply(pos, rng, context)
        return self.entries[-1][1].apply(pos, rng, context)


class ClipboardPattern(Pattern):
    """Repeats the player's clipboard blocks relative to the paste/pattern origin."""

    def apply(self, pos: BlockVec3, rng: random.Random, context: PatternContext) -> BlockSpec:
        cb = context.clipboard
        if cb is None or not cb.blocks:
            return AIR_SPEC
        size_x = max(1, cb.max_point.x - cb.min_point.x + 1)
        size_y = max(1, cb.max_point.y - cb.min_point.y + 1)
        size_z = max(1, cb.max_point.z - cb.min_point.z + 1)
        rel = pos - context.origin
        wrapped = BlockVec3(
            cb.min_point.x + (rel.x % size_x),
            cb.min_point.y + (rel.y % size_y),
            cb.min_point.z + (rel.z % size_z),
        )
        return cb.blocks.get(wrapped, AIR_SPEC)


class HandPattern(Pattern):
    """Uses the block type currently held in the player's main hand."""

    def apply(self, pos: BlockVec3, rng: random.Random, context: PatternContext) -> BlockSpec:
        if context.hand_block is None:
            raise ValueError("You must hold a block in your main hand to use '#hand'.")
        return context.hand_block


class CategoryPattern(Pattern):
    """Randomly picks a block from a block tag/category such as ##wool or #logs."""

    def __init__(self, category: str) -> None:
        key = category.lower()
        if key not in BLOCK_CATEGORIES:
            raise ValueError(f"Unknown block category '#{category}'.")
        self.category = key
        self.choices = tuple(sorted(BLOCK_CATEGORIES[key]))

    def apply(self, pos: BlockVec3, rng: random.Random, context: PatternContext) -> BlockSpec:
        return BlockSpec(rng.choice(self.choices))


class BlockStatePattern(Pattern):
    """Applies specific block states onto existing blocks (or overrides type + states)."""

    def __init__(self, states: tuple[tuple[str, bool | int | str], ...], override_type: str | None) -> None:
        self.states = states
        self.override_type = override_type

    def apply(self, pos: BlockVec3, rng: random.Random, context: PatternContext) -> BlockSpec:
        if context.world is None:
            base = BlockSpec(self.override_type or "minecraft:stone")
        else:
            base = context.world.get_block(pos)
        merged = dict(base.states)
        for k, v in self.states:
            merged[k] = v
        btype = self.override_type or base.block_type
        return BlockSpec(btype, tuple(sorted(merged.items())))


def _parse_single_pattern(token: str, context: PatternContext | None) -> Pattern:
    tok = token.strip()
    if not tok:
        raise ValueError("Empty pattern component.")
    low = tok.lower()

    if low in ("#clipboard", "#copy"):
        if context is not None and context.clipboard is None:
            raise ValueError("Your clipboard is empty for '#clipboard'.")
        return ClipboardPattern()
    if low == "#hand":
        if context is not None and context.hand_block is None:
            raise ValueError("You must hold a block in your hand for '#hand'.")
        return HandPattern()
    if low.startswith("##"):
        return CategoryPattern(low[2:])
    if low.startswith("#"):
        cat = low[1:]
        if cat in BLOCK_CATEGORIES:
            return CategoryPattern(cat)
        raise ValueError(f"Unknown pattern tag '{tok}'.")
    if tok.startswith("^"):
        raw_inner = tok[1:].strip()
        if raw_inner.startswith("[") and raw_inner.endswith("]"):
            # State-only override: ^[facing_direction=2]
            spec = parse_block_spec(f"stone{raw_inner}")
            return BlockStatePattern(spec.states, override_type=None)
        spec = parse_block_spec(raw_inner)
        return BlockStatePattern(spec.states, override_type=spec.block_type)

    return BlockPattern(parse_block_spec(tok))


def parse_pattern(expr: str, context: PatternContext | None = None) -> Pattern:
    """Parse a WorldEdit pattern string (e.g., '50%stone,30%cobblestone,20%andesite')."""
    text = expr.strip()
    if not text:
        raise ValueError("Pattern cannot be empty.")

    parts = split_top_level(text, ",")
    if len(parts) == 1:
        m = _WEIGHT_RE.match(parts[0])
        if m:
            return _parse_single_pattern(m.group(2), context)
        return _parse_single_pattern(parts[0], context)

    entries: list[tuple[float, Pattern]] = []
    for part in parts:
        m = _WEIGHT_RE.match(part)
        if m:
            weight = float(m.group(1))
            inner = _parse_single_pattern(m.group(2), context)
            entries.append((weight, inner))
        else:
            entries.append((1.0, _parse_single_pattern(part, context)))
    return RandomPattern(entries)
