"""World abstraction bridging Endstone Dimension/Server and in-memory test worlds."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..core.types import AIR_SPEC, BlockSpec, BlockVec3


@dataclass
class ActorInfo:
    """Lightweight representation of an entity in a world."""

    entity_id: int
    entity_type: str
    pos: BlockVec3
    name: str = ""
    raw_actor: Any = None


class WorldAdapter(Protocol):
    """Protocol implemented by both EndstoneWorldAdapter and InMemoryWorldAdapter."""

    @property
    def name(self) -> str: ...

    @property
    def min_y(self) -> int: ...

    @property
    def max_y(self) -> int: ...

    def get_block(self, pos: BlockVec3) -> BlockSpec: ...

    def set_block(self, pos: BlockVec3, spec: BlockSpec, apply_physics: bool = True) -> None: ...

    def get_highest_y(self, x: int, z: int) -> int: ...

    def get_entities(self) -> list[ActorInfo]: ...

    def remove_entity(self, info: ActorInfo) -> bool: ...

    def get_loaded_chunks(self) -> list[tuple[int, int]]: ...

    def get_biome(self, pos: BlockVec3) -> str: ...

    def set_biome(self, pos: BlockVec3, biome: str) -> bool: ...


class EndstoneWorldAdapter:
    """Adapter wrapping a live Endstone Dimension and Server."""

    def __init__(self, dimension: Any, server: Any) -> None:
        self.dimension = dimension
        self.server = server
        self._biome_overrides: dict[tuple[int, int, int], str] = {}

    @property
    def name(self) -> str:
        return str(self.dimension.name)

    @property
    def min_y(self) -> int:
        dim_low = self.name.lower()
        if "nether" in dim_low or "end" in dim_low:
            return 0
        return -64

    @property
    def max_y(self) -> int:
        dim_low = self.name.lower()
        if "nether" in dim_low:
            return 127
        if "end" in dim_low:
            return 255
        return 319

    def get_block(self, pos: BlockVec3) -> BlockSpec:
        if pos.y < self.min_y or pos.y > self.max_y:
            return AIR_SPEC
        block = self.dimension.get_block_at(pos.x, pos.y, pos.z)
        btype = str(block.type)
        states: tuple[tuple[str, bool | int | str], ...] = ()
        try:
            raw_states = block.data.block_states
            if raw_states:
                states = tuple(sorted((str(k), v) for k, v in raw_states.items()))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            states = ()
        return BlockSpec(btype, states)

    def set_block(self, pos: BlockVec3, spec: BlockSpec, apply_physics: bool = True) -> None:
        if pos.y < self.min_y or pos.y > self.max_y:
            return
        block = self.dimension.get_block_at(pos.x, pos.y, pos.z)
        if spec.states and self.server is not None:
            with suppress(AttributeError, RuntimeError, TypeError, ValueError):
                data = self.server.create_block_data(spec.block_type, spec.states_dict)
                block.set_data(data, apply_physics=apply_physics)
                return
        block.set_type(spec.block_type, apply_physics=apply_physics)

    def get_highest_y(self, x: int, z: int) -> int:
        return int(self.dimension.get_highest_block_y_at(x, z))

    def get_entities(self) -> list[ActorInfo]:
        out: list[ActorInfo] = []
        for actor in self.dimension.actors:
            loc = actor.location
            out.append(
                ActorInfo(
                    entity_id=int(actor.id),
                    entity_type=str(actor.type),
                    pos=BlockVec3(int(loc.block_x), int(loc.block_y), int(loc.block_z)),
                    name=str(getattr(actor, "name", "")),
                    raw_actor=actor,
                )
            )
        return out

    def remove_entity(self, info: ActorInfo) -> bool:
        if info.raw_actor is None or info.entity_type == "minecraft:player":
            return False
        info.raw_actor.remove()
        return True

    def get_loaded_chunks(self) -> list[tuple[int, int]]:
        return [(int(c.x), int(c.z)) for c in self.dimension.loaded_chunks]

    def get_biome(self, pos: BlockVec3) -> str:
        key = (pos.x, pos.y, pos.z)
        if key in self._biome_overrides:
            return self._biome_overrides[key]
        dim_low = self.name.lower()
        if "nether" in dim_low:
            return "hell"
        if "end" in dim_low:
            return "the_end"
        return "plains"

    def set_biome(self, pos: BlockVec3, biome: str) -> bool:
        # Endstone 0.11 does not expose a native chunk biome setter; store session-level mapping.
        self._biome_overrides[(pos.x, pos.y, pos.z)] = biome.lower()
        return True


@dataclass
class InMemoryWorldAdapter:
    """Fast dict-backed world adapter for unit tests and offline dry-runs."""

    _name: str = "overworld"
    _min_y: int = -64
    _max_y: int = 319
    blocks: dict[BlockVec3, BlockSpec] = field(default_factory=dict)
    biomes: dict[BlockVec3, str] = field(default_factory=dict)
    entities: list[ActorInfo] = field(default_factory=list)
    default_biome: str = "plains"

    @property
    def name(self) -> str:
        return self._name

    @property
    def min_y(self) -> int:
        return self._min_y

    @property
    def max_y(self) -> int:
        return self._max_y

    def get_block(self, pos: BlockVec3) -> BlockSpec:
        if pos.y < self._min_y or pos.y > self._max_y:
            return AIR_SPEC
        return self.blocks.get(pos, AIR_SPEC)

    def set_block(self, pos: BlockVec3, spec: BlockSpec, apply_physics: bool = True) -> None:
        if pos.y < self._min_y or pos.y > self._max_y:
            return
        if spec.is_air and spec.block_type == "minecraft:air":
            self.blocks.pop(pos, None)
        else:
            self.blocks[pos] = spec

    def get_highest_y(self, x: int, z: int) -> int:
        highest = self._min_y - 1
        for p in self.blocks:
            if p.x == x and p.z == z and p.y > highest:
                highest = p.y
        return highest

    def get_entities(self) -> list[ActorInfo]:
        return list(self.entities)

    def remove_entity(self, info: ActorInfo) -> bool:
        if info.entity_type == "minecraft:player":
            return False
        before = len(self.entities)
        self.entities = [e for e in self.entities if e.entity_id != info.entity_id]
        return len(self.entities) < before

    def get_loaded_chunks(self) -> list[tuple[int, int]]:
        chunks = {p.chunk_coords() for p in self.blocks}
        return sorted(chunks)

    def get_biome(self, pos: BlockVec3) -> str:
        return self.biomes.get(pos, self.default_biome)

    def set_biome(self, pos: BlockVec3, biome: str) -> bool:
        self.biomes[pos] = biome.lower()
        return True
