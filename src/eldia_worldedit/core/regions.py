"""WorldEdit regions and all 7 region selector types (cuboid, extend, ellipsoid, sphere, cyl, poly, convex)."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field

from .types import BlockVec3


class IncompleteRegionError(ValueError):
    """Raised when a player has not completed selecting a region."""


class Region(ABC):
    """Abstract 3D editable region."""

    @property
    @abstractmethod
    def min_point(self) -> BlockVec3:
        """Minimum inclusive corner of the region bounding box."""

    @property
    @abstractmethod
    def max_point(self) -> BlockVec3:
        """Maximum inclusive corner of the region bounding box."""

    @property
    def dimensions(self) -> BlockVec3:
        lo, hi = self.min_point, self.max_point
        return BlockVec3(hi.x - lo.x + 1, hi.y - lo.y + 1, hi.z - lo.z + 1)

    @property
    def center(self) -> BlockVec3:
        lo, hi = self.min_point, self.max_point
        return BlockVec3((lo.x + hi.x) // 2, (lo.y + hi.y) // 2, (lo.z + hi.z) // 2)

    @property
    def volume(self) -> int:
        count = 0
        for _ in self.iter_positions():
            count += 1
        return count

    @abstractmethod
    def contains(self, pos: BlockVec3) -> bool:
        """Return True if `pos` is inside this region."""

    def iter_positions(self) -> Iterator[BlockVec3]:
        lo, hi = self.min_point, self.max_point
        for x in range(lo.x, hi.x + 1):
            for z in range(lo.z, hi.z + 1):
                for y in range(lo.y, hi.y + 1):
                    p = BlockVec3(x, y, z)
                    if self.contains(p):
                        yield p

    def iter_walls(self) -> Iterator[BlockVec3]:
        lo, hi = self.min_point, self.max_point
        for p in self.iter_positions():
            if p.x in (lo.x, hi.x) or p.z in (lo.z, hi.z):
                yield p

    def iter_faces(self) -> Iterator[BlockVec3]:
        lo, hi = self.min_point, self.max_point
        for p in self.iter_positions():
            if p.x in (lo.x, hi.x) or p.y in (lo.y, hi.y) or p.z in (lo.z, hi.z):
                yield p

    @abstractmethod
    def expand(self, delta: BlockVec3) -> None: ...

    @abstractmethod
    def contract(self, delta: BlockVec3) -> None: ...

    @abstractmethod
    def shift(self, delta: BlockVec3) -> None: ...

    def outset(self, amount: int, h_only: bool = False, v_only: bool = False) -> None:
        if not v_only:
            self.expand(BlockVec3(amount, 0, amount))
            self.expand(BlockVec3(-amount, 0, -amount))
        if not h_only:
            self.expand(BlockVec3(0, amount, 0))
            self.expand(BlockVec3(0, -amount, 0))

    def inset(self, amount: int, h_only: bool = False, v_only: bool = False) -> None:
        if not v_only:
            self.contract(BlockVec3(amount, 0, amount))
            self.contract(BlockVec3(-amount, 0, -amount))
        if not h_only:
            self.contract(BlockVec3(0, amount, 0))
            self.contract(BlockVec3(0, -amount, 0))

    @abstractmethod
    def clone(self) -> Region: ...


@dataclass
class CuboidRegion(Region):
    """Axis-aligned cuboid defined by two inclusive endpoints."""

    pos1: BlockVec3
    pos2: BlockVec3

    @property
    def min_point(self) -> BlockVec3:
        return self.pos1.min_with(self.pos2)

    @property
    def max_point(self) -> BlockVec3:
        return self.pos1.max_with(self.pos2)

    @property
    def volume(self) -> int:
        dims = self.dimensions
        return dims.x * dims.y * dims.z

    def contains(self, pos: BlockVec3) -> bool:
        lo, hi = self.min_point, self.max_point
        return lo.x <= pos.x <= hi.x and lo.y <= pos.y <= hi.y and lo.z <= pos.z <= hi.z

    def iter_positions(self) -> Iterator[BlockVec3]:
        lo, hi = self.min_point, self.max_point
        for x in range(lo.x, hi.x + 1):
            for z in range(lo.z, hi.z + 1):
                for y in range(lo.y, hi.y + 1):
                    yield BlockVec3(x, y, z)

    def _normalize_endpoints(self) -> tuple[BlockVec3, BlockVec3]:
        return self.min_point, self.max_point

    def expand(self, delta: BlockVec3) -> None:
        lo, hi = self._normalize_endpoints()
        nx1 = lo.x + delta.x if delta.x < 0 else lo.x
        ny1 = lo.y + delta.y if delta.y < 0 else lo.y
        nz1 = lo.z + delta.z if delta.z < 0 else lo.z
        nx2 = hi.x + delta.x if delta.x > 0 else hi.x
        ny2 = hi.y + delta.y if delta.y > 0 else hi.y
        nz2 = hi.z + delta.z if delta.z > 0 else hi.z
        self.pos1 = BlockVec3(min(nx1, nx2), min(ny1, ny2), min(nz1, nz2))
        self.pos2 = BlockVec3(max(nx1, nx2), max(ny1, ny2), max(nz1, nz2))

    def contract(self, delta: BlockVec3) -> None:
        lo, hi = self._normalize_endpoints()
        # Positive delta contracts from the negative/min face inward; negative contracts from max face inward.
        nx1 = lo.x + delta.x if delta.x > 0 else lo.x
        ny1 = lo.y + delta.y if delta.y > 0 else lo.y
        nz1 = lo.z + delta.z if delta.z > 0 else lo.z
        nx2 = hi.x + delta.x if delta.x < 0 else hi.x
        ny2 = hi.y + delta.y if delta.y < 0 else hi.y
        nz2 = hi.z + delta.z if delta.z < 0 else hi.z
        self.pos1 = BlockVec3(min(nx1, nx2), min(ny1, ny2), min(nz1, nz2))
        self.pos2 = BlockVec3(max(nx1, nx2), max(ny1, ny2), max(nz1, nz2))

    def shift(self, delta: BlockVec3) -> None:
        self.pos1 = self.pos1 + delta
        self.pos2 = self.pos2 + delta

    def clone(self) -> CuboidRegion:
        return CuboidRegion(self.pos1, self.pos2)


@dataclass
class EllipsoidRegion(Region):
    """Axis-aligned 3D ellipsoid centered at `origin` with semi-axes `radius`."""

    origin: BlockVec3
    rx: float
    ry: float
    rz: float

    @property
    def min_point(self) -> BlockVec3:
        return BlockVec3(
            self.origin.x - math.floor(self.rx),
            self.origin.y - math.floor(self.ry),
            self.origin.z - math.floor(self.rz),
        )

    @property
    def max_point(self) -> BlockVec3:
        return BlockVec3(
            self.origin.x + math.floor(self.rx),
            self.origin.y + math.floor(self.ry),
            self.origin.z + math.floor(self.rz),
        )

    def contains(self, pos: BlockVec3) -> bool:
        dx = (pos.x - self.origin.x) / max(0.5, self.rx + 0.5)
        dy = (pos.y - self.origin.y) / max(0.5, self.ry + 0.5)
        dz = (pos.z - self.origin.z) / max(0.5, self.rz + 0.5)
        return dx * dx + dy * dy + dz * dz <= 1.0

    def expand(self, delta: BlockVec3) -> None:
        self.rx = max(0.0, self.rx + abs(delta.x))
        self.ry = max(0.0, self.ry + abs(delta.y))
        self.rz = max(0.0, self.rz + abs(delta.z))

    def contract(self, delta: BlockVec3) -> None:
        self.rx = max(0.0, self.rx - abs(delta.x))
        self.ry = max(0.0, self.ry - abs(delta.y))
        self.rz = max(0.0, self.rz - abs(delta.z))

    def shift(self, delta: BlockVec3) -> None:
        self.origin = self.origin + delta

    def clone(self) -> EllipsoidRegion:
        return EllipsoidRegion(self.origin, self.rx, self.ry, self.rz)


@dataclass
class CylinderRegion(Region):
    """Vertical elliptical cylinder centered at (center_x, center_z) spanning [min_y, max_y]."""

    center_x: int
    center_z: int
    rx: float
    rz: float
    min_y: int
    max_y: int

    @property
    def min_point(self) -> BlockVec3:
        return BlockVec3(self.center_x - math.floor(self.rx), self.min_y, self.center_z - math.floor(self.rz))

    @property
    def max_point(self) -> BlockVec3:
        return BlockVec3(self.center_x + math.floor(self.rx), self.max_y, self.center_z + math.floor(self.rz))

    def contains(self, pos: BlockVec3) -> bool:
        if not (self.min_y <= pos.y <= self.max_y):
            return False
        dx = (pos.x - self.center_x) / max(0.5, self.rx + 0.5)
        dz = (pos.z - self.center_z) / max(0.5, self.rz + 0.5)
        return dx * dx + dz * dz <= 1.0

    def expand(self, delta: BlockVec3) -> None:
        self.rx = max(0.0, self.rx + abs(delta.x))
        self.rz = max(0.0, self.rz + abs(delta.z))
        if delta.y < 0:
            self.min_y += delta.y
        elif delta.y > 0:
            self.max_y += delta.y

    def contract(self, delta: BlockVec3) -> None:
        self.rx = max(0.0, self.rx - abs(delta.x))
        self.rz = max(0.0, self.rz - abs(delta.z))
        if delta.y > 0:
            self.min_y = min(self.max_y, self.min_y + delta.y)
        elif delta.y < 0:
            self.max_y = max(self.min_y, self.max_y + delta.y)

    def shift(self, delta: BlockVec3) -> None:
        self.center_x += delta.x
        self.center_z += delta.z
        self.min_y += delta.y
        self.max_y += delta.y

    def clone(self) -> CylinderRegion:
        return CylinderRegion(self.center_x, self.center_z, self.rx, self.rz, self.min_y, self.max_y)


@dataclass
class Polygonal2DRegion(Region):
    """2D polygon extruded vertically between `min_y` and `max_y`."""

    points: list[tuple[int, int]]
    min_y: int
    max_y: int

    @property
    def min_point(self) -> BlockVec3:
        min_x = min(p[0] for p in self.points)
        min_z = min(p[1] for p in self.points)
        return BlockVec3(min_x, self.min_y, min_z)

    @property
    def max_point(self) -> BlockVec3:
        max_x = max(p[0] for p in self.points)
        max_z = max(p[1] for p in self.points)
        return BlockVec3(max_x, self.max_y, max_z)

    def contains(self, pos: BlockVec3) -> bool:
        if not (self.min_y <= pos.y <= self.max_y) or len(self.points) < 3:
            return False
        px, pz = pos.x + 0.5, pos.z + 0.5
        inside = False
        n = len(self.points)
        j = n - 1
        for i in range(n):
            xi, zi = self.points[i][0] + 0.5, self.points[i][1] + 0.5
            xj, zj = self.points[j][0] + 0.5, self.points[j][1] + 0.5
            # Check exact vertex/edge match first
            if _point_on_segment(pos.x, pos.z, self.points[i][0], self.points[i][1], self.points[j][0], self.points[j][1]):
                return True
            if ((zi > pz) != (zj > pz)) and (px < (xj - xi) * (pz - zi) / (zj - zi + 1e-12) + xi):
                inside = not inside
            j = i
        return inside

    def iter_walls(self) -> Iterator[BlockVec3]:
        if len(self.points) < 2:
            return
        seen: set[tuple[int, int]] = set()
        n = len(self.points)
        for i in range(n):
            x0, z0 = self.points[i]
            x1, z1 = self.points[(i + 1) % n]
            for x, z in _bresenham_2d(x0, z0, x1, z1):
                if (x, z) not in seen:
                    seen.add((x, z))
                    for y in range(self.min_y, self.max_y + 1):
                        yield BlockVec3(x, y, z)

    def expand(self, delta: BlockVec3) -> None:
        if delta.y < 0:
            self.min_y += delta.y
        elif delta.y > 0:
            self.max_y += delta.y

    def contract(self, delta: BlockVec3) -> None:
        if delta.y > 0:
            self.min_y = min(self.max_y, self.min_y + delta.y)
        elif delta.y < 0:
            self.max_y = max(self.min_y, self.max_y + delta.y)

    def shift(self, delta: BlockVec3) -> None:
        self.points = [(x + delta.x, z + delta.z) for x, z in self.points]
        self.min_y += delta.y
        self.max_y += delta.y

    def clone(self) -> Polygonal2DRegion:
        return Polygonal2DRegion(list(self.points), self.min_y, self.max_y)


@dataclass
class ConvexPolyhedralRegion(Region):
    """3D convex polyhedron formed by selected vertices (uses bounding/half-space planes)."""

    vertices: list[BlockVec3]
    _planes: list[tuple[BlockVec3, tuple[float, float, float]]] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self._rebuild_faces()

    def _rebuild_faces(self) -> None:
        self._planes.clear()
        n = len(self.vertices)
        if n < 4:
            return
        cx = sum(v.x for v in self.vertices) / n
        cy = sum(v.y for v in self.vertices) / n
        cz = sum(v.z for v in self.vertices) / n
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    a, b, c = self.vertices[i], self.vertices[j], self.vertices[k]
                    ab = b - a
                    ac = c - a
                    nx = float(ab.y * ac.z - ab.z * ac.y)
                    ny = float(ab.z * ac.x - ab.x * ac.z)
                    nz = float(ab.x * ac.y - ab.y * ac.x)
                    norm_len = math.sqrt(nx * nx + ny * ny + nz * nz)
                    if norm_len < 1e-6:
                        continue
                    if nx * (cx - a.x) + ny * (cy - a.y) + nz * (cz - a.z) > 0:
                        nx, ny, nz = -nx, -ny, -nz
                    if all(
                        nx * (v.x - a.x) + ny * (v.y - a.y) + nz * (v.z - a.z) <= 1e-5
                        for idx, v in enumerate(self.vertices)
                        if idx not in (i, j, k)
                    ):
                        self._planes.append((a, (nx / norm_len, ny / norm_len, nz / norm_len)))

    @property
    def min_point(self) -> BlockVec3:
        return BlockVec3(
            min(v.x for v in self.vertices),
            min(v.y for v in self.vertices),
            min(v.z for v in self.vertices),
        )

    @property
    def max_point(self) -> BlockVec3:
        return BlockVec3(
            max(v.x for v in self.vertices),
            max(v.y for v in self.vertices),
            max(v.z for v in self.vertices),
        )

    def contains(self, pos: BlockVec3) -> bool:
        if len(self.vertices) == 0:
            return False
        if len(self.vertices) < 4 or not self._planes:
            lo, hi = self.min_point, self.max_point
            return lo.x <= pos.x <= hi.x and lo.y <= pos.y <= hi.y and lo.z <= pos.z <= hi.z
        for anchor, (nx, ny, nz) in self._planes:
            if nx * (pos.x - anchor.x) + ny * (pos.y - anchor.y) + nz * (pos.z - anchor.z) > 0.5:
                return False
        return True

    def expand(self, delta: BlockVec3) -> None:
        cx = sum(v.x for v in self.vertices) / max(1, len(self.vertices))
        cy = sum(v.y for v in self.vertices) / max(1, len(self.vertices))
        cz = sum(v.z for v in self.vertices) / max(1, len(self.vertices))
        updated: list[BlockVec3] = []
        for v in self.vertices:
            vx = v.x + (delta.x if (v.x - cx) * delta.x >= 0 else 0)
            vy = v.y + (delta.y if (v.y - cy) * delta.y >= 0 else 0)
            vz = v.z + (delta.z if (v.z - cz) * delta.z >= 0 else 0)
            updated.append(BlockVec3(vx, vy, vz))
        self.vertices = updated
        self._rebuild_faces()

    def contract(self, delta: BlockVec3) -> None:
        self.expand(-delta)

    def shift(self, delta: BlockVec3) -> None:
        self.vertices = [v + delta for v in self.vertices]
        self._rebuild_faces()

    def clone(self) -> ConvexPolyhedralRegion:
        return ConvexPolyhedralRegion(list(self.vertices))


def _point_on_segment(px: int, pz: int, x1: int, z1: int, x2: int, z2: int) -> bool:
    cross = (px - x1) * (z2 - z1) - (pz - z1) * (x2 - x1)
    if cross != 0:
        return False
    return min(x1, x2) <= px <= max(x1, x2) and min(z1, z2) <= pz <= max(z1, z2)


def _bresenham_2d(x0: int, z0: int, x1: int, z1: int) -> list[tuple[int, int]]:
    pts: list[tuple[int, int]] = []
    dx = abs(x1 - x0)
    dz = abs(z1 - z0)
    sx = 1 if x0 < x1 else -1
    sz = 1 if z0 < z1 else -1
    err = dx - dz
    x, z = x0, z0
    while True:
        pts.append((x, z))
        if x == x1 and z == z1:
            break
        e2 = 2 * err
        if e2 > -dz:
            err -= dz
            x += sx
        if e2 < dx:
            err += dx
            z += sz
    return pts


class RegionSelector(ABC):
    """Interactive selector state updated by wand clicks or //pos1 / //pos2."""

    mode: str = "cuboid"

    @abstractmethod
    def select_primary(self, pos: BlockVec3) -> str: ...

    @abstractmethod
    def select_secondary(self, pos: BlockVec3) -> str: ...

    @abstractmethod
    def clear(self) -> None: ...

    @abstractmethod
    def is_defined(self) -> bool: ...

    @abstractmethod
    def get_region(self) -> Region: ...

    @property
    def primary_position(self) -> BlockVec3 | None:
        return None


