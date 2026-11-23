"""Per-player bound item tools, brushes, super pickaxe settings, and click debouncing."""

from __future__ import annotations

import time

from ..tools.brushes import BrushConfig
from ..tools.items import SuperPickaxeConfig, ToolConfig


class ToolManager:
    """Stores per-player item-bound tools, brushes, and Super Pickaxe state."""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, ToolConfig]] = {}
        self._brushes: dict[str, dict[str, BrushConfig]] = {}
        self._super_pickaxe: dict[str, SuperPickaxeConfig] = {}
        self._last_left_click: dict[str, float] = {}

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

    def should_debounce_left_click(
        self,
        player_key: str,
        now_ms: float | None = None,
        cooldown_ms: float = 150.0,
    ) -> bool:
        """Prevent duplicate wand/tool firing when BDS sends both interact & break events."""
        ts = now_ms if now_ms is not None else time.monotonic() * 1000.0
        prev = self._last_left_click.get(player_key, -1e12)
        if ts - prev < cooldown_ms:
            return True
        self._last_left_click[player_key] = ts
        return False

    def remove_player(self, player_key: str) -> None:
        self._tools.pop(player_key, None)
        self._brushes.pop(player_key, None)
        self._super_pickaxe.pop(player_key, None)
        self._last_left_click.pop(player_key, None)
