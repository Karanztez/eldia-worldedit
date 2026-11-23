"""Per-player WorldEdit configuration session (limits, gmask, fast mode, reorder, wand, placement)."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.masks import Mask, MaskContext, parse_mask
from ..core.regions import RegionSelector
from ..core.types import BlockVec3


@dataclass
class LocalSession:
    """Mutable per-player WorldEdit preferences and session guards."""

    block_change_limit: int = 500_000
    fast_mode: bool = False
    reorder_mode: str = "none"
    side_effect_mode: str = "default"
    wand_enabled: bool = True
    wand_item: str = "minecraft:wooden_axe"
    nav_wand_item: str = "minecraft:compass"
    drawsel_enabled: bool = False
    place_mode: str = "pos1"
    gmask_expr: str | None = None
    gtransform_expr: str | None = None
    timeout_ms: int = 30_000
    keep_inventory_drop: bool = True


class SessionManager:
    """Manages LocalSession records and policy limits across connected players."""

    def __init__(self, default_limit: int = 500_000, max_limit: int = -1) -> None:
        self.default_limit = default_limit
        self.max_limit = max_limit
        self._sessions: dict[str, LocalSession] = {}

    def get(self, player_key: str) -> LocalSession:
        sess = self._sessions.get(player_key)
        if sess is None:
            sess = LocalSession(block_change_limit=self.default_limit)
            self._sessions[player_key] = sess
        return sess

    def set_limit(self, player_key: str, limit: int) -> int:
        sess = self.get(player_key)
        if self.max_limit >= 0 and (limit < 0 or limit > self.max_limit):
            effective = self.max_limit
        else:
            effective = limit
        sess.block_change_limit = effective
        return effective

    def resolve_placement_origin(
        self,
        player_key: str,
        player_pos: BlockVec3,
        selector: RegionSelector,
    ) -> BlockVec3:
        sess = self.get(player_key)
        if sess.place_mode == "pos1" and selector.primary_position is not None:
            return selector.primary_position
        return player_pos

    def get_gmask(self, player_key: str, context: MaskContext | None = None) -> Mask | None:
        expr = self.get(player_key).gmask_expr
        if not expr:
            return None
        return parse_mask(expr, context)

    def remove(self, player_key: str) -> None:
        self._sessions.pop(player_key, None)
