"""Per-player Clipboard state and Schematic directory management."""

from __future__ import annotations

from pathlib import Path

from ..clipboard.clipboard import Clipboard
from ..clipboard.schematic import (
    SchematicEntry,
    delete_schematic,
    list_schematics,
    load_schematic,
    save_schematic,
)


class ClipboardManager:
    """Manages active player clipboards and saved schematic files on disk."""

    def __init__(self, schematics_dir: Path) -> None:
        self.schematics_dir = schematics_dir
        self._clipboards: dict[str, Clipboard] = {}

    def get(self, player_key: str) -> Clipboard | None:
        return self._clipboards.get(player_key)

    def set(self, player_key: str, clipboard: Clipboard) -> None:
        self._clipboards[player_key] = clipboard

    def clear(self, player_key: str) -> None:
        self._clipboards.pop(player_key, None)

    def save_to_disk(
        self,
        player_key: str,
        name: str,
        fmt: str = "schem",
        overwrite: bool = False,
    ) -> Path:
        cb = self.get(player_key)
        if cb is None:
            raise ValueError("Your clipboard is empty. Use //copy first.")
        return save_schematic(cb, self.schematics_dir, name, fmt=fmt, overwrite=overwrite)

    def load_from_disk(self, player_key: str, name: str) -> Clipboard:
        cb = load_schematic(self.schematics_dir, name)
        self.set(player_key, cb)
        return cb

    def list_files(self, sort: str = "name") -> list[SchematicEntry]:
        return list_schematics(self.schematics_dir, sort=sort)

    def delete_file(self, name: str) -> Path:
        return delete_schematic(self.schematics_dir, name)
