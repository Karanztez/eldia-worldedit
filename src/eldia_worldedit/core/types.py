"""Core immutable coordinate vectors, Bedrock block specs, categories, and direction helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass

StateValue = bool | int | str

LEGACY_BLOCK_IDS: dict[str, str] = {
    "0": "minecraft:air",
    "1": "minecraft:stone",
    "2": "minecraft:grass_block",
    "3": "minecraft:dirt",
    "4": "minecraft:cobblestone",
    "5": "minecraft:oak_planks",
    "7": "minecraft:bedrock",
    "8": "minecraft:water",
    "9": "minecraft:water",
    "10": "minecraft:lava",
    "11": "minecraft:lava",
    "12": "minecraft:sand",
    "13": "minecraft:gravel",
    "14": "minecraft:gold_ore",
    "15": "minecraft:iron_ore",
    "16": "minecraft:coal_ore",
    "17": "minecraft:oak_log",
    "18": "minecraft:oak_leaves",
    "19": "minecraft:sponge",
    "20": "minecraft:glass",
    "21": "minecraft:lapis_ore",
    "22": "minecraft:lapis_block",
    "24": "minecraft:sandstone",
    "35": "minecraft:white_wool",
    "41": "minecraft:gold_block",
    "42": "minecraft:iron_block",
    "43": "minecraft:double_stone_slab",
    "44": "minecraft:stone_slab",
    "45": "minecraft:brick_block",
    "46": "minecraft:tnt",
    "47": "minecraft:bookshelf",
    "48": "minecraft:mossy_cobblestone",
    "49": "minecraft:obsidian",
    "50": "minecraft:torch",
    "51": "minecraft:fire",
    "53": "minecraft:oak_stairs",
    "54": "minecraft:chest",
    "57": "minecraft:diamond_block",
    "58": "minecraft:crafting_table",
    "65": "minecraft:ladder",
    "67": "minecraft:stone_stairs",
    "79": "minecraft:ice",
    "80": "minecraft:snow",
    "82": "minecraft:clay",
    "86": "minecraft:pumpkin",
    "87": "minecraft:netherrack",
    "88": "minecraft:soul_sand",
    "89": "minecraft:glowstone",
    "95": "minecraft:stained_glass",
    "98": "minecraft:stone_bricks",
    "112": "minecraft:nether_brick",
    "121": "minecraft:end_stone",
    "133": "minecraft:emerald_block",
    "152": "minecraft:redstone_block",
    "155": "minecraft:quartz_block",
    "159": "minecraft:stained_hardened_clay",
    "169": "minecraft:sea_lantern",
    "174": "minecraft:packed_ice",
    "251": "minecraft:concrete",
    "cobble": "minecraft:cobblestone",
}

AIR_BLOCKS: frozenset[str] = frozenset({
    "minecraft:air",
    "minecraft:cave_air",
    "minecraft:void_air",
    "minecraft:structure_void",
})

WATER_BLOCKS: frozenset[str] = frozenset({"minecraft:water", "minecraft:flowing_water"})
LAVA_BLOCKS: frozenset[str] = frozenset({"minecraft:lava", "minecraft:flowing_lava"})
LIQUID_BLOCKS: frozenset[str] = WATER_BLOCKS | LAVA_BLOCKS

NON_SOLID_EXTRA: frozenset[str] = (
    AIR_BLOCKS
    | LIQUID_BLOCKS
    | frozenset({
        "minecraft:fire",
        "minecraft:soul_fire",
        "minecraft:snow_layer",
        "minecraft:short_grass",
        "minecraft:tall_grass",
        "minecraft:fern",
        "minecraft:large_fern",
        "minecraft:deadbush",
        "minecraft:dandelion",
        "minecraft:poppy",
        "minecraft:blue_orchid",
        "minecraft:allium",
        "minecraft:azure_bluet",
        "minecraft:red_tulip",
        "minecraft:orange_tulip",
        "minecraft:white_tulip",
        "minecraft:pink_tulip",
        "minecraft:oxeye_daisy",
        "minecraft:cornflower",
        "minecraft:lily_of_the_valley",
        "minecraft:torch",
        "minecraft:soul_torch",
        "minecraft:redstone_torch",
        "minecraft:vine",
        "minecraft:ladder",
    })
)

_COLORS = (
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black",
)
_WOOD_TYPES = ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry", "bamboo")

BLOCK_CATEGORIES: dict[str, frozenset[str]] = {
    "air": AIR_BLOCKS,
    "water": WATER_BLOCKS,
    "lava": LAVA_BLOCKS,
    "liquid": LIQUID_BLOCKS,
    "liquids": LIQUID_BLOCKS,
    "fire": frozenset({"minecraft:fire", "minecraft:soul_fire"}),
    "snow": frozenset({"minecraft:snow", "minecraft:snow_layer", "minecraft:powder_snow"}),
    "logs": frozenset(
        {f"minecraft:{w}_log" for w in _WOOD_TYPES if w != "bamboo"}
        | {f"minecraft:stripped_{w}_log" for w in _WOOD_TYPES if w != "bamboo"}
        | {"minecraft:crimson_stem", "minecraft:warped_stem", "minecraft:bamboo_block"}
    ),
    "planks": frozenset(
        {f"minecraft:{w}_planks" for w in _WOOD_TYPES}
        | {"minecraft:crimson_planks", "minecraft:warped_planks"}
    ),
    "leaves": frozenset({
        "minecraft:oak_leaves", "minecraft:spruce_leaves", "minecraft:birch_leaves",
        "minecraft:jungle_leaves", "minecraft:acacia_leaves", "minecraft:dark_oak_leaves",
        "minecraft:mangrove_leaves", "minecraft:cherry_leaves", "minecraft:azalea_leaves",
        "minecraft:azalea_leaves_flowered",
    }),
    "wool": frozenset({f"minecraft:{c}_wool" for c in _COLORS}),
    "glass": frozenset(
        {"minecraft:glass", "minecraft:tinted_glass", "minecraft:glass_pane"}
        | {f"minecraft:{c}_stained_glass" for c in _COLORS}
        | {f"minecraft:{c}_stained_glass_pane" for c in _COLORS}
    ),
    "terracotta": frozenset(
        {"minecraft:terracotta", "minecraft:hardened_clay"}
        | {f"minecraft:{c}_terracotta" for c in _COLORS}
        | {f"minecraft:{c}_glazed_terracotta" for c in _COLORS}
    ),
    "concrete": frozenset(
        {f"minecraft:{c}_concrete" for c in _COLORS}
        | {f"minecraft:{c}_concrete_powder" for c in _COLORS}
    ),
    "stone": frozenset({
        "minecraft:stone", "minecraft:granite", "minecraft:diorite", "minecraft:andesite",
        "minecraft:deepslate", "minecraft:cobblestone", "minecraft:cobbled_deepslate",
        "minecraft:stone_bricks", "minecraft:deepslate_bricks", "minecraft:smooth_stone",
        "minecraft:tuff", "minecraft:calcite", "minecraft:blackstone", "minecraft:basalt",
    }),
    "ores": frozenset({
        "minecraft:coal_ore", "minecraft:deepslate_coal_ore",
        "minecraft:iron_ore", "minecraft:deepslate_iron_ore",
        "minecraft:copper_ore", "minecraft:deepslate_copper_ore",
        "minecraft:gold_ore", "minecraft:deepslate_gold_ore",
        "minecraft:redstone_ore", "minecraft:deepslate_redstone_ore",
        "minecraft:emerald_ore", "minecraft:deepslate_emerald_ore",
        "minecraft:lapis_ore", "minecraft:deepslate_lapis_ore",
        "minecraft:diamond_ore", "minecraft:deepslate_diamond_ore",
        "minecraft:nether_gold_ore", "minecraft:nether_quartz_ore",
        "minecraft:ancient_debris",
    }),
    "stairs": frozenset({
        "minecraft:oak_stairs", "minecraft:spruce_stairs", "minecraft:birch_stairs",
        "minecraft:jungle_stairs", "minecraft:acacia_stairs", "minecraft:dark_oak_stairs",
        "minecraft:stone_stairs", "minecraft:cobblestone_stairs", "minecraft:stone_brick_stairs",
        "minecraft:brick_stairs", "minecraft:sandstone_stairs", "minecraft:quartz_stairs",
        "minecraft:nether_brick_stairs", "minecraft:prismarine_stairs", "minecraft:deepslate_brick_stairs",
    }),
    "slabs": frozenset({
        "minecraft:oak_slab", "minecraft:spruce_slab", "minecraft:birch_slab",
        "minecraft:jungle_slab", "minecraft:acacia_slab", "minecraft:dark_oak_slab",
        "minecraft:stone_slab", "minecraft:cobblestone_slab", "minecraft:stone_brick_slab",
        "minecraft:brick_slab", "minecraft:sandstone_slab", "minecraft:quartz_slab",
        "minecraft:smooth_stone_slab", "minecraft:deepslate_brick_slab",
    }),
    "flowers": frozenset({
        "minecraft:dandelion", "minecraft:poppy", "minecraft:blue_orchid", "minecraft:allium",
        "minecraft:azure_bluet", "minecraft:red_tulip", "minecraft:orange_tulip",
        "minecraft:white_tulip", "minecraft:pink_tulip", "minecraft:oxeye_daisy",
        "minecraft:cornflower", "minecraft:lily_of_the_valley", "minecraft:sunflower",
        "minecraft:lilac", "minecraft:rose_bush", "minecraft:peony", "minecraft:wither_rose",
    }),
}
BLOCK_CATEGORIES["wood"] = BLOCK_CATEGORIES["logs"] | BLOCK_CATEGORIES["planks"]
BLOCK_CATEGORIES["plants"] = BLOCK_CATEGORIES["flowers"] | frozenset({
    "minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern", "minecraft:large_fern",
    "minecraft:sugar_cane", "minecraft:bamboo", "minecraft:cactus", "minecraft:pumpkin",
    "minecraft:melon_block", "minecraft:sweet_berry_bush",
})

KNOWN_BEDROCK_BIOMES: tuple[str, ...] = (
    "ocean", "plains", "desert", "extreme_hills", "forest", "taiga", "swampland", "river",
    "hell", "the_end", "frozen_ocean", "frozen_river", "ice_plains", "ice_mountains",
    "mushroom_island", "mushroom_island_shore", "beach", "desert_hills", "forest_hills",
    "taiga_hills", "extreme_hills_edge", "jungle", "jungle_hills", "jungle_edge",
    "deep_ocean", "stone_beach", "cold_beach", "birch_forest", "birch_forest_hills",
    "roofed_forest", "cold_taiga", "cold_taiga_hills", "mega_taiga", "mega_taiga_hills",
    "extreme_hills_plus_trees", "savanna", "savanna_plateau", "mesa", "mesa_plateau_stone",
    "mesa_plateau", "warm_ocean", "lukewarm_ocean", "cold_ocean", "deep_warm_ocean",
    "deep_lukewarm_ocean", "deep_cold_ocean", "deep_frozen_ocean", "sunflower_plains",
    "flower_forest", "ice_plains_spikes", "bamboo_jungle", "bamboo_jungle_hills",
    "soulsand_valley", "crimson_forest", "warped_forest", "basalt_deltas",
    "dripstone_caves", "lush_caves", "meadow", "grove", "snowy_slopes",
    "jagged_peaks", "frozen_peaks", "stony_peaks", "deep_dark", "mangrove_swamp",
    "cherry_grove", "pale_garden",
)

KNOWN_BEDROCK_BLOCKS: tuple[str, ...] = tuple(sorted(
    set(LEGACY_BLOCK_IDS.values())
    | BLOCK_CATEGORIES["stone"]
    | BLOCK_CATEGORIES["logs"]
    | BLOCK_CATEGORIES["planks"]
    | BLOCK_CATEGORIES["leaves"]
    | BLOCK_CATEGORIES["wool"]
    | BLOCK_CATEGORIES["glass"]
    | BLOCK_CATEGORIES["terracotta"]
    | BLOCK_CATEGORIES["concrete"]
    | BLOCK_CATEGORIES["ores"]
    | BLOCK_CATEGORIES["stairs"]
    | BLOCK_CATEGORIES["slabs"]
    | BLOCK_CATEGORIES["flowers"]
    | BLOCK_CATEGORIES["snow"]
    | {
        "minecraft:grass_block", "minecraft:podzol", "minecraft:mycelium", "minecraft:farmland",
        "minecraft:sand", "minecraft:red_sand", "minecraft:gravel", "minecraft:clay",
        "minecraft:coarse_dirt", "minecraft:rooted_dirt", "minecraft:mud", "minecraft:packed_mud",
        "minecraft:mud_bricks", "minecraft:sponge", "minecraft:wet_sponge",
        "minecraft:sea_lantern", "minecraft:glowstone", "minecraft:shroomlight", "minecraft:lantern",
        "minecraft:soul_lantern", "minecraft:amethyst_block", "minecraft:budding_amethyst",
        "minecraft:copper_block", "minecraft:cut_copper", "minecraft:quartz_block",
        "minecraft:chiseled_quartz_block", "minecraft:quartz_pillar", "minecraft:purpur_block",
        "minecraft:end_stone", "minecraft:end_bricks", "minecraft:obsidian", "minecraft:crying_obsidian",
        "minecraft:prismarine", "minecraft:dark_prismarine", "minecraft:prismarine_bricks",
        "minecraft:sculk", "minecraft:hay_block", "minecraft:bone_block", "minecraft:slime",
        "minecraft:honey_block", "minecraft:melon_block", "minecraft:pumpkin", "minecraft:carved_pumpkin",
        "minecraft:lit_pumpkin", "minecraft:chest", "minecraft:barrel", "minecraft:furnace",
        "minecraft:crafting_table", "minecraft:bookshelf", "minecraft:enchanting_table",
        "minecraft:beacon", "minecraft:conduit", "minecraft:anvil", "minecraft:bell",
    }
))


@dataclass(frozen=True, order=True)
class BlockVec3:
    """Immutable 3D integer block coordinate vector."""

    x: int
    y: int
    z: int

    def __add__(self, other: BlockVec3) -> BlockVec3:
        return BlockVec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: BlockVec3) -> BlockVec3:
        return BlockVec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, factor: int) -> BlockVec3:
        return BlockVec3(self.x * factor, self.y * factor, self.z * factor)

    def __rmul__(self, factor: int) -> BlockVec3:
        return self.__mul__(factor)

    def __neg__(self) -> BlockVec3:
        return BlockVec3(-self.x, -self.y, -self.z)

    def floor_div(self, divisor: int) -> BlockVec3:
        return BlockVec3(self.x // divisor, self.y // divisor, self.z // divisor)

    def distance_sq(self, other: BlockVec3) -> int:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return dx * dx + dy * dy + dz * dz

    def distance(self, other: BlockVec3) -> float:
        return math.sqrt(self.distance_sq(other))

    def min_with(self, other: BlockVec3) -> BlockVec3:
        return BlockVec3(min(self.x, other.x), min(self.y, other.y), min(self.z, other.z))

    def max_with(self, other: BlockVec3) -> BlockVec3:
        return BlockVec3(max(self.x, other.x), max(self.y, other.y), max(self.z, other.z))

    def chunk_coords(self) -> tuple[int, int]:
        return self.x >> 4, self.z >> 4

    def to_tuple(self) -> tuple[int, int, int]:
        return (self.x, self.y, self.z)

    def format_short(self) -> str:
        return f"({self.x}, {self.y}, {self.z})"


@dataclass(frozen=True)
class BlockSpec:
    """Represents a Minecraft Bedrock block type plus optional block states."""

    block_type: str
    states: tuple[tuple[str, StateValue], ...] = ()

    @property
    def states_dict(self) -> dict[str, StateValue]:
        return dict(self.states)

    @property
    def is_air(self) -> bool:
        return self.block_type in AIR_BLOCKS

    @property
    def is_liquid(self) -> bool:
        return self.block_type in LIQUID_BLOCKS

    @property
    def is_solid(self) -> bool:
        return self.block_type not in NON_SOLID_EXTRA

    def to_string(self) -> str:
        if not self.states:
            return self.block_type
        parts: list[str] = []
        for k, v in self.states:
            if isinstance(v, bool):
                parts.append(f"{k}={'true' if v else 'false'}")
            else:
                parts.append(f"{k}={v}")
        return f"{self.block_type}[{','.join(parts)}]"

    def __str__(self) -> str:
        return self.to_string()


AIR_SPEC = BlockSpec("minecraft:air")
STONE_SPEC = BlockSpec("minecraft:stone")


def normalize_block_id(raw: str) -> str:
    """Normalize legacy numeric IDs and unnamespaced block names to 'minecraft:<id>'."""
    token = raw.strip().lower()
    if not token:
        raise ValueError("Block identifier cannot be empty.")
    if token in LEGACY_BLOCK_IDS:
        return LEGACY_BLOCK_IDS[token]
    if ":" not in token:
        return f"minecraft:{token}"
    return token


def _parse_state_value(raw: str) -> StateValue:
    val = raw.strip()
    low = val.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if val.lstrip("-").isdigit():
        return int(val)
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    return val


def parse_block_spec(raw: str) -> BlockSpec:
    """Parse 'stone' or 'minecraft:oak_stairs[weirdo_direction=2,upside_down_bit=true]'."""
    text = raw.strip()
    if not text:
        raise ValueError("Empty block specification.")
    if "[" in text:
        if not text.endswith("]"):
            raise ValueError(f"Invalid block state syntax: '{raw}'.")
        name_part, state_part = text.split("[", 1)
        state_body = state_part[:-1].strip()
        block_id = normalize_block_id(name_part)
        parsed_states: list[tuple[str, StateValue]] = []
        if state_body:
            for item in state_body.split(","):
                item = item.strip()
                if "=" not in item:
                    raise ValueError(f"Expected key=value in block states: '{item}'.")
                k, v = item.split("=", 1)
                parsed_states.append((k.strip(), _parse_state_value(v)))
        parsed_states.sort(key=lambda pair: pair[0])
        return BlockSpec(block_id, tuple(parsed_states))
    return BlockSpec(normalize_block_id(text))


_CARDINAL_CW = ("north", "east", "south", "west")
# Bedrock facing_direction: 0=down, 1=up, 2=north, 3=south, 4=west, 5=east
_FACING_DIR_CW = {2: 5, 5: 3, 3: 4, 4: 2}
# Bedrock weirdo_direction (stairs): 0=east, 1=west, 2=south, 3=north
_WEIRDO_CW = {0: 2, 2: 1, 1: 3, 3: 0}
# Generic horizontal direction: 0=south, 1=west, 2=north, 3=east
_DIR_CW = {0: 1, 1: 2, 2: 3, 3: 0}


def rotate_block_spec(spec: BlockSpec, degrees_y: int) -> BlockSpec:
    """Rotate directional Bedrock block states clockwise around the Y axis in 90-degree steps."""
    steps = (degrees_y // 90) % 4
    if steps == 0 or not spec.states:
        return spec

    new_states: list[tuple[str, StateValue]] = []
    for k, v in spec.states:
        nv = v
        if k == "minecraft:cardinal_direction" and isinstance(v, str) and v in _CARDINAL_CW:
            nv = _CARDINAL_CW[(_CARDINAL_CW.index(v) + steps) % 4]
        elif k == "facing_direction" and isinstance(v, int) and v in _FACING_DIR_CW:
            cur = v
            for _ in range(steps):
                cur = _FACING_DIR_CW[cur]
            nv = cur
        elif k == "weirdo_direction" and isinstance(v, int) and v in _WEIRDO_CW:
            cur = v
            for _ in range(steps):
                cur = _WEIRDO_CW[cur]
            nv = cur
        elif k == "direction" and isinstance(v, int) and v in _DIR_CW:
            cur = v
            for _ in range(steps):
                cur = _DIR_CW[cur]
            nv = cur
        elif k == "pillar_axis" and isinstance(v, str) and steps % 2 == 1:
            if v == "x":
                nv = "z"
            elif v == "z":
                nv = "x"
        new_states.append((k, nv))
    return BlockSpec(spec.block_type, tuple(new_states))


def flip_block_spec(spec: BlockSpec, axis: str) -> BlockSpec:
    """Flip directional Bedrock block states across 'x', 'y', or 'z'."""
    if not spec.states:
        return spec

    new_states: list[tuple[str, StateValue]] = []
    for k, v in spec.states:
        nv = v
        if axis == "x":
            if k == "minecraft:cardinal_direction" and v in ("east", "west"):
                nv = "west" if v == "east" else "east"
            elif k == "facing_direction" and v in (4, 5):
                nv = 5 if v == 4 else 4
            elif k == "weirdo_direction" and v in (0, 1):
                nv = 1 if v == 0 else 0
            elif k == "direction" and v in (1, 3):
                nv = 3 if v == 1 else 1
        elif axis == "z":
            if k == "minecraft:cardinal_direction" and v in ("north", "south"):
                nv = "south" if v == "north" else "north"
            elif k == "facing_direction" and v in (2, 3) or k == "weirdo_direction" and v in (2, 3):
                nv = 3 if v == 2 else 2
            elif k == "direction" and v in (0, 2):
                nv = 2 if v == 0 else 0
        elif axis == "y":
            if k == "facing_direction" and v in (0, 1):
                nv = 1 if v == 0 else 0
            elif k == "upside_down_bit" and isinstance(v, bool) or k == "top_slot_bit" and isinstance(v, bool):
                nv = not v
        new_states.append((k, nv))
    return BlockSpec(spec.block_type, tuple(new_states))


def _yaw_pitch_to_cardinal(yaw: float, pitch: float) -> BlockVec3:
    """Convert Bedrock yaw/pitch into the nearest 6-way unit BlockVec3."""
    if pitch <= -45.0:
        return BlockVec3(0, 1, 0)
    if pitch >= 45.0:
        return BlockVec3(0, -1, 0)
    # In Minecraft: yaw 0 = +Z (south), 90 = -X (west), 180/-180 = -Z (north), -90/270 = +X (east)
    angle = (yaw % 360.0 + 360.0) % 360.0
    if 45.0 <= angle < 135.0:
        return BlockVec3(-1, 0, 0)  # west
    if 135.0 <= angle < 225.0:
        return BlockVec3(0, 0, -1)  # north
    if 225.0 <= angle < 315.0:
        return BlockVec3(1, 0, 0)   # east
    return BlockVec3(0, 0, 1)       # south


def _horizontal_yaw_to_cardinal(yaw: float) -> BlockVec3:
    angle = (yaw % 360.0 + 360.0) % 360.0
    if 45.0 <= angle < 135.0:
        return BlockVec3(-1, 0, 0)
    if 135.0 <= angle < 225.0:
        return BlockVec3(0, 0, -1)
    if 225.0 <= angle < 315.0:
        return BlockVec3(1, 0, 0)
    return BlockVec3(0, 0, 1)


def resolve_direction(token: str | None, yaw: float = 0.0, pitch: float = 0.0) -> BlockVec3:
    """Resolve a WorldEdit direction string or player orientation into a unit BlockVec3."""
    if token is None or not token.strip():
        return _yaw_pitch_to_cardinal(yaw, pitch)

    key = token.strip().lower()
    fixed: dict[str, BlockVec3] = {
        "n": BlockVec3(0, 0, -1),
        "north": BlockVec3(0, 0, -1),
        "s": BlockVec3(0, 0, 1),
        "south": BlockVec3(0, 0, 1),
        "e": BlockVec3(1, 0, 0),
        "east": BlockVec3(1, 0, 0),
        "w": BlockVec3(-1, 0, 0),
        "west": BlockVec3(-1, 0, 0),
        "u": BlockVec3(0, 1, 0),
        "up": BlockVec3(0, 1, 0),
        "d": BlockVec3(0, -1, 0),
        "down": BlockVec3(0, -1, 0),
    }
    if key in fixed:
        return fixed[key]

    fwd = _yaw_pitch_to_cardinal(yaw, pitch)
    if key in ("me", "f", "forward", "front"):
        return fwd
    if key in ("b", "back"):
        return -fwd
    h_fwd = _horizontal_yaw_to_cardinal(yaw)
    if key in ("l", "left"):
        # Left of (dx, 0, dz) looking down +Y -> (dz, 0, -dx)
        return BlockVec3(h_fwd.z, 0, -h_fwd.x)
    if key in ("r", "right"):
        return BlockVec3(-h_fwd.z, 0, h_fwd.x)

    raise ValueError(
        f"Unknown direction '{token}'. Use north, south, east, west, up, down, me, back, left, or right."
    )
