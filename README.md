# Kiripix

A local pixel asset studio for Godot games. Kiripix turns generated or imported images, 2D frames and 3D Models into
consistent, game-ready pixel art: rooms with Layers, Masks, Looks and Loops; props and icons; dialogue portraits; and
animated characters, sprites, Wearables and background NPCs. It enforces one palette and one resolution per game. You can
drive it from the terminal, and an AI coding agent can drive it just as well.

> **Status: Milestone 6 (rooms at chapter scale, style that holds, NPCs from bases) is mostly built.** M0 to M5 are
> done. M6 added the review queue, districts, `to-paint` and `inbox`, style references, room normal maps, named Masks,
> sprite effects, the `npc` Kind, and generation through Providers (OpenAI's GPT Image for rooms, Props and portraits;
> PixelLab for sprites), with approval, a budget and a cost ledger. The UI's style and NPC screens are still open, and
> the Owner's gate ([backlog/m6/0338](backlog/m6/0338-m6-gate.md)) comes after them. See
> [What's not built yet](#whats-not-built-yet). Everything else here describes what Kiripix does now.

- [Install](#install)
- [Quick start: a room](#quick-start-a-room)
- [Larger rooms, areas, Looks and Loops](#larger-rooms-areas-looks-and-loops)
- [Many rooms at once](#many-rooms-at-once)
- [Generation](#generation)
- [Props, icons and portraits](#props-icons-and-portraits)
- [Characters, Wearables and NPCs](#characters-wearables-and-npcs)
- [Sprites and effects](#sprites-and-effects)
- [Style that holds](#style-that-holds)
- [How Kiripix thinks](#how-kiripix-thinks)
- [Command reference](#command-reference)
- [Output, findings and exit codes](#output-findings-and-exit-codes)
- [A Project on disk](#a-project-on-disk)
- [What's not built yet](#whats-not-built-yet)
- [Further reading](#further-reading)

## Install

Kiripix needs Python 3.12 and [uv](https://docs.astral.sh/uv/). Binaries in a Project (PNG, GLB, FBX) are meant for
[git LFS](https://git-lfs.com/). Exports target Godot 4.7. Characters and Wearables need [Blender](https://www.blender.org/)
5.2 LTS for headless renders; sprites don't (see [docs/versions.md](docs/versions.md)).

```
git clone <this repo> kiripix
cd kiripix
uv sync
uv run kiripix --help
```

The command is `kiripix`, with the short alias `kpx`. From inside the repo, prefix it with `uv run`. To use it from
your game's asset folder, either activate the virtualenv (`.venv\Scripts\activate` on Windows,
`source .venv/bin/activate` elsewhere) or call `.venv/Scripts/kiripix.exe` directly.

`uv sync` also installs CUDA's libraries for ONNX Runtime (about 1.1 GB), so the Runners (SAM 2, LaMa, BiRefNet,
Depth Anything V2) can use an NVIDIA GPU. `uv sync --no-group cuda` leaves them out, and the Runners then use the CPU.

Kiripix finds Blender on `PATH`, or at `[character] blender = "..."` in `kiripix.toml`.

Generation is optional. To use it, put a Provider's key in the Project's `.env` file (`OPENAI_API_KEY`,
`PIXELLAB_API_KEY`). `init` keeps `.env` out of git, and Kiripix never reads the key from `kiripix.toml` or the
environment.

The web UI is a separate build. It needs [Node](https://nodejs.org/) 22 or later; `kiripix` itself doesn't:

```
cd web
npm ci
npm run build
```

Then run `kiripix ui` from inside a Project. It serves the UI and opens your browser with the session token that lets
the UI accept reviews. A wheel made with `uv build --wheel` includes the built UI.

## Quick start: a room

This walks one room from an image you painted or generated elsewhere. Every step prints what to do next, so you rarely
need to remember a command.

**1. Create a Project** (one per game) and look at what it can make.

```
kiripix init my-game-assets
cd my-game-assets
kiripix describe project        # the Kinds and their Recipes, the ramp table and the clip table
kiripix describe room           # each room Stage: parameters, Decisions, Checks
```

Edit `kiripix.toml` to set your game's internal resolution, tile size, Body and Godot export target. Replace
`style/palette.gpl` with your palette (`kiripix palette` lists the colours as the Stages read them).

**2. Create an Asset.** Asset IDs are `<kind>.<name>`, with lower-case letters, digits and underscores.

```
kiripix new room queen_west_alley --view top
kiripix status
```

**3. Ask what's next, and do it.** `next` always answers with either a command to run or something only you can do.

```
kiripix next room.queen_west_alley
# room.queen_west_alley brief is todo; run: kiripix run room.queen_west_alley

kiripix run room.queen_west_alley
# room.queen_west_alley brief: done in 0.02s
# room.queen_west_alley source: needs-input: no Source picked
# error stage.needs_input: room.queen_west_alley source: needs-input: no Source picked
#   fix: kiripix import room.queen_west_alley <file>
```

A new room's brief is 640x368: 23 rows of 16 px tiles, which fills a 640x360 screen. To change it, use
`kiripix set room.queen_west_alley brief width=... height=...`. The brief also takes `mood`, `exits` and `notes`. If the
Project has a room prompt template (`style/prompts/room.j2`; [docs/examples/room-prompt.j2](docs/examples/room-prompt.j2)
is a start), the brief renders the room's image-model prompt from them and the style bible.

Failures come with a `fix:` line, the exact command that fixes them. Here, it's the next step.

**4. Bring in the art and pick it.** `import` adds a PNG or JPEG as a Variant, named by its hash, and `pick` makes it the
Source. `kiripix gen` can paint the Variant instead ([Generation](#generation)).

```
kiripix import room.queen_west_alley ~/art/alley.png
# added the Variant ec428e583c7b2e09 ...; pick it with kiripix pick room.queen_west_alley ec428e583c7b2e09

kiripix pick room.queen_west_alley ec428e583c7b2e09
kiripix run room.queen_west_alley
```

**5. Tune, look and check.**

```
kiripix set room.queen_west_alley fit mode=downscale scale=2
kiripix run room.queen_west_alley        # rebuilds only what the change made stale
kiripix preview room.queen_west_alley    # writes .kiripix/previews/<asset>.<stage>.x4.png, prints the path
kiripix check room.queen_west_alley
```

**6. Lift Layers, paint Masks, place Markers.** These Stages take clicks, brushes and polygons, which are easiest in
the UI (`kiripix ui`). From the terminal, each one is a Decision (`kiripix decide`). The Probes answer "what would this
click do?" without recording anything: `kiripix probe segment-preview room.queen_west_alley 120,200`. You can bring in a
painted Mask or Plate whole with `mask-import` or `plate-import`.

**7. Export.** When every Stage is `done`, `kiripix export room.queen_west_alley` writes these into your Godot project:
the scene, the Plate, the foreground Layers, collision, Markers, the Masks as 1-bit PNGs (`solid`, `pit` and any named
ones), the normal map if the room has one, and `room.json` (the same data for the game's own code). It records them all in
the Manifest.

Changed your mind? `kiripix undo room.queen_west_alley source` takes back the last Decision on a Stage, and `redo`
brings it back. Nothing is ever deleted from the Decision journal.

## Larger rooms, areas, Looks and Loops

**A room larger than one screen** is grown from its picked Source with `extend`, one piece at a time, before the
`source` Stage. Kiripix writes the canvas for the next piece: the image's edge plus empty space, at
`[extend] canvas` in `kiripix.toml`. An image model paints the piece, either in its own UI or through
`kiripix gen <room> --side east`. Kiripix then joins the piece back on: it undoes the model's slight rescale, matches its
brightness and cuts the seam along the least difference.

```
kiripix extend room.harbour canvas --side east           # writes the canvas and prints its path
kiripix extend room.harbour add ~/art/harbour_east.png   # joins the painted piece
kiripix extend room.harbour canvas --side east,south     # a corner piece joins two edges at once
kiripix extend room.harbour add ~/art/harbour_se.png
kiripix extend room.harbour done                         # the joined image becomes a Variant to pick
```

`extend ... undo` drops the last piece. `--keep` sets how much of the image the canvas keeps along the join: one number,
or `across,down` for a corner. `--offset` sets where along the edge it starts. `add` refuses a piece whose registration
misses by more than `[extend] max_residual` (0.5 px). A model that re-renders the kept strip (GPT Image) needs up to
1.0 px; `add` then warns `extend.strip_repainted`, so you look at the seam. The join's three steps are also Ops of their
own: `op register-piece`, `op match-tone` and `op seam-join`.

**An area** is a box Marker on `place`, with any ID. The game decides what it is for, such as a battle area, an escape
route or an Exit's trigger box. It can snap to a cell grid, and `walkable` asks `place` and `reach` to check that it holds
walkable ground the Body can get to. It exports as an `Area2D` with its metadata. `kiripix area-settle <room> <area>`
settles the cells that `solid` or `pit` half covers, by majority.

```
kiripix decide room.harbour place --decision '{"decision": "marker", "data": {"id": "battle.dock", "type": "area", "x": 64, "y": 96, "x2": 351, "y2": 255, "cell": 32, "walkable": true}}'
```

**A Link** is a Marker with two ends in one room, where an actor crosses by a scripted move (a hop, a climb). `reach`
counts it. **An Exit** can be `one_way`, so Exit pairing doesn't expect a way back.

**A Look** is another appearance of part of a room: a door shut, a lamp unlit. Declare it on the `looks` Stage (a `look`
Decision, with an optional Condition label). Bring in an edit of the room's Source with `import --look <look>` (or
`gen --look`), `pick --look` it, and draw its region. Kiripix registers the edit to the Source, fits and maps it as it did
the room, and reports drift outside the region. It exports the Look hidden, for the game to show by its ID. A Look may
have its own `solid`, its own Markers and its own `reach`, and two Looks may show at once (ADR 0013).

**A Loop** is a part of a room that plays by itself, over and over, on the `loops` Stage. It can be a colour cycle
(palette colours stepping through a list, or up and down their ramps). It can also be frames: made by an Op from the
room's own pixels (`sway`, `shimmer`, `scroll`), painted on a kit (`kiripix loop kit`, then `import --loop`), or picked
from image-model edits (`import --loop <loop> --frame <n>`, then `pick`). Frame 0 is always the room, timing is in whole
game ticks, and the game plays the Loop from its own frame counter. Emitter Markers also carry a shape, a direction and
palette colours for the game's particles.

**Normal maps** for a painted room come from the `normals` Stage, between `masks` and `palette` (ADR 0014). It is off by
default. Turned on, it estimates depth with Depth Anything V2 and turns it into normals, so Godot's 2D lights can shade
the room. `preview --overlay lit` shows the room lit from a corner, so you can judge the normals without Godot.

**Named Masks** beyond `solid` and `pit` (`kiripix masks-add cover --colour "#FF00FF" --meaning "half cover"`) are
painted like any Mask and exported for the game's grid. Kiripix attaches no meaning to them.

The UI has a screen for each of these. The place screen draws areas, Links and emitters, and the looks and loops screens
have a live preview.

## Many rooms at once

A **District** is the set of Assets an ID glob matches, such as `room.ch01_dungeon_*`. `status`, `check`, `run`,
`export`, `queue` and `stats` take it as `--match <glob>`. Nothing about it is stored.

```
kiripix district "room.ch01_dungeon_*"           # each room's size, furthest Stage, queue counts, Exits and Links
kiripix to-paint --match "room.ch01_dungeon_*"   # a folder of prompts and extend canvases for the rooms waiting on art
kiripix inbox                                    # files the images that came back, by their file names
kiripix run --match "room.ch01_dungeon_*"
kiripix queue --match "room.ch01_dungeon_*"      # everything waiting on the Owner, in one list
```

- **`to-paint` and `inbox`.** `to-paint` writes each waiting room's prompt and, for a room mid-`extend`, its next
  canvas, with an `index.md` naming the file each image should come back as. You paint them in the image model, then drop
  the results in `inbox/`. `inbox` imports `<room>.png` as a Variant and joins `<room>.<side>.png` with `extend add`. It
  never picks.
- **First passes without the Owner.** The [room-first-pass skill](skills/room-first-pass/SKILL.md) takes an agent
  through a room from brief to export. Its `batch.py` runs it over many rooms, one Claude Code session per room. Each room
  stops where it needs you, and the agent leaves a **hand-over note** (`kiripix note <asset> <stage> "..."`) saying why
  it stopped and what's left.
- **The review queue.** `kiripix queue` lists every stop you own across the Assets: each `needs-review` Stage, each
  owner-only `needs-input` and each finding with an `owner_action`, with the Stage's live hand-over notes. In the UI it
  is one keyboard flow, so you can approve many rooms' first passes in one sitting. The UI also has a district view.

## Generation

`kiripix gen` paints through a **Provider**. Every image it brings back is a Variant, like an imported one. `gen` never
picks or joins.

| Provider | Paints |
|---|---|
| `openai` (GPT Image) | A room's Source from its brief's prompt, a Prop's or portrait's Source (`--prompt`), a Look's edit (`--look`), a Prop's state (`--state`), a portrait's emotion (`--emotion`), and the next `extend` piece (`--side`). |
| `pixellab` | Sprites only: a character from text or from its own frames, a state (pose) of it, and clips moved by PixelLab's rig or by a character's render (`--motion rig\|skeleton`). Each is stored as a sheet for `frames`. |

```
kiripix gen room.harbour -n 2                     # two candidates from the brief's prompt
kiripix gen room.harbour --look door_shut --prompt "the door is shut"
kiripix gen room.harbour --side east --prompt "the quay continues, with moored boats"
kiripix gen sprite.pigeon --clip peck --motion rig --prompt "pecks at the ground"
```

Spending is guarded in `[providers]` in `kiripix.toml`. Before it sends a call, `gen` states the estimate and the
month's budget. It refuses a call that would go past `budget_usd_month`, `max_images_per_call` or `max_calls_per_day`.
With `approve = "each"` (the default), `gen` only writes a pending call and exits 3. You send it with
`kiripix approve <id>`, which is owner-only, or drop it with `kiripix reject <id>`. `kiripix cost` reads the cost
ledger: spend by month and Provider, and what's left this month.

## Props, icons and portraits

**A Prop** works like a room: `kiripix new prop bench`, then `import` (or `gen`), `pick` and `run`. Its `cutout` Stage
removes a flat chroma background, or mattes the object out with BiRefNet. `footprint` sets the base's collision and the
y-sort origin, and `export` writes a `Sprite2D` scene. A Prop can have **States**, such as a bin standing and toppled.
Each State has its own ID, size, image (`import --state`, `pick --state`), cutout, footprint and origin, and shares the
Prop's scale and palette.

**An icon** (`kiripix new icon key`) is an item or skill icon at a fixed square size of 16, 24 or 32 px (`[icon] size`).
It is a Prop without a footprint or an origin.

**A portrait** (`kiripix new portrait hero`) holds one character's set of dialogue portraits: a neutral image and an
**Emotion** for each mood. Each Emotion is an edit of the neutral image (`import --emotion`, `pick --emotion`, or
`gen --emotion`). `register` puts every image on one canvas with one anchor, so swapping an emotion never moves the body.
The set gets one fit and its own colours.

## Characters, Wearables and NPCs

**A character** starts from a 3D Model instead of an image:

```
kiripix new character courier
kiripix import character.courier ~/models/courier.fbx                 # a Variant to pick
kiripix import character.courier ~/mixamo/courier_rigged.fbx --role rigged
kiripix import character.courier ~/mixamo/walking.fbx --role clip-source
kiripix decide character.courier clips --decision '{"decision": "clip", "data": {"name": "walk", "source": "walking", "start": 0, "end": 24, "fps": 12, "loop": true}}'
kiripix run character.courier
```

`rig` checks a humanoid rig, or walks you through the Mixamo round trip; `next` tells you which file to bring back.
`render` runs Blender headless with an orthographic camera preset from `kiripix.toml` (top-down 3/4, 8 directions by
default) at the target pixel height, with toon shading. It also records named points per frame, such as a hand or the
head. `palette` gives the character one palette across all its frames. `finish` draws a 1 px outline in a palette colour
and lines the normal map up with the colour frames. `sheet` packs both into atlases with the feet at a fixed pivot.
`kiripix export` writes:

- a `SpriteFrames`;
- a `CanvasTexture` with the normal map;
- an `AnimatedSprite2D` scene whose animations are `<clip>_<dir>`, such as `walk_sw`;
- `character.json` beside the scene, with each clip's foot frames and each frame's points.

`kiripix describe character` lists every clip field and Check.

More for characters:

- **Clips.** Deciding a clip again under its name changes its range and keeps its animation names. A clip can play
  faster (`speed`), hold one pose (`still`) and name its `blink` frames. A `transition` Decision blends one clip's pose
  into another's. `kiripix clips copy` copies clip Decisions from another character.
- **The clip table.** `[[character.clips]]` in `kiripix.toml`, filled with `kiripix clips-add`, fixes a clip's frame
  count, fps, loop and foot frames on every body, so they all play one timing.
- **Held things.** `import --role thing --thing phone` adds a mesh that a clip's `attach` puts in a hand; its origin and
  axes are the grip. `thing-remove` takes it out.
- **Parts and ramps.** With `palette` `parts` set, each swappable part (one or more Blender materials) gets its own ramp
  of palette colours. The ramps are exported in `character.json` and as `ramps.png`, so the game can recolour skin or
  hair with a shader. The Project's ramp table (`[[character.ramps]]`, filled with `kiripix ramps-add`, owner-only)
  makes a part the same row and length on every character, and can name colour `choices` for NPCs.
- **A flatter look.** `render`'s `band_edge` and `band_smooth`, and `finish`'s `inner_lines` and `line_darkness`.
  `inner_lines` includes depth steps inside one material, where a part crosses itself. Stamped eyes (`finish`
  `eyes=stamp`) stay crisp and blink.
- **Bases.** `kiripix new character guard --base character.body_m` makes a character on another's skeleton. It needs no
  rigged file, gets the base's clips, and takes the base's parameters where it sets none (ADR 0012).
- **Generated Models.** A Project may name its own Blender generator under `[character.generators]`.
  `kiripix new character <name> --from-parameters <file>` builds the Model from a parameter file.
- **Comparing a cast.** `kiripix cast-sheet character.hero,character.elder` draws several characters side by side on
  one ground line, to compare their sizes. `kiripix snapshot --label outline character.hero,...` keeps their built sheets
  under a label, and `cast-sheet --snapshots` lays settings side by side. `set` takes several Assets at once.

**A Wearable** (`kiripix new wearable hair_bob --body character.body_f`) is a hair style, an outfit or an accessory with
its own Model on the body's skeleton. It is rendered once over the body, with the body as a holdout, on the body's clips,
camera and cell, so the game stacks it on the body pixel for pixel. No combination is ever rendered.

**An NPC** (`kiripix new npc walker --base character.body_m`) is a background figure that is a choice, not a render: a
base, some Wearables worn on it and a named colour choice per part (ADR 0015). Its `choose` Stage holds the choice, and
the game draws it from the base's and the Wearables' exports. `--count 20 --seed 7` makes a crowd whose every member
passes the NPC Checks, and `--reroll` picks one again.

## Sprites and effects

**A sprite** is an actor made from 2D frames, such as a PixelLab export. It is exported exactly as a character is, so
the game loads both with the same code:

```
kiripix new sprite raccoon
kiripix import sprite.raccoon ~/pixellab/raccoon.zip      # a PNG sheet or a ZIP of PNGs
kiripix run sprite.raccoon
```

`frames` cuts the sheets into clips and directions. A missing direction is an error and is never mirrored. `fit` puts
each frame on the target grid and finds the feet for the pivot. `palette`, `finish` (normals from height, or flat),
`sheet` and `export` work as they do for a character. With PixelLab's key in `.env`, `kiripix gen sprite.<name>` paints
the character and its clips straight into the sprite ([Generation](#generation)).

**A battle effect**, such as a hit spark or a summon puff, is a sprite with effect parameters: an anchor, an exact cell,
no figure rules, a blank last frame and ticks per clip. Its export carries the effect's blend and light mode.
`kiripix op dither-alpha` turns a soft glow's partial alpha into an ordered-dither pattern.

## Style that holds

3D characters, painted rooms and imported sprites must look like one game. The Owner names some Assets as **style
references** with `kiripix style-add <asset>` (owner-only). After that, `check` measures every other Asset of a Kind
with style Checks (character, sprite, wearable, room, prop) against them: outline density and pixel scale, among others.
`kiripix probe style <asset>` shows the measures. `check --all` also reports any character whose camera preset's
`light_angle` differs from the others (`style.light_angle_differs`).

## How Kiripix thinks

The words below are used exactly this way in every command, message and finding. The full list is in
[GLOSSARY.md](GLOSSARY.md).

| Word | Meaning |
|---|---|
| **Project** | One game's asset workspace: palette, resolution, tile size, style bible, Mask definitions, export target. |
| **Asset** | One thing in the game, with a Kind and a stable ID such as `room.queen_west_alley`. |
| **District** | The Assets an ID glob matches, given as `--match`; nothing about it is stored. |
| **Kind** | `room`, `prop`, `icon`, `portrait`, `character`, `wearable`, `npc` or `sprite`. The Kind fixes the Recipe. |
| **Recipe** / **Stage** | A Kind's ordered list of Stages. Each Stage has inputs, parameters, outputs and Checks. |
| **Variant** / **Source** | A candidate image or Model (imported or generated); the one you Pick becomes the Source. |
| **Decision** | Recorded human input a Stage replays: a Pick, clicks, an Override, Marker positions, a clip. |
| **Override** | A hand edit painted over a Stage's image, recorded and re-applied every time the Stage runs. |
| **Hand-over note** / **Review queue** | A note on a Stage saying why a pass stopped / every stop the Owner owns, across the Assets. |
| **Mask** / **Layer** | A binary gameplay region (`solid`, `pit`, or a named one) / a visible image plane (the Plate, foreground Layers). |
| **Marker** / **Area** / **Link** | A placed point, line or box with a stable ID (Exit, Spawn, light, emitter, y-sort line) / a box Marker the game gives a meaning / a Marker with two ends where an actor crosses by a scripted move. |
| **Look** / **Loop** | Another appearance of part of a room, shown by the game / a part of a room that plays by itself, over and over. |
| **State** / **Emotion** | Another form of a Prop / another mood of a portrait, each an edit of the Source. |
| **Piece** / **Join** | An image painted from a room's edge to extend it / putting it on the room: register, match tone, seam. |
| **Part** / **Ramp** | A swappable piece of a character's look / the palette colours it gets, so the game can recolour it. |
| **Wearable** / **NPC** | A part of dress rendered once over a body / a background figure that is a choice of base, Wearables and colours. |
| **Runner** | A local ML model (SAM 2, LaMa, BiRefNet, Depth Anything V2) whose results are pinned, so a rebuild replays them exactly. |
| **Provider** | An image generator behind one interface (GPT Image, PixelLab), behind a budget and the Owner's approval. |
| **Check** | A pass/fail verification with located findings. |
| **Op** | A pure image function (quantise, flood fill), reachable directly through `kiripix op`. |
| **Probe** | A read-only question about an Asset ("what would this click segment?"); it records nothing. |
| **Owner** | You. The one person whose Decisions and acceptances count as human judgement. An agent never is. |

**Recipes today:**

```
room:      brief -> source -> fit -> layers -> masks -> normals -> palette -> looks -> loops -> place -> reach -> export
prop:      brief -> source -> cutout -> fit -> palette -> finish -> footprint -> export
icon:      brief -> source -> cutout -> fit -> palette -> finish -> export
portrait:  brief -> source -> cutout -> register -> fit -> palette -> finish -> export
character: model -> rig -> clips -> render -> palette -> finish -> sheet -> export
wearable:  model -> rig -> render -> palette -> finish -> sheet -> export
npc:       choose -> export
sprite:    frames -> fit -> palette -> finish -> sheet -> export
```

**Non-destructive.** A Stage's output is a pure function of its inputs, parameters, Decisions and pinned results.
Change something upstream (a parameter, the palette, a Pick) and everything below it becomes `stale` and rebuilds on
the next `run`. A change to a Stage's own code makes it stale too. Never edit a generated file by hand: record an
Override instead.

**Status is derived, never stored.** Kiripix works out each Stage's status from the hashes of its inputs every time
you ask:

| Status | Meaning | What to do |
|---|---|---|
| `todo` | Never produced output. | `kiripix run <asset>` |
| `stale` | An input changed since the output was built. | `kiripix run <asset>` |
| `needs-input` | Waiting for a Decision from you (for example, no Source picked). The reason is shown. | `kiripix next <asset>` says what. |
| `needs-review` | Rebuilt by replaying your Decisions onto changed input; you need to confirm it. | Look at a `preview`, then `kiripix accept <asset> <stage>`. |
| `done` | The output matches its inputs. | Nothing. |
| `failed` | The last run failed. Kept only in the local cache. | Read the findings, fix, `run` again. |

`run` goes through Stages in order and stops at the first one that is `needs-input`, `needs-review` or `failed`.
Long work (a Runner call, a render) can be cancelled, and a cancel leaves nothing half-written.

## Command reference

Every command has `--help`, and that help is always current. Three commands describe Kiripix to itself:
`describe` (Kinds, Stages, parameters, Decisions, Checks), `schema` (the JSON Schema of every command) and `next`
(what to do now).

Options most commands take: `--json` (print one JSON object) and `--progress jsonl` (stream progress events on stderr).
Commands that write also take `--wait <seconds>`, which waits for a lock another process holds instead of failing at
once. `status`, `run`, `check`, `export`, `queue` and `stats` take `--match <glob>` for a District.

### Project

| Command | What it does |
|---|---|
| `kiripix init [DIR]` | Create a Project in `DIR` (default `.`): `kiripix.toml`, `style/` (palette, style bible, refs, prompts), `assets/`, `.gitattributes`, `.gitignore`. |
| `kiripix describe project` | List every Kind with its Recipe, and the Project's ramp and clip tables. |
| `kiripix describe <kind> [--stage S]` | Every Stage of a Kind, or one: parameters with types and defaults, the Decisions it accepts, and its Checks. |
| `kiripix schema [COMMAND]` | JSON Schemas of command inputs and outputs, for one command (`schema run`, `schema "op quantize"`) or all. |
| `kiripix status [--kind K] [--match G]` | Every Asset and the status of each of its Stages, with the reason where there is one. |
| `kiripix assets [--kind K] [--match G]` | The Assets from their `asset.toml` alone (ID, Kind, base, body, style reference), with no status, so it answers at once. |
| `kiripix show <asset>` | One Asset: its Variants and Pick, and each Stage's status, current parameters, Decisions and files. |
| `kiripix queue [--match G] [--kind K]` | The review queue: every stop the Owner owns, with hand-over notes. |
| `kiripix district <glob>` | A Probe: a District's rooms with their sizes, furthest Stage, queue counts and thumbnails, every Exit's pairing and the Links. |
| `kiripix palette` | The Project palette: its file and every colour, in file order, as the Stages read it. |
| `kiripix palette-add <proposal>` | **Owner-only.** Append the colours from an `op palette-suggest` proposal to the Project's palette. |
| `kiripix ramps-add <character> --parts a,b [--colours] [--dry-run]` | **Owner-only.** Append parts of a character's built palette to the Project's ramp table, optionally with their colours. |
| `kiripix clips-add <character> --clips a,b [--foot a] [--dry-run]` | Append a character's decided clips to the Project's clip table. |
| `kiripix masks-add <name> --colour C --meaning M [--view top\|side]` | Add a named painted Mask to the Project, for the game to read. |
| `kiripix style-add <asset>` / `style-remove <asset>` | **Owner-only.** Make an Asset a style reference, or take it out. |
| `kiripix stats <asset>\|--all [--since DATE]` | Your measured active minutes per Asset and Stage (the UI logs them), with the Decisions, undos and redos. |
| `kiripix track <asset> <stage> --seconds N` | **Owner-only.** Log a span of active time; the UI sends these. |

### Assets and Stages

| Command | What it does |
|---|---|
| `kiripix new <kind> <name> [--view top\|side] [--base B] [--body B] [--from-parameters F]` | Create an Asset from its Kind's Recipe. A room needs `--view`, and other Kinds refuse it. A character can be made on a base, or from a parameter file for the Project's generator. A Wearable needs `--body`, and an NPC needs `--base`. |
| `kiripix new npc <prefix> --base B --count N --seed S` / `--reroll` | Make a crowd of NPCs that pass the NPC Checks, or pick one NPC's choice again. |
| `kiripix next <asset>` | The next Stage of an Asset and what it needs: a command to run, or an action only you can take. |
| `kiripix run <asset> [STAGE] [--force [--from S]] [--rerun] [--cpu]` | Run stale and todo Stages in order. With `STAGE`, run only that Stage (its upstream must be done). `--force` re-runs `done` Stages too, and `--from` re-runs a Stage and everything after it. `run` never calls a Runner on its own: `--rerun` makes the Runner calls with no pinned result, which land in `needs-review`, and `--cpu` runs them on the CPU without the GPU lock. |
| `kiripix run --all [--kind K] [--match G]` | Run every Asset, locking one at a time. A base character is built before the characters made from it. |
| `kiripix set <asset> <stage> key=value ...` | Set Stage parameters. Values are checked against the Stage's declared parameters (`describe <kind>` lists them). |
| `kiripix note <asset> <stage> "<text>"` | Write a hand-over note: why a pass stopped and what is left. It isn't a Decision. |
| `kiripix check <asset>` / `--all` / `--match G` | Run the Checks of every built Stage and list the findings, including which Stages are out of date. `--all` adds the Project checks (those across Assets, such as Exit pairing and matching part ramps). |
| `kiripix preview <asset> [--stage S] [--zoom N] [--overlay masks\|walkable\|reachable\|layers\|lit] [--layer L] [--region x,y,w,h] [--grid N] [--brighten F]` | Write a Stage's image to `.kiripix/previews/` at a whole-number zoom (default 4, nearest neighbour) and print its path. Defaults to the last done Stage with an image. |
| `kiripix probe <name> <asset> [ARGS]` | A read-only question that records nothing: `segment-preview` (clicks or a box), `click-preview`, `flood-preview`, `look-difference`, `layer-stats`, `reach`, `style`, `half-cells`, `inspect <file>`. The Runner-backed ones are fast only through `kiripix serve`, which keeps the Runners warm. |
| `kiripix area-settle <room> <area> [--dry-run]` | Settle an area's half-covered cells by majority, as `masks` Decisions. |
| `kiripix cast-sheet <asset,...> [--clips C] [--directions D] [--frames N] [--scale N] [--snapshots]` | A Probe: several characters or sprites side by side, each at its pivot on one ground line, to `.kiripix/previews/`. |
| `kiripix snapshot <asset,...> --label L` / `--list` / `--drop L` | Keep characters' or sprites' built sheets under a label, for `cast-sheet --snapshots`. |
| `kiripix runners list\|pull <runner>\|rm <runner>` | The local Runners: licence, weights hash and size. `pull` downloads their weights now rather than on first use, and `rm` deletes them. |

### Sources

| Command | What it does |
|---|---|
| `kiripix import <asset> <file> [--role ...]` | Add a file made elsewhere, as a Variant named by its hash: a room's, Prop's, icon's or portrait's PNG or JPEG, or a character's or Wearable's `.glb`, `.fbx` or `.blend`. For a character, `--role clip-source` adds an animation file, `--role rigged` the rigged file back from Mixamo, `--role parameters` a parameter file and `--role thing --thing ID` a held mesh. For a sprite, `--role sheet` (its default) adds a PNG sheet or a ZIP of PNGs. Prints the next command. |
| `kiripix import <asset> <file> --look L \| --state S \| --emotion E` | Add an edit of the Source as a Variant of a room's Look, a Prop's State or a portrait's Emotion. |
| `kiripix import <room> <files...> --loop L [--kit kit.json]` / `--loop L --frame N` | Import a frame Loop's painted kit frames, or an edit of the Source as frame `N`. |
| `kiripix pick <asset> <variant> [--look L \| --state S \| --emotion E \| --loop L --frame N]` | Pick a Variant as the Source, or as a Look's, State's, Emotion's or Loop frame's image (records a Pick Decision). `next` lists the Variants. |
| `kiripix extend <room> canvas\|add <png>\|undo\|done [--side S] [--keep N\|A,D] [--offset N] [--max-residual PX]` | Grow a room's Source past its edge, one piece at a time: write the canvas for the next piece, join a painted piece, drop the last one, or import the joined image as a Variant. |
| `kiripix to-paint --match G [--out DIR]` | Write a District's prompts and `extend` canvases into one folder, with an `index.md` of the file names `inbox` expects. |
| `kiripix inbox [--folder DIR] [--dry-run]` / `--file F --asset A [--sides S]` | File images made elsewhere by their file names: import a Variant, or join an `extend` piece. Never picks. |
| `kiripix loop kit <room> <loop> <folder> [--frames N]` | Write a frame Loop's kit to paint on: frame 0 (the room inside the Loop's region), copies of it, the palette and a README. |
| `kiripix clips copy <character> --from <character> [--clip C] [--replace]` | Copy another character's clips as `clip` Decisions, with the clip sources they name. |
| `kiripix thing-remove <character> <thing>` | Remove a held thing and all its Variants. |

### Generation

| Command | What it does |
|---|---|
| `kiripix gen <asset> [-n N] [--provider P] [--prompt T] [--look L \| --state S \| --emotion E \| --side S]` | Paint Variants through a Provider. States the estimate and the budget first, and refuses past a limit. For a sprite's options (`--clip`, `--motion`, `--from-frames`, `--render`, `--preview`), see `gen --help`. |
| `kiripix approve <id>` / `--list` | **Owner-only.** Send a pending call `gen` wrote, after checking the budget and inputs again; or list them. |
| `kiripix reject <id>` | Delete a pending call without sending it. |
| `kiripix cost [--month] [--since T]` | The spend on Providers from the cost ledger: by month and Provider, and this month's budget and what's left. |

### Decisions

Every Decision goes into the Stage's append-only journal, `decisions/<stage>.jsonl`.

| Command | What it does |
|---|---|
| `kiripix decide <asset> <stage> --decision '<json>'` | Record a Decision, validated against the Stage's Decision schema. The JSON is `{"decision": "<name>", "data": {...}}`, and `describe <kind>` lists each Stage's Decision names. Use `--file d.json` instead of `--decision` for long input. A file may hold a JSON array of Decisions, which are recorded all or none. |
| `kiripix mask-import <asset> <painted.png>` | Record a room's Masks from a painted image, in the Mask colours `describe room` lists. |
| `kiripix plate-import <asset> <plate.png>` | Record a Plate you painted or inpainted elsewhere for the `layers` Stage. |
| `kiripix override <asset> <stage> <painted.png>` | Record an Override: a PNG the same size as the Stage's image, painted over it on every run. If the Stage's own image later changes, the Stage goes to `needs-review`. |
| `kiripix undo <asset> <stage>` | Undo the Stage's latest current Decision. It appends an undo entry; nothing is removed. |
| `kiripix redo <asset> <stage>` | Redo the latest undone Decision. |
| `kiripix accept <asset> <stage>` | **Owner-only.** Confirm a `needs-review` Stage: re-record its Decisions against the current image so the next replay is exact. It refuses unless stdin is an interactive terminal (or the UI's session token), so an agent can't accept its own work. |

### Export

| Command | What it does |
|---|---|
| `kiripix export <asset>` | Write a fully built Asset into the Godot project at `export.godot.project`: its scene, images and Manifest entries, plus a room's Masks, normal map and `room.json`, or a character's or sprite's `character.json`. A single room only warns about Exit pairing. |
| `kiripix export --all` / `--match G` | Export every Asset (or a District's), or none: Exit pairing must hold and no file may be refused. |
| `--force` / `--adopt` | Back up and overwrite a file the game changed since it was exported / a file at a target path the Manifest doesn't list. Without them, export refuses both. |
| `--prune` | Remove the files of Assets deleted from the Project, under the same rule. |
| `--dry-run` | Write nothing; list what would be written, removed or refused. |
| `kiripix manifest install\|merge\|repair` | Install the Manifest's git merge driver in the game's clone, run it, or repair a Manifest committed with conflict markers. |

### Ops

Ops run one image function directly, outside any Asset. They use the Project's palette unless you pass `--palette`.

| Command | What it does |
|---|---|
| `kiripix op quantize <in.png> <out.png> [--palette P] [--dither none\|bayer2\|bayer4\|bayer8] [--strength 0..1]` | Map an image to the palette in OKLab, strictly or with ordered dithering. |
| `kiripix op conformance <image.png> [--palette P]` | Report pixels off the palette and partially transparent pixels. Exits 2 if there are any. |
| `kiripix op dither-alpha <in.png> <out.png> [--pattern bayer2\|bayer4\|bayer8]` | Turn partial alpha into a fixed ordered-dither pattern of opaque and clear pixels (a glow's haze). |
| `kiripix op palette-suggest <image.png> --add N` | Suggest up to N colours the palette lacks for an image, as a proposal file for `palette-add`. Changes nothing. |
| `kiripix op register-piece` / `match-tone` / `seam-join` | The three steps of `extend`'s join, one at a time, for trying a piece by hand. |

Palettes can be GIMP `.gpl` or `.hex` files.

### The UI

| Command | What it does |
|---|---|
| `kiripix serve` | Serve the REST API and the web UI for this Project on `127.0.0.1`. Keep it local: there is no login. |
| `kiripix ui` | Serve, and open the browser with the session token. |

The UI has:

- the status board, the review queue and the district view;
- a screen per Stage: the Variant grid, the before/after view, Layers, Masks with segment, flood, brush and polygon
  tools, normals, looks and loops with a live preview, place with areas, Links and emitter shapes, footprint, a
  character's model, rig and clips screens with points, and a sprite's import, frame strip and pivot;
- progress for long work;
- the walk test: a stand-in Body walking the room on its real collision.

It logs your active time per Stage for `kiripix stats`.

## Output, findings and exit codes

By default commands print readable text: results on stdout, findings on stderr. With `--json`, a command prints
exactly one object on stdout, always shaped the same way:

```json
{
  "api_version": 1,
  "ok": true,
  "data": { "asset": "room.queen_west_alley", "stage": "brief", "status": "done",
            "command": "kiripix set room.queen_west_alley brief width=640 height=368", "owner_action": null, "...": "..." },
  "findings": []
}
```

Every finding has a stable dotted `code` (such as `palette.off_palette` or `fit.size_mismatch`), a message, and
exactly one remedy: `fix`, a command anyone can run, or `owner_action`, something only you can do.

| Exit code | Meaning |
|---|---|
| 0 | OK |
| 1 | Error (bad input, missing file, ...) |
| 2 | A Check failed |
| 3 | Needs the Owner: a Stage is `needs-input` or `needs-review`, or a Provider call waits for `approve` |
| 4 | Busy: another process holds the lock (the JSON names it); retry, or pass `--wait` |

**Using Kiripix from an AI agent.** Point the agent at `kiripix --help`, `kiripix describe project`,
`kiripix next <asset> --json` and `kiripix check <asset> --json`; they are designed to be all it needs. Exit code 3
means the agent should stop, leave a hand-over note, and report back to you rather than retry. An agent can't run an
owner-only command: `accept`, `approve`, `palette-add`, `ramps-add`, `style-add` and `track`.

## A Project on disk

```
my-game-assets/
  kiripix.toml              Project settings: resolution, tile, palette, Body, Masks, extend, icon, portrait, inbox,
                            style references, characters, ramp and clip tables, Providers and budget, export target
  .env                      Provider keys (git-ignored)
  style/
    palette.gpl             the Project palette
    bible.md                style notes, for prompt templates
    refs/  prompts/         reference images and prompt templates (room.j2 renders a room's prompt)
  inbox/                    images made elsewhere, waiting for `kiripix inbox`
  assets/
    room/queen_west_alley/
      asset.toml            Kind and parameters (never status)
      history.jsonl         append-only log of runs and generations
      imported.jsonl        the file name each src/ file was imported with
      notes.jsonl           hand-over notes
      time.jsonl            your measured active time, for `stats`
      src/                  Variants, named by hash (immutable once picked); looks/, loops/ for edits
      extend/               the pieces and joins of `extend`, with their journal
      decisions/            one Decision journal per Stage (<stage>.jsonl), plus Override PNGs
      pinned/               pinned Runner and Provider results
      work/                 deterministic Stage outputs: a cache, safe to delete
      out/                  final outputs, the exporter's input
    prop/bin/src/states/    a Prop's States
    portrait/hero/src/emotions/
    character/courier/
      src/clips/ src/rigged/ src/parameters/ src/things/   clip sources, the rigged file, a parameter file, held things
    sprite/raccoon/
      src/sheets/           the imported and generated sheets and ZIPs, whole
  .kiripix/                 hash cache, last-run failures, locks, previews, snapshots, pending Provider calls,
                            the cost ledger (cost.jsonl), Runner weights (git-ignored)
```

Commit `kiripix.toml`, `style/` and everything in each Asset's folder except `work/`. Don't commit `.kiripix/` or `.env`.
`init` writes a `.gitignore` and `.gitattributes` that handle this.

## What's not built yet

These are designed in [the spec](docs/KIRIPIX_SPEC.md) but don't exist yet:

- **The rest of M6:** the UI's style scores beside an Asset's references (0335) and its NPC screen (0360), characters
  rendered to match the GPT Image rooms (0382, after the trial 0383), PixelLab's one image to a sprite (0390) and
  keyframe motion for objects (0391). Then the M6 gate (0338).
- **The `tileset` Kind:** a tile kit for the game's procedural dungeon, exported as an atlas and a kit file. Planned, not
  scheduled ([0384](backlog/m6/0384-tileset-kind-for-a-procedural-dungeon.md)).
- **Generation and agents, deferred:** the MCP adapter, the image-to-3D trial (0144) and a trial of local generation as
  a Runner.
- **Later:** side view (side-view Masks `oneway` and `ladder`, the parallax split, platform reachability), "promote to
  Prop" for a room's foreground Layer, renaming exported IDs with aliases, and a `vfx` Kind.

`kiripix describe <kind>` lists the Stages that exist, so it is the quickest way to check.

## Further reading

- [GLOSSARY.md](GLOSSARY.md): the vocabulary.
- [docs/KIRIPIX_SPEC.md](docs/KIRIPIX_SPEC.md): the full design and milestones.
- [docs/adr/](docs/adr/): the decisions behind the design.
- [docs/versions.md](docs/versions.md): the pinned Godot and Blender versions.
- [docs/terminals.md](docs/terminals.md): which terminals `accept` works in.
- [docs/runner-licences.md](docs/runner-licences.md): the Runners' licences.
- [docs/test-speed.md](docs/test-speed.md): how the test suite is kept fast.
- [docs/acceptance/](docs/acceptance/): the agent acceptance test and its recorded runs.
- [docs/examples/room-prompt.j2](docs/examples/room-prompt.j2): a starting room prompt template.
- [CLAUDE.md](CLAUDE.md): rules for contributors and agents working on Kiripix itself.
- [skills/room-first-pass/](skills/room-first-pass/SKILL.md): a Claude Code skill for an agent's first pass on a room,
  from brief to export. To install it in your asset Project, copy the folder to `.claude/skills/room-first-pass/` there.
  The folder's `batch.py` runs the first pass over many rooms, one Claude Code session per room
  (`python .claude/skills/room-first-pass/batch.py --match "room.ch01_*"`); the skill says how.

## License

MIT; see [LICENSE](LICENSE).
