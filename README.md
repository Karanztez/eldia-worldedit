# Eldia WorldEdit

In-game map editing, terrain sculpting, and schematic building plugin for [Endstone](https://github.com/EndstoneMC/endstone) Bedrock Dedicated Servers.

## Features

- **7 Selection Modes & Wand**: Select regions with a wooden axe (`//wand`), line-of-sight commands (`//hpos1`, `//hpos2`), chunk selection, or particle wireframe outlines (`//drawsel`) across `cuboid`, `extend`, `ellipsoid`, `sphere`, `cyl`, `poly`, and `convex` modes.
- **Batched Block Editing & Undo/Redo**: Execute large fill, replace, smooth, hollow, deform, move, stack, and spline operations in tick-safe batches with per-player `//undo`, `//redo`, block change limits, and global masks.
- **Patterns & Masks**: Combine weighted block mixes, categories (`##wool`), clipboard/hand references, block states, inverted/neighbor filters (`>`, `<`, `!`), and math formulas (`=x^2+z^2<25`).
- **3D Shapes & World Generators**: Build spheres, cylinders, cones, pyramids, math-driven shapes (`//g`), trees, forests, flora, and natural terrain layers.
- **Clipboard & Schematics**: Copy, cut, paste, rotate (with directional block state rotation), flip, revolve radially, and save/load `.schem` (Sponge v2/v3), `.schematic`, `.mcstructure` (Bedrock structure files), or `.wejson` files.
- **24 Brushes, 11 Item Tools & Super Pickaxe**: Bind sculpting brushes (`sphere`, `cyl`, `splatter`, `smooth`, `heightmap`, `morph`, `erode`, `dilate`, `paint`, etc.) and tools (`info`, `tree`, `stacker`, `repl`, `cycler`, `floodfill`, `deltree`, `farwand`, `lrbuild`) onto any held item, plus 3 Super Pickaxe mining modes.
- **Snapshots & Navigation**: Back up and restore region snapshots, run `.wescript` macros, set biomes, or teleport cleanly with `/unstuck`, `/ascend`, `/descend`, `/ceil`, `/thru`, `/jumpto`, and `/up`.
- **Multi-Language & Bedrock UI**: Switch messages and Bedrock form menus between English (`en`) and Thai (`th`) via `config.yml` or `/ewe lang th`, with clean `[EWE]` chat prefixes.

## Installation

1. Download `endstone_eldia_worldedit-0.1.2-py3-none-any.whl` from [GitHub Releases](https://github.com/Karanztez/eldia-worldedit/releases).
2. Place the `.whl` file into `bedrock_server/plugins/`.
3. Restart your Endstone server.

## Quick Start

1. Run `//wand` to receive a Wooden Axe selection wand (left click = Pos 1, right click = Pos 2), or stand at corners and run `//pos1` and `//pos2`.
2. Run `//drawsel` to preview your selected bounds with particles.
3. Run `//set 50%stone,50%cobblestone` to fill the region.
4. Made a mistake? Run `//undo` (and `//redo` to reapply).
5. Prefer menus or Thai messages? Run `/ewe gui` or switch language with `/ewe lang th`.

## Configuration (`config.yml`)

After first launch, edit `plugins/eldia_worldedit/config.yml`:

```yaml
language: "th"   # "en" or "th"
prefix: "[EWE]"
max_history: 30
default_limit: 500000
```

Then run `/ewe reload` in-game to apply without restarting.

## Patterns & Masks

- **Patterns**:
  - Single block: `stone`, `quartz_block`, `oak_stairs[weirdo_direction=2]`
  - Weighted random mix: `50%stone,30%cobblestone,20%andesite`
  - Contextual & category tags: `#hand`, `#clipboard`, `##wool`, `##stone`
  - State override only: `^[facing_direction=3]`
- **Masks**:
  - Basic & categories: `stone`, `!air`, `#existing`, `#solid`, `#liquid`, `#surface`, `#exposed`, `#region`
  - Relative neighbors: `>grass_block` (blocks directly above grass), `<air` (blocks with air above)
  - Random chance & formulas: `%35`, `=x^2+z^2<25`
  - Combinators: comma `,` for OR union (`dirt,grass_block`), space for AND intersection (`#solid #region`)

## Commands

All `//<command>` commands can also be run as `/ewe <command>` (or `/we <command>`). Non-colliding commands work directly with a single `/`.

### Selection

| Command | Aliases | Description |
| --- | --- | --- |
| `//wand [-n]` | — | Give selection wand (`-n` gives navigation wand) |
| `//pos1 [x,y,z]` | `//1` | Set position 1 at player or coordinates |
| `//pos2 [x,y,z]` | `//2` | Set position 2 at player or coordinates |
| `//hpos1` / `//hpos2` | — | Set position 1 or 2 at targeted block |
| `//chunk [x,z]` | — | Select the entire chunk column |
| `//sel [mode]` | `//desel`, `/;` | Clear selection or switch selector mode |
| `//expand <amt\|vert> [dir]` | — | Expand selection along direction or sky-to-bedrock |
| `//contract <amt> [dir]` | — | Contract selection boundaries |
| `//outset [-hv] <amt>` / `//inset [-hv] <amt>` | — | Grow or shrink all faces evenly |
| `//shift <amt> [dir]` | — | Move selection box without moving blocks |
| `//size [-c]` | — | Show selection or clipboard dimensions |
| `//count <mask>` / `//distr [-d]` | — | Count matching blocks or show distribution |
| `//drawsel` | — | Toggle selection outline particle display |
| `/toggleeditwand` / `/toggleplace` | `/tew` | Toggle wand clicks or pos1/player placement |

### Region Editing

| Command | Aliases | Description |
| --- | --- | --- |
| `//set <pattern>` | — | Fill selection with pattern |
| `//replace [from] <to>` | `//re`, `//rep` | Replace non-air or masked blocks |
| `//overlay <pattern>` | — | Place one layer atop surface columns |
| `//walls <pattern>` | — | Build vertical perimeter walls |
| `//faces <pattern>` | `//outline` | Build outer 6 faces of selection |
| `//center <pattern>` | `//middle` | Place blocks at center point(s) |
| `//smooth [-n] [iters]` / `//snowsmooth` | — | Smooth terrain heightmaps or snow layers |
| `//move [-saeb] [n] [dir] [leave]` | — | Shift selected blocks (optionally entities/biomes) |
| `//stack [-saeb] [n] [dir]` | — | Repeat selection `n` times along direction |
| `//line [-h] <pat> [thickness]` | — | Draw straight 3D line between `pos1` and `pos2` |
| `//curve [-h] <pat> [thickness]` | — | Draw smooth spline through convex vertices |
| `//hollow [thickness] [pattern]` | — | Hollow solid interiors |
| `//deform [-ro] <expr>` | — | Deform blocks using math formula |
| `//revolve [-r] <count> [start] [end] [dy]` | — | Clone selection radially around player |
| `//forest` / `//flora` / `//naturalize` / `//regen` | — | Generate trees, plants, soil layers, or reset ground |

### Shapes & Generation

| Command | Aliases | Description |
| --- | --- | --- |
| `//cyl [-h] <pat> <rad> [h]` / `//hcyl` | — | Solid or hollow cylinder |
| `//sphere [-rh] <pat> <rad>` / `//hsphere` | — | Solid or hollow sphere/ellipsoid (`-r` raises base) |
| `//pyramid [-h] <pat> <size>` / `//hpyramid` | — | Solid or hollow step pyramid |
| `//cone [-h] <pat> <rad> <h> [thick]` | — | Tapered elliptical cone |
| `//g [-hroc] <pat> <expr>` | `//gen`, `//generate` | Generate shape from math equation |
| `/forestgen [size] [type] [density]` / `/pumpkins` | — | Generate local forest or pumpkin patch |
| `//generatebiome <biome>` | — | Apply biome across selection |

### Clipboard & Schematics

| Command | Description |
| --- | --- |
| `//copy [-eb] [-m mask]` / `//cut` | Copy or cut selection relative to player origin |
| `//paste [-aosben] [-m mask]` | Paste clipboard (`-a` skip air, `-o` original pos, `-s` select result) |
| `//rotate <y> [x] [z]` | Rotate clipboard in 90-degree increments |
| `//flip [direction]` | Mirror clipboard along axis/direction |
| `//clearclipboard` | Clear clipboard buffer |
| `//schem <save\|load\|list\|delete\|formats>` | Save or load `.schem`, `.schematic`, `.mcstructure`, and `.wejson` files |

### History

| Command | Description |
| --- | --- |
| `//undo [count] [player]` | Revert recent edits |
| `//redo [count] [player]` | Reapply undone edits |
| `//clearhistory` | Clear undo and redo history |

### Navigation

| Command | Aliases | Description |
| --- | --- | --- |
| `/unstuck` | `/!` | Escape upward out of solid blocks |
| `/ascend [levels]` / `/descend [levels]` | `/asc`, `/desc` | Move up or down floors |
| `/ceil [-g] [clearance]` | — | Rise directly beneath the ceiling |
| `/thru` | — | Pass through wall you are looking at |
| `/jumpto` | `/j` | Teleport atop targeted block |
| `/up [-f] <distance>` | — | Rise upward with optional glass foothold |

### Utility

| Command | Aliases | Description |
| --- | --- | --- |
| `//fill [-u] <pat> <rad> [depth]` / `//fillr` | — | Flood-fill pits (`-u` upward, `fillr` recursive) |
| `//drain [-w] <rad>` / `/fixwater` / `/fixlava` | — | Drain connected liquids or level liquid pools |
| `/removeabove [size] [h]` / `/removebelow` | — | Clear vertical blocks above or below player |
| `/removenear <mask> [size]` / `/replacenear` | — | Remove or replace blocks around player |
| `/snow [-s] [rad]` / `/thaw` / `/green [-f]` | — | Add snow/ice, melt snow, or spread grass |
| `/extinguish [rad]` | `/ex` | Extinguish nearby fire |
| `/butcher [-pangbf] [rad]` / `/remove <type>` | `/rem` | Kill mobs or clear items/entities |
| `//calc <expr>` | `//eval` | Evaluate math formulas (`sin`, `cos`, `noise`, `pi`) |

### Brushes, Tools & Super Pickaxe

| Command | Aliases | Description |
| --- | --- | --- |
| `//br <type> ...` | `//brush` | Bind brush (`sphere`, `cyl`, `cone`, `splatter`, `clipboard`, `smooth`, `snowsmooth`, `extinguish`, `gravity`, `butcher`, `height`, `deform`, `set`, `forest`, `feature`, `raise`, `lower`, `snow`, `biome`, `morph`, `erode`, `dilate`, `apply`, `paint`, `none`) |
| `/mat`, `/size`, `/range`, `/mask`, `/smask`, `/tracemask` | `/material` | Customize held brush material, radius, range, and masks |
| `/tool <type>` | — | Bind item tool (`selwand`, `navwand`, `info`, `tree`, `stack`, `repl`, `cycler`, `floodfill`, `deltree`, `farwand`, `lrbuild`, `none`, `unbindall`) |
| `/info`, `/tree`, `/repl`, `/cycler`, `/stacker`, `/floodfill`, `/deltree`, `/farwand`, `/lrbuild`, `/none` | `/flood` | Direct item tool shortcuts |
| `//sp [toggle\|single\|area\|recursive] [r]` | `//`, `/,` | Toggle Super Pickaxe and switch mining mode |

### General, Biomes, Snapshots & Scripts

| Command | Description |
| --- | --- |
| `/ewe <gui\|lang\|version\|help\|reload\|cui\|report>` | Open UI, switch `en`/`th`, reload `config.yml`, help |
| `//gmask [mask]` / `//gtransform [expr]` | Set global edit mask or transform |
| `//fast` / `//perf [mode]` | Toggle physics suppression and placement ordering |
| `//limit [count]` / `//timeout <ms>` | Set per-edit block limit or timeout |
| `/searchitem <query>` | Search known Bedrock block IDs |
| `/biomeinfo [-pt]` / `/biomelist [page]` / `//setbiome` | Inspect, list, and set region biomes |
| `/chunkinfo` / `/listchunks` / `/delchunks` | Inspect chunk coordinates and loaded chunks |
| `//snap <save\|list\|use\|sel\|before\|after>` / `//restore` | Capture and restore region backup snapshots |
| `/cs <file> [args...]` / `/.s [args...]` | Execute or repeat `.wescript` command macros |
