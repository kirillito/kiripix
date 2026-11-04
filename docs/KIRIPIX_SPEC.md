# Kiripix — Pixel Asset Studio

Spec v0.3, 2026-11-02. Status: reviewed with the owner; M0 is done, and M1 is split into tickets in `backlog/`.

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
2. **Faster.** Most assets go from source to Godot in minutes. The owner's time goes to choosing and clicking.
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
   decisions (clicks, picks, Overrides) and its pinned Runner and Provider results. Change anything upstream, the
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
11. **Never re-run a Runner or Provider silently.** A rebuild re-runs only deterministic Ops. Running a Runner again
    is always an explicit request, and calling a Provider (which costs money) only ever happens through `gen`.

## 3. Concepts

[GLOSSARY.md](../GLOSSARY.md) is the canonical vocabulary. The terms this spec leans on most:

| Term | Meaning |
|---|---|
| **Asset**, **Kind**, **Recipe**, **Stage** | An asset has a kind; the kind fixes its recipe, an ordered list of stages. Kinds: `room`, `prop`, `character` first; `tileset`, `portrait`, `vfx`, `ui` later. |
| **Decision** | Recorded human input that a stage replays: a Pick, segmentation clicks, an Override, marker positions. |
| **Override** | A recorded hand edit on a stage's image output, tied to the hash of the image it was painted on. |
| **Layer** / **Plate** | A visible image plane of a room; the Plate is the room with its foreground objects removed. |
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
      src/                   variants and the picked source (immutable once picked)
      decisions/             one Decision journal per stage (<stage>.jsonl), plus Override PNGs
      pinned/                pinned Runner and Provider results, keyed by input hash
      work/                  deterministic stage outputs (cache, safe to delete)
      out/                   final outputs, the exporter's input
    prop/ttc_bench/ ...
    character/raccoon_boss/ ...
  .kiripix/                  hash cache, last-run failures, locks, Runner weights, backups, the cost ledger (git-ignored)