class CuboidSelector(RegionSelector):
    mode = "cuboid"

    def __init__(self) -> None:
        self.pos1: BlockVec3 | None = None
        self.pos2: BlockVec3 | None = None
        self._region: CuboidRegion | None = None

    @property
    def primary_position(self) -> BlockVec3 | None:
        return self.pos1

    def select_primary(self, pos: BlockVec3) -> str:
        self.pos1 = pos
        self._sync()
        extra = f" ({self._region.volume} blocks)" if self._region is not None else ""
        return f"First position set to {pos.format_short()}{extra}."

    def select_secondary(self, pos: BlockVec3) -> str:
        self.pos2 = pos
        self._sync()
        extra = f" ({self._region.volume} blocks)" if self._region is not None else ""
        return f"Second position set to {pos.format_short()}{extra}."

    def _sync(self) -> None:
        if self.pos1 is not None and self.pos2 is not None:
            self._region = CuboidRegion(self.pos1, self.pos2)

    def clear(self) -> None:
        self.pos1 = None
        self.pos2 = None
        self._region = None

    def is_defined(self) -> bool:
        return self._region is not None

    def get_region(self) -> CuboidRegion:
        if self._region is None:
            raise IncompleteRegionError("Make a region selection first (//pos1 and //pos2).")
        return self._region


