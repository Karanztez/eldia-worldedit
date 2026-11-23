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

    def select_pos1(self, player_key: str, pos: BlockVec3) -> str:
        return self.get_selector(player_key).select_primary(pos)

    def select_pos2(self, player_key: str, pos: BlockVec3) -> str:
        return self.get_selector(player_key).select_secondary(pos)

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

        # Cuboid or bounding box edges (12 edges of the inclusive box)
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