```

**Committed:** `src/`, `decisions/`, `pinned/`, `out/`, `asset.toml` and `history.jsonl`. **Not committed:** `work/`
and `.kiripix/`. Python dependencies are locked in `uv.lock`, because deterministic ops are bit-exact only on the same
numpy and OpenCV versions.

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
(CUDA or CPU) is not part of the key. The deterministic Ops around a call rebuild freely.

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
prompt, seed, parameters, cost and time. The file is `merge=union` in git, so lines from both branches survive
a merge.

## 6. Recipes

Every recipe keeps Runners before the palette (ADR 0004): a palette tweak then invalidates only deterministic work.
`palette` means the same thing in every recipe, and outlines are drawn after it, in `finish`.

### 6.1 Room

A background scene with Layers, Masks, Markers and lights. A room is either `view = "top"` or `view = "side"`.

**brief → source → fit → layers → masks → palette → place → reach → export**

| Stage | What it does | Owner input | Checks |
|---|---|---|---|
| **brief** | Size in px or tiles, view, mood, exits and their sides, notes. Renders the generation prompt from the kind's template and the style bible. | Writes the brief | Size is a whole number of tiles |
| **source** | Generates N variants with a Provider (through `gen`), or **imports** an image made elsewhere (a first-class path: the owner may keep using an external image tool). | Picks between several (an agent may pick a lone variant) | Has a picked source |
| **fit** | Detects the source's pixel grid, or downscales with a mode filter to the target size. Records the Grid transform. Palette-free. | Tunes the grid, with a before/after view | Exact size |
| **layers** | Builds the **Plate** and the foreground Layers. Paths: (a) the source was generated as a plate plus props, so the Layers come from their difference; (b) segment the foreground objects (SAM 2), then inpaint the Plate (LaMa locally, or an edit API for large areas); (c) side view: depth-assisted parallax split into N planes. One **grow** parameter widens both a Layer's alpha and its Plate hole, in target pixels, only where the Runner's alpha was partial (default 1 px, 0 allowed). | Clicks objects to lift out | Plate + Layers recompose exactly to the fit image; no holes in the Plate |
| **masks** | Paints the painted Masks (`solid` and `pit` for top view; `solid`, `oneway`, `ladder` for side view): click-to-segment (SAM 2), flood by colour region, polygon, brush, or import of a painted image; optional snap to an N px cell grid. | Clicks and brushes | Every Mask binary |
| **palette** | Maps the whole composite once to the palette in OKLab (strict, or with optional ordered dithering) and removes orphan pixels. Each foreground Layer is that mapped image cut by its alpha; the Plate is the same image with only its inpainted areas mapped separately. | Tunes 2–3 sliders, with a before/after view | Every pixel on the palette; Plate + Layers still recompose exactly |
| **place** | Puts Markers on the room: Exits (with a target room and Exit ID), Spawns, interactables, lights (colour, radius, energy), particle emitters, y-sort lines. | Places Markers | Unique IDs; Exits and Spawns on walkable ground; every foreground Layer has a y-sort line or an "always above" flag |
| **reach** | Reachability: the body's footprint, flood-filled over walkable at sub-tile steps, from each Spawn and Exit to all the others (side view: over platforms, with jump settings, M5+). Lists unreachable Markers, unreachable walkable islands and the narrowest gaps. | — | All Markers reachable |
| **export** | Writes the Godot scene (see §9). | — | Export target set; Project checks (see below) |

**palette reads `layers`, not `masks`**: its upstream is the Plate and the Layers, so a Mask edit never rebuilds the
palette mapping. `place` reads both `palette` and `masks`.

**Walkable** depends only on the `solid` and `pit` Masks and the body's footprint, so changing `[body]` re-derives it
cheaply. Reachability lives only in `reach`. A dash crosses a `pit` and never `solid`.

**A foreground Layer belongs to its room.** It is painted into that room's art and isn't reused; its collision comes
from the room's `solid` Mask and its draw order from its y-sort line. A reusable object is a Prop. ("Promote to Prop"
may come later, not in the first milestones.)

**Exit pairing is a Project check.** Every Exit must name an existing room and Exit ID that points back. `check --all`
and `export --all` run it; exporting a single room only warns, so a room can be worked on before its neighbour
exists.

**Walk test (UI):** the stand-in body walks the room with the arrow keys, on the real collision, at game resolution,
with the foreground Layers drawn over it by their y-sort lines.

### 6.2 Prop

A standalone, reusable object for scenes: benches, signs, lamps, bins.

**brief → source → cutout → fit → palette → finish → footprint → export**

| Stage | What it does |
|---|---|
| **brief** | Size, viewing angle (top-down 3/4 or side), notes. |
| **source** | Generated on a flat chroma background, or imported. |
| **cutout** | Chroma key (exact, for flat backgrounds) or matting (BiRefNet) on the full-size source. |
| **fit** | Grid snap or downscale, as for rooms; the alpha goes to the target grid by majority vote, so it is binary (pixel art has no partial alpha). |
| **palette** | Palette mapping and orphan cleanup, as for rooms. |
| **finish** | Optional 1 px outline in a chosen palette colour. |
| **footprint** | The base's collision shape and the y-sort origin; optional foreground split (a lamp's head drawn over the player). |
| **export** | `Sprite2D` scene with collision and origin. |

Checks: binary alpha, palette, size within limits, and an origin is set.

### 6.3 Character (3D to pixel)

Characters, NPCs and enemies are rendered from 3D, so every animation stays on-model. They are rendered at the target
pixel size (52 px tall in the Toronto RPG), so the recipe has no `fit`.

**model → rig → clips → render → palette → finish → sheet → export**

| Stage | What it does | Owner input |
|---|---|---|
| **model** | Imports `.glb`, `.fbx` or `.blend`; optional image-to-3D (a local Runner if one fits 8 GB, or a Provider). Normalises scale and the up axis. | Picks or imports |
| **rig** | Validates a humanoid rig, or guides the Mixamo auto-rig round trip (the tool shows the steps and picks up the downloaded file). Rigify for non-humanoids. | Mixamo step, when used |
| **clips** | Maps named clips (`idle`, `walk`, `run`, `attack_1`, `hit`, `ko`, `cast`…) to animation sources, with frame range, frame rate and loop flag. | Chooses clips |
| **render** | Blender headless. Orthographic camera from a preset: top-down 3/4 at 4 or 8 directions, side view, battle-pose camera. Rendered at the target pixel size, no anti-aliasing, toon shading. Passes: colour, normal, depth and an object mask. Frames are subsampled to the clip's frame rate. | Tunes the camera preset once per project |
| **palette** | One palette per character across all frames (a project-palette subset), orphan cleanup. | — |
| **finish** | Outline, drawn after mapping, in a palette colour; outline consistency across frames. The normal pass is quantised to its own levels (not palette-mapped) and aligned to the colour frames. | — |
| **sheet** | Packs frames into an atlas with a fixed pivot (the feet) per frame, plus frame metadata. | — |
| **export** | Godot `SpriteFrames` `.tres`, plus a `CanvasTexture` with the normal map for 2D lights, plus a scene with `AnimatedSprite2D`. | — |

Checks:
- **pivot drift:** the feet don't move between frames of a stationary clip;
- every frame fits its cell;
- palette;
- frame counts match the clip;
- no empty frames;
- normal map size equals the colour frame's.

## 7. Ops library (first set)

- **colour:**
  - palette load and save;
  - OKLab conversion;
  - nearest-colour mapping;
  - ordered dithering (Bayer 2/4/8);
  - palette extraction (k-means in OKLab, then a manual merge);
  - palette conformance report.
- **resample:**
  - pixel-grid detection (scale and offset of upscaled pixel art), returning a Grid transform;
  - mapping points, images and masks through a Grid transform (a click maps to the centre of its target pixel);
  - nearest, mode-filter and majority-vote downscale;
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
| Click-to-segment | SAM 2 (small or base) | Colour flood plus GrabCut (OpenCV) |
| Background matting | BiRefNet | Chroma key |
| Depth (parallax, normals) | Depth Anything V2 (the small model; check licences of larger ones) | Manual depth planes |
| Inpainting (plate holes) | LaMa | OpenCV Telea or PatchMatch for small holes; an edit API for large ones |
| Image-to-3D (optional) | Decide at M3, after testing which fit 8 GB | Bought or hand-made models |

ONNX Runtime with CUDA is preferred to keep installs small, with PyTorch where a model needs it. The core works with
no GPU: Runners run on CPU, slower. Because results are pinned, the device that produced one doesn't matter.

## 9. Godot export

Kiripix writes Godot 4 text resources (`.tscn`, `.tres`) and PNGs under `export.godot.root`.

| Asset | Godot output |
|---|---|
| Room | A scene with these nodes: `Sprite2D` Plate; foreground `Sprite2D`s, y-sorted by their y-sort lines or above actors when flagged "always above"; `StaticBody2D` + `CollisionPolygon2D` from the `solid` Mask; `NavigationRegion2D` + `NavigationPolygon` from walkable ∩ reachable; `Marker2D` for Spawns and Exits (with metadata: IDs, targets); `PointLight2D` from light Markers; `LightOccluder2D` (optional); `GPUParticles2D` stubs from emitter Markers. `solid` is on collision layer 1 and `pit` is a `StaticBody2D` of its own on layer 2: the game's Body drops layer 2 from its mask while it dashes. Side view: `oneway` → one-way collision; parallax planes → `Parallax2D`. |
| Prop | A scene: `Sprite2D` + `StaticBody2D` footprint, origin at the y-sort point. |
| Character | `SpriteFrames` `.tres`, `CanvasTexture` (diffuse + normal), a scene with `AnimatedSprite2D` and its feet at the origin. |

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
- **Deleting an asset:** its files stay until an explicit `export --prune`, under the same hash rule and backup.
- **Frozen IDs:** once exported, an ID can't be renamed or removed; adding new IDs is always fine. Before the first
  export, IDs can be renamed freely. Deleting an asset and creating one under a new ID is allowed, with a warning if
  the old ID is still referenced.
- **Branch merges:** when two game branches export the same asset, `kiripix manifest merge` (a git merge driver)
  resolves it: the higher counter plus one. Export checks that the driver is configured in the clone and offers to
  install it (`.gitattributes` alone does nothing). GitHub never runs custom drivers, so for a conflict in a pull
  request, merge locally or run `kiripix manifest repair`.

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
- **The GPU lock**, held while a Runner or a Blender GPU render is loaded, because they all share 8 GB. `serve`
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
kiripix describe project|<kind>             Kinds, Recipes, stage parameters, Decision schemas, Checks
kiripix schema [command]                    JSON Schemas of Command inputs and outputs
kiripix status [--kind room]                board: every asset, its stage and state
kiripix show <id>                           one asset: variants, the pick, each stage's parameters, decisions and images
kiripix new <kind> <id> [--view top|side]   new asset from its recipe
kiripix next <id>                           the next stage and what it needs (a command, or the owner's action)
kiripix run <id>|--all [stage] [--force] [--rerun] [--cpu]   run stale and todo stages; --rerun also re-runs stale Runner calls
kiripix set <id> <stage> key=value...       set stage parameters
kiripix decide <id> <stage> --decision '<json>' | --file d.json   record a Decision (validated against the stage's schema)
kiripix override <id> <stage> <png>         record an Override from a painted image
kiripix mask-import <id> <png>              import a painted mask image (the masks Stage's import Decision)
kiripix undo <id> <stage>                   undo the stage's last Decision
kiripix redo <id> <stage>                   redo it
kiripix accept <id> <stage>                 confirm a needs-review stage (owner-only)
kiripix import <id> <file>                  set a source from an outside image or model
kiripix gen <id> [-n 4] [--provider x]      generate source variants (the only command that calls Providers)
kiripix pick <id> <variant>                 record the chosen variant
kiripix check <id>|--all                    run checks (--all includes Project checks), list findings with positions
kiripix preview <id> [--stage s] [--overlay masks]   write a preview PNG, print its path
kiripix probe <name> <id> <args...>         run a Probe, such as segment-preview
kiripix export [<id>|--all] [--dry-run] [--force] [--adopt] [--prune]   write to the Godot project
kiripix manifest [merge|repair]             the git merge driver, and the manual fallback
kiripix op <op> <args...>                   one op directly (quantize, snap-mask, reach, ...)
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
timeout or until another process asks for the GPU lock. That is the only exception to "unload after use", and it
applies only to the long-running server.

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
- **Place:** Markers with an ID field and a dropdown of target rooms; y-sort lines drawn on each foreground Layer.
- **Reach:** the walk test.
- **Character:** a frame strip with onion skin, a direction picker and a clip player at game speed.

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
| Images | numpy, Pillow, OpenCV, scikit-image |
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
  export/      godot/ (tscn and tres writers), manifest (ownership, freeze, merge)
  cli/         Typer adapter, generated from commands/
  server/      FastAPI and MCP adapters, generated from commands/; the warm Runner and the embedding cache
web/           UI (TypeScript)
tests/         unit/, golden/, e2e/
```