class ExtendingCuboidSelector(CuboidSelector):
    mode = "extend"

    def select_primary(self, pos: BlockVec3) -> str:
        self.pos1 = pos
        self.pos2 = pos
        self._region = CuboidRegion(pos, pos)
        return f"Starting extending cuboid at {pos.format_short()} (1 block)."

    def select_secondary(self, pos: BlockVec3) -> str:
        if self._region is None:
            self.pos1 = pos
            self.pos2 = pos
            self._region = CuboidRegion(pos, pos)
        else:
            lo = self._region.min_point.min_with(pos)
            hi = self._region.max_point.max_with(pos)
            self._region.pos1 = lo
            self._region.pos2 = hi
            self.pos1, self.pos2 = lo, hi
        return f"Extended selection to {pos.format_short()} ({self._region.volume} blocks)."


class EllipsoidSelector(RegionSelector):
    mode = "ellipsoid"

    def __init__(self) -> None:
        self.center: BlockVec3 | None = None
        self._region: EllipsoidRegion | None = None

    @property
    def primary_position(self) -> BlockVec3 | None:
        return self.center

    def select_primary(self, pos: BlockVec3) -> str:
        self.center = pos
        self._region = EllipsoidRegion(pos, 0.0, 0.0, 0.0)
        return f"Ellipsoid center set to {pos.format_short()}."

    def select_secondary(self, pos: BlockVec3) -> str:
        if self.center is None:
            return self.select_primary(pos)
        diff = pos - self.center
        self._region = EllipsoidRegion(self.center, float(abs(diff.x)), float(abs(diff.y)), float(abs(diff.z)))
        return (
            f"Ellipsoid radius set to ({abs(diff.x)}, {abs(diff.y)}, {abs(diff.z)}) "
            f"({self._region.volume} blocks)."
        )

    def clear(self) -> None:
        self.center = None
        self._region = None

    def is_defined(self) -> bool:
        return self._region is not None

    def get_region(self) -> EllipsoidRegion:
        if self._region is None:
            raise IncompleteRegionError("Select ellipsoid center (pos1) and radius corner (pos2) first.")
        return self._region


