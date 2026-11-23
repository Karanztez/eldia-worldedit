"""Per-player bound item tools, brushes, super pickaxe settings, and click debouncing."""

from __future__ import annotations

import time

from ..core.types import BlockVec3
from ..tools.brushes import BrushConfig
from ..tools.items import SuperPickaxeConfig, ToolConfig


class ToolManager:
    """Stores per-player item-bound tools, brushes, and Super Pickaxe state."""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, ToolConfig]] = {}
        self._brushes: dict[str, dict[str, BrushConfig]] = {}
        self._super_pickaxe: dict[str, SuperPickaxeConfig] = {}
        self._last_click: dict[tuple[str, str], float] = {}
        self._last_pos: dict[tuple[str, str], tuple[BlockVec3, float]] = {}

    def bind_tool(self, player_key: str, item_id: str, tool: ToolConfig) -> None:
        key = item_id.lower()
        self._brushes.get(player_key, {}).pop(key, None)
        self._tools.setdefault(player_key, {})[key] = tool

    def bind_brush(self, player_key: str, item_id: str, brush: BrushConfig) -> None:
        key = item_id.lower()
        self._tools.get(player_key, {}).pop(key, None)
        self._brushes.setdefault(player_key, {})[key] = brush

    def get_tool(self, player_key: str, item_id: str) -> ToolConfig | None:
        return self._tools.get(player_key, {}).get(item_id.lower())

    def get_brush(self, player_key: str, item_id: str) -> BrushConfig | None:
        return self._brushes.get(player_key, {}).get(item_id.lower())

    def unbind(self, player_key: str, item_id: str) -> bool:
        key = item_id.lower()
        removed_t = self._tools.get(player_key, {}).pop(key, None) is not None
        removed_b = self._brushes.get(player_key, {}).pop(key, None) is not None
        return removed_t or removed_b

    def unbind_all(self, player_key: str) -> int:
        cnt = len(self._tools.get(player_key, {})) + len(self._brushes.get(player_key, {}))
        self._tools.pop(player_key, None)
        self._brushes.pop(player_key, None)
        return cnt

    def get_super_pickaxe(self, player_key: str) -> SuperPickaxeConfig:
        cfg = self._super_pickaxe.get(player_key)
        if cfg is None:
            cfg = SuperPickaxeConfig()
            self._super_pickaxe[player_key] = cfg
        return cfg

    def should_debounce(
        self,
        player_key: str,
        action: str = "left",
        now_ms: float | None = None,
        cooldown_ms: float = 250.0,
    ) -> bool:
        """Debounce rapid repeated Bedrock click events per player and click direction."""
        ts = now_ms if now_ms is not None else time.monotonic() * 1000.0
        key = (player_key, action)
        prev = self._last_click.get(key, -1e12)
        if ts - prev < cooldown_ms:
            return True
        self._last_click[key] = ts
        return False

    def should_debounce_left_click(
        self,
        player_key: str,
        now_ms: float | None = None,
        cooldown_ms: float = 200.0,
    ) -> bool:
        return self.should_debounce(player_key, action="left", now_ms=now_ms, cooldown_ms=cooldown_ms)

    def should_debounce_right_click(
        self,
        player_key: str,
        now_ms: float | None = None,
        cooldown_ms: float = 300.0,
    ) -> bool:
        return self.should_debounce(player_key, action="right", now_ms=now_ms, cooldown_ms=cooldown_ms)

    def should_suppress_repeat_pos(
        self,
        player_key: str,
        slot: str,
        pos: BlockVec3,
        now_ms: float | None = None,
        window_ms: float = 750.0,
    ) -> bool:
        """Suppress continuous Bedrock hold/spam selecting the identical coordinate repeatedly."""
        ts = now_ms if now_ms is not None else time.monotonic() * 1000.0
        key = (player_key, slot)
        prev = self._last_pos.get(key)
        self._last_pos[key] = (pos, ts)
        if prev is not None:
            prev_pos, prev_ts = prev
            if prev_pos == pos and (ts - prev_ts) < window_ms:
                return True
        return False

    def remove_player(self, player_key: str) -> None:
        self._tools.pop(player_key, None)
        self._brushes.pop(player_key, None)
        self._super_pickaxe.pop(player_key, None)
        self._last_click = {k: v for k, v in self._last_click.items() if k[0] != player_key}
        self._last_pos = {k: v for k, v in self._last_pos.items() if k[0] != player_key}
