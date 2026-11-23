"""Endstone plugin entry point for Eldia WorldEdit (no postponed annotations for @event_handler!)."""

import os
from pathlib import Path

from endstone import ColorFormat, Player
from endstone.command import Command, CommandSender
from endstone.event import (
    BlockBreakEvent,
    EventPriority,
    PlayerCommandEvent,
    PlayerInteractEvent,
    PlayerQuitEvent,
    ServerCommandEvent,
    event_handler,
)
from endstone.plugin import Plugin

from .commands import (
    CommandActor,
    CommandRouter,
    register_all_commands,
    rewrite_double_slash_command,
)
from .core.types import BlockSpec, BlockVec3, parse_block_spec
from .managers import WorldEditServices
from .tools.brushes import execute_brush
from .tools.items import execute_super_pickaxe, execute_tool
from .world.adapter import EndstoneWorldAdapter, WorldAdapter
from .world.navigation import find_jumpto_pos, find_thru_pos, raycast_block


def _build_static_metadata() -> tuple[dict, dict]:
    dummy_services = WorldEditServices.create(Path("."), create_dirs=False)
    router = CommandRouter(dummy_services)
    register_all_commands(router)
    cmds = router.build_endstone_commands()
    perms = router.build_endstone_permissions()
    return cmds, perms


_BOOTSTRAP_COMMANDS, _BOOTSTRAP_PERMISSIONS = _build_static_metadata()


def _block_face_to_normal(face: object) -> BlockVec3:
    key = str(face).lower()
    if "up" in key:
        return BlockVec3(0, 1, 0)
    if "down" in key:
        return BlockVec3(0, -1, 0)
    if "north" in key:
        return BlockVec3(0, 0, -1)
    if "south" in key:
        return BlockVec3(0, 0, 1)
    if "east" in key:
        return BlockVec3(1, 0, 0)
    if "west" in key:
        return BlockVec3(-1, 0, 0)
    return BlockVec3(0, 1, 0)


class EndstoneCommandActor:
    """Wraps a live Endstone Player or ConsoleCommandSender into CommandActor."""

    def __init__(self, plugin: "WorldEditPlugin", sender: CommandSender) -> None:
        self.plugin = plugin
        self.sender = sender
        self._player: Player | None = sender if isinstance(sender, Player) else None

    @property
    def key(self) -> str:
        if self._player is not None:
            return str(self._player.unique_id)
        return "console"

    @property
    def name(self) -> str:
        return str(self.sender.name)

    @property
    def is_player(self) -> bool:
        return self._player is not None

    @property
    def world(self) -> WorldAdapter:
        if self._player is not None:
            return self.plugin.get_world_adapter(self._player.dimension)
        dim = self.plugin.server.level.get_dimension("overworld")
        return self.plugin.get_world_adapter(dim)

    @property
    def position(self) -> BlockVec3:
        if self._player is not None:
            loc = self._player.location
            return BlockVec3(int(loc.block_x), int(loc.block_y), int(loc.block_z))
        return BlockVec3(0, 64, 0)

    @property
    def eye_position(self) -> tuple[float, float, float]:
        if self._player is not None:
            loc = self._player.location
            return (float(loc.x), float(loc.y) + 1.62, float(loc.z))
        return (0.5, 65.62, 0.5)

    @property
    def yaw(self) -> float:
        return float(self._player.location.yaw) if self._player is not None else 0.0

    @property
    def pitch(self) -> float:
        return float(self._player.location.pitch) if self._player is not None else 0.0

    @property
    def hand_item(self) -> str | None:
        if self._player is None:
            return None
        try:
            item = self._player.inventory.item_in_main_hand
            return str(item.type) if item is not None else None
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return None

    @property
    def hand_block(self) -> BlockSpec | None:
        item_id = self.hand_item
        if not item_id or item_id == "minecraft:air":
            return None
        try:
            return parse_block_spec(item_id)
        except ValueError:
            return None

    @property
    def raw_player(self):
        return self._player

    def send_message(self, msg: str) -> None:
        prefix = self.plugin.services.config.config.prefix
        self.sender.send_message(f"{ColorFormat.LIGHT_PURPLE}{prefix} {ColorFormat.RESET}{msg}")

    def send_error(self, msg: str) -> None:
        prefix = self.plugin.services.config.config.prefix
        self.sender.send_error_message(f"{ColorFormat.RED}{prefix} {msg}")

    def teleport(self, pos: BlockVec3) -> None:
        if self._player is None:
            return
        from endstone.level import Location

        loc = self._player.location
        target_loc = Location(self._player.dimension, pos.x + 0.5, float(pos.y), pos.z + 0.5, loc.pitch, loc.yaw)
        self._player.teleport(target_loc)

    def give_item(self, item_id: str, amount: int = 1) -> bool:
        if self._player is None:
            return False
        try:
            from endstone.inventory import ItemStack

            self._player.inventory.add_item(ItemStack(item_id, amount))
            return True
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False

    def has_permission(self, permission: str) -> bool:
        return bool(self.sender.has_permission(permission) or self.sender.has_permission("worldedit.*"))

    def resolve_world(self, dimension_name: str) -> WorldAdapter | None:
        try:
            dim = self.plugin.server.level.get_dimension(dimension_name)
            return self.plugin.get_world_adapter(dim)
        except (AttributeError, KeyError, RuntimeError, ValueError):
            return None

    def run_command(self, command_line: str) -> bool:
        if self._player is not None:
            return bool(self._player.perform_command(command_line))
        return bool(self.plugin.server.dispatch_command(self.sender, command_line))