class SphereSelector(EllipsoidSelector):
    mode = "sphere"

    def select_secondary(self, pos: BlockVec3) -> str:
        if self.center is None:
            return self.select_primary(pos)
        r = round(self.center.distance(pos), 2)
        self._region = EllipsoidRegion(self.center, r, r, r)
        return f"Sphere radius set to {r} ({self._region.volume} blocks)."


class CylinderSelector(RegionSelector):
    mode = "cyl"

    def __init__(self) -> None:
        self.center: BlockVec3 | None = None
        self._region: CylinderRegion | None = None

    @property
    def primary_position(self) -> BlockVec3 | None:
        return self.center

    def select_primary(self, pos: BlockVec3) -> str:
        self.center = pos
        self._region = CylinderRegion(pos.x, pos.z, 0.0, 0.0, pos.y, pos.y)
        return f"Cylinder center set to {pos.format_short()}."

    def select_secondary(self, pos: BlockVec3) -> str:
        if self.center is None:
            return self.select_primary(pos)
        rx = float(abs(pos.x - self.center.x))
        rz = float(abs(pos.z - self.center.z))
        lo_y = min(self.center.y, pos.y)
        hi_y = max(self.center.y, pos.y)
        self._region = CylinderRegion(self.center.x, self.center.z, rx, rz, lo_y, hi_y)
        return f"Cylinder radius=({rx:.0f}, {rz:.0f}), height={hi_y - lo_y + 1} ({self._region.volume} blocks)."

    def clear(self) -> None:
        self.center = None
        self._region = None

    def is_defined(self) -> bool:
        return self._region is not None

    def get_region(self) -> CylinderRegion:
        if self._region is None:
            raise IncompleteRegionError("Select cylinder center (pos1) and edge (pos2) first.")
        return self._region


