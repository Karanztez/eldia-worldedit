"""Unified WorldEditServices container wiring all stateful manager instances."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..core.masks import Mask, MaskContext
from ..core.types import BlockSpec, BlockVec3
from ..world.adapter import WorldAdapter
from ..world.edit_session import EditSession
from .clipboard_manager import ClipboardManager
from .config_manager import ConfigManager, PluginConfig
from .history_manager import HistoryManager
from .lang_manager import LangManager
from .script_manager import ScriptManager
from .selection_manager import SelectionManager
from .session_manager import LocalSession, SessionManager
from .snapshot_manager import SnapshotEntry, SnapshotManager
from .tool_manager import ToolManager
from .ui_manager import UIManager


@dataclass
class WorldEditServices:
    """Service container grouping every WorldEdit subsystem manager."""

    config: ConfigManager
    lang: LangManager
    sessions: SessionManager
    selections: SelectionManager
    history: HistoryManager
    clipboards: ClipboardManager
    tools: ToolManager
    snapshots: SnapshotManager
    scripts: ScriptManager
    ui: UIManager

    @classmethod
    def create(
        cls,
        data_folder: Path,
        max_history: int | None = None,
        default_limit: int | None = None,
        max_limit: int = -1,
        create_dirs: bool = True,
    ) -> WorldEditServices:
        if create_dirs:
            data_folder.mkdir(parents=True, exist_ok=True)
        cfg_mgr = ConfigManager(data_folder / "config.yml", create_file=create_dirs)
        cfg = cfg_mgr.config
        eff_history = max_history if max_history is not None else cfg.max_history
        eff_limit = default_limit if default_limit is not None else cfg.default_limit
        return cls(
            config=cfg_mgr,
            lang=LangManager(cfg.language),
            sessions=SessionManager(default_limit=eff_limit, max_limit=max_limit),
            selections=SelectionManager(),
            history=HistoryManager(max_history=eff_history),
            clipboards=ClipboardManager(schematics_dir=data_folder / "schematics"),
            tools=ToolManager(),
            snapshots=SnapshotManager(snapshots_dir=data_folder / "snapshots"),
            scripts=ScriptManager(craftscripts_dir=data_folder / "craftscripts"),
            ui=UIManager(),
        )

    def reload_config(self) -> PluginConfig:
        cfg = self.config.reload()
        self.lang.set_language(cfg.language)
        self.sessions.default_limit = cfg.default_limit
        self.history.max_history = cfg.max_history
        return cfg

    def create_edit_session(
        self,
        player_key: str,
        world: WorldAdapter,
        origin: BlockVec3 | None = None,
        hand_block: BlockSpec | None = None,
        description: str = "",
        extra_mask: Mask | None = None,
    ) -> EditSession:
        sess = self.sessions.get(player_key)
        sel = self.selections.get_selector(player_key)
        region = sel.get_region() if sel.is_defined() else None
        mctx = MaskContext(region=region, origin=origin or BlockVec3(0, 0, 0), hand_block=hand_block)
        gmask = extra_mask or self.sessions.get_gmask(player_key, mctx)
        return EditSession(
            world=world,
            limit=sess.block_change_limit,
            gmask=gmask,
            fast_mode=sess.fast_mode,
            reorder_mode=sess.reorder_mode,
            mask_context=mctx,
            description=description,
        )

    def cleanup_player(self, player_key: str) -> None:
        self.sessions.remove(player_key)
        self.selections.remove_player(player_key)
        self.tools.remove_player(player_key)
        self.scripts.remove_player(player_key)


__all__ = [
    "ClipboardManager",
    "ConfigManager",
    "HistoryManager",
    "LangManager",
    "LocalSession",
    "PluginConfig",
    "ScriptManager",
    "SelectionManager",
    "SessionManager",
    "SnapshotEntry",
    "SnapshotManager",
    "ToolManager",
    "UIManager",
    "WorldEditServices",
]
