# Kiripix — Pixel Asset Studio

Spec v0.5, 2026-11-08. Status: reviewed with the owner; M0 to M2 are done, M3 is in progress, and M4 is split into tickets in `backlog/m4/`.

The vocabulary is defined in [GLOSSARY.md](../GLOSSARY.md), and the decisions behind this spec are recorded in
[docs/adr/](adr/). Where they disagree with this spec, fix the spec.

## 1. What it is

Kiripix is a local tool that turns generated or imported images, and 3D models, into consistent game-ready pixel art
assets: backgrounds with layers and collision, props, and animated characters. It exports them straight into a Godot
project.

Its first customer is the owner's next game:
- a 2D RPG about Toronto and its urban legends;
- turn-based combat;
- built in Godot;
- top-down exploration, with some side-view scenes;
- a Sea of Stars-like look: colourful painted backgrounds at a limited resolution, many animations, foreground and
  background layers, particles and lighting.

**Name:** "kiri" (切り) is Japanese for "cut", as in kirie (cut-paper pictures) and kirigami. A picture gets cut into
layers, and the layers get stacked back into a scene.

### Goals

1. **Cheaper.** Pixel work moves out of LLM conversations and into deterministic code and direct clicking. A Claude
   session calls one command instead of writing a script every ticket.
2. **Faster.** Most assets go from source to Godot in minutes. The owner's time goes to choosing and clicking. Each
   milestone gate records the time per room, and each milestone looks for what would cut it.
3. **Consistent.** One palette, one resolution and one style bible per project, enforced by checks, not by memory.
4. **Repeatable.** Every asset can be rebuilt from its committed files: sources, recorded decisions and pinned Runner
   and Provider results (ADR 0002).

### Non-goals (for now)

- A general image editor. Aseprite, Krita or Photoshop stay the tools for hand painting, and Kiripix imports from them.
- Animation authoring. Animation comes from 3D (Blender and Mixamo clips) or is imported.
- Cloud hosting or multiple users. Kiripix runs on one machine, for one owner.
- Engines other than Godot. Export stays behind an interface, but only Godot is built.

## 2. Principles (non-negotiables)

1. **Assets and stages, not functions.** The user works on an asset, and the asset's kind gives it a fixed list of
   stages. Ops (the image functions) are reached through stages. `kiripix op` exposes them directly for power use.
2. **Non-destructive.** A stage's output is a pure function of its inputs, its parameters, its recorded human
   decisions (clicks, picks, Overrides) and its pinned Runner and Provider results. A Blender render counts as a function
   of its inputs, the Blender version and render settings among them, though it isn't bit-exact across devices
   (ADR 0010). Change anything upstream, the
   palette for example, and everything below it rebuilds. Nobody edits a generated file by hand. Hand edits are
   Overrides: recorded, and replayed on top.
3. **Built for agents and UIs.** Every operation is a Command, defined once in core and offered identically through
   the CLI, REST and MCP (ADR 0006). An AI coding agent can drive the whole tool from its own output, and any UI
   (the built-in one or another) is built on the same Commands and adds no logic of its own. Nothing is UI-only.
4. **Pure ops, tested.** `ops/` holds pure functions (numpy arrays in, arrays out) with unit tests and golden images.
   No I/O, no global state, no Runner loading inside an op.
5. **Local first.** The core pipeline runs offline. Image APIs are optional Providers. Runners (local ML models) fit
   **8 GB VRAM**, load lazily and one at a time, and unload after use.
6. **Exact palette, binary Masks.** Every exported pixel is a palette colour, and every Mask is a 1-bit image
   (ADR 0001). A check fails on anything else. (Lesson from Lost-and-Found: off-palette mask colours cost several
   rounds.)
7. **Check before export.** Reachability, palette, resolution and layer coverage are verified by code. The UI shows
   failures live while the owner works.
8. **Stable IDs.** Every asset, Layer, Marker and animation clip has a stable string ID, carried into Godot. Once
   exported, an ID is frozen (ADR 0003).
9. **Text on disk.** Project and asset metadata are TOML, JSON or JSON Lines, git-friendly. Binaries are PNG and GLB,
   in git LFS.
10. **Never overwrite the game's own work.** Export writes only files the Manifest says Kiripix owns, and only while
    they are unchanged (ADR 0003). Game logic lives in scenes that instance Kiripix's scenes, never inside them.
11. **Never re-run a Runner or Provider silently.** A rebuild re-runs only deterministic work: Ops, and Blender renders (ADR 0010). Running a Runner again
    is always an explicit request, and calling a Provider (which costs money) only ever happens through `gen`.

## 3. Concepts

[GLOSSARY.md](../GLOSSARY.md) is the canonical vocabulary. The terms this spec leans on most:

| Term | Meaning |
|---|---|
| **Asset**, **Kind**, **Recipe**, **Stage** | An asset has a kind; the kind fixes its recipe, an ordered list of stages. Kinds: `room`, `prop`, `character` first, then `sprite` (an actor from imported 2D frames, M4); `tileset`, `portrait`, `vfx`, `ui` later. |
| **Decision** | Recorded human input that a stage replays: a Pick, segmentation clicks, an Override, marker positions. |
| **Override** | A recorded hand edit on a stage's image output, tied to the hash of the image it was painted on. |
| **Layer** / **Plate** | A visible image plane of a room; the Plate is the room with its foreground objects removed. |
| **Look** / **Condition** | Another appearance of part of a room (a door shut, a lamp unlit), painted as an edit of its Source; an optional label naming the game state that shows it, for people and other Exporters. |
| **Mask** | A named binary gameplay region (`solid`, `oneway`, `ladder`). Derived masks (`walkable`, `foreground`) are computed, never painted. |
| **Model** / **Runner** / **Provider** | A 3D model; a local ML model; an image or 3D-model generator. In names Kiripix controls (paths, fields, flags, code), `model` means only the 3D Model; a Runner's files are its **weights**. |
| **Pinned output** | A committed Runner or Provider result, keyed on all of its inputs. |
| **Grid transform** | The recorded Source-to-target scale and offset. |
| **Check** / **Project check** | A verification inside one asset / across assets. |
| **Manifest** | The record of exported files and their hashes, in the Godot project. |
| **Command** / **Probe** | One operation, identical on the CLI, REST and MCP; a read-only Command that records nothing. |
| **Owner** | The one person whose Decisions and acceptances count as human judgement. An agent is never the Owner. |

## 4. Project on disk

```
my-game-assets/
  kiripix.toml              project settings
  .gitattributes            LFS for binaries; merge=union and LF for history.jsonl and decision journals
  style/
    palette.gpl              the project palette (GIMP .gpl; .hex and .ase import)
    bible.md                 style notes, read into prompt templates
    refs/                    reference images for providers that take them
    prompts/                 prompt templates per kind (Jinja2)
  assets/
    room/queen_west_alley/
      asset.toml             kind and parameters (no stage status, ADR 0005)
      history.jsonl          append-only log of runs and generations
      imported.jsonl         append-only: the file name each src/ file was imported with (outside src/, so a rename stales nothing)
      src/                   variants and the picked source (immutable once picked)
        looks/<look>/        a Look's edit Variants (outside src/*.png, so a new one never touches the Source)
      decisions/             one Decision journal per stage (<stage>.jsonl), plus Override PNGs
      pinned/                pinned Runner and Provider results, keyed by input hash
      work/                  deterministic stage outputs (cache, safe to delete)
      out/                   final outputs, the exporter's input
    prop/ttc_bench/ ...
    character/raccoon_boss/ ...
  .kiripix/                  hash cache, last-run failures, locks, Runner weights, backups, the cost ledger (git-ignored)
```

**Committed:** `src/`, `decisions/`, `pinned/`, `out/`, `asset.toml`, `history.jsonl` and `imported.jsonl`. **Not committed:** `work/`
and `.kiripix/`. Python dependencies are locked in `uv.lock`, because deterministic ops are bit-exact only on the same
library versions. Data files the owner's work lives in have migrations; a Stage's rebuilt output, such as `room.json`,
is refused when it's old, and the finding names the rebuild. Through M3 there are no production rooms, so any format
change may be refused the same way instead of migrated.

### kiripix.toml (example)

```toml
[project]
name = "toronto-rpg"
resolution = [640, 360]        # internal resolution
tile = 16
palette = "style/palette.gpl"

[body]                         # the stand-in player for walkable, reachability and walk tests
size = [12, 8]                 # feet footprint in px
dash = 0                       # the widest pit it can dash over, px (0: none)

[masks.top]                    # Masks for top-down rooms; colours are for display and import only
solid      = { colour = "#FF0000", meaning = "blocks movement" }
pit        = { colour = "#0000FF", meaning = "no walking on it, but the Body can dash over it" }
walkable   = { derived = true }   # where the body's footprint fits without touching solid or a pit
foreground = { derived = true }   # the union of the foreground Layers' alpha

[masks.top.import]             # extra colours accepted from a single painted image
"#FFFF00" = ["solid"]          # the old "both": solid; its foreground part now comes from Layers

[masks.side]                   # Masks for side-view scenes
solid      = { colour = "#FF0000" }
oneway     = { colour = "#00FFFF", meaning = "platform passable from below" }
ladder     = { colour = "#00FF00" }
foreground = { derived = true }

[export.godot]
project = "C:/Workspace/toronto-rpg"
root = "res://kiripix"         # everything Kiripix writes goes under here, Manifest included
version = "4.7"                # pinned at M0: Godot 4.7 (4.7.2-stable); see docs/versions.md

[providers]
default = "import"             # import | openai | gemini | pixellab | local-sd
budget_usd_month = 20          # hard cap; calls fail beyond it
```

Secrets (API keys) come from environment variables or a git-ignored `.env`, never from `kiripix.toml`.

