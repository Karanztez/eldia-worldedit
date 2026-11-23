"""Transactional EditSession with undo/redo ChangeSets, global mask, block limit, and batched commits."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..core.masks import Mask, MaskContext
from ..core.types import BlockSpec, BlockVec3
from .adapter import WorldAdapter


class MaxChangedBlocksException(RuntimeError):
    """Raised when an operation attempts to modify more blocks than the session limit allows."""


@dataclass(frozen=True)
class BlockChange:
    """Single block mutation recorded for undo/redo."""

    pos: BlockVec3
    before: BlockSpec
    after: BlockSpec


@dataclass
class ChangeSet:
    """Ordered collection of block mutations inside a specific dimension."""

    dimension_name: str
    changes: list[BlockChange] = field(default_factory=list)
    description: str = ""

    def __len__(self) -> int:
        return len(self.changes)

    def apply_undo(self, world: WorldAdapter, fast_mode: bool = False) -> int:
        count = 0
        for change in reversed(self.changes):
            world.set_block(change.pos, change.before, apply_physics=not fast_mode)
            count += 1
        return count

    def apply_redo(self, world: WorldAdapter, fast_mode: bool = False) -> int:
        count = 0
        for change in self.changes:
            world.set_block(change.pos, change.after, apply_physics=not fast_mode)
            count += 1
        return count


class EditSession:
    """Buffers or applies block edits with limit checking, gmask filtering, and undo tracking."""

    def __init__(
        self,
        world: WorldAdapter,
        limit: int = -1,
        gmask: Mask | None = None,
        fast_mode: bool = False,
        reorder_mode: str = "none",
        mask_context: MaskContext | None = None,
        description: str = "",
    ) -> None:
        self.world = world
        self.limit = limit
        self.gmask = gmask
        self.fast_mode = fast_mode
        self.reorder_mode = reorder_mode
        self.mask_context = mask_context
        self.change_set = ChangeSet(dimension_name=world.name, description=description)
        self._staged: dict[BlockVec3, BlockSpec] = {}
        self.changes_count = 0

    def get_block(self, pos: BlockVec3) -> BlockSpec:
        if pos in self._staged:
            return self._staged[pos]
        return self.world.get_block(pos)

    def set_block(self, pos: BlockVec3, spec: BlockSpec) -> bool:
        """Queue a block change if within bounds, passing gmask, and under change limit."""
        if pos.y < self.world.min_y or pos.y > self.world.max_y:
            return False
        if self.gmask is not None and not self.gmask.test(self.world, pos, self.mask_context):
            return False

        before = self.get_block(pos)
        if before == spec:
            return False

        if 0 <= self.limit <= self.changes_count:
            raise MaxChangedBlocksException(
                f"Block change limit ({self.limit}) exceeded while editing."
            )

        self._staged[pos] = spec
        self.change_set.changes.append(BlockChange(pos=pos, before=before, after=spec))
        self.changes_count += 1
        return True

    def _ordered_changes(self) -> list[BlockChange]:
        changes = list(self.change_set.changes)
        if self.reorder_mode == "multi_stage":
            # Place solid structural blocks before non-solid attachments (torches, plants, etc.).
            changes.sort(key=lambda c: (0 if c.after.is_solid else 1, c.pos.y))
        elif self.reorder_mode == "bottom_up":
            changes.sort(key=lambda c: c.pos.y)
        return changes

    def commit(
        self,
        scheduler: Any = None,
        plugin: Any = None,
        batch_size: int = 4096,
        on_complete: Callable[[int], None] | None = None,
    ) -> int:
        """Apply all staged changes synchronously or in per-tick batches via Endstone Scheduler."""
        ordered = self._ordered_changes()
        self.change_set.changes = ordered
        total = len(ordered)
        if total == 0:
            if on_complete is not None:
                on_complete(0)
            return 0

        apply_physics = not self.fast_mode
        if scheduler is None or plugin is None or total <= batch_size:
            for ch in ordered:
                self.world.set_block(ch.pos, ch.after, apply_physics=apply_physics)
            self._staged.clear()
            if on_complete is not None:
                on_complete(total)
            return total

        index = 0
        task_holder: dict[str, Any] = {"task": None}

        def _step() -> None:
            nonlocal index
            end = min(index + batch_size, total)
            for i in range(index, end):
                ch = ordered[i]
                self.world.set_block(ch.pos, ch.after, apply_physics=apply_physics)
            index = end
            if index >= total:
                self._staged.clear()
                if task_holder["task"] is not None:
                    task_holder["task"].cancel()
                if on_complete is not None:
                    on_complete(total)

        task_holder["task"] = scheduler.run_task(plugin, _step, delay=1, period=1)
        return total