class Polygonal2DSelector(RegionSelector):
    mode = "poly"

    def __init__(self) -> None:
        self._points: list[tuple[int, int]] = []
        self._min_y: int = 0
        self._max_y: int = 0
        self._region: Polygonal2DRegion | None = None

    @property
    def primary_position(self) -> BlockVec3 | None:
        if not self._points:
            return None
        return BlockVec3(self._points[0][0], self._min_y, self._points[0][1])

    def select_primary(self, pos: BlockVec3) -> str:
        self._points = [(pos.x, pos.z)]
        self._min_y = pos.y
        self._max_y = pos.y
        self._region = None
        return f"Started 2D polygon at ({pos.x}, {pos.z}) Y={pos.y}."

    def select_secondary(self, pos: BlockVec3) -> str:
        if not self._points:
            return self.select_primary(pos)
        self._points.append((pos.x, pos.z))
        self._min_y = min(self._min_y, pos.y)
        self._max_y = max(self._max_y, pos.y)
        if len(self._points) >= 3:
            self._region = Polygonal2DRegion(self._points, self._min_y, self._max_y)
            return f"Added polygon point #{len(self._points)} ({pos.x}, {pos.z}) ({self._region.volume} blocks)."
        return f"Added polygon point #{len(self._points)} ({pos.x}, {pos.z}). Need at least 3 points."

    def clear(self) -> None:
        self._points.clear()
        self._region = None

    def is_defined(self) -> bool:
        return self._region is not None and len(self._points) >= 3

    def get_region(self) -> Polygonal2DRegion:
        if not self.is_defined() or self._region is None:
            raise IncompleteRegionError("Select at least 3 polygon points first (//pos1 then //pos2).")
        return self._region