The import rule: `ops` and `checks` import nothing from the rest; `recipes` use `ops`, `checks`, `runners` and
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
- the Manifest with ownership, `--force`, `--adopt` and the ID freeze;
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
- Lights and emitters exported; `export --prune`; the Manifest merge driver.

**M3: characters.**
- Blender render presets, Mixamo round trip, clips and the palette per character.
- Finish (outline, normal alignment), sheet and `SpriteFrames` export; the pivot drift check.
- One character with idle, walk and attack in 8 directions in Godot.

**M4: generation and agents.**
- Providers (one API provider plus PixelLab), prompt templates, the style bible, the cost ledger and budget.
- The MCP adapter, with its tool selection tuned on the agent acceptance test.

**M5: side view.** Side-view Masks (one-way, ladder), the parallax split with depth, platform reachability.

**Later:** tileset recipe (autotile rules), portraits, VFX sheets, UI icons, battle backgrounds, a batch view for
whole districts, normal maps for painted backgrounds, "promote to Prop" for a room's foreground Layer, renaming exported
IDs with aliases.

## 15. Lessons carried over from Lost-and-Found

- **Masks:** drawn in an editor, they drift off-palette. Snap them on import, store them binary, and fail a check on
  anything else.
- **Painted doors can be unreachable:** check reachability with the real body footprint before wiring exits.
- **Previews:** taking a still through a throwaway e2e spec was slow and costly. `kiripix preview` and the walk test
  replace it.