**Importing a painted mask image.** A single colour image painted in an editor is accepted: each pixel snaps to the
nearest defined colour (each Mask's `colour`, plus the `import` table), and the image is split into one 1-bit Mask
per name. A combined colour is only an import mapping to several Masks, never stored.

## 5. The stage graph

**Status is derived, never stored** (ADR 0005). Each stage declares its inputs: files, upstream stage outputs,
project settings such as the palette and the body, Decisions and pinned results. Kiripix hashes them every time it
needs a status; file hashes are cached by modification time and size in `.kiripix/`. The statuses:

| Status | Meaning |
|---|---|
| `todo` | Never produced output. |
| `stale` | An input changed since the output was produced. |
| `needs-input` | Waiting for a Decision from the owner, or for an explicit `--rerun` of a stale pinned call. Carries a reason. |
| `needs-review` | Produced output by replaying Decisions onto changed input; waiting for the owner to accept it. |
| `done` | Output matches its inputs. |
| `failed` | The last run failed. Kept only in the git-ignored cache, so a fresh checkout never shows an old failure. |

**Running.**
- `kiripix run <asset>` runs every stale or todo stage in order, and stops at the first one that is `needs-input`,
  `needs-review` or `failed`. Stages below a `needs-review` stage don't build provisionally.
- `run` re-runs only deterministic work. A stage whose pinned call has a changed input key goes to `needs-input` with
  the reason "Runner input changed".
- `run --rerun` re-runs stale Runner calls, at any scope including `--all`. Its results land in `needs-review`.
- Providers are called only through `gen`, never through `run`.

**Pinned calls** (ADR 0002). Each Runner or Provider call is pinned, not each stage output. The key covers the input
image or crop hash, the click Decisions, the parameters, and the Runner's ID with a hash of its weights. The device
(CUDA or CPU) is not part of the key. The deterministic Ops around a call rebuild freely. A Blender render is not a
pinned call (ADR 0010): it rebuilds like deterministic work, with the Blender version and render settings among the
Stage's inputs.

**Replaying Decisions.**
- If a stage's input hash is unchanged, replay is exact and the stage goes straight to `done`.
- If the input changed, replayed clicks and Overrides put the stage in `needs-review`. A click that now lands on a
  different object, or a stroke over an object that has moved, is wrong without anyone noticing, so a human confirms
  it.
- Picks replay automatically. If a Decision can't apply at all (a picked variant was deleted), the stage goes to
  `needs-input` with a reason.
- `kiripix accept <asset> <stage>` (owner-only, §10.3) confirms a review. It re-records the replayed clicks
  against the new input hash and rebases the Overrides onto the new image hash, so the next replay is exact.

**Overrides.** An Override can attach to the output of any image-producing stage. It is stored under `decisions/`,
records the hash of the image it was painted on, and is a Decision of the stage whose output it paints. Core paints it
over that stage's image after the stage runs, so every stage that reads the image sees it. If the stage's own image
(before its Overrides) has changed since the Override was painted, the stage goes to `needs-review`.

**The Decision journal.** Each stage's Decisions live in an append-only `decisions/<stage>.jsonl`, one entry per line,
LF line endings, `merge=union` in git.
- Each entry has a ULID (sortable by time, unique across machines) and records its parent: the ID of the entry it
  followed. Overrides stay PNGs, referenced from the journal by hash.
- `undo` and `redo` append `{undo: <id>}` and `{redo: <id>}` entries; nothing is ever removed or rewritten. The stage's
  current Decisions are the journal replayed in ULID order.
- Two entries with the same parent mean a merge combined two branches' Decisions (for example, both placed
  `spawn.main`). The stage goes to `needs-review` with that reason, rather than letting the later one win silently.

**Writes are atomic.** Every output is written to a temporary file and renamed into place, so a cancelled or crashed
run never leaves a half-written output that looks done.

**History.** Every generation and every Runner call is appended to the asset's `history.jsonl`: `runner` (our
ID) for a Runner call, or `provider` and `provider_model` (the vendor's own model name) for a Provider call, plus the
prompt, seed, and either the parameters or, when the result was pinned, its `key` (the parameters are in
`pinned/<key>.json`), plus cost and time. The file is `merge=union` in git, so lines from both branches survive
a merge.

## 6. Recipes

Every recipe keeps Runners before the palette (ADR 0004): a palette tweak then invalidates only deterministic work.
`palette` means the same thing in every recipe, and outlines are drawn after it, in `finish`.

### 6.1 Room

A background scene with Layers, Masks, Markers and lights. A room is either `view = "top"` or `view = "side"`.

**brief → source → fit → layers → masks → palette → looks → place → reach → export**

| Stage | What it does | Owner input | Checks |
|---|---|---|---|
| **brief** | Size in px or tiles, view, mood, exits and their sides, notes. Renders the generation prompt from the kind's template and the style bible. | Writes the brief | Size is a whole number of tiles |
| **source** | Generates N variants with a Provider (through `gen`), or **imports** an image made elsewhere (a first-class path: the owner may keep using an external image tool). | Picks between several (an agent may pick a lone variant) | Has a picked source |
| **fit** | Detects the source's pixel grid, or downscales to the target size. The downscale uses one scale on both axes, the largest that still fills the brief, and crops the rest (`offset_x` and `offset_y` place the crop; an info finding, `fit.cropped`, says what was cropped and offers the centring `set`). Each cell takes the colour of its dark or light group, so a thin dark line stays one continuous pixel and flat areas stay even (the cell's mean when it has no clear line or edge). In grid mode, a grid output smaller than the brief is padded on the right and bottom up to the brief with transparent pixels (alpha 0, RGB 0), so no coordinate moves; an info finding, `fit.padded`, says how much, and `grid.json` records `pad_right` and `pad_bottom`. `masks` ORs the strip into `solid` (derived from `grid.json`, not a Decision), and a click or box that starts in it fails. A grid output larger than the brief stays `fit.size_mismatch`, whose `fix` is the brief rounded up to whole tiles. Records the Grid transform. Palette-free. | Tunes the grid, with a before/after view | Exact size |
| **layers** | Builds the **Plate** and the foreground Layers. Paths: (a) the source was generated as a plate plus props, so the Layers come from their difference; (b) segment the foreground objects (SAM 2; a negative click takes the object under it away from that Layer, and so from the Plate's hole, at its place in the replay), then inpaint the Plate (LaMa locally, or an edit API for large areas); (c) side view: depth-assisted parallax split into N planes. On path (a) the owner names a Layer with one click in a region of the difference; unclicked regions stay in the Plate. One **grow** parameter widens both a Layer's alpha and its Plate hole, in target pixels, only where the Runner's alpha was partial: a target pixel whose Source cell is partly covered by the Runner's Mask or has alpha strictly between 0 and 255 (default 1 px, 0 allowed). With no Decisions the Stage is `done`, and the Plate is the fit image. | Clicks objects to lift out; trims a rim with a brush on the Layer's alpha | Plate + Layers recompose exactly to the fit image; no holes in the Plate |
| **masks** | Paints the painted Masks (`solid` and `pit` for top view; `solid`, `oneway`, `ladder` for side view): click-to-segment (SAM 2: a positive click adds the object under it to the Mask, a negative click, a shift-click, takes that object away from the Mask at its place in the replay, whichever Decision put it there; each is one Runner call), flood by colour region within an OKLab tolerance of the clicked pixel, brush, polygon (`{mask, erase, points}`, at least three corners in target pixels; it closes itself, the outline pixels are included so a rectangle fills exactly its box, a self-crossing polygon follows the even-odd rule, points outside the Mask are clipped; not `on_image`, so a changed Plate leaves it as it is), a wall along the room's chosen edges, or import of a painted image; optional snap to an N px cell grid. The UI has no polygon tool yet (ticket 0080). | Clicks and brushes | Every Mask binary |
| **palette** | Maps the whole composite once to the palette in OKLab (strict, or with optional ordered dithering) and removes orphan pixels. Each foreground Layer is that mapped image cut by its alpha; the Plate is the same image with only its inpainted areas mapped separately. | Tunes 2–3 sliders, with a before/after view | Every pixel on the palette; Plate + Layers still recompose exactly |
| **looks** | The room's other Looks (see Looks, below). Each is an edit of the Source, picked as a Variant of that Look. It is resized to the Source, registered to it, fitted with the room's Grid transform, optionally regraded, mapped to the palette as `palette` maps the room, and cut to its region. The region's pixels over a foreground Layer become a piece at that Layer's depth. A Look may have its own `solid` Mask. With no Looks the Stage is `done`. M4. | Imports or generates an edit, names the Look, draws the region; paints `solid` where the Look blocks | Every pixel on the palette; the edit registers to the Source; drift outside the region is reported; the region shows a change |
| **place** | Puts Markers on the room: Exits (with a target room and Exit ID), Spawns, interactables, lights (colour, radius, energy), particle emitters, y-sort lines, areas (a box, optionally snapped to a `cell` from the room's top-left corner, optionally `walkable`; any number, any Marker ID, one pixel or one cell wide at least; Kiripix gives an area no meaning, and the game decides what it's for, such as a battle area, an escape route over a fence or an Exit's trigger box, M4). | Places Markers | Unique IDs; Exits and Spawns on walkable ground; every foreground Layer has a y-sort line or an "always above" flag; a sloped line sorts at its mean y, with a warning if its ends differ by more than half a tile; an area lies inside the room, and a `walkable` one holds walkable ground; with a `cell`, the cells a Mask leaves between a quarter and three quarters blocked are listed (info) |
| **reach** | Reachability: the body's footprint, flood-filled over walkable at sub-tile steps, from each Spawn and Exit to all the others (side view: over platforms, with jump settings, Later). Warns when no walkable part of a `walkable` area is reachable. Lists unreachable Markers, unreachable walkable islands and the narrowest gaps. | — | All Markers reachable |
| **export** | Writes the Godot scene (see §9). | — | Export target set; Project checks (see below) |

**palette reads `layers`, not `masks`**: its upstream is the Plate and the Layers, so a Mask edit never rebuilds the
palette mapping. `place` reads both `palette` and `masks`.

**Walkable** depends only on the `solid` and `pit` Masks and the body's footprint, so changing `[body]` re-derives it
cheaply. Reachability lives only in `reach`. A dash crosses a `pit` and never `solid`.

**A room's edges need a wall.** Walkable already keeps the footprint inside the room, so the walk test stops at an edge,
but the exported scene collides only with `solid`. The `border` Decision paints `solid` along the chosen sides, and an
info finding names an open edge. A side can stay open on purpose.

**A foreground Layer belongs to its room.** It is painted into that room's art and isn't reused; its collision comes
from the room's `solid` Mask and its draw order from its y-sort line. A reusable object is a Prop. ("Promote to Prop"
may come later, not in the first milestones.)

**Exit pairing is a Project check.** Every Exit must name an existing room and Exit ID that points back. `check --all`
and `export --all` run it; exporting a single room only warns, so a room can be worked on before its neighbour
exists.

**An Exit's trigger box is an area.** An Exit is a point. When the game needs a rectangle the player walks into, the room
gives it as an `area` Marker (for example `exit.back_door` and the area `exit.back_door.trigger`), and the game's own room data
names that area on its Exit. Kiripix doesn't pair them and adds nothing to the Exit (decided by the Owner, 2026-11-12, for the
game's exits ticket 0040), so the box is drawn on the room and moves with it, never typed into the game's data.

**Walk test (UI):** the stand-in body walks the room with the arrow keys, on the real collision, at game resolution,
with the foreground Layers drawn over it by their y-sort lines.

#### Looks (ADR 0009, M4)

A painted room is one baked picture, so a door that opens or a lamp that goes out has its other appearance painted too.
That appearance is a **Look**. The game finds it by its ID and decides when to show it. A Look may carry a **Condition**,
an opaque string to Kiripix (`door.cell_3:shut`, `circuit.hall:off`): a label for people and for other Exporters, which the
game never evaluates. Urban Mystery Club binds each Look by ID in its own room data, with its own condition JSON over its
Facts, as it binds lights and interactables (decided by the Owner, 2026-11-12). A Look belongs to the room's Asset
because it must share the room's Grid transform, palette mapping and Layers exactly.

**Making one.**
- A `look` Decision gives the Look an ID and, optionally, a Condition.
- Its edit is added with `kiripix import <id> <png> --look <look>`. From M6, `gen <id> --look <look>` makes one with an
  edit prompt ("Edit this image. Keep everything exactly the same except: …"). An edit can also be painted by hand on a
  copy of the Source.
- `pick <id> <variant> --look <look>` chooses the edit, and records the hash of the room's Source it was made on.

**Building one,** in the `looks` Stage:
1. **Resize** the edit to the Source's exact size, because an edit often comes back at another size.
2. **Register:** estimate the edit's scale and shift against the Source outside the region, and undo them (`register`,
   on by default). An image model rescales its redraw by up to about 1 % (trial 0063). The limits come from trial 0128.