class ConvexPolyhedralSelector(RegionSelector):
    mode = "convex"

    def __init__(self) -> None:
        self._vertices: list[BlockVec3] = []
        self._region: ConvexPolyhedralRegion | None = None

    @property
    def primary_position(self) -> BlockVec3 | None:
        return self._vertices[0] if self._vertices else None

    def select_primary(self, pos: BlockVec3) -> str:
        self._vertices = [pos]
        self._region = ConvexPolyhedralRegion(self._vertices)
        return f"Cleared convex hull and set vertex #1 at {pos.format_short()}."

    def select_secondary(self, pos: BlockVec3) -> str:
        self._vertices.append(pos)
        self._region = ConvexPolyhedralRegion(self._vertices)
        return f"Added convex hull vertex #{len(self._vertices)} at {pos.format_short()}."

    def clear(self) -> None:
        self._vertices.clear()
        self._region = None

    def is_defined(self) -> bool:
        return self._region is not None and len(self._vertices) >= 1

    def get_region(self) -> ConvexPolyhedralRegion:
        if self._region is None:
            raise IncompleteRegionError("Select at least 1 vertex for convex region.")
        return self._region


SELECTOR_TYPES: dict[str, type[RegionSelector]] = {
    "cuboid": CuboidSelector,
    "extend": ExtendingCuboidSelector,
    "ellipsoid": EllipsoidSelector,
    "sphere": SphereSelector,
    "cyl": CylinderSelector,
    "poly": Polygonal2DSelector,
    "convex": ConvexPolyhedralSelector,
}


def create_selector(mode: str) -> RegionSelector:
    key = mode.strip().lower()
    cls = SELECTOR_TYPES.get(key)
    if cls is None:
        valid = ", ".join(sorted(SELECTOR_TYPES))
        raise ValueError(f"Unknown selector type '{mode}'. Valid types: {valid}.")
    return cls()
