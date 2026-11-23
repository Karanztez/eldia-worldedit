"""Undo and redo ChangeSet stack management per player."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable

from ..world.adapter import WorldAdapter
from ..world.edit_session import ChangeSet


class HistoryManager:
    """Maintains bounded per-player undo and redo stacks."""

    def __init__(self, max_history: int = 30) -> None:
        self.max_history = max(1, max_history)
        self._undo: dict[str, deque[ChangeSet]] = {}
        self._redo: dict[str, deque[ChangeSet]] = {}

    def record(self, player_key: str, change_set: ChangeSet) -> None:
        if len(change_set) == 0:
            return
        undo_stack = self._undo.setdefault(player_key, deque(maxlen=self.max_history))
        undo_stack.append(change_set)
        self._redo[player_key] = deque(maxlen=self.max_history)

    def undo(
        self,
        player_key: str,
        world_resolver: Callable[[str], WorldAdapter | None],
        count: int = 1,
        fast_mode: bool = False,
    ) -> tuple[int, int]:
        """Undo up to `count` edits. Returns `(steps_undone, blocks_reverted)`."""
        if count <= 0:
            return 0, 0
        undo_stack = self._undo.get(player_key)
        if not undo_stack:
            return 0, 0
        redo_stack = self._redo.setdefault(player_key, deque(maxlen=self.max_history))
        steps = 0
        blocks = 0
        for _ in range(count):
            if not undo_stack:
                break
            cs = undo_stack.pop()
            world = world_resolver(cs.dimension_name)
            if world is None:
                undo_stack.append(cs)
                break
            blocks += cs.apply_undo(world, fast_mode=fast_mode)
            redo_stack.append(cs)
            steps += 1
        return steps, blocks

    def redo(
        self,
        player_key: str,
        world_resolver: Callable[[str], WorldAdapter | None],
        count: int = 1,
        fast_mode: bool = False,
    ) -> tuple[int, int]:
        """Redo up to `count` undone edits. Returns `(steps_redone, blocks_applied)`."""
        if count <= 0:
            return 0, 0
        redo_stack = self._redo.get(player_key)
        if not redo_stack:
            return 0, 0
        undo_stack = self._undo.setdefault(player_key, deque(maxlen=self.max_history))
        steps = 0
        blocks = 0
        for _ in range(count):
            if not redo_stack:
                break
            cs = redo_stack.pop()
            world = world_resolver(cs.dimension_name)
            if world is None:
                redo_stack.append(cs)
                break
            blocks += cs.apply_redo(world, fast_mode=fast_mode)
            undo_stack.append(cs)
            steps += 1
        return steps, blocks

    def clear(self, player_key: str) -> int:
        cleared = len(self._undo.get(player_key, ())) + len(self._redo.get(player_key, ()))
        self._undo.pop(player_key, None)
        self._redo.pop(player_key, None)
        return cleared

    def stats(self, player_key: str) -> tuple[int, int]:
        return len(self._undo.get(player_key, ())), len(self._redo.get(player_key, ()))