class WorldEditPlugin(Plugin):
    """Full-featured WorldEdit plugin port for Endstone (Minecraft Bedrock)."""

    api_version = "0.10"
    commands = _BOOTSTRAP_COMMANDS
    permissions = _BOOTSTRAP_PERMISSIONS

    def on_load(self) -> None:
        data_dir = Path(str(self.data_folder)) if self.data_folder else Path("plugins") / "eldia_worldedit"
        env_hist = os.environ.get("ELDIA_WE_HISTORY")
        env_lim = os.environ.get("ELDIA_WE_LIMIT")
        self.services = WorldEditServices.create(
            data_folder=data_dir,
            max_history=int(env_hist) if env_hist is not None else None,
            default_limit=int(env_lim) if env_lim is not None else None,
        )
        self.router = CommandRouter(self.services)
        register_all_commands(self.router)
        self._world_adapters: dict[str, EndstoneWorldAdapter] = {}
        self._drawsel_task = None

    def on_enable(self) -> None:
        self.register_events(self)
        self._drawsel_task = self.server.scheduler.run_task(self, self._tick_drawsel, delay=20, period=10)
        self.logger.info(f"Eldia WorldEdit enabled with {len(self.router.all_specs())} commands.")

    def on_disable(self) -> None:
        if self._drawsel_task is not None:
            self._drawsel_task.cancel()
            self._drawsel_task = None

    def get_world_adapter(self, dimension: object) -> EndstoneWorldAdapter:
        key = str(getattr(dimension, "name", "overworld"))
        adapter = self._world_adapters.get(key)
        if adapter is None:
            adapter = EndstoneWorldAdapter(dimension, self.server)
            self._world_adapters[key] = adapter
        return adapter

    def _tick_drawsel(self) -> None:
        for player in self.server.online_players:
            pkey = str(player.unique_id)
            if not self.services.sessions.get(pkey).drawsel_enabled:
                continue
            pts = self.services.selections.get_outline_points(pkey, max_points=140)
            for x, y, z in pts:
                try:
                    player.spawn_particle("minecraft:villager_happy", x, y, z)
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    break

    def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
        actor: CommandActor = EndstoneCommandActor(self, sender)
        raw_args = " ".join(args)
        return self.router.dispatch(
            actor,
            command.name,
            raw_args,
            scheduler=self.server.scheduler,
            plugin=self,
        )

    @event_handler(priority=EventPriority.HIGHEST)
    def on_player_command(self, event: PlayerCommandEvent) -> None:
        rewritten = rewrite_double_slash_command(event.command)
        if rewritten is not None:
            event.command = rewritten

    @event_handler(priority=EventPriority.HIGHEST)
    def on_server_command(self, event: ServerCommandEvent) -> None:
        rewritten = rewrite_double_slash_command(event.command)
        if rewritten is not None:
            event.command = rewritten

    @event_handler
    def on_player_quit(self, event: PlayerQuitEvent) -> None:
        self.services.cleanup_player(str(event.player.unique_id))

    @event_handler
    def on_block_break(self, event: BlockBreakEvent) -> None:
        player = event.player
        actor = EndstoneCommandActor(self, player)
        pkey = actor.key
        sess = self.services.sessions.get(pkey)
        item = actor.hand_item
        pos = BlockVec3(int(event.block.x), int(event.block.y), int(event.block.z))

        if item and sess.wand_enabled and item == sess.wand_item:
            event.cancel()
            if not self.services.tools.should_debounce_left_click(pkey) and not self.services.tools.should_suppress_repeat_pos(pkey, "pos1", pos):
                actor.send_message(self.services.selections.select_pos1(pkey, pos, lang=self.services.lang))
            return

        if item:
            tool = self.services.tools.get_tool(pkey, item)
            if tool is not None:
                event.cancel()
                if not self.services.tools.should_debounce_left_click(pkey):
                    session = self.services.create_edit_session(pkey, actor.world, origin=pos, hand_block=actor.hand_block, description=f"tool:{tool.kind}")
                    cnt, msgs = execute_tool(tool, actor.world, session, pos, is_left_click=True, hand_block=actor.hand_block)
                    session.commit(scheduler=self.server.scheduler, plugin=self)
                    if cnt > 0:
                        self.services.history.record(pkey, session.change_set)
                    for m in msgs:
                        actor.send_message(m)
                return

        sp = self.services.tools.get_super_pickaxe(pkey)
        if sp.enabled:
            event.cancel()
            session = self.services.create_edit_session(pkey, actor.world, origin=pos, description="superpickaxe")
            cnt = execute_super_pickaxe(sp, actor.world, session, pos)
            if cnt > 0:
                session.commit(scheduler=self.server.scheduler, plugin=self)
                self.services.history.record(pkey, session.change_set)

    @event_handler
    def on_player_interact(self, event: PlayerInteractEvent) -> None:
        player = event.player
        actor = EndstoneCommandActor(self, player)
        pkey = actor.key
        sess = self.services.sessions.get(pkey)
        item = actor.hand_item
        if not item:
            return

        is_left = event.action in (
            PlayerInteractEvent.Action.LEFT_CLICK_BLOCK,
            PlayerInteractEvent.Action.LEFT_CLICK_AIR,
        )
        is_right = event.action in (
            PlayerInteractEvent.Action.RIGHT_CLICK_BLOCK,
            PlayerInteractEvent.Action.RIGHT_CLICK_AIR,
        )
        has_block = bool(event.has_block and event.block is not None)
        clicked_pos = BlockVec3(int(event.block.x), int(event.block.y), int(event.block.z)) if has_block else None
        normal = _block_face_to_normal(event.block_face) if has_block else BlockVec3(0, 1, 0)

        # 1. Selection wand
        if sess.wand_enabled and item == sess.wand_item and clicked_pos is not None:
            event.cancel()
            if (
                is_left
                and not self.services.tools.should_debounce_left_click(pkey)
                and not self.services.tools.should_suppress_repeat_pos(pkey, "pos1", clicked_pos)
            ):
                actor.send_message(self.services.selections.select_pos1(pkey, clicked_pos, lang=self.services.lang))
            elif (
                is_right
                and not self.services.tools.should_debounce_right_click(pkey)
                and not self.services.tools.should_suppress_repeat_pos(pkey, "pos2", clicked_pos)
            ):
                actor.send_message(self.services.selections.select_pos2(pkey, clicked_pos, lang=self.services.lang))
            return

        # 2. Navigation wand
        if item == sess.nav_wand_item:
            event.cancel()
            ex, ey, ez = actor.eye_position
            if is_left:
                if not self.services.tools.should_debounce_left_click(pkey):
                    dest = find_jumpto_pos(actor.world, ex, ey, ez, actor.yaw, actor.pitch)
                    if dest is not None:
                        actor.teleport(dest)
            elif is_right and not self.services.tools.should_debounce_right_click(pkey):
                dest = find_thru_pos(actor.world, ex, ey, ez, actor.yaw, actor.pitch)
                if dest is not None:
                    actor.teleport(dest)
            return

        # 3. Bound item tool
        tool = self.services.tools.get_tool(pkey, item)
        if tool is not None:
            event.cancel()
            if is_left and self.services.tools.should_debounce_left_click(pkey):
                return
            if is_right and self.services.tools.should_debounce_right_click(pkey):
                return
            ex, ey, ez = actor.eye_position
            target = clicked_pos or raycast_block(actor.world, ex, ey, ez, actor.yaw, actor.pitch, max_dist=128.0)
            if tool.kind == "farwand":
                if target is not None:
                    slot = "pos1" if is_left else "pos2"
                    if not self.services.tools.should_suppress_repeat_pos(pkey, slot, target):
                        msg = (
                            self.services.selections.select_pos1(pkey, target, lang=self.services.lang)
                            if is_left
                            else self.services.selections.select_pos2(pkey, target, lang=self.services.lang)
                        )
                        actor.send_message(msg)
                return
            if target is not None:
                session = self.services.create_edit_session(pkey, actor.world, origin=target, hand_block=actor.hand_block, description=f"tool:{tool.kind}")
                cnt, msgs = execute_tool(tool, actor.world, session, target, face_normal=normal, is_left_click=is_left, hand_block=actor.hand_block)
                if cnt > 0:
                    session.commit(scheduler=self.server.scheduler, plugin=self)
                    self.services.history.record(pkey, session.change_set)
                for m in msgs:
                    actor.send_message(m)
            return

        # 4. Bound terrain brush (right-click raycast)
        brush = self.services.tools.get_brush(pkey, item)
        if brush is not None and is_right and not self.services.tools.should_debounce_right_click(pkey):
            event.cancel()
            ex, ey, ez = actor.eye_position
            target = clicked_pos or raycast_block(actor.world, ex, ey, ez, actor.yaw, actor.pitch, max_dist=brush.range_limit)
            if target is None:
                actor.send_error("No block in sight within brush range.")
                return
            session = self.services.create_edit_session(pkey, actor.world, origin=target, hand_block=actor.hand_block, description=f"brush:{brush.kind}")
            cb = self.services.clipboards.get(pkey)
            try:
                cnt, msg = execute_brush(brush, actor.world, session, target, clipboard=cb, hand_block=actor.hand_block)
                if cnt > 0:
                    session.commit(scheduler=self.server.scheduler, plugin=self)
                    self.services.history.record(pkey, session.change_set)
                actor.send_message(msg)
            except (ValueError, RuntimeError, LookupError) as exc:
                actor.send_error(str(exc))
