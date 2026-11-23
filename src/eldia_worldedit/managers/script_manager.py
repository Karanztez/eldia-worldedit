"""CraftScript command-script runner and /.s last-script repeater."""

from __future__ import annotations

from pathlib import Path


class ScriptManager:
    """Stores last executed script/command per player and runs .wescript files from craftscripts/."""

    def __init__(self, craftscripts_dir: Path) -> None:
        self.craftscripts_dir = craftscripts_dir
        self._last_command: dict[str, str] = {}
        self._last_script: dict[str, tuple[str, list[str]]] = {}

    def record_last_command(self, player_key: str, command_line: str) -> None:
        self._last_command[player_key] = command_line

    def get_last_command(self, player_key: str) -> str | None:
        return self._last_command.get(player_key)

    def record_last_script(self, player_key: str, filename: str, args: list[str]) -> None:
        self._last_script[player_key] = (filename, list(args))

    def get_last_script(self, player_key: str) -> tuple[str, list[str]] | None:
        return self._last_script.get(player_key)

    def list_scripts(self) -> list[str]:
        if not self.craftscripts_dir.exists():
            return []
        return sorted(
            p.name
            for p in self.craftscripts_dir.iterdir()
            if p.is_file() and p.suffix.lower() in (".wescript", ".txt", ".script")
        )

    def load_script_lines(self, filename: str, args: list[str] | None = None) -> list[str]:
        clean = filename.strip()
        if not clean or "/" in clean or "\\" in clean or ".." in clean:
            raise ValueError(f"Invalid script name '{filename}'.")
        cands = [self.craftscripts_dir / clean]
        for ext in (".wescript", ".txt", ".script"):
            cands.append(self.craftscripts_dir / f"{clean}{ext}")
        path = next((c for c in cands if c.is_file()), None)
        if path is None:
            raise FileNotFoundError(f"CraftScript '{clean}' not found in {self.craftscripts_dir}.")

        argv = args or []
        lines: list[str] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            for idx, val in enumerate(argv):
                line = line.replace(f"${idx}", val).replace(f"${{{idx}}}", val)
            lines.append(line)
        return lines

    def remove_player(self, player_key: str) -> None:
        self._last_command.pop(player_key, None)
        self._last_script.pop(player_key, None)
