"""WorldEdit snapshot capture, lookup, selection, and region restoration."""

from __future__ import annotations

import gzip
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

from ..core.regions import Region
from ..core.types import AIR_SPEC, BlockSpec, BlockVec3, parse_block_spec
from ..world.adapter import WorldAdapter
from ..world.edit_session import EditSession


@dataclass(frozen=True)
class SnapshotEntry:
    """Metadata summary for a saved region snapshot on disk."""

    name: str
    path: Path
    created_ts: float
    dimension: str
    min_point: BlockVec3
    max_point: BlockVec3


class SnapshotManager:
    """Manages local chunk/region backup snapshots for //restore and //snapshot commands."""

    def __init__(self, snapshots_dir: Path) -> None:
        self.snapshots_dir = snapshots_dir
        self._selected: dict[str, str] = {}

    def _safe_name(self, name: str) -> str:
        clean = name.strip()
        if not clean or "/" in clean or "\\" in clean or ".." in clean:
            raise ValueError(f"Invalid snapshot name '{name}'.")
        return clean[:-7] if clean.lower().endswith(".wesnap") else clean

    def save_snapshot(
        self,
        name: str,
        world: WorldAdapter,
        region: Region,
        overwrite: bool = False,
    ) -> SnapshotEntry:
        clean = self._safe_name(name)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        path = self.snapshots_dir / f"{clean}.wesnap"
        if path.exists() and not overwrite:
            raise FileExistsError(f"Snapshot '{clean}' already exists.")

        lo, hi = region.min_point, region.max_point
        palette_idx: dict[str, int] = {"minecraft:air": 0}
        palette_list: list[str] = ["minecraft:air"]
        blocks: list[list[int]] = []
        for pos in region.iter_positions():
            spec = world.get_block(pos)
            key = spec.to_string()
            if key not in palette_idx:
                palette_idx[key] = len(palette_list)
                palette_list.append(key)
            pidx = palette_idx[key]
            if pidx != 0:
                blocks.append([pos.x, pos.y, pos.z, pidx])

        ts = time.time()
        payload = {
            "version": 1,
            "name": clean,
            "created_ts": ts,
            "dimension": world.name,
            "min": [lo.x, lo.y, lo.z],
            "max": [hi.x, hi.y, hi.z],
            "palette": palette_list,
            "blocks": blocks,
        }
        path.write_bytes(gzip.compress(json.dumps(payload).encode("utf-8")))
        return SnapshotEntry(
            name=clean,
            path=path,
            created_ts=ts,
            dimension=world.name,
            min_point=lo,
            max_point=hi,
        )

    def _read_entry(self, path: Path) -> SnapshotEntry:
        raw = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
        lo = raw["min"]
        hi = raw["max"]
        return SnapshotEntry(
            name=str(raw["name"]),
            path=path,
            created_ts=float(raw["created_ts"]),
            dimension=str(raw["dimension"]),
            min_point=BlockVec3(int(lo[0]), int(lo[1]), int(lo[2])),
            max_point=BlockVec3(int(hi[0]), int(hi[1]), int(hi[2])),
        )

    def list_snapshots(self, sort: str = "newest") -> list[SnapshotEntry]:
        if not self.snapshots_dir.exists():
            return []
        out: list[SnapshotEntry] = []
        for p in self.snapshots_dir.iterdir():
            if p.is_file() and p.suffix.lower() == ".wesnap":
                try:
                    out.append(self._read_entry(p))
                except (OSError, ValueError, KeyError) as exc:
                    _LOGGER.debug("Skipping unreadable snapshot %s: %s", p.name, exc)
                    continue
        if sort == "oldest":
            out.sort(key=lambda e: e.created_ts)
        elif sort == "name":
            out.sort(key=lambda e: e.name.lower())
        else:
            out.sort(key=lambda e: e.created_ts, reverse=True)
        return out

    def select_snapshot(self, player_key: str, query: str) -> SnapshotEntry:
        snaps = self.list_snapshots(sort="newest")
        if not snaps:
            raise FileNotFoundError("No snapshots found.")
        q = query.strip()
        if q.lower() == "latest":
            chosen = snaps[0]
        elif q.lower() == "oldest":
            chosen = snaps[-1]
        else:
            matches = [s for s in snaps if s.name.lower() == q.lower()]
            if not matches:
                raise FileNotFoundError(f"Snapshot '{query}' not found.")
            chosen = matches[0]
        self._selected[player_key] = chosen.name
        return chosen

    def select_by_time(self, player_key: str, target_ts: float, before: bool = True) -> SnapshotEntry:
        snaps = self.list_snapshots(sort="oldest")
        if before:
            cands = [s for s in snaps if s.created_ts <= target_ts]
            if not cands:
                raise FileNotFoundError("No snapshot found before that timestamp.")
            chosen = cands[-1]
        else:
            cands = [s for s in snaps if s.created_ts >= target_ts]
            if not cands:
                raise FileNotFoundError("No snapshot found after that timestamp.")
            chosen = cands[0]
        self._selected[player_key] = chosen.name
        return chosen

    def get_selected_name(self, player_key: str) -> str | None:
        return self._selected.get(player_key)

    def restore_region(
        self,
        player_key: str,
        session: EditSession,
        region: Region,
        snapshot_name: str | None = None,
        only_air: bool = False,
    ) -> tuple[str, int]:
        name = snapshot_name or self._selected.get(player_key)
        if not name:
            snaps = self.list_snapshots(sort="newest")
            if not snaps:
                raise FileNotFoundError("No snapshot selected or available. Use //snap list or //snap save.")
            name = snaps[0].name
        clean = self._safe_name(name)
        path = self.snapshots_dir / f"{clean}.wesnap"
        if not path.is_file():
            raise FileNotFoundError(f"Snapshot '{clean}' not found.")

        raw = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
        palette: list[BlockSpec] = [parse_block_spec(item) for item in raw["palette"]]
        snap_blocks: dict[BlockVec3, BlockSpec] = {}
        for x, y, z, pidx in raw["blocks"]:
            snap_blocks[BlockVec3(int(x), int(y), int(z))] = palette[int(pidx)]

        changed = 0
        for pos in region.iter_positions():
            if only_air and not session.get_block(pos).is_air:
                continue
            target_spec = snap_blocks.get(pos, AIR_SPEC)
            if session.set_block(pos, target_spec):
                changed += 1
        return clean, changed
