"""Per-player region selector state and selection wireframe outline point generator."""

from __future__ import annotations

import math

from ..core.regions import (
    CuboidSelector,
    CylinderRegion,
    EllipsoidRegion,
    Polygonal2DRegion,
    Region,
    RegionSelector,
    create_selector,
)
from ..core.types import BlockVec3
from .lang_manager import LangManager


class SelectionManager:
    """Stores active RegionSelectors per player and computes particle visualization outlines."""

    def __init__(self) -> None:
        self._selectors: dict[str, RegionSelector] = {}

    def get_selector(self, player_key: str) -> RegionSelector:
        sel = self._selectors.get(player_key)
        if sel is None:
            sel = CuboidSelector()
            self._selectors[player_key] = sel
        return sel

    def set_mode(self, player_key: str, mode: str) -> RegionSelector:
        sel = create_selector(mode)
        self._selectors[player_key] = sel
        return sel

    def clear(self, player_key: str) -> None:
        self.get_selector(player_key).clear()

    def remove_player(self, player_key: str) -> None:
        self._selectors.pop(player_key, None)

    def get_region(self, player_key: str) -> Region:
        return self.get_selector(player_key).get_region()

    def _localize_pos(
        self,
        sel: RegionSelector,
        slot: int,
        pos: BlockVec3,
        fallback_msg: str,
        lang: LangManager | None,
    ) -> str:
        if lang is None or lang.language == "en":
            return fallback_msg
        if sel.mode in ("cuboid",) and sel.is_defined():
            extra = f" ({sel.get_region().volume} บล็อก)"
        elif sel.mode == "cuboid":
            extra = ""
        else:
            extra = f" ({sel.get_region().volume} บล็อก)" if sel.is_defined() else ""
        if sel.mode == "cuboid":
            key = "wand.pos1" if slot == 1 else "wand.pos2"
            return lang.t(key, pos=pos.format_short(), extra=extra)
        if sel.mode == "extend" and sel.is_defined():
            return lang.t("wand.extend1" if slot == 1 else "wand.extend2", pos=pos.format_short(), vol=sel.get_region().volume)
        if sel.mode == "ellipsoid":
            if slot == 1:
                return lang.t("wand.ellipsoid1", pos=pos.format_short())
            reg = sel.get_region()
            if isinstance(reg, EllipsoidRegion):
                return lang.t("wand.ellipsoid2", rx=int(reg.rx), ry=int(reg.ry), rz=int(reg.rz), vol=reg.volume)
        if sel.mode == "sphere" and slot == 2 and sel.is_defined():
            reg = sel.get_region()
            if isinstance(reg, EllipsoidRegion):
                return lang.t("wand.sphere2", r=reg.rx, vol=reg.volume)
        if sel.mode == "cyl":
            if slot == 1:
                return lang.t("wand.cyl1", pos=pos.format_short())
            reg = sel.get_region()
            if isinstance(reg, CylinderRegion):
                return lang.t("wand.cyl2", rx=f"{reg.rx:.0f}", rz=f"{reg.rz:.0f}", h=reg.max_y - reg.min_y + 1, vol=reg.volume)
        return lang.t("wand.pos1" if slot == 1 else "wand.pos2", pos=pos.format_short(), extra=extra)

    def select_pos1(self, player_key: str, pos: BlockVec3, lang: LangManager | None = None) -> str:
        sel = self.get_selector(player_key)
        raw = sel.select_primary(pos)
        return self._localize_pos(sel, 1, pos, raw, lang)

    def select_pos2(self, player_key: str, pos: BlockVec3, lang: LangManager | None = None) -> str:
        sel = self.get_selector(player_key)
        raw = sel.select_secondary(pos)
        return self._localize_pos(sel, 2, pos, raw, lang)

    def get_outline_points(self, player_key: str, max_points: int = 160) -> list[tuple[float, float, float]]:
        """Sample outline coordinates for particle rendering (`//drawsel`)."""
        sel = self._selectors.get(player_key)
        if sel is None or not sel.is_defined():
            return []
        region = sel.get_region()

        if isinstance(region, EllipsoidRegion):
            pts: list[tuple[float, float, float]] = []
            cx, cy, cz = region.origin.x + 0.5, region.origin.y + 0.5, region.origin.z + 0.5
            steps = 24
            for i in range(steps):
                a = 2.0 * math.pi * i / steps
                ca, sa = math.cos(a), math.sin(a)
                pts.append((cx + region.rx * ca, cy, cz + region.rz * sa))
                pts.append((cx + region.rx * ca, cy + region.ry * sa, cz))
                pts.append((cx, cy + region.ry * ca, cz + region.rz * sa))
            return pts[:max_points]

        if isinstance(region, CylinderRegion):
            pts = []
            cx, cz = region.center_x + 0.5, region.center_z + 0.5
            steps = 28
            for y in (float(region.min_y), float(region.max_y + 1)):
                for i in range(steps):
                    a = 2.0 * math.pi * i / steps
                    pts.append((cx + (region.rx + 0.5) * math.cos(a), y, cz + (region.rz + 0.5) * math.sin(a)))
            return pts[:max_points]

        if isinstance(region, Polygonal2DRegion) and len(region.points) >= 2:
            pts = []
            n = len(region.points)
            for y in (float(region.min_y), float(region.max_y + 1)):
                for i in range(n):
                    x0, z0 = region.points[i]
                    x1, z1 = region.points[(i + 1) % n]
                    for s in range(6):
                        t = s / 6.0
                        pts.append((x0 + 0.5 + (x1 - x0) * t, y, z0 + 0.5 + (z1 - z0) * t))
            return pts[:max_points]

        lo, hi = region.min_point, region.max_point
        x0, y0, z0 = float(lo.x), float(lo.y), float(lo.z)
        x1, y1, z1 = float(hi.x + 1), float(hi.y + 1), float(hi.z + 1)
        pts = []
        edge_samples = max(2, min(16, max_points // 12))
        edges = [
            ((x0, y0, z0), (x1, y0, z0)), ((x0, y1, z0), (x1, y1, z0)),
            ((x0, y0, z1), (x1, y0, z1)), ((x0, y1, z1), (x1, y1, z1)),
            ((x0, y0, z0), (x0, y1, z0)), ((x1, y0, z0), (x1, y1, z0)),
            ((x0, y0, z1), (x0, y1, z1)), ((x1, y0, z1), (x1, y1, z1)),
            ((x0, y0, z0), (x0, y0, z1)), ((x1, y0, z0), (x1, y0, z1)),
            ((x0, y1, z0), (x0, y1, z1)), ((x1, y1, z0), (x1, y1, z1)),
        ]
        for (ax, ay, az), (bx, by, bz) in edges:
            for s in range(edge_samples + 1):
                t = s / edge_samples
                pts.append((ax + (bx - ax) * t, ay + (by - ay) * t, az + (bz - az) * t))
        return pts[:max_points]
