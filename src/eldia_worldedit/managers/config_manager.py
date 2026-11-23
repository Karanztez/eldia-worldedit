"""Persistent YAML plugin configuration manager (language, prefix, limits, wands)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_DEFAULT_YAML = """# Eldia WorldEdit Configuration
# language: "en" or "th" (Thai)
language: "en"
prefix: "[EWE]"
max_history: 30
default_limit: 500000
wand_item: "minecraft:wooden_axe"
nav_wand_item: "minecraft:compass"
"""


@dataclass
class PluginConfig:
    """Typed plugin configuration loaded from config.yml."""

    language: str = "en"
    prefix: str = "[EWE]"
    max_history: int = 30
    default_limit: int = 500_000
    wand_item: str = "minecraft:wooden_axe"
    nav_wand_item: str = "minecraft:compass"


def _parse_yaml_mapping(raw_text: str) -> dict[str, object]:
    try:
        import yaml

        loaded = yaml.safe_load(raw_text)
        if isinstance(loaded, dict):
            return loaded
    except ImportError:
        pass

    result: dict[str, object] = {}
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        val = v.strip().strip('"').strip("'")
        if val.lstrip("-").isdigit():
            result[k.strip()] = int(val)
        else:
            result[k.strip()] = val
    return result


class ConfigManager:
    """Loads, creates, and reloads `config.yml` for Eldia WorldEdit."""

    def __init__(self, config_path: Path, create_file: bool = True) -> None:
        self.config_path = config_path
        self.config = PluginConfig()
        if create_file:
            self.load_or_create()

    def load_or_create(self) -> PluginConfig:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.is_file():
            self.config_path.write_text(_DEFAULT_YAML, encoding="utf-8")
            self.config = PluginConfig()
            return self.config
        return self.reload()

    def reload(self) -> PluginConfig:
        if not self.config_path.is_file():
            self.config = PluginConfig()
            return self.config
        data = _parse_yaml_mapping(self.config_path.read_text(encoding="utf-8"))
        lang_raw = str(data.get("language", data.get("lang", "en"))).strip().lower()
        lang = lang_raw if lang_raw in ("en", "th") else "en"
        self.config = PluginConfig(
            language=lang,
            prefix=str(data.get("prefix", "[EWE]")).strip() or "[EWE]",
            max_history=max(1, int(str(data.get("max_history", 30)))),
            default_limit=int(str(data.get("default_limit", 500_000))),
            wand_item=str(data.get("wand_item", "minecraft:wooden_axe")).strip(),
            nav_wand_item=str(data.get("nav_wand_item", "minecraft:compass")).strip(),
        )
        return self.config

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        content = (
            "# Eldia WorldEdit Configuration\n"
            '# language: "en" or "th" (Thai)\n'
            f'language: "{self.config.language}"\n'
            f'prefix: "{self.config.prefix}"\n'
            f"max_history: {self.config.max_history}\n"
            f"default_limit: {self.config.default_limit}\n"
            f'wand_item: "{self.config.wand_item}"\n'
            f'nav_wand_item: "{self.config.nav_wand_item}"\n'
        )
        self.config_path.write_text(content, encoding="utf-8")