3. **Fit** through the room's Grid transform: the same mode, scale and offsets.
4. **Regrade**, optionally (`regrade`, default `none`). `outside` fits the edit's colours, in OKLab, to the Source's on
   the pixels outside the region, and applies that fit to the whole edit. It is off by default: an unlit Look's darkening
   is often the point.
5. **Map** the whole fitted edit to the palette with the `palette` Stage's parameters, so that orphan cleanup sees the
   same context it saw in the room. Then cut the region.
6. **Split:** the region's pixels inside a foreground Layer's alpha become a piece for that Layer, drawn at its depth,
   so an actor still sorts right. The rest draws with the Plate.

**Decisions,** in target pixels, each naming its Look:
- `look` (ID, optional Condition) and `pick` (the edit);
- region: `polygon` and `brush` as on `masks`, and `difference`: inside a box, the pixels where the mapped edit differs
  from the mapped room by more than a tolerance, with specks removed. A `difference` region picks out a lamp's glass
  without anyone drawing it, and it is on the image, so a new edit or a refit puts it in `needs-review`. A polygon or a
  brush stroke stays where it is. The region is the Look's binary alpha, not a Mask, because it is visible.
- `solid`: the Look's own `solid` Mask, by polygon or brush, with the `masks` Stage's `snap_cell`. It adds collision
  while the Look shows, such as a shut door. A Look can't take collision away from the room yet (§16, open decision 8).

**Staleness.** A new room Source invalidates every Look's pick, and the Stage goes to `needs-input` with "the edit was
made on another Source". A refit or a Layer change rebuilds every Look: its `difference` regions and registration go to
`needs-review`. A palette change rebuilds them, and they are `done`. A room with no Looks has a `looks` Stage that is
`done` at once. `place` and `reach` read the room without its Looks.

**Checks:**
- `look.off_palette`: every pixel is a palette colour.
- `look.misaligned`: after registration, the edit still sits more than half a target pixel off the Source outside the
  region, or registration hit its limits. This is an error, because the picture would jump when the Look toggles. Its
  `owner_action` is to re-make the edit.
- `look.drift` (warning): target pixels outside the region where the edit changed the room, with a count and the box
  of each patch. A model drifts, and this reports the drift; it never hides or quietly fixes it. Its `owner_action` is to
  widen the region if the change belongs to the Look, or to re-make the edit.
- `look.unchanged` (warning): most of the region matches the room, so the region is in the wrong place or the edit
  missed it.

**Keep Looks small.** A large crop of an edit shows the edit's compression noise and redraw as blotches, which
Lost-and-Found found (§15). Cut a lamp's glass, not the wall around it. Look IDs are frozen once exported, like Layer
IDs.

### 6.2 Prop

A standalone, reusable object for scenes: benches, signs, lamps, bins.

**brief → source → cutout → fit → palette → finish → footprint → export**

| Stage | What it does |
|---|---|
| **brief** | Size, viewing angle (top-down 3/4 or side), notes. |
| **source** | Generated on a flat chroma background, or imported. |
| **cutout** | Chroma key (exact, for flat backgrounds; a finding points to matting when it removes almost nothing or leaves a fringe) or matting (BiRefNet) on the full-size source. |
| **fit** | Grid snap or downscale, as for rooms, including the transparent padding up to the brief (`fit.padded`); the alpha goes to the target grid by majority vote, so it is binary (pixel art has no partial alpha). |
| **palette** | Palette mapping and orphan cleanup, as for rooms. |
| **finish** | Optional 1 px outline in a chosen palette colour. |
| **footprint** | The base's collision shape and the y-sort origin. A foreground split is deferred: y-sort at the origin handles a lamp's head, and only arch-like props would need one. |
| **export** | `Sprite2D` scene with collision and origin. |

Checks: binary alpha, palette, exactly the brief's size and no larger than the project's resolution, and an origin is set.

### 6.3 Character (3D to pixel)

Characters, NPCs and enemies are rendered from 3D, so every animation stays on-model. They are rendered at the target
pixel size (52 px tall in the Toronto RPG), so the recipe has no `fit`.

**model → rig → clips → render → palette → finish → sheet → export**

| Stage | What it does | Owner input |
|---|---|---|
| **model** | Imports `.glb`, `.fbx` or `.blend`; optional image-to-3D (a local Runner if one fits 8 GB, or a Provider). Normalises scale and the up axis. | Picks or imports |
| **rig** | Validates a humanoid rig, or guides the Mixamo auto-rig round trip (the tool shows the steps and picks up the downloaded file). Rigify for non-humanoids. | Mixamo step, when used |
| **clips** | Maps named clips (`idle`, `walk`, `run`, `attack`, `hit`, `ko`, `cast`…) to animation sources, with frame range, frame rate and loop flag. Clip IDs are snake_case verbs; a variant is named for what it is (`attack_kick`), not numbered. Deciding a clip again under its name changes its range (M4). Records the frames where a foot plants, the same in every direction (M4, lower priority). A class's weapon in its battle clips: how it gets there is a trial (M4, [0170](../backlog/m4/0170-m4-weapon-in-a-battle-clip-trial.md)). A clip can also play its action faster (`speed`), hold one pose (`still`: a standing idle), and name the frames drawn with closed eyes (`blink`) (M4, ticket 0203). | Chooses clips |
| **render** | Blender headless. Orthographic camera from a preset: top-down 3/4 at 4 or 8 directions (all rendered, none mirrored, so an asymmetric character stays right), side view. Battle clips use the same camera as walking, because the game fights in the room. Directions are named `s sw w nw n ne e se` from the screen's view, `s` facing the camera. Rendered at the target pixel size, no anti-aliasing, toon shading, in one square cell per character, grown from 1.5 x its height until every pose of every clip fits with a pixel to spare for the outline, so no pose is cut. A stationary clip's pivot is the same pixel in every frame (the feet, not the swaying hips). Passes: colour, normal, depth and an object mask. Frames are subsampled to the clip's frame rate. Renders aren't pinned: they rebuild as deterministic work, with the Blender version and render settings among the Stage's inputs. With `eyes` naming the Model's eye materials, it also records where each eye is in every frame, from the posed mesh (M4, ticket 0203). | Tunes the camera preset once per project |
| **palette** | One palette per character across all frames (a project-palette subset), orphan cleanup. With `parts` (M4), each swappable part (one or more Blender materials) owns a ramp of palette colours that nothing else uses. The Project's ramp table (`[[character.ramps]]` in `kiripix.toml`) fixes each part's name, length and row for every character, and its colours where they're shared (skin, hair), so one swap means the same on every body. | — |
| **finish** | Outline, drawn after mapping, in a palette colour: a 1 px silhouette from the object mask (§16, decision 3); outline consistency across frames. The normal pass is quantised to its own levels (not palette-mapped) and aligned to the colour frames. With `eyes=stamp`, the eyes `render` followed are painted as a small fixed pattern, a pupil and a white on whole pixels, chosen once for a clip and a direction and moved only when the head has moved most of a pixel; a clip's `blink` frames get closed eyes (M4, ticket 0203). | — |
| **sheet** | Packs frames into an atlas with a fixed pivot (the feet) per frame, plus frame metadata. | — |
| **export** | Godot `SpriteFrames` `.tres`, plus a `CanvasTexture` with the normal map for 2D lights, plus a scene with `AnimatedSprite2D`. An animation is named `<clip>_<dir>`, such as `walk_sw`. | — |

Checks:
- **pivot drift:** the feet don't move between frames of a stationary clip;
- every frame fits its cell;
- palette;
- frame counts match the clip;
- no empty frames;
- normal map size equals the colour frame's.

### 6.4 Sprite (2D frames to pixel; M4)