- **Agent sessions should get numbers, not pictures,** unless a picture is needed to decide.
- **Stable IDs and versioned data with migrations** paid off, so Kiripix keeps both.

## 16. Open decisions

1. ~~The game's internal resolution and tile size~~: decided 2026-11-03, for the Toronto RPG: 640 x 360, 16 px tiles,
   characters 52 px tall. 360 px is 22.5 tiles, so a room that fills the screen is 640 x 368. Resolution and tile are set
   in `kiripix.toml`; character height has no setting until the character recipe (M3) adds one.
2. ~~The UI framework~~: decided 2026-11-02, React with TypeScript and Vite (ADR 0008).
3. The outline method for 3D renders: inverted hull, Freestyle or a post-process edge pass (M3, by test).
4. Image-to-3D: which local Runner fits 8 GB well enough, or none (M3).
5. Which API provider comes first (M4).
6. Licence for Kiripix itself, if it's ever published.

## Changes since v0.2

- A new `pit` Mask: the body can't walk on it but can dash over it, and a dash never crosses `solid`.
- The choice of Runner model stays open (§8).
- The game is 640 x 360 with 16 px tiles and 52 px characters (open decision 1 closed).
- The UI is React with TypeScript and Vite (open decision 2 closed; ADR 0008).
- `palette` reads `layers`, not `masks`, so Mask edits don't rebuild it.
- In M1, `layers` is a pass-through; the real Stage is M2.
- M1 is split into tickets: [backlog/0010](../backlog/0010-m1-room-end-to-end.md) and its children.

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
