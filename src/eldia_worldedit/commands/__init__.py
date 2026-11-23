"""Command infrastructure, Endstone command collision shield, // rewriter, and CommandRouter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..core.command_parser import tokenize_args
from ..core.types import BlockSpec, BlockVec3
from ..managers import WorldEditServices
from ..world.adapter import InMemoryWorldAdapter, WorldAdapter
from ..world.edit_session import EditSession

# Vanilla BDS commands that must never be registered directly at top-level in plugin.commands.
VANILLA_COMMANDS: frozenset[str] = frozenset({
    "camera",
    "clear",
    "clone",
    "damage",
    "deop",
    "dialogue",
    "effect",
    "enchant",
    "event",
    "execute",
    "fill",
    "fog",
    "gamemode",
    "gamerule",
    "give",
    "help",
    "hud",
    "inputpermission",
    "kick",
    "kill",
    "list",
    "locate",
    "loot",
    "me",
    "mobevent",
    "msg",
    "music",
    "op",
    "particle",
    "permission",
    "playanimation",
    "playsound",
    "recipe",
    "reload",
    "remove",
    "replaceitem",
    "ride",
    "say",
    "schedule",
    "scoreboard",
    "script",
    "seed",
    "setblock",
    "setmaxplayers",
    "spawnpoint",
    "spreadplayers",
    "stop",
    "stopsound",
    "structure",
    "summon",
    "tag",
    "teleport",
    "tell",
    "testfor",
    "testforblock",
    "testforblocks",
    "tickingarea",
    "time",
    "title",
    "titleraw",
    "toggledownfall",
    "tp",
    "transferserver",
    "weather",
    "whitelist",
    "world",
    "worlds",
    "wsserver",
    "xp",
})


def rewrite_double_slash_command(raw_command: str) -> str | None:
    """Rewrite `//cmd ...`, `/.s ...`, `/;`, `/!`, `/,` into `/ewe ...` for BDS/Endstone routing."""
    cmd = raw_command.strip()
    if not cmd.startswith("/"):
        return None
    body = cmd[1:]
    if body == "/":
        return "/ewe sp toggle"
    if body.startswith("/"):
        rest = body[1:].strip()
        if not rest:
            return "/ewe sp toggle"
        return f"/ewe {rest}"
    if body == ".s" or body.startswith(".s "):
        rest = body[2:].strip()
        return f"/ewe .s {rest}".strip()
    if body == ";" or body.startswith("; "):
        rest = body[1:].strip()
        return f"/ewe sel {rest}".strip()
    if body == "!":
        return "/ewe unstuck"
    if body == ",":
        return "/ewe sp toggle"
    return None


class CommandActor(Protocol):
    """Unified command executor interface implemented for Endstone players, console, and tests."""

    @property
    def key(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def is_player(self) -> bool: ...

    @property
    def world(self) -> WorldAdapter: ...

    @property
    def position(self) -> BlockVec3: ...

    @property
    def eye_position(self) -> tuple[float, float, float]: ...

    @property
    def yaw(self) -> float: ...

    @property
    def pitch(self) -> float: ...

    @property
    def hand_item(self) -> str | None: ...

    @property
    def hand_block(self) -> BlockSpec | None: ...

    @property
    def raw_player(self) -> Any: ...

    def send_message(self, msg: str) -> None: ...

    def send_error(self, msg: str) -> None: ...

    def teleport(self, pos: BlockVec3) -> None: ...

    def give_item(self, item_id: str, amount: int = 1) -> bool: ...

    def has_permission(self, permission: str) -> bool: ...

    def resolve_world(self, dimension_name: str) -> WorldAdapter | None: ...

    def run_command(self, command_line: str) -> bool: ...


@dataclass
class MockCommandActor:
    """In-memory CommandActor for isolated unit & command-dispatch testing."""

    _key: str = "uuid-player-1"
    _name: str = "Builder"
    _is_player: bool = True
    _world: WorldAdapter = field(default_factory=InMemoryWorldAdapter)
    _position: BlockVec3 = field(default_factory=lambda: BlockVec3(0, 64, 0))
    _yaw: float = 0.0
    _pitch: float = 0.0
    _hand_item: str | None = "minecraft:wooden_axe"
    _hand_block: BlockSpec | None = field(default_factory=lambda: BlockSpec("minecraft:stone"))
    messages: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    given_items: list[tuple[str, int]] = field(default_factory=list)
    permissions: set[str] = field(default_factory=lambda: {"*"})
    extra_worlds: dict[str, WorldAdapter] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return self._key

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_player(self) -> bool:
        return self._is_player

    @property
    def world(self) -> WorldAdapter:
        return self._world

    @property
    def position(self) -> BlockVec3:
        return self._position

    @property
    def eye_position(self) -> tuple[float, float, float]:
        return (self._position.x + 0.5, self._position.y + 1.62, self._position.z + 0.5)

    @property
    def yaw(self) -> float:
        return self._yaw

    @property
    def pitch(self) -> float:
        return self._pitch

    @property
    def hand_item(self) -> str | None:
        return self._hand_item

    @property
    def hand_block(self) -> BlockSpec | None:
        return self._hand_block

    @property
    def raw_player(self) -> Any:
        return None

    def send_message(self, msg: str) -> None:
        self.messages.append(msg)

    def send_error(self, msg: str) -> None:
        self.errors.append(msg)

    def teleport(self, pos: BlockVec3) -> None:
        self._position = pos

    def give_item(self, item_id: str, amount: int = 1) -> bool:
        self.given_items.append((item_id, amount))
        return True

    def has_permission(self, permission: str) -> bool:
        return "*" in self.permissions or permission in self.permissions

    def resolve_world(self, dimension_name: str) -> WorldAdapter | None:
        if dimension_name == self._world.name:
            return self._world
        return self.extra_worlds.get(dimension_name)

    def run_command(self, command_line: str) -> bool:
        return True


@dataclass
class CommandContext:
    """Per-invocation context passed to command handlers."""

    actor: CommandActor
    services: WorldEditServices
    router: CommandRouter
    command_name: str
    raw_args: str
    tokens: list[str]
    scheduler: Any = None
    plugin: Any = None
    batch_size: int = 4096

    def require_player(self) -> None:
        if not self.actor.is_player:
            raise ValueError(self.t("cmd.player_only"))

    def t(self, key: str, **kwargs: object) -> str:
        return self.services.lang.t(key, **kwargs)

    def create_edit_session(self, description: str = "", origin: BlockVec3 | None = None) -> EditSession:
        return self.services.create_edit_session(
            player_key=self.actor.key,
            world=self.actor.world,
            origin=origin or self.actor.position,
            hand_block=self.actor.hand_block,
            description=description or self.command_name,
        )

    def commit_edit(self, session: EditSession, message: str | None = None) -> int:
        count = session.commit(
            scheduler=self.scheduler,
            plugin=self.plugin,
            batch_size=self.batch_size,
        )
        self.services.history.record(self.actor.key, session.change_set)
        if message:
            self.actor.send_message(message)
        return count


@dataclass
class CommandSpec:
    """Declarative specification of a WorldEdit command."""

    name: str
    aliases: tuple[str, ...]
    permission: str
    description: str
    usage: str
    category: str
    handler: Callable[[CommandContext], None]
    player_only: bool = True


class CommandRouter:
    """Registry and dispatcher for all WorldEdit commands and aliases."""

    def __init__(self, services: WorldEditServices) -> None:
        self.services = services
        self._commands: dict[str, CommandSpec] = {}
        self._aliases: dict[str, str] = {}
        self._world_edit_version = "0.1.2"

    def register(self, spec: CommandSpec) -> None:
        primary = spec.name.lower()
        self._commands[primary] = spec
        self._aliases[primary] = primary
        for alias in spec.aliases:
            self._aliases[alias.lower()] = primary

    def find(self, name: str) -> CommandSpec | None:
        key = name.strip().lower().lstrip("/")
        primary = self._aliases.get(key)
        if primary is None:
            return None
        return self._commands.get(primary)

    def all_specs(self) -> list[CommandSpec]:
        return sorted(self._commands.values(), key=lambda c: (c.category, c.name))

    def dispatch(
        self,
        actor: CommandActor,
        command_name: str,
        raw_args: str = "",
        scheduler: Any = None,
        plugin: Any = None,
        batch_size: int = 4096,
    ) -> bool:
        spec = self.find(command_name)
        if spec is None:
            return False

        if spec.player_only and not actor.is_player:
            actor.send_error(self.services.lang.t("cmd.player_only"))
            return True

        if not actor.has_permission(spec.permission):
            actor.send_error(self.services.lang.t("cmd.no_permission", perm=spec.permission))
            return True

        try:
            tokens = tokenize_args(raw_args)
        except ValueError as exc:
            actor.send_error(str(exc))
            return True

        ctx = CommandContext(
            actor=actor,
            services=self.services,
            router=self,
            command_name=spec.name,
            raw_args=raw_args,
            tokens=tokens,
            scheduler=scheduler,
            plugin=plugin,
            batch_size=batch_size,
        )

        # Record last command for /.s (avoid overwriting with .s itself)
        if spec.name not in (".s", "we", "ewe", "worldedit"):
            full_cmd = f"//{spec.name} {raw_args}".strip()
            self.services.scripts.record_last_command(actor.key, full_cmd)

        try:
            spec.handler(ctx)
        except ValueError as exc:
            actor.send_error(str(exc))
        except FileNotFoundError as exc:
            actor.send_error(str(exc))
        except FileExistsError as exc:
            actor.send_error(str(exc))
        except RuntimeError as exc:
            actor.send_error(str(exc))
        return True

    def dispatch_line(
        self,
        actor: CommandActor,
        line: str,
        scheduler: Any = None,
        plugin: Any = None,
    ) -> bool:
        stripped = line.strip()
        rewritten = rewrite_double_slash_command(stripped)
        if rewritten is not None:
            stripped = rewritten
        stripped = stripped.removeprefix("/")
        if not stripped:
            return False
        parts = stripped.split(None, 1)
        cmd_name = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        if cmd_name in ("ewe", "we", "worldedit") and rest:
            sub_parts = rest.split(None, 1)
            sub_cmd = sub_parts[0].lower()
            sub_rest = sub_parts[1] if len(sub_parts) > 1 else ""
            if (
                sub_cmd
                not in ("version", "ver", "help", "reload", "cui", "gui", "ui", "tz", "report", "commands", "lang")
                and self.find(sub_cmd) is not None
            ):
                return self.dispatch(actor, sub_cmd, sub_rest, scheduler=scheduler, plugin=plugin)
        return self.dispatch(actor, cmd_name, rest, scheduler=scheduler, plugin=plugin)

    def build_endstone_commands(self) -> dict[str, dict[str, Any]]:
        """Generate Endstone plugin.commands dict safely without vanilla command collisions."""
        out: dict[str, dict[str, Any]] = {}
        for spec in self._commands.values():
            if spec.name in VANILLA_COMMANDS or not spec.name.replace("_", "").isalnum():
                continue
            valid_aliases = [
                a for a in spec.aliases
                if a not in VANILLA_COMMANDS and a.replace("_", "").isalnum()
            ]
            out[spec.name] = {
                "description": spec.description,
                "usages": [f"/{spec.name}", f"/{spec.name} <args: message>"],
                "permissions": [spec.permission],
                **({"aliases": valid_aliases} if valid_aliases else {}),
            }
        return out

    def build_endstone_permissions(self) -> dict[str, dict[str, Any]]:
        """Generate Endstone plugin.permissions dict covering every registered WorldEdit node."""
        perms: dict[str, dict[str, Any]] = {
            "worldedit.*": {"description": "Full access to Eldia WorldEdit.", "default": "op"},
        }
        for spec in self._commands.values():
            perms[spec.permission] = {
                "description": spec.description,
                "default": "op",
            }
        perms["worldedit.navigation.thru.tool"] = {"description": "Use navigation wand", "default": "op"}
        perms["worldedit.brush.options.mask"] = {"description": "Set brush mask", "default": "op"}
        perms["worldedit.brush.options.material"] = {"description": "Set brush material", "default": "op"}
        perms["worldedit.brush.options.range"] = {"description": "Set brush range", "default": "op"}
        perms["worldedit.brush.options.size"] = {"description": "Set brush size", "default": "op"}
        return perms


def register_all_commands(router: CommandRouter) -> None:
    """Register every WorldEdit command module onto `router`."""
    from . import (
        clipboard,
        general_world,
        generation,
        history,
        navigation,
        region,
        selection,
        tools_brushes,
        utility,
    )

    selection.register(router)
    region.register(router)
    generation.register(router)
    clipboard.register(router)
    history.register(router)
    navigation.register(router)
    utility.register(router)
    tools_brushes.register(router)
    general_world.register(router)