An actor built from imported 2D frames, such as a PixelLab figure, exported exactly as a character is (the game's sprite route,
DEC-012). On PixelLab's free plan a figure is one frame per direction, so a clip of one frame in 4 or 8 directions is the common
case; whole animations import too. Design: [0174](../backlog/m4/0174-m4-sprite-kind.md).

**frames → fit → palette → finish → sheet → export**

| Stage | What it does | Owner input | Checks |
|---|---|---|---|
| **frames** | Cuts the imported sheets (`import --role sheet`: a PNG, or a ZIP of PNGs; stored whole in `src/sheets/`) into `<clip>/<dir>/<NNN>` frames at source resolution. Parameter `directions`: `8` (`s sw w nw n ne e se`), `4` (`s w n e`, the default) or `1` (`s`). A ZIP is read by a naming rule (a direction word, PixelLab's `south`, `south-east`... or ours, in a folder or a file's name; a frame number; the clip is the folder above, snake_case; `idle` for rotations alone). The rule is provisional until the trial on a real export ([0175](../backlog/m4/0175-m4-sprite-pixellab-export-trial.md)). A clip gets fps 8, loop on, and is stationary when it has one frame. | A `sheet` Decision (a PNG's file, clip, layout, directions and frame count; a ZIP's clip renames), a `clip` Decision (fps, loop, stationary) | `frames.direction_missing` (error, never mirrored), `frames.frame_count`, `frames.unknown_direction`, `clips.bad_name`, `clips.duplicate_name` |
| **fit** | Per frame onto the target grid: `grid` (default: `detect_grid`; one scale for every frame) or `downscale` (one Grid for the Asset that brings the reference frame's figure to `height`, line-keeping, for AI images); `chroma` clears a flat background first; the alpha is binary by vote. Measures each frame's feet (`feet_point`), takes a pivot per direction (the median over its stationary frames, else all), and places every frame on one cell, the smallest that holds them around the pivot with 1 px to spare for the outline. `align_feet` places each stationary frame by its own feet. Writes `render.json` in the character's schema, with each frame's measured `feet`. | A `pivot` Decision, only when the measured feet are wrong | `fit.grid_differs`, `fit.alpha_partial`, `fit.height` (info), `fit.cell_grew` (info) |
| **palette** | The character's, without `parts`. | — | `palette.off_palette` |
| **finish** | The character's; `normals` is `height` by default (a rounded height from the alpha, Sobel; `relief` mixes in lightness), or `flat`; `placement` is `edge`: the source's own dark edge is repainted in the Project's outline colour. | — | `normal.size_mismatch`, `palette.off_palette` |
| **sheet** | The character's. `sheet.pivot_drift` compares the frames' measured feet; its fix is `fit align_feet=true`. | — | as the character's, without `sheet.part_vanishes` |
| **export** | The character's: `color.png`, `normal.png`, `character.json`, and the Exporter's files. | — | `export.no_target` |

Nothing is mirrored: a direction a clip lacks is an error, and the game picks the nearest facing. Palette ramps per part need a
part label per pixel and are Later for sprites.

## 7. Ops library (first set)

- **colour:**
  - palette load and save;
  - OKLab conversion;
  - nearest-colour mapping;
  - ordered dithering (Bayer 2/4/8);
  - palette extraction (k-means in OKLab, then a manual merge);
  - palette suggestion: new colours for a palette from an image, with the existing colours held fixed, new clusters
    seeded where the palette fits worst, and candidates near an existing or chosen colour dropped;
  - palette conformance report.
- **resample:**
  - pixel-grid detection (scale and offset of upscaled pixel art), returning a Grid transform;
  - mapping points, images and masks through a Grid transform (a click maps to the centre of its target pixel);
  - nearest, line-keeping and majority-vote downscale;
  - integer upscale.
- **cleanup:**
  - orphan pixel removal;
  - outline add or strip;
  - alpha binarise.
- **masks:**
  - flood fill by colour or region;
  - split a painted colour image into binary Masks (nearest defined colour, plus the import table);
  - cell-grid quantise;
  - morphology (open, close, grow), including grow only where a source alpha was partial;
  - mask from a difference (plate versus full).
- **geometry:**
  - contour trace;
  - polygon simplify (Douglas–Peucker, with a pixel tolerance);
  - polygon to collision shapes;
  - navigation polygon.
- **reach:** walkable from solid and a footprint; the footprint flood over walkable at a step size; a dash over pits;
  a narrowest-gap report.
- **compose:**
  - layer stack and recompose;
  - cut a mapped image by a Layer's alpha;
  - overlay tint (the mask readout);
  - before/after sheets;
  - atlas packing.
- **normals:** normals from height (Sobel), from a depth map, or from Blender's normal pass, encoded as Godot expects.

## 8. Runners (8 GB VRAM)

Runners are local ML models, loaded lazily through `runners/`, one at a time, unloaded after use, with weights
downloaded on first use into `.kiripix/weights/`. Each entry records its licence and a hash of its weights (part of
every pinned call's key). **Verify every licence at M0**; some model sizes are non-commercial.

Runners work on the high-resolution source, and their inputs and outputs map through the asset's Grid transform
(ADR 0004). Inputs are capped at about 1–1.5k px, or cropped around each hole, to fit 8 GB.

**The choice of model stays open.** New models appear every month, so the first choices below are only today's. A Stage
names a Runner by ID, nothing outside the Runner's own file knows its engine, and Decisions are stored in target pixels,
never in a model's terms. Replacing one means a new class in `runners/` and pointing the Stage at it. Every pinned call
it made then goes to `needs-input` with "Runner input changed", and `run --rerun --all` remakes them for the Owner's
review, so a swap can never change an exported asset silently.

| Use | First choice | Fallback (no ML) |
|---|---|---|
| Click-to-segment | SAM 2 (small or base) | Colour flood plus GrabCut (OpenCV, not a dependency yet) |
| Background matting | BiRefNet | Chroma key |
| Depth (parallax, normals) | Depth Anything V2 (the small model; check licences of larger ones) | Manual depth planes |
| Inpainting (plate holes) | LaMa | OpenCV Telea or PatchMatch for small holes (OpenCV isn't a dependency yet); an edit API for large ones |
| Image-to-3D (optional) | Decide at M6, after testing which fit 8 GB, beside Providers (deferred from M3) | Bought or hand-made models |

ONNX Runtime with CUDA is preferred to keep installs small, with PyTorch where a model needs it. The core works with
no GPU: Runners run on CPU, slower. Because results are pinned, the device that produced one doesn't matter.

## 9. Godot export

Kiripix writes Godot 4 text resources (`.tscn`, `.tres`) and PNGs under `export.godot.root`.

| Asset | Godot output |
|---|---|
| Room | A scene with these nodes: `Sprite2D` Plate; foreground `Sprite2D`s, y-sorted by their y-sort lines or above actors when flagged "always above"; `StaticBody2D` + `CollisionPolygon2D` from the `solid` Mask; `NavigationRegion2D` + `NavigationPolygon` from walkable ∩ reachable; `Marker2D` for Spawns and Exits (with metadata: IDs, targets); `PointLight2D` from light Markers; `GPUParticles2D` stubs from emitter Markers; an `Area2D` per area Marker (M4), with a `RectangleShape2D` the size of its box, `monitoring` and `monitorable` off and collision layer 0, so it never touches physics, and metadata `kiripix_id`, `kiripix_type`, `walkable` and `cell`. **Masks and `room.json` (M4):** the `solid` and `pit` Masks go beside the scene as 1-bit PNGs (`masks/solid.png`, `masks/pit.png`, and each Look's own `solid`), with `room.json`; the scene's root names `room.json` in `metadata/kiripix_room`. The game builds cell data, such as a battle grid, from these exact pixels, not from the simplified collision polygons; Godot's default lossless import keeps them exact for `Texture2D.get_image()`. (`LightOccluder2D` has no source for its shape yet, so it isn't in M2.) `solid` is on collision layer 1 and `pit` is a `StaticBody2D` of its own on layer 2: the game's Body drops layer 2 from its mask while it dashes. Side view: `oneway` → one-way collision; parallax planes → `Parallax2D`. **Looks** (M4): a `Sprite2D` per Look in a `Looks` node drawn with the Plate, at its region's box, `visible = false`, with metadata `kiripix_id` and, when the Look has one, `condition`; each piece over a foreground Layer is a `Sprite2D` child of that Layer's node, so it sorts with the Layer and draws over it, also hidden and with the same metadata; a Look's `solid` is a `StaticBody2D` on layer 1 whose `CollisionPolygon2D`s start `disabled = true`. The game shows a Look by showing every node whose `kiripix_id` is that Look's and enabling its polygons; when to do so is in the game's own room data, not in the Condition. `room.json` carries the same data (`looks`: ID, Condition or `null`, file, box, pieces with their Layer, collision), so another Exporter reads it, not the scene. `room.json` is part of the game's contract from M4: each format change bumps its `schema_version`, and through M4 a change means a re-export, not a migration (the Owner has no production rooms). |
| Prop | A scene: a `Node2D` root at the origin (the y-sort point), a `Sprite2D` offset so the origin pixel is the root's own place, and a `StaticBody2D` footprint on collision layer 1, with a `CollisionPolygon2D` per convex piece of the polygon, relative to the origin. No body when the polygon is empty. The prop's `export` Stage leaves `sprite.png` and `prop.json` (`schema_version`, `asset`, `size`, `origin`, `collision`) in `out/export/`. The scene instances the sprite as `sprite.png` beside it. No prop ID is frozen, so the footprint can be emptied. |
| Character | `texture.tres` (`CanvasTexture`: the colour atlas as diffuse, the normal atlas as its normal map), `frames.tres` (`SpriteFrames`: one animation `<clip>_<dir>` per clip and direction, such as `walk_sw`, each frame an `AtlasTexture` region of the `CanvasTexture`, at the clip's speed and loop flag), and a scene: a `Node2D` root at the feet with an `AnimatedSprite2D` child `Sprite`, `centered = false`, offset so the pivot pixel is the origin. Both atlases sit beside them. The character's `export` Stage leaves `color.png`, `normal.png` and `character.json` (`schema_version`, `asset`, `files`, `cell`, `pivot`, `atlas`, `directions`, `clips` with each direction's frames as `index` and `rect`, `fps`, `loop`, `stationary`) in `out/export/`. The frozen IDs are the animation names. **Part ramps (M4):** `character.json`'s `parts` (each part's name, materials, row, `shared` when its colours are the table's, palette indexes and RGB, dark to light) and `rows` (the table's part names and lengths, in order), and `ramps.png` beside the atlases, one row per part of the Project's ramp table in its order, padded to the longest ramp; a part the character lacks is a transparent row, so a row is the same part on every character. The scene's root names it in `metadata/kiripix_ramps`, with the part names in row order in `metadata/kiripix_parts`. **Events (M4, lower priority):** each clip's `events`, such as `foot`, the game frames where a foot plants. |
| Sprite | As a character, under `sprite/`. |

The game instances these scenes and adds its own scripts in its own scenes, so nothing it writes is ever regenerated
over (principle 10).

### The Manifest (ADR 0003)

- **Where:** only in the Godot project, under the export root, committed with the game. It has one file per asset,
  so unrelated assets never conflict in git. A copy in `.kiripix/` is only a cache. Without the game repo at the
  configured path, export and the ID freeze checks refuse rather than guess.
- **Contents:** each asset's ID, every ID it exports (Markers, Layers, clips, node names derived from Masks), its
  files with their hashes, an "exported" flag and a counter that goes up each time its exported hash changes. The
  Manifest also records its schema version and the Kiripix version that wrote it. The game's tests read it.
- **Ownership:** Kiripix overwrites or removes a file only if the Manifest lists it and its current hash matches.
  Each generated text file starts with a `; generated by kiripix, do not edit` comment, but that is a hint for humans,
  not the rule. Godot's `.import` sidecars are ignored.
- **Conflicts with the game's edits:** a hash mismatch (someone saved the scene in the Godot editor) makes export
  refuse and name the file. `--force` backs it up to `.kiripix/backups/<timestamp>/` and overwrites it. An unmanaged
  file already at a target path needs `--adopt`, with the same backup. `--dry-run` lists the two cases separately.
- **Deleting an asset:** no Command does this yet: it means removing the asset's folder. Its files stay in the game until
  an explicit `export --prune`, under the same hash rule and backup. Alone, `--prune` prunes every deleted asset and
  exports nothing; with `--all` it exports, then prunes; with an ID it prunes that deleted asset, and refuses if the asset
  still exists.
- **Frozen IDs:** once exported, an ID can't be renamed or removed; adding new IDs is always fine. Before the first
  export, IDs can be renamed freely. A y-sort line makes no node, so its Marker ID isn't frozen. Deleting an asset and
  creating one under a new ID is allowed, with a warning if the old ID is still referenced.
- **Branch merges:** when two game branches export the same asset, `kiripix manifest merge` (a git merge driver)
  resolves it: the higher counter plus one, the union of the IDs, and our `files` with theirs in `replacing`, so the next
  export accepts either. Export checks that the driver is configured in the clone, and its finding's `fix` is `kiripix
  manifest install` (`.gitattributes` alone does nothing). The exported images and scenes (`*.png`, `*.tscn`, `*.tres`
  under the export root) can't be merged by git either, and the Manifest already accepts either side, so `manifest
  install` also writes those rules to `<root>/.gitattributes` with a `kiripix-ours` driver (`true`, configured in the
  clone): a merge keeps our file with no conflict, and the next export puts the right one in place. The same check and
  `fix` cover these rules. GitHub never runs custom drivers, so for a conflict in a pull
  request, merge locally or run `kiripix manifest repair`, which handles a Manifest with conflict markers.

## 10. Commands: CLI, REST and MCP

Kiripix must be easy for AI coding agents to drive, and easy to build UIs on. Both come from one rule: every operation
is a **Command** in a single registry in core, and the CLI, REST and MCP are thin adapters generated from it (ADR 0006).

### 10.1 The registry

Each Command declares:
- typed input and output (Pydantic), including non-JSON data: a file passed in (an import PNG), an image returned,
  and progress events, which each adapter maps in its own way;
- CLI metadata: positional arguments and short aliases, so the generated CLI is pleasant to type;
- its kind: **writing**, **Probe** (read-only, never recorded or pinned) or **owner-only**;
- its MCP exposure: exposed, hidden or owner-only. Only the Commands an agent needs are MCP tools, because each tool
  costs an agent context.

Every UI action maps to exactly one Command. Continuous gestures (dragging a Marker, a brush stroke) become one Command
when the mouse is released, not one per mouse-move. One exception: on the masks screen, with its rebuild option on, an
edit is followed by a `run` of the Stage (ADR 0006).

### 10.2 The contract

- **One API version** for the whole tool, carried in every result as `api_version`. Breaking changes bump it.
- **Schemas:** `kiripix schema [command]` prints the JSON Schema of every Command's input and output, generated from
  its types.
- **Self-description:** `kiripix describe project` lists the Kinds and their Recipes; `kiripix describe <kind>` gives
  each stage's parameters (types, defaults, ranges), the Decisions it accepts (with their schema) and its Checks.
- **Findings and errors** carry a stable string `code` (`palette.off_palette`, `reach.unreachable_marker`), a position
  where there is one, and a `fix`: the exact command that fixes it. When only the owner can fix it, the finding says
  so explicitly: `fix: null` plus `owner_action: "…"`.
- **`next`** always returns either a runnable command or an explicit owner action.
- **Output:** `--json` prints exactly one final object on stdout. `--progress=jsonl` streams progress events on
  stderr; REST streams the same events over SSE.
- **Cancellation:** Ctrl+C in the CLI, a cancel endpoint in REST. Atomic writes (§5) mean a cancelled run leaves
  nothing half-done.

**Exit codes:**

| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | error |
| 2 | check failed |
| 3 | needs the owner: `needs-input` or `needs-review` (the JSON says which, and why) |
| 4 | busy: a lock is held (the JSON names the holder) |

### 10.3 Owner-only Commands

`accept`, and any future Command that stands for the owner's own judgement, is **owner-only**. This is a guardrail
against an agent accepting its own work by mistake, not security:
- from the CLI, it refuses unless stdin is an interactive terminal (an agent's shell is not);
- over REST, it requires the session token that `serve` gives the browser when it opens it;
- it is never an MCP tool;
- `KIRIPIX_TEST_OWNER=1` bypasses the check, for the test harness only. CLAUDE.md says agents must never set it.

On Windows, Python under Git Bash's mintty can report that stdin isn't a TTY even when the owner is typing. Test
`isatty` at M0 in every terminal the owner uses (Windows Terminal, the VS Code terminal, Git Bash); where it fails,
the UI is the accept path.

### 10.4 Concurrency

The UI, an agent's CLI calls and the MCP server can all run at once. They coordinate only through lock files in
`.kiripix/`:
- **Asset locks**, held by writing Commands on that Asset. Probes never lock.
- **The project lock**, for project-wide writes: the palette, `kiripix.toml`, and export writing the Manifest. Locks
  are always taken in a fixed order (project, then Asset), so two writers can't deadlock.
- **The GPU lock**, held only while a Runner or a Blender GPU render is loaded, because they all share 8 GB, and not
  through a Stage's rebuild that only reads pinned results. `serve`
  unloads its warm Runner when another process asks for the lock; the other process waits with progress events, or
  runs on the CPU with `--cpu`.
- A lock records the process ID, the host and the start time. If that process is dead, the lock is stale and is taken
  over.
- A writer that finds a lock held fails at once with exit code 4, or waits with `--wait <seconds>`.
- `run --all` locks one Asset at a time, so the UI stays usable during a long run.

The CLI always runs in-process and never forwards calls to a running server, so a CLI call works whether or not a
server is up. The UI watches the project folder and refreshes when an agent changes something.

### 10.5 The CLI

One command, `kiripix` (alias `kpx`), with subcommand groups. Every command takes `--json`.

```
kiripix init [dir]                          new project
kiripix describe project|<kind> [--stage s] Kinds, Recipes, stage parameters, Decision schemas, Checks; --stage gives one Stage
kiripix schema [command]                    JSON Schemas of Command inputs and outputs
kiripix status [--kind room]                board: every asset, its stage and state
kiripix show <id>                           one asset: variants, the pick, each stage's parameters, decisions and images
kiripix new <kind> <id> [--view top|side]   new asset from its recipe
kiripix next <id>                           the next stage and what it needs (a command, or the owner's action)
kiripix run <id>|--all [stage] [--force] [--rerun] [--cpu]   run stale and todo stages; --rerun also re-runs stale Runner calls
kiripix set <id> <stage> key=value...       set stage parameters
kiripix decide <id> <stage> --decision '<json>' | --file d.json [--brief]   record a Decision (validated against the stage's schema); a file may hold a JSON array of Decisions, recorded all or none; --brief leaves out `current`
kiripix override <id> <stage> <png>         record an Override from a painted image
kiripix mask-import <id> <png>              import a painted mask image (the masks Stage's import Decision)
kiripix plate-import <id> <png>             import a Plate image (the layers Stage's plate Decision)
kiripix undo <id> <stage> [--brief]         undo the stage's last Decision
kiripix redo <id> <stage> [--brief]         redo it
kiripix accept <id> <stage>                 confirm a needs-review stage (owner-only)
kiripix extend <id> canvas|add <png>|undo|done [--side east|south|west|north] [--keep N]   the canvas for the next piece of a large room, joining a piece onto it, and the joined image as a Variant (M4)
kiripix import <id> <file> [--look l]       set a source from an outside image or model; --look adds an edit Variant of Look l (M4)
kiripix gen <id> [-n 4] [--provider x] [--look l]   generate source variants, or edits of Look l (the only command that calls Providers)
kiripix pick <id> <variant> [--look l]      record the chosen variant; --look picks Look l's edit (M4)
kiripix check <id>|--all                    run checks (--all includes Project checks), list findings with positions
kiripix preview <id> [--stage s] [--overlay masks|walkable|reachable] [--region x,y,w,h] [--grid N]
                                            write a preview PNG, print its path
kiripix probe <name> <id> <args...>         run a Probe, such as segment-preview or flood-preview x,y,tolerance ...
                                            (several flood tries in one call, nothing recorded); every Mask answer
                                            has `pixels` and a bounding box `box`, and `--summary` leaves out `runs`
kiripix export [<id>|--all] [--dry-run] [--force] [--adopt] [--prune]   write to the Godot project
kiripix manifest [merge|install|repair]     the git merge driver, installing it, and the manual fallback
kiripix op <op> <args...>                   one op directly (quantize, snap-mask, reach, ...)
kiripix op palette-suggest <image> --add N [--scale 2.15] [--min-distance d]   propose up to N colours the palette lacks; writes a proposal under .kiripix/, changes nothing in the palette
kiripix palette-add <proposal> [--name prefix]   append a proposal's colours to the palette (owner-only); rooms using the palette go stale
kiripix cost [--month]                      provider spend from the ledger
kiripix runners [list|pull|rm]              local Runner management
kiripix serve                               the REST API and the web UI; holds a warm Runner
kiripix ui                                  serve, and open the browser
kiripix mcp                                 start the MCP server (stdio)
```

Every writing command takes `--wait <seconds>`; long commands take `--progress=jsonl`.

### 10.6 REST and MCP

**REST** is served by `kiripix serve`, one route per Command. Probes are fast only here: the server caches SAM 2's
image embedding by image hash, so a hover runs only the cheap decoder, and it keeps the last Runner warm until an idle
timeout or until another process asks for the GPU lock. A `run --rerun` through the server uses the same warm Runner and
embeddings, unless it asks for `--cpu`. That is the only exception to "unload after use", and it applies only to the
long-running server.

**MCP** (`kiripix mcp`, stdio) exposes only the Commands tagged for it, at first `status`, `describe`, `next`, `run`,
`set`, `decide`, `check`, `preview`, `export`, `op`, `gen`, `pick`, `cost`.
- **Reviews:** when a stage is `needs-review`, the result says "needs-review: owner must accept" with the preview
  path, so the agent can report back instead of stalling.
- **Results:** JSON plus file paths. Images are returned only when the caller asks (`preview` with `inline=true`),
  because images cost tokens.
- **Spend:** a tool that spends money (`gen`) states the estimated cost in its result and respects the budget cap.

## 11. UI

A local web app served by `kiripix serve` (`kiripix ui` also opens the browser). It is built only on the REST
Commands of §10, so it can do nothing an agent can't, and another UI (a VS Code panel, a Claude-built page) can be
built the same way.

```
┌ Assets ───────┬ Canvas ─────────────────────────────┬ Stage panel ───────┐
│ search/filter │ the asset at integer zoom           │ this stage's few   │
│ ▸ room        │ layer toggles · overlay opacity     │ controls           │
│   alley   ●   │ before/after split                  │ live checks ✓ ✗    │
│   ttc_car ◐   │                                     │ [Primary action ▶] │
│ ▸ prop        │                                     │                    │
├───────────────┴─────────────────────────────────────┴────────────────────┤
│ stages: brief ✓ source ✓ fit ✓ layers ✓ MASKS palette place reach export  │
└──────────────────────────────────────────────────────────────────────────┘
```

**Rules:**
- One screen per stage, not per tool. Each shows only its controls and one primary action, and Next moves along the
  stage bar.
- Keyboard first: number keys pick variants, letters switch tools and Masks, `[ ]` change the brush size, `Space`
  pans, `Z` zooms, `Ctrl+Z` undoes a decision.
- Integer zoom only, with nearest-neighbour rendering. A "game frame" view at the real resolution.
- Checks run live in the panel. Clicking a finding jumps to its position on the canvas.
- A `needs-review` stage opens with a before/after of the replayed result, and Accept is its primary action.
- Every action is one Command: a click is one `decide`, and a drag or brush stroke is one `decide` or `override` when
  the mouse is released. `Ctrl+Z` and `Ctrl+Shift+Z` are `undo` and `redo`. On the masks screen, with its rebuild option
  on, an edit is followed by a cancellable `run` of the Stage, so that it shows on the canvas (ADR 0006).
- Hover feedback (click-to-segment previews) uses Probes, which record nothing.
- Stage panels are rendered from `describe`: parameter-only stages need no front-end code. The stages that matter most
  (masks, layers, place, the walk test, the frame strip) still need hand-written canvas widgets.
- The UI watches the project folder and refreshes when an agent changes something. Owner-only calls send the session
  token `serve` gave the browser.

**Stage screens:**
- **Source:** the variant grid, plus drag-and-drop import.
- **Fit and palette:** a before/after slider.
- **Layers and masks:** click-to-segment previews on hover; shift-click subtracts.
- **Place:** Markers with an ID field and a dropdown of target rooms; y-sort lines drawn on each foreground Layer; areas
  dragged as boxes, with their cell grid (M4).
- **Reach:** the walk test.
- **Character:** a frame strip with onion skin, a direction picker and a clip player at game speed, and a sprite's Stages from `fit`.

**Status board:** all assets by kind and stage, filtered by "needs me" (input or review), "stale" and "failing".

**Front end:** React with TypeScript and Vite, with canvas rendering (the owner's decision, 2026-11-02; ADR 0008).
The canvas widgets are plain TypeScript classes that React components mount through a `ref`, so hover and brush
updates never go through React state.

## 12. Tech stack

| Area | Choice |
|---|---|
| Language | Python 3.12, managed with uv; dependencies locked in `uv.lock` |
| Commands | One registry in core; each adapter below is generated from it |
| CLI | Typer |
| Data | Pydantic models for every TOML and JSON file and every Command input and output, versioned with migrations; JSON Schemas generated from them |
| API | FastAPI (REST and SSE) |
| MCP | The official Python MCP SDK |
| IDs | ULIDs for Decision journal entries |
| Images | numpy and Pillow; OpenCV or scikit-image only when an Op needs one, added through `uv.lock` |
| ML | ONNX Runtime (CUDA), PyTorch where needed |
| 3D | Blender 5.2 LTS (pinned at M0, see docs/versions.md; found through config or PATH), run headless: `blender -b -P kiripix/blender/<script>.py -- <args>`, with arguments and results as JSON files |
| Templates | Jinja2 for prompts |
| Storage | git LFS for PNG and GLB (`src/`, `pinned/`, `out/`) |
| UI | React, TypeScript and Vite; canvas widgets in plain TypeScript |
| Tests | pytest with golden images (pixel-exact diff); Playwright for a few UI flows; Blender tests marked and skipped when Blender is missing |

## 13. Code layout

```
kiripix/
  core/        project, asset, recipe, stage graph, hashing, status, decisions, pinning, history, locks (no I/O beyond the project dir)
  commands/    the Command registry: every operation's typed input, output and metadata
  ops/         pure image functions
  checks/      check functions returning findings, including Project checks
  runners/     local ML runners (lazy load, unload)
  providers/   image generation adapters: import, openai, gemini, pixellab, local-sd
  recipes/     room.py, prop.py, character.py: stage definitions per kind
  blender/     bpy scripts (run inside Blender only)
  export/      godot.py (tscn and tres writers), manifest (ownership, freeze, merge)
  cli/         Typer adapter, generated from commands/
  server/      FastAPI and MCP adapters, generated from commands/; the warm Runner and the embedding cache
web/           UI (TypeScript), with its Playwright tests in web/e2e/
tests/         cli/, golden/, acceptance/
```

The import rule: `ops` imports nothing from the rest; `checks` only `ops`; `recipes` use `ops`, `checks`, `runners` and
`providers`; `core` sits on `recipes`; `export` on `core`; `commands` on `export`; `cli` and `server` use only
`commands`, so no adapter can hold logic of its own.

## 14. Milestones

**M0: skeleton.**
- The repo, CLAUDE.md, uv with `uv.lock`, git LFS and CI. CLAUDE.md states that agents never commit: the owner
  reviews every change and commits it.
- The Command registry with the CLI adapter, `schema`, `describe`, exit codes and the JSON contract.
- `init`, `new`, `status`, and a stage graph with derived status and the hash cache.
- Locks (project, Asset, GPU) with stale-lock takeover.
- Palette load and the quantise op, with golden tests.
- Pin the Godot and Blender versions; verify the Runner licences; test `isatty` in each of the owner's terminals.

**M1: a room, end to end (the vertical slice).** Room recipe with an imported source:
- brief, fit, masks (flood plus brush plus SAM 2, with pinning and `needs-review`), palette, place, reach and export;
  `layers` is a pass-through until M2 (the Plate is the fit image, with no foreground Layers), so M1 rooms rebuild
  from `layers` down when the real Stage lands;
- `set`, `decide`, `override`, `undo`, `redo` and `accept`, with the Decision journal;
- the Manifest with ownership, `--force`, `--adopt` and the ID freeze; light and emitter Markers exported;
- `serve` with REST, SSE progress, Probes and the SAM 2 embedding cache;
- in the UI: fit, masks, palette, place and the walk test;
- done when a real room from the Toronto game walks correctly in Godot, **and** the agent acceptance test passes.

**The agent acceptance test** (run at every milestone gate from M1, not in CI, because each run costs money): an
agent with no project knowledge takes a room from `import` to `export` using only `--help`, `describe`, `next` and
`check` output, without reading the source or this spec. A stand-in owner is a fixture file of the owner's Decisions,
fed in through `decide` and `accept` with `KIRIPIX_TEST_OWNER=1`. It runs on a cheap model with a fixed token budget,
and the tokens used are recorded at each milestone, as the measure of goal 1 ("cheaper"). Its failures are tool bugs.

**M2: layers and props.**
- Room layers: Plate from a difference, segment and LaMa inpaint, grow, y-sort lines.
- The prop recipe with chroma key and BiRefNet.
- Lights and emitters proven in Godot (built in M1); `export --prune`; the Manifest merge driver.
- Time per room: click-to-segment timed and fixed, a one-action room border, flood that works on painted art, and a trial
  of Claude doing a room's first pass. The gate records the time per room, as a second data point.

**M3: characters.**
- Blender render presets, Mixamo round trip, clips and the palette per character.
- Finish (outline, normal alignment), sheet and `SpriteFrames` export; the pivot drift check.
- One character with idle, walk and attack in 8 directions in Godot.

**M4: rooms for grid battles.** Re-cut on 2026-11-08, when the game moved to tactical combat on a grid in the room (its
DEC-048): rooms grow past one screen in both directions, and a battle area in the room becomes a grid of cells built from
`solid`. The work is [0133](../backlog/m4/0133-m4-rooms-for-grid-battles.md).
- A trial of a room extended in both directions, taken to export
  ([0134](../backlog/m4/0134-m4-trial-room-extended-both-ways.md)): the corner join, SAM 2 at that size, the collision piece count.
- `extend`, a preprocessing tool before `source`: Kiripix writes the canvas for the next piece, the Owner makes the piece in the
  image model's own UI (the budget is $0), and Kiripix joins it. No Provider is needed; from M6 `gen` may drive it. The trial
  [0063](../backlog/m2/0063-m2-multi-screen-source-trial.md) found that the join needs three steps. Register: the model redraws
  the kept strip and scales the whole piece by up to about 1 %, so a plain shift leaves a step. Tone: the redrawn strip's
  brightness differs, so match it row by row. Seam: take the least-difference path through the overlap, with a short blend. A
  piece also fails when too little of a subject is in the kept strip, so the tool must let the Owner choose the strip and retry.
- The `area` Marker and its `Area2D`; the Masks and `room.json` exported into the game (§9).
- Room Looks (§6.1, ADR 0009): the `looks` Stage, edits by `import --look`, and their export to Godot. Trial
  [0128](../backlog/m4/0128-m4-room-look-edit-trial.md) comes first; the work is [0127](../backlog/m4/0127-m4-room-looks.md).
  The game's M05 bins that a boss knocks over are Props the game moves, not a Look (the Owner, 2026-11-12; as the bench,
  decision 8). So the game's first Look is its M09 (R6: the power comes back and the lights come on); Looks stay in M4 anyway.
- An optional SAM 2 crop on a large room, chosen by the Owner or an agent, only if the trial (0134) shows clicks get worse.
- First in M4: **palette ramps per part** for characters ([0147](../backlog/m4/0147-m4-character-palette-ramps.md); open
  decision 9, the game's DEC-053). A part is a Blender material; `render` writes a material pass, the character `palette`
  gives each swappable part its own ramp of palette colours that nothing else uses, and the export gives the game each
  part's ramp in `character.json` and as `ramps.png`.
- **Characters after the M3 gate** ([0161](../backlog/m4/0161-m4-characters-after-the-m3-gate.md)): change a decided clip's
  range, a Check for small parts that vanish from some frames, and trials of transitions between clips and of a flatter,
  more 2D character look.
- **A faster start** ([0163](../backlog/m4/0163-m4-start-faster.md)): every Command spends 0.65 s importing before it works.
- **A `sprite` Kind** ([0174](../backlog/m4/0174-m4-sprite-kind.md); the game's DEC-012 and DEC-044, needed by its M04): an
  actor from imported 2D frames (a PixelLab sheet or ZIP, or AI images), `frames → fit`, then the character's `palette`,
  `finish`, `sheet` and `export`, so the game loads it as a character. A missing direction is a finding, never mirrored; the
  pivot comes from the feet; normals from height or flat.
- **Four bodies, one swap shader** (added 2026-11-12, for the game's M03: 2 genders x 2 outfits): ramps that match across
  characters, from a Project ramp table ([0166](../backlog/m4/0166-m4-ramps-match-across-characters.md)), right after the
  ramps per part; a trial of a class's weapon in its battle clips ([0170](../backlog/m4/0170-m4-weapon-in-a-battle-clip-trial.md));
  a stop-gap that copies clip Decisions between characters until M5's bases
  ([0171](../backlog/m4/0171-m4-copy-clips-from-a-character.md)); and, lower priority, foot contact frames
  ([0172](../backlog/m4/0172-m4-foot-contact-frames.md)). The game's M03 waits on the clip edit (0156), the flatter-look trial
  (0160) and the weapon trial, so they go before the rooms work.
- **Rooms that move** ([0183](../backlog/m4/0183-m4-ambient-animation.md), added 2026-11-12 by the Owner): ambient animation
  for painted rooms. A shape, a direction and opaque palette colours on emitter Markers, for the game's particles. **Loops**, a
  `loops` Stage after `looks`: colour cycles baked into frames, and frame loops from whole-pixel Ops (`sway`, `shimmer`,
  `scroll`), a hand-painted kit or image-model edits. Frame 0 is always the room, timing is in whole ticks, and the game plays the
  frames from its frame counter. A trial in the game's kitchen comes first
  ([0184](../backlog/m4/0184-m4-ambient-animation-trial.md)) and sets the defaults the child tickets (0185 to 0196) mark
  "set by 0184". Animated separable objects are
  `sprite` Assets, and a runtime shader on the Plate is out.

**M5: character layers.** Added on 2026-11-11 for the game's customizable MC (its DEC-052, needed by its M10): hair styles
and outfits rendered once each as layers over a body, with the body as a holdout, on the body's clips, camera, frames and
pivots, so the cost adds per layer and no combination is rendered. A trial comes first
([0153](../backlog/m5/0153-m5-character-layer-trial.md)); the work is [0152](../backlog/m5/0152-m5-character-layers.md).
The two bodies are base Models built by Claude in headless Blender
([0164](../backlog/m5/0164-m5-claude-built-base-models-trial.md)), and a character made from a base shares its rig and clips,
so it needs no Mixamo round trip of its own ([0165](../backlog/m5/0165-m5-characters-share-a-base.md)).

**M6: generation and agents.** Moved from M4 on 2026-11-08, and from M5 on 2026-11-11.
- Providers (one API provider plus PixelLab), prompt templates, the style bible, the cost ledger and budget.
- The MCP adapter, with its tool selection tuned on the agent acceptance test and on M2's first-pass trial
  ([0062](../backlog/m2/0062-m2-claude-first-pass-trial.md)).
- `gen --look` ([0143](../backlog/m6/0143-m6-gen-a-look-edit.md)), and `gen` driving `extend`.
- The image-to-3D trial ([0144](../backlog/m6/0144-m6-image-to-3d-trial.md)).

**Later:** side view (side-view Masks: one-way, ladder; the parallax split with depth; platform reachability; the lowest
priority, moved here from M7 on 2026-11-11), tileset recipe (autotile rules; see below), portraits, VFX sheets, UI icons, a batch view for
whole districts, normal maps for painted backgrounds, "promote to Prop" for a room's foreground Layer, renaming exported
IDs with aliases, custom named Masks (`cover`, `high`, `water`…) painted like `solid` and exported as images beside it, with
no meaning in Kiripix (as areas have none), for terrain the game reads on its grid (filed when a room needs one). (Battle backgrounds were dropped on 2026-11-08: the game fights in the room, and its DEC-048 rejects
separate battle maps.)

**The tileset recipe, estimated on 2026-11-08, not planned.** The game compares painted rooms with a modular kit for its
dungeons in its M09 (its ISS-017), and grid battles cluster in dungeons. A minimal recipe is a Kind `tileset`: brief → source
→ fit → palette → tiles (slice to tiles, dedupe, an edge-match check) → terrain (peering bits per tile, a Decision) → export
(a `TileSet` `.tres` with a terrain set and a physics layer), with props on top from the prop recipe. That's about 8–10
tickets and 2–3.5M tokens, close to M2's props plus a heavy UI for tagging peering bits. The unknown is the art: whether the
free image model can paint a tile sheet that tiles and matches the painted districts. A trial with no code (about 100k tokens)
answers that first, before the game's M09.

## 15. Lessons carried over from Lost-and-Found

- **Masks:** drawn in an editor, they drift off-palette. Snap them on import, store them binary, and fail a check on
  anything else.
- **Painted doors can be unreachable:** check reachability with the real body footprint before wiring exits.
- **Previews:** taking a still through a throwaway e2e spec was slow and costly. `kiripix preview` and the walk test
  replace it.
- **Agent sessions should get numbers, not pictures,** unless a picture is needed to decide.
- **Stable IDs and versioned data with migrations** paid off, so Kiripix keeps both.
- **Rooms need other looks** (its D10 "states"): shut doors, unlit lamps, unbuilt stations, each an image-model edit of the
  room's source cut to a rect. They became one of the art pipeline's most-used parts. The edit came back at another size, so it
  was resized to the source first. Where a look met a foreground piece, a second crop drew at that piece's depth. Large crops
  showed the edit's JPEG noise as blotches, so looks were kept small. Kiripix has Looks (§6.1), and reports an edit's drift
  outside its region instead of trusting it.

## 16. Open decisions

1. ~~The game's internal resolution and tile size~~: decided 2026-11-03, for the Toronto RPG: 640 x 360, 16 px tiles,
   characters 52 px tall. 360 px is 22.5 tiles, so a room that fills the screen is 640 x 368. Resolution and tile are set
   in `kiripix.toml`; character height has no setting until the character recipe (M3) adds one.
2. ~~The UI framework~~: decided 2026-11-02, React with TypeScript and Vite (ADR 0008).
3. ~~The outline method for 3D renders~~: decided 2026-11-07 by the owner: a 1 px silhouette from the render's object mask,
   drawn in `finish`. The mask is exact, so the line has no isolated pixels; Blender's own lines (inverted hull, Freestyle)
   are sized in scene units and break up at 52 px. Trial [0106](../backlog/m3/0106-m3-outline-method-trial.md) confirmed it on a
   real character (`character.mc02`, 2026-11-11): the silhouette is kept and inner lines are out. On the idle it has no
   flicker on still parts; inner lines would add a third more line pixels.
4. Image-to-3D: which local Runner fits 8 GB well enough, a Provider, or none (M6, deferred from M3).
5. Which API provider comes first (M6).
6. Licence for Kiripix itself, if it's ever published.
7. ~~How a multi-screen room is made~~: decided 2026-11-06 by the owner, after the trial
   [0063](../backlog/m2/0063-m2-multi-screen-source-trial.md). The game allows multi-screen rooms (its DEC-024), and **expects
   about as many of them as single-screen rooms**, so neither is the exception. Exits still join rooms at natural breaks such as
   doors, stairs and corners. A room's size is only the brief's width and height, so **one room has one Source and one set of
   Masks**: any extending happens before `source`, and walls and Masks go on the whole image after it.

   **The method, for now: extend from the edge.** Each piece is generated from the edge of the last, in single generations, and
   the pieces are joined by hand until the M4 tool. A flaw in a piece, such as a light that throws no pool, is fixed room by room.
   - **Not tried:** a higher-resolution model, since the budget is $0.
   - **Independently generated images:** not tried either. Expect a hard visual break at the join, because their horizon,
     perspective, light and scale won't match.

   **What the trial found:**
   - **The Source:** it must be at least the room's size, and about 2.15 Source px per target px means a free-tier image of
     1,376 px covers one screen. One extension reached 1024 target px across and another 528 down, and neither join is visible
     after `fit` and `palette`.
   - **SAM 2:** its encoder stretches the whole image to 1024 x 1024, but on these rooms clicks were accurate and no worse than
     on a single-screen room, so a crop around the click isn't needed yet.
   - **`fit`:** grid mode doesn't fit an AI painting, so these rooms use `downscale`, which must keep one scale on both axes
     ([0081](../backlog/m3/0081-m3-downscale-keeps-one-scale.md)).
   - **The rest:** `reach` and `export` stay under a second at 1024 x 320, though on test Masks, so its collision piece count
     (530) is a lower bound. Pieces follow the Masks' edges, not the room's width. The canvas needs better navigation
     ([0082](../backlog/m3/0082-m3-ui-canvas-navigation.md)).
   - **In the game:** a scrolling camera is the game's work. The exported scene has no room size or camera limits, but the Plate's
     texture gives the size.

   **Updated 2026-11-08, for the game's grid battles (DEC-048):** rooms now grow past one screen in both directions, often 2 x 2
   screens. 0063 extended one direction per room; trial [0134](../backlog/m4/0134-m4-trial-room-extended-both-ways.md) joins a
   corner piece to two neighbours and takes the room to export. The join tool moves to M4 without a Provider, because the
   budget is $0 and the pieces are made in the image model's own UI anyway. `harbor_front`'s 1,533 collision pieces were an
   anomaly of the brush tool at the time, and the Owner expects normal rooms to have far fewer; 0134 counts them on a full
   room, and a lighter collision export (one `ConcavePolygonShape2D` per Mask) is planned only if the count is high.
8. **Room Looks beyond one picture and added collision** (§6.1, M4). Not settled: whether Looks stack or combine (an unbuilt
   station with the lamps off, Lost-and-Found's `relight`); whether a Look can take collision away (rubble cleared) or change
   walkable, navigation and `reach`; whether a Look has its own Markers, such as a light that goes off with an unlit Look; and
   whether a soft edge is allowed with binary alpha. Each waits for a room that needs it. (2026-11-08: a boss phase that moves a
   bench doesn't need a Look to take collision away. The bench is a Prop, and the game moves it. 2026-11-12, decided by the
   Owner: the same for the game's M05 bins that a boss knocks over. A toppled bin frees the cells it stood on, which is a Look
   taking collision away, and bins are cover on single cells, which the game keeps on its grid; so they are Props the game
   moves, and the laneway is painted without them.)

9. **Character customization**, narrowed on 2026-11-11 (the game's DEC-013, DEC-027 and DEC-051 to DEC-054). The player
   picks gender, skin colour, hair, clothes and a class. Rendering every combination is out: a full body with about 15 clips is
   about 10 minutes of rendering (mc02: 70 ms a frame at 52 px, plus `palette` and `finish`). Decided:
   - **Colours by palette swap in the game,** with no extra render. Each swappable part (a Blender material, or several) owns a
     ramp of palette colours that no other part, fixed colour or the outline uses (M4,
     [0147](../backlog/m4/0147-m4-character-palette-ramps.md)). **Ramps match across characters** (2026-11-12): a Project
     ramp table fixes each part's name, length and `ramps.png` row on every character, and optionally its colours, so one
     shader and one appearance record serve every body ([0166](../backlog/m4/0166-m4-ramps-match-across-characters.md)).
     Decided by the Owner the same day: a table, not a character reading another's ramps; skin and hair share their colours
     on every character, and every other part, clothing included, shares only its name, length and row.
   - **Gender as whole bodies** (2). **A class changes only the battle clips** (3 sets per body, the weapon in the frames), not
     the body, the exploration clips or the outfits; one character holds them all, by clip name. How the weapon gets into the
     frames (a clip's attachment, a rigged file per class, or a layer) is a trial
     ([0170](../backlog/m4/0170-m4-weapon-in-a-battle-clip-trial.md)).
   - **Four character Assets at the game's M03** (2 bodies x 2 outfits) each decide their clips. Until characters share a base
     (M5, [0165](../backlog/m5/0165-m5-characters-share-a-base.md)), `kiripix clips copy` copies clip Decisions between them
     ([0171](../backlog/m4/0171-m4-copy-clips-from-a-character.md); chosen 2026-11-12), and each body's second outfit is
     modelled on the first's rigged file, so it needs no Mixamo trip.
   - **Camera:** `top34_8` for every character; the game changed its own rule to match.
   - **Outfits are whole-body variants** until hair styles and outfits become **layers** (M5,
     [0152](../backlog/m5/0152-m5-character-layers.md)), rendered with the body as a holdout.
   Still open, for M5's trial: outfits that change the silhouette (a long coat), the outline and the normal map per layer or in
   the game, and how Kiripix holds a layer.

## Changes since v0.4

- M4, 2026-11-12: rooms that move (0183), decided by the Owner. Loops are a `loops` Stage of their own, not animated Looks.
  A `pulse` may brighten a light source's own pixels, never the surfaces around it (the game's Option A). Particles draw opaque
  palette colours. Cycles are baked into frames. `loop.flash` is an error. When a Look over a Loop shows, the game hides the
  Loop by its ID. A Loop may name a light Marker to flicker in step. §6.1 and §9 get the details with 0189 and 0190.
- M4 rooms, 2026-11-12, after the game's M04 and M05 plans: the walkable Checks apply only to an area marked `walkable`; an
  Exit's trigger box is an area the game pairs by ID; a Look's Condition is an optional label, since the game binds Looks by
  ID; the M05 bins are Props, not a Look, and Looks stay in M4; custom named Masks under Later. All decided by the Owner.
- Open decision 9: character customization (2026-11-11), narrowed the same day. Palette ramps per part come first in M4.
  On 2026-11-12, for the game's four M03 bodies: ramps that match across characters (a Project ramp table), a trial of a
  class's weapon in its battle clips, `clips copy`, and foot contact frames in `character.json`.
- A new M5, character layers (2026-11-11). Generation and agents move to M6; side view moves to Later, as the lowest priority.
- M4 is re-cut as "rooms for grid battles" (2026-11-08, after the game's DEC-048). Generation and agents move to M5, side view
  to M6.
- A new `area` Marker: a box with a stable ID, optionally on a cell grid, exported as an `Area2D`.
- The `solid` and `pit` Masks and `room.json` are exported into the game. `room.json` is now part of the game's contract.
- `kiripix extend` joins a large room's pieces before `source`, without a Provider.
- The `battle` camera preset and battle backgrounds are dropped. The tileset recipe has an estimate.

## Changes since v0.3

- Time per room is measured at each gate. M2 gains a room border, a flood tolerance, click-to-segment timing and a trial of
  a Claude first pass.
- Rims are trimmed with a `trim` Decision, not an Override (ADR 0004), and "partial" alpha is defined for binary Runners.
- `kiripix manifest install` and `kiripix plate-import` are new. The merge rule covers IDs and `files` (ADR 0003).
- Lights and emitters were built in M1. The prop foreground split and `LightOccluder2D` are deferred.
- The spec's code layout, stack and import rule now match the repo.
- Open decision 7 closed: multi-screen rooms are as ordinary as single-screen ones, made by extending from the edge. An M4 tool
  extends a Source through a Provider.
- Room Looks (ADR 0009): a `looks` Stage after `palette` for a room's other appearances, shown by an opaque Condition, with
  their own `solid`, pieces at a Layer's depth, drift reported, and `room.json` schema 3. M4. Open decision 8 lists what's
  left.

## Changes since v0.2

- A new `pit` Mask: the body can't walk on it but can dash over it, and a dash never crosses `solid`.
- The choice of Runner model stays open (§8).
- The game is 640 x 360 with 16 px tiles and 52 px characters (open decision 1 closed).
- The UI is React with TypeScript and Vite (open decision 2 closed; ADR 0008).
- `palette` reads `layers`, not `masks`, so Mask edits don't rebuild it.
- In M1, `layers` is a pass-through; the real Stage is M2.
- M1 is split into tickets: [backlog/0010](../backlog/m1/0010-m1-room-end-to-end.md) and its children.

## Changes since v0.1

- Vocabulary: Layer (visible), Mask (gameplay, binary), Override (hand edit); Model (3D) versus Runner (ML); the
  room's `check` stage is now `reach`. `[layers.*]` is now `[masks.*]`.
- `foreground` and `walkable` are derived Masks; walkable no longer includes reachability.
- `clean` is split into `fit` and `palette`, with Runners in between; outlines move to a new `finish` stage.
- Runner and Provider calls are pinned and committed; `run` never re-runs them silently; `--rerun` and `accept` added.
- New status `needs-review`; stage status is derived, never stored; history moves to `history.jsonl`.
- Every foreground Layer needs a y-sort line or an "always above" flag.
- Exit pairing is a Project check.
- The Manifest lives in the Godot project, one file per asset, decides ownership by hash, freezes exported IDs, and
  has a merge driver.
- Built for agents and UIs: one Command registry generates the CLI, REST and MCP; a versioned JSON contract with
  schemas, `describe` and stable finding codes; nothing is UI-only (`set`, `decide`, `override`, `undo`, `redo`).
- Owner-only Commands (`accept`) need a terminal or the UI's session token.
- Decision journals are append-only, with ULIDs and parents; divergent merges go to `needs-review`.
- Locks (project, Asset, GPU), exit code 4, `--wait`; atomic writes; progress and cancellation; `serve` with Probes and
  a warm Runner; the agent acceptance test is part of M1's definition of done.
