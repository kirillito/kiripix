# Kiripix — Pixel Asset Studio

Spec v0.5, 2026-11-08. Status: reviewed with the owner; M0 to M3 are done, every M4 ticket is done and M4 waits for its gate
([0142](../backlog/m4/0142-m4-gate.md)), and M5 is split into tickets in `backlog/m5/` (re-planned on 2026-11-16 from the game's list,
[0236](../backlog/m5/0236-m5-the-games-next-needs.md)). M6 was re-planned on 2026-11-18 and split into tickets in `backlog/m6/` on 2026-11-19
([0324](../backlog/m6/0324-m6-rooms-at-chapter-scale-style-npcs.md); §14).

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
- Animation authoring. Animation comes from 3D (Blender and Mixamo clips) or is imported. Clips made from a sprite's still by
  Ops (a bob, a lunge, a squash) are out too (the Owner, 2026-11-16): the game tweens them. A pose made as an image-model
  edit imports as a one-frame clip.
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
   rounds.) **One exception, portraits** (the Owner, 2026-11-16, M5): a dialogue portrait is generated with gradients that a
   strict sprite palette can't hold, so a portrait set's pixels are the set's own colours, chosen once over the whole set
   ([0240](../backlog/m5/0240-m5-portrait-kind.md)). Its alpha is still binary, and the check is against the set's colours.
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
| **Asset**, **Kind**, **Recipe**, **Stage** | An asset has a kind; the kind fixes its recipe, an ordered list of stages. Kinds: `room`, `prop`, `character` first, then `sprite` (an actor from imported 2D frames, M4) and `icon` (an item or skill icon on a fixed square, M5) and `wearable` (a part of a character's dress, M5: hair, an outfit, an accessory; it names its body, a character, in `body`, and follows it) and `portrait` (a character's dialogue portraits, one image per emotion, M5); `npc` (a background figure chosen from a base character, its Wearables and named colours, with no render, M6, ADR 0015); `tileset`, `vfx` later. |
| **Decision** | Recorded human input that a stage replays: a Pick, segmentation clicks, an Override, marker positions. |
| **Override** | A recorded hand edit on a stage's image output, tied to the hash of the image it was painted on. |
| **Layer** / **Plate** | A visible image plane of a room; the Plate is the room with its foreground objects removed. |
| **Look** / **Condition** | Another appearance of part of a room (a door shut, a lamp unlit), painted as an edit of its Source; an optional label naming the game state that shows it, for people and other Exporters. |
| **Mask** | A named binary gameplay region (`solid`, `oneway`, `ladder`). Derived masks (`walkable`, `foreground`) are computed, never painted. Only `solid` and `pit` block anything in Kiripix; a Mask the Project adds with `masks-add` (`cover`, `water`) has no meaning to `reach` or the walk test, as an area has none: it is the game's to read. |
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
                             room.<ext> is the room brief's (any extension, such as room.j2), rendered by `brief` with Jinja2
                             (sandboxed, strict: an unknown field is an error). Fields: `asset`, `view`, `width`, `height`
                             (px), `tile`, `tiles_wide`, `tiles_high`, `aspect`, `canvas_width`, `canvas_height`,
                             `canvas_aspect`, `mood`, `notes`, `exits` (a list of `name` and `side`) and `bible` (the text of
                             bible.md). `gen` renders two more the same way (M6): <kind>-edit.<ext> for an edit
                             (`--look`, `--state`, `--emotion`; fields `asset`, `edit`, the Owner's words, the
                             `look`, `state` or `emotion`, and `bible`; without it "Edit this image. Keep
                             everything exactly the same except: <edit>"), and room-extend.<ext> for an `extend`
                             piece (`asset`, `prompt`, the room's built prompt, `sides`, `edit`, `bible`).
  assets/
    room/queen_west_alley/
      asset.toml             kind and parameters (no stage status, ADR 0005)
      history.jsonl          append-only log of runs and generations
      imported.jsonl         append-only: the file name each src/ file was imported with (outside src/, so a rename stales nothing)
      time.jsonl             append-only: the Owner's active time, for `stats` (M4)
      src/                   variants and the picked source (immutable once picked)
        looks/<look>/        a Look's edit Variants (outside src/*.png, so a new one never touches the Source)
        loops/<loop>/        a frame Loop's kit frames and edit Variants (M4)
      extend/                `extend`'s journal, its pieces and joined images, and the latest canvas (M4)
      decisions/             one Decision journal per stage (<stage>.jsonl), plus Override PNGs
      pinned/                pinned Runner and Provider results, keyed by input hash
      work/                  deterministic stage outputs (cache, safe to delete)
      out/                   final outputs, the exporter's input
    prop/ttc_bench/ ...
    character/raccoon_boss/ ...
      src/clips/, src/rigged/  a character's clip sources and its rigged file
      src/parameters/        a generated character's parameter file, in place of imported Models (§6.3)
    sprite/raccoon/ ...
      src/sheets/            a sprite's imported PNG sheets and ZIPs, stored whole (§6.4)
  chargen/ ...               the Project's own Model generator, if it has one: any folder, named in kiripix.toml (§6.3)
  .kiripix/                  hash cache, last-run failures, locks, Runner weights, backups, the cost ledger (git-ignored)
```

**Committed:** `src/`, `decisions/`, `pinned/`, `out/`, `extend/`, `asset.toml`, `history.jsonl`, `imported.jsonl`, `notes.jsonl` and `time.jsonl`. **Not committed:** `work/`
and `.kiripix/`. Python dependencies are locked in `uv.lock`, because deterministic ops are bit-exact only on the same
library versions. Data files the owner's work lives in have migrations; a Stage's rebuilt output, such as `room.json`,
is refused when it's old, and the finding names the rebuild. From the M4 gate there are production rooms, so a data
file's format change always needs its migration.

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
                               # more painted Masks (M6): `kiripix masks-add cover --colour "#00AA00" --meaning "half cover"`

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

[extend]                       # `kiripix extend <id> canvas`: the canvas pasted into the image model (M4)
canvas = [1376, 768]           # width and height in px
max_residual = 0.5             # px `extend add` lets a piece's registration miss by (M6); 0.5 for a model that leaves the kept strip untouched, up to 1.0 for one that re-renders it (GPT Image); `--max-residual` overrides it

[inbox]                        # `kiripix inbox`: the images made elsewhere, filed by their file names (M6)
folder = "inbox"               # relative to the Project; `--folder` overrides it

[style]                        # the Project's look (M6, §6): `check` measures every other Asset against these (`style-add`, owner-only)
references = ["character.hero", "room.ch01_dungeon_r01"]   # Asset IDs of a Kind with style Checks; an unknown one is `style.reference_unknown`

[icon]                         # `kiripix new icon <name>` (M5)
size = 24                      # 16, 24 or 32 px; an icon's own `size` (brief) overrides it

[portrait]                     # `kiripix new portrait <name>` (M5, §6.7)
canvas = [192, 240]            # width and height in px; a portrait's own brief overrides it
# anchor = [96, 239]           # the pixel the figure stands on; the bottom centre when unset

[character]
height = 52                    # target height in px; a character's own `height` parameter overrides it
blender = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"   # otherwise found on PATH

[character.camera.top34_8]     # a camera preset, picked by name by a character's `camera` parameter
elevation = 30                 # degrees above the ground plane
directions = 8

[[character.ramps]]            # the ramp table (M4, §6.3): one row per part, the same on every character; `ramps-add` fills it
name = "skin"
length = 3                     # steps, at least 2
rgb = [[171, 82, 54], [255, 163, 0], [255, 241, 232]]   # optional: shared colours, dark to light
choices = { auburn = ["#ab5236", "#ffa300", "#fff1e8"] }   # optional (M6, ADR 0015): named ramps for this part, `length` colours of the Project palette each, [r, g, b] or "#rrggbb"; an `npc` names one per part

[[character.clips]]            # the clip table (M5, §6.3): a clip named here plays the same on every body; `clips-add` fills it
name = "idle"
frames = 8                     # rendered frames in one direction
fps = 4
loop = true
foot = false                   # optional: the clip must have foot frames (`events.foot`)

[character.generators.chargen] # a Model generator of the Project's own (§6.3): a Blender script and what it reads
script = "chargen/generate.py"
library = ["chargen/library.toml", "chargen/bases", "chargen/parts"]

[providers]                    # `kiripix gen` (M6; tickets 0379, 0378, 0381)
default = "import"             # import | openai: the Provider `gen` uses; import paints nothing (`--provider` overrides it)
budget_usd_month = 20          # hard cap: `gen` refuses a call whose estimate would take the month's spend (UTC) past it
approve = "each"               # each: `gen` writes a pending call for `kiripix approve <id>`; none: `gen` sends at once
max_images_per_call = 4
max_calls_per_day = 20         # UTC, counted from the cost ledger

[providers.openai]             # the Owner's choice; empty: the Provider's default
model = "gpt-image-2.6-sunburst"
quality = "medium"             # low | medium | high
size = ""                      # WIDTHxHEIGHT; empty: the image the call is for, fitted to what the model takes
```

Secrets (API keys) come only from the git-ignored `.env` at the Project's root (`OPENAI_API_KEY=...`), never from
`kiripix.toml` or the environment, and are written nowhere else: not in a log, a finding, the ledger or a pending call.

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

**Hand-over notes.** `kiripix note <id> <stage> "<text>"` appends a note (`schema_version`, a ULID, the Stage, the text, the
Stage's input hash when written) to the Asset's append-only `notes.jsonl`, committed and `merge=union`. A note is not a
Decision: it changes no output and no input hash, and `undo` doesn't reach it. It is *live* while its Stage has no newer
Decision (or undo or redo) and no `accept`, derived from the two files and never stored; `show` lists each Stage's notes
with `live`. A note over 2,000 characters is refused (`note.too_long`).

**History.** Every generation and every Runner call is appended to the asset's `history.jsonl`: `runner` (our
ID) for a Runner call, or `provider` and `provider_model` (the vendor's own model name) for a Provider call, plus the
prompt, seed, and either the parameters or, when the result was pinned, its `key` (the parameters are in
`pinned/<key>.json`), plus cost and time. The file is `merge=union` in git, so lines from both branches survive
a merge.

## 6. Recipes

Every recipe keeps Runners before the palette (ADR 0004): a palette tweak then invalidates only deterministic work.
`palette` means the same thing in every recipe, and outlines are drawn after it, in `finish`.

**Style Checks (M6, tickets [0332](../backlog/m6/0332-m6-style-match-trial.md), [0333](../backlog/m6/0333-m6-style-measures-and-check.md),
[0334](../backlog/m6/0334-m6-style-references-and-wiring.md)).** `[style] references` in `kiripix.toml` lists Assets whose look is the
Project's (`style-add` and `style-remove`, owner-only, §10.3; `schema_version` 11). With at least one built reference other than the
Asset itself, `check` (one Asset, `--all` and `--match`) measures the Asset's Stage below, in the Ops of §7, and gives the warnings
(the Owner's Q5 in [0324](../backlog/m6/0324-m6-rooms-at-chapter-scale-style-npcs.md)); with no references nothing runs and nothing is
reported. `style.measures` (info) carries the numbers beside the Asset's other findings. A reference whose Stage isn't built is
`style.reference_unbuilt` (info) and is left out of the range; a `[style] references` entry that names no Asset, or one of another Kind,
is `style.reference_unknown` (an error, in `check --all`). `kiripix probe style <id>` answers with the numbers (§10.5).

| Kind | Measured on | `style.outline_density` (warning below 0.5) | `style.pixel_scale` (warning at a gcd of 2 or more over 50 runs or more) |
|---|---|---|---|
| Character, Sprite, Wearable | `finish`'s colour frame: clip `idle` (else the first), direction `s` (else the first), frame 0, cut to its opaque box | yes, in the outline colour `finish` drew (a Wearable's `finish` draws none, so only the scale is judged) | yes |
| Room | `palette`'s Plate (`plate.png`, not the composite with its Layers) | no | yes |
| Prop | the `export` Stage's `sprite.png` | no | yes |
| Icon, Portrait | not measured | no | no |

### 6.1 Room

A background scene with Layers, Masks, Markers and lights. A room is either `view = "top"` or `view = "side"`.

**brief → source → fit → layers → masks → normals → palette → looks → loops → place → reach → export** (`normals`: ADR 0014)

| Stage | What it does | Owner input | Checks |
|---|---|---|---|
| **brief** | Size in px, view, `mood`, `notes`, `exits` (`name:side` separated by commas, a side being top, right, bottom or left) and `canvas_width` x `canvas_height` (the image the prompt asks for, default 1376 x 768). Renders `prompt.txt` from `style/prompts/room.<ext>` and `style/bible.md` (§4): no Provider, no judgement, and nothing, with no error, when the Project has no room template. A template or bible change makes the brief stale. A field the template uses and the brief doesn't have is `brief.prompt_field` (the Owner corrects the template); an `exits` side that isn't one of the four is `brief.exit_side`. | Writes the brief | Size is a whole number of tiles |
| **source** | Generates N variants with a Provider (through `gen`), or **imports** an image made elsewhere (a first-class path: the owner may keep using an external image tool). | Picks between several (an agent may pick a lone variant) | Has a picked source |
| **fit** | Detects the source's pixel grid, or downscales to the target size. The downscale uses one scale on both axes, the largest that still fills the brief, and crops the rest (`offset_x` and `offset_y` place the crop; an info finding, `fit.cropped`, says what was cropped and offers the centring `set`). Each cell takes the colour of its dark or light group, so a thin dark line stays one continuous pixel and flat areas stay even (the cell's mean when it has no clear line or edge). In grid mode, a grid output smaller than the brief is padded on the right and bottom up to the brief with transparent pixels (alpha 0, RGB 0), so no coordinate moves; an info finding, `fit.padded`, says how much, and `grid.json` records `pad_right` and `pad_bottom`. `masks` ORs the strip into `solid` (derived from `grid.json`, not a Decision), and a click or box that starts in it fails. A grid output larger than the brief stays `fit.size_mismatch`, whose `fix` is the brief rounded up to whole tiles. Records the Grid transform. Palette-free. | Tunes the grid, with a before/after view | Exact size |
| **layers** | Builds the **Plate** and the foreground Layers. Paths: (a) the source was generated as a plate plus props, so the Layers come from their difference; (b) segment the foreground objects (SAM 2; a negative click takes the object under it away from that Layer, and so from the Plate's hole, at its place in the replay), then inpaint the Plate (LaMa locally, or an edit API for large areas); (c) side view: depth-assisted parallax split into N planes. On path (a) the owner names a Layer with one click in a region of the difference; unclicked regions stay in the Plate. One **grow** parameter widens both a Layer's alpha and its Plate hole, in target pixels, only where the Runner's alpha was partial: a target pixel whose Source cell is partly covered by the Runner's Mask or has alpha strictly between 0 and 255 (default 1 px, 0 allowed). With no Decisions the Stage is `done`, and the Plate is the fit image. | Clicks objects to lift out; trims a rim with a brush on the Layer's alpha | Plate + Layers recompose exactly to the fit image; no holes in the Plate |
| **masks** | Paints the painted Masks (`solid` and `pit` for top view; `solid`, `oneway`, `ladder` for side view): click-to-segment (SAM 2: a positive click adds the object under it to the Mask, a negative click, a shift-click, takes that object away from the Mask at its place in the replay, whichever Decision put it there; each is one Runner call), flood by colour region within an OKLab tolerance of the clicked pixel, brush, polygon (`{mask, erase, points}`, at least three corners in target pixels; it closes itself, the outline pixels are included so a rectangle fills exactly its box, a self-crossing polygon follows the even-odd rule, points outside the Mask are clipped; not `on_image`, so a changed Plate leaves it as it is), a wall along the room's chosen edges, or import of a painted image; optional snap to an N px cell grid. The UI has no polygon tool yet (ticket 0080). | Clicks and brushes | Every Mask binary |
| **normals** | **ADR 0014; M6.** The room's normal map, for Godot's 2D lights. `mode` is `off` (the default: `done`, no output, no Runner call) or `depth`. With `depth`: the depth Runner on the Source (one pinned call; its input size is in the key), mapped through the Grid transform to target pixels; each foreground Layer's depth outside its alpha is refilled from inside it; then Sobel, `strength`, a flat `deadzone` and `levels` per side. Output: one `normal.png`, the room's size, each pixel from its front-most Layer, in Godot's encoding, never palette-mapped; `export` cuts the Plate's, each Layer's, and each Look's and Loop's maps from it by their alpha or box. A `flatten` Decision (brush or polygon, in target pixels) makes the normal face the camera inside it; an Override paints normals by hand. Reads `layers`, `source`, `fit`, `masks` and the `[body]` setting; only `export` reads it, so a palette change never rebuilds it. | Turns it on for a room; flattens or paints where the normals are wrong | The normal map is the room's size (`normals.size`, error); walkable ground is flat within a threshold (`normals.not_flat_walkable`, warning, top view; fix: a `flatten`) |
| **palette** | Maps the whole composite once to the palette in OKLab (strict, or with optional ordered dithering) and removes orphan pixels. Each foreground Layer is that mapped image cut by its alpha; the Plate is the same image with only its inpainted areas mapped separately. | Tunes 2–3 sliders, with a before/after view | Every pixel on the palette; Plate + Layers still recompose exactly |
| **looks** | The room's other Looks (see Looks, below). Each is an edit of the Source, picked as a Variant of that Look. It is resized to the Source, registered to it, fitted with the room's Grid transform, optionally regraded, mapped to the palette as `palette` maps the room, and cut to its region. The region's pixels over a foreground Layer become a piece at that Layer's depth. A Look may have its own `solid` Mask. With no Looks the Stage is `done`. M4. | Imports or generates an edit, names the Look, draws the region; paints or erases `solid` where the Look blocks or opens the way | Every pixel on the palette; the edit registers to the Source; drift outside the region is reported; the region shows a change |
| **loops** | The room's Loops (see the glossary; ADR 0011): parts that play by themselves, over and over, cut to a region. A `loop` Decision declares one: an ID (unique among the room's Looks and Loops), a `form` (`cycle` or `frames`), a `layer` (the Plate or a foreground Layer, whose alpha cuts it), an optional `light` Marker ID and a `phase` in ticks; `remove` and `rename` take a Loop away or give it another ID. Its region is `polygon`, `brush`, `flood` or `difference` Decisions (the code `looks` uses). A colour cycle steps chosen palette colours through a list (`rotate`) or along their ramps and back by a `lift` in OKLab lightness, default 0.15 (`pulse`; a `depth` in ramp places is refused, the Loop held: `lift` = depth x 0.075), on the mapped room. A frame Loop's frames come from an Op on the room's own pixels (`sway`, which needs a foreground Layer, `shimmer`, `scroll`) or from a kit painted at target size (`loop kit`, then `import --loop`); edit frames are each picked from an edit of the Source (`import --loop --frame`, `pick`) and go through a Look's edit pipeline, with a `hold` Decision to keep a part of the region still (the ticker under a still picture). Frame 0 is the room either way. `timing` is `ticks`, `pingpong` or a seeded `flicker`, with `rest` to leave frame 0 out of the played frames, expanded into a `sequence` of (frame, ticks). A Loop that can't be built yet is held: it shows its region, `loop.held` says why, and the other Loops build. Output: the distinct frames of each piece as a strip, the cycle's index image and `loops.json`. A palette change rebuilds cycles and Op frames (`done`) and remaps kit frames (`needs-review`); a refit or a Layer change puts a `flood` in `needs-review`, and a refit holds a kit painted on the old fit. With no Loops the Stage is `done`; `place` and `reach` don't read it. M4. | Declares a Loop, draws its region, picks the colours or the frames, and the timing | Every Loop can be built (error); every colour and pixel on the palette (a kit's off-palette pixels take the nearest colour, an error over 1 % of the region); frame 0 is the room inside the region; a kit frame's alpha is 0 or 255, and its strokes outside the region are cut away (warning); a `sway` sits on a Layer; the wrap has no jump (warning); an edit frame lies on the Source and redraws nothing outside the region (`loop.misaligned` error, `loop.drift` warning), no more than 30 % of the region outside the holds changes between edit frames (`loop.flicker`, warning), and on a Layer nothing changes past its alpha (`loop.past_layer`, warning); the Loop has a region and changes something (warnings); no more than 3 flashes a second (error); no overlap with a Look (warning); a pulse's region stays near its colours (info); the Loops' texture size (info); `light` names a light Marker (checked at `export`) |
| **place** | Puts Markers on the room: Exits (with a target room and Exit ID), Spawns, interactables, lights (colour, radius, energy), particle emitters, y-sort lines, Links (a Marker with two ends, `from` and `to`, a free-text snake_case `kind` such as `hop`, `climb` or `jump` and `two_way`, default true, for a scripted move across one room; `markers.json` lists them under `links`; `reach` crosses them), areas (a box, optionally snapped to a `cell` from the room's top-left corner, optionally `walkable`; any number, any Marker ID, one pixel or one cell wide at least; Kiripix gives an area no meaning, and the game decides what it's for, such as a battle area, an escape route over a fence or an Exit's trigger box, M4). A light, an emitter or an interactable may name a `look` (a built Look's ID) and then belongs to that Look (ADR 0013); every Marker in `markers.json`, schema 3, has `look`, a Look's ID or `null`, and an older file is refused, naming the rebuild. For each Look with its own `solid`, `place` also writes `looks/<look>/walkable.png` and `looks/<look>/clear.png`, derived from the Look's `solid` and the room's `pit` as the room's are. | Places Markers, in the room or in a Look | Unique IDs over the room and its Looks (a Link's too); a `look` only on a light, an emitter or an interactable (`marker.look_type`) and naming a built Look (`marker.unknown_look`); both are errors, and `decide` refuses them before recording; Exits and Spawns on walkable ground; Exits and Spawns on walkable ground; both ends of a Link inside the room (`link.outside`) and on walkable ground (`link.not_walkable`), and a tile apart (`link.same_place`, warning); every foreground Layer has a y-sort line or an "always above" flag; a sloped line sorts at its mean y, with a warning if its ends differ by more than half a tile; an area lies inside the room, and a `walkable` one holds walkable ground; with a `cell`, the cells a Mask leaves between a quarter and three quarters blocked are listed (info), and `kiripix area-settle <room> <area>` settles them by majority (a cell at least half `solid` or `pit` is filled on the Mask covering it most, the others are cleared on every Mask that touches them) with `polygon` Decisions on `masks`, one per cell and Mask (so one per cell unless a cleared cell is touched by both `solid` and `pit`); `--dry-run` lists them, and an agent may run it |
| **reach** | Reachability: the body's footprint, flood-filled over walkable at sub-tile steps, from each Spawn and Exit to all the others (side view: over platforms, with jump settings, Later). Warns when no walkable part of a `walkable` area is reachable. Lists unreachable Markers, unreachable walkable islands and the narrowest gaps. A Link is crossed when the flood reaches one end (the `from` end of a one-way Link): the other end is seeded, until nothing new is reached, so ground reached only through a Link is reachable, and the exported navigation still follows walkable ∩ reachable, because the game moves the actor across a Link by script. `reach.link_joins` (info) names each Link that joins ground the Body can't walk between. For each Look with its own `solid`, it floods the room's Spawns and Exits (crossing Links) over that Look's walkable from `place` and writes `looks/<look>/reachable.png`; a Look's own Markers are not targets. `report.json` (schema 1; an older one is refused, naming the rebuild) gains `looks.<look>` with `markers`, `main`, `islands` (each with `added`, its spots that only the Look makes walkable) and `areas`, as the room's are, and each room island and area lists the `looks` that reach it. A room island some Look reaches is `reach.island_under_look` (info) instead of `reach.unreachable_island`, and `area.not_reached` is info when a Look reaches the area. `reach.look_island` (warning) is ground only a Look makes walkable that it doesn't reach; `reach.look_cuts_off` (info) is a Spawn or Exit the room reaches and a Look doesn't. | — | All Markers reachable; every Link reachable (`reach.unreachable_link`, error) |
| **export** | Writes the Godot scene (see §9). `room.json` is schema 13 (ticket 0345): `masks` lists every painted Mask of the room's view (`kiripix masks-add`) as `name`, `file` (`masks/<name>.png`, 1-bit, the room's size, byte for byte what `masks` built), `meaning` (from `kiripix.toml`, `null` when it has none) and, only for `solid` and `pit`, `collision: true` (their shapes are `collision.<name>`); no scene node is made for any other, since the game reads its PNG for its grid. A Look's own Mask files are listed under the Look, not in `masks`. Schema 15 (ticket 0342): `normals`, the cut normal maps (§9). Schema 12 (ticket 0316): each Look with its own `solid` also gets its added and cleared Masks (`masks/<look>.added.png`, `masks/<look>.cleared.png`, 1-bit, the room's size, from its `solid` against the room's), a navigation (its walkable ∩ its reachable, from `place` and `reach`) and the bodies the scene is split into (`scene`); a Look's own Markers are listed under the Look. | — | Export target set; no Loop held; a Loop's `light` names a light Marker; a Loop's strip is no larger than 4096 x 4096 px; Project checks (see below) |

**palette reads `layers`, not `masks`**: its upstream is the Plate and the Layers, so a Mask edit never rebuilds the
palette mapping. Nor does it read `normals` (ADR 0014), which only `export` reads. `place` reads both `palette` and `masks`.

**Named Masks (M6, ticket 0344).** `kiripix masks-add` adds a painted Mask to `[masks.<view>]`; the `masks` Stage paints it
like any other (`brush`, `polygon`, `flood`, `import`) and writes its `<name>.png`. It is the game's to read, such as a grid
battle's `cover`, `water` or `high`: `reach` and the walk test never look at it. A Decision on a Mask the Project no longer
has fails `masks` as `masks.unknown`, naming the Mask and the Decision.

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
exists. `check <id>` agrees with `export <id>`: the same finding (`exit.no_room`, `exit.no_exit`, `exit.not_paired`) is a
warning for one room, and an error under `check --all` and `export --all`. **A one-way Exit** (ticket 0352): an Exit Marker takes
`one_way` (boolean, default false) for a drop through a pit or a door that locks behind the player. `target_room` and
`target_exit` stay required, since the target Exit is where the player arrives, and must exist (`exit.no_room`,
`exit.no_exit`), but the target needn't point back, so a `one_way` Exit never gives `exit.not_paired`. `district` gives it the
pairing `one_way` (or `outside`). An ordinary Exit that points at a `one_way` Exit is checked as before. `markers.json`
(`schema_version` 4) writes `one_way` on every Exit, `false` when unset.

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
- Its edit is added with `kiripix import <id> <png> --look <look>`. Once generation lands (deferred from M6, §14), `gen <id> --look <look>` makes one with an
  edit prompt ("Edit this image. Keep everything exactly the same except: …"). An edit can also be painted by hand on a
  copy of the Source.
- **Which edits are accepted** (M5, [0232](../backlog/m5/0232-m5-look-edit-of-a-piece-or-crop.md)): an edit of the room's
  whole Source (the default), or one made on a piece or a crop of it, with `--of`. An image model resizes what it is given to
  its own size (1376 x 768), so an edit of a large extended room's Source comes back smaller and must be scaled up, which blurs
  the Look. `--of <piece>` names one of the room's pieces (the start of its hash in `extend/pieces/`) or a Variant; `--of <crop>`
  names a crop `kiripix extend <id> crop --box x0,y0,x1,y1 [--size WxH]` wrote (the picked Source's crop at the model's size,
  centred on the box, kept as `extend/crops/<hash>.png`; the room keeps every crop, so two Looks can have two crops, and `--of
  crop` alone means the latest one; a crop of a Source that is no longer picked is `import.crop_stale`). Kiripix finds where the piece or crop lies, registers the edit there (scale and shift, as the `looks`
  Stage does) and stores an edit of the whole Source: the Source's own pixels everywhere the edit doesn't reach, so the
  Look's listing, its region and its drift are unchanged. The same `--of` works for a Loop's edit frame (`--loop --frame`).
  A piece is found by matching its picture in the Source, so it must be part of the picked Source; a crop is placed where it
  was cut, and registered when it has enough texture.
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
- `solid`: the Look's own `solid` Mask, by polygon or brush, with the `masks` Stage's `snap_cell`. It starts as the
  room's `solid`: a stroke adds to it (a shut door) and an `erase` stroke clears it (an open gate), so a Look can add
  collision or take it away. It is the whole Mask while the Look shows, and the game uses it in place of the room's
  `solid` (§9). A Look has no `pit` of its own. Walkable and `reach` are per Look (`place`, `reach`); navigation is still the room's (§16, open
  decision 8).

**Staleness.** A new room Source invalidates every Look's pick, and the Stage goes to `needs-input` with "the edit was
made on another Source". A refit or a Layer change rebuilds every Look: its `difference` regions and registration go to
`needs-review`. A palette change rebuilds them, and they are `done`. A room with no Looks has a `looks` Stage that is
`done` at once. `place` reads the Looks (a Marker's `look`, and the walkable of a Look with its own `solid`); `reach` floods each Look with its own `solid` as well (below).

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
- `look.overlap` (warning): two Looks' regions share pixels, naming both. The game may show any number of Looks together
  and decides which draws on top (ADR 0013).

**Keep Looks small.** A large crop of an edit shows the edit's compression noise and redraw as blotches, which
Lost-and-Found found (§15). Cut a lamp's glass, not the wall around it. Look IDs are frozen once exported, like Layer
IDs. Look and Loop IDs are one set: a Loop that takes a Look's ID is held (ADR 0011).

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

**A Prop's states** (M5, [0257](../backlog/m5/0257-m5-prop-states.md); the Owner, 2026-11-16): a bin standing, toppled,
dented. A Prop may hold any number of named states. The picked Source is the default state, and each other state has its
own image, cutout, size, footprint and origin, at the Prop's one scale, with its palette and `finish`. The scene has one node
per state, only the default shown, and the game switches between them.

### 6.3 Character (3D to pixel)

Characters, NPCs and enemies are rendered from 3D, so every animation stays on-model. They are rendered at the target
pixel size (52 px tall in the Toronto RPG), so the recipe has no `fit`.

**model → rig → clips → render → palette → finish → sheet → export**

| Stage | What it does | Owner input |
|---|---|---|
| **model** | Imports `.glb`, `.fbx` or `.blend`; optional image-to-3D (a local Runner if one fits 8 GB, or a Provider). Normalises scale and the up axis. | Picks or imports |
| **rig** | Validates a humanoid rig, or guides the Mixamo auto-rig round trip (the tool shows the steps and picks up the downloaded file). Rigify for non-humanoids. | Mixamo step, when used |
| **clips** | Maps named clips (`idle`, `walk`, `run`, `attack`, `hit`, `ko`, `cast`…) to animation sources, with frame range, frame rate and loop flag. Clip IDs are snake_case verbs; a variant is named for what it is (`attack_kick`), not numbered. Deciding a clip again under its name changes its range (M4). Records the frames where a foot plants, the same in every direction (M4, lower priority). A thing held in the hand (a class's weapon in its battle clips, the phone) is attached in the character's render for the clips that hold it: a clip's `attach` names the thing and its socket bone (`grip_r` under the right hand), and a clip whose extent outgrows the body's cell gets its own cell and pivot (M5, decided in [0238](../backlog/m5/0238-m5-held-things-trial.md), built in 0300 to 0306). A clip can also play its action faster (`speed`), hold one pose (`still`: a standing idle), and name the frames drawn with closed eyes (`blink`) (M4, ticket 0203). A `transition` Decision makes a clip that blends one clip's pose into another's (`idle_to_attack`): `from` and `to` name a clip and one of its frames, `length` frames (default 3) lie between the two poses, each bone's location and scale linear and its rotation a slerp, the root kept in place; `render` renders it and `export` names it like any clip (M4, [0218](../backlog/m4/0218-m4-transition-clips.md)). The Project's clip table (`[[character.clips]]`: name, `frames`, `fps`, `loop`, optional `foot`; filled by `clips-add`) holds every body to one timing: the Project check `clips.timing_differs`, run by `check --all` and `export --all`, names a character whose built clip of a table's name differs (its `fix` is the clip Decision with the table's fps and loop, or an `owner_action` when only a range, a speed or a `still` can bring the frame count in line); a character without that clip raises nothing, and a sprite's clip of that name is a warning (M5, [0239](../backlog/m5/0239-m5-project-clip-table.md)). | Chooses clips |
| **render** | Blender headless. Orthographic camera from a preset: top-down 3/4 at 4 or 8 directions (all rendered, none mirrored, so an asymmetric character stays right), side view. Battle clips use the same camera as walking, because the game fights in the room. Directions are named `s sw w nw n ne e se` from the screen's view, `s` facing the camera. Rendered at the target pixel size, no anti-aliasing, toon shading, in one square cell per character, grown from 1.5 x its height until every pose of every clip fits with a pixel to spare for the outline, so no pose is cut. A stationary clip's pivot is the same pixel in every frame (the feet, not the swaying hips). Passes: colour, normal, depth and an object mask. Frames are subsampled to the clip's frame rate. Renders aren't pinned: they rebuild as deterministic work, with the Blender version and render settings among the Stage's inputs. With `eyes` naming the Model's eye materials, it also records where each eye is in every frame, from the posed mesh (M4, ticket 0203). With `points` (`<name>@<target>`, comma-separated; a name of `[a-z][a-z0-9_]*`, a target a bone of the Model's armature, which gives its head, or an Empty of the Model, which gives its own place, so a socket parented to a bone can sit where the game wants it), it records each named point's place in every frame and direction from the posed Model, in render px with its depth and `hidden` when the body is in front of it (by more than 8 % of the Model's height, so a bone's head, which lies inside the body, often reads hidden: a point the game needs `hidden` for is an Empty on the surface), as `points` in `render.json`; a target the Model lacks is `render.point_unknown`, listing its bones. Nothing is written without the parameter (M5, ticket 0237). | Tunes the camera preset once per project |
| **palette** | One palette per character across all frames (a project-palette subset), orphan cleanup. With `parts` (M4), each swappable part (one or more Blender materials) owns a ramp of palette colours that nothing else uses. The Project's ramp table (`[[character.ramps]]` in `kiripix.toml`) fixes each part's name, length and row for every character, and its colours where they're shared (skin, hair), so one swap means the same on every body. | — |
| **finish** | Outline, drawn after mapping, in a palette colour: a 1 px silhouette from the object mask (§16, decision 3); outline consistency across frames. The normal pass is quantised to its own levels (not palette-mapped) and aligned to the colour frames. With `eyes=stamp`, the eyes `render` followed are painted as a small fixed pattern, a pupil and a white on whole pixels, chosen once for a clip and a direction and moved only when the head has moved most of a pixel; a clip's `blink` frames get closed eyes (M4, ticket 0203). With `inner_lines=outline` or `dark`, the farther pixel of each border between two materials gets a line in the outline's or the material's own dark palette colour (`line_skip` drops borders; M4, ticket 0215); `line_depth=<px>` (default 0, off) adds a line inside one material where the depth steps by more than that many px of the render's scale (`px_per_unit` and `depth_range` of `render.json`, so it means the same at any `height`), in the material's line colour (M5, ticket 0247). | — |
| **sheet** | Packs frames into an atlas with a fixed pivot (the feet) per frame, plus frame metadata. | — |
| **export** | Godot `SpriteFrames` `.tres`, plus a `CanvasTexture` with the normal map for 2D lights, plus a scene with `AnimatedSprite2D`. An animation is named `<clip>_<dir>`, such as `walk_sw`. | — |

Checks:
- **pivot drift:** the feet don't move between frames of a stationary clip;
- every frame fits its cell;
- palette;
- frame counts match the clip;
- no empty frames;
- normal map size equals the colour frame's;
- **one key light** (Project check, run by `check --all` and `export --all`, M6, [0361](../backlog/m6/0361-m6-light-angle-consistency.md)): `style.light_angle_differs` (warning) names each character, base included, whose `render` camera preset's `light_angle` differs from the Project's most common; its `fix` is the `set` of `camera` to a preset that has the common angle, or an `owner_action` when no angle is the most common. A Wearable follows its body's render, so it is named in its body's finding, not reported twice. It compares settings, not images: light direction isn't measurable on a painting ([0332](../backlog/m6/0332-m6-style-match-trial.md)).

**A character made from a base** (M4, ADR 0012, [0165](../backlog/m4/0165-m4-characters-share-a-base.md)). `kiripix new
character guard --base character.body_m` (the `base` parameter in `asset.toml`) names another character, which has no base
of its own; anything else is `asset.base_invalid`. Some Stages then read the base, and what they read is part of their input
hash, so a change on the base makes them stale. Nothing is copied, and nothing of the base is written or locked.

| Stage | With a base |
|---|---|
| **model** | Nothing: the character's own Model, built on the base's skeleton. |
| **rig** | No rigged file and no Mixamo trip. The Model's armature must have every bone of the base's `rig.json`, by its exact name and under the same parent; more bones are fine, and rest proportions aren't compared, since a build, an age or a posture changes them on purpose. Otherwise `rig.base_mismatch`, naming the bones. The base's roles hold for the character. |
| **clips** | The base's current Decisions come first, then the character's own, which add a clip, replace one of the same name, or `remove` one (with every transition from or to it). `undo` never reaches the base. The base's clip sources are read in the base's folder; a file of the character's own with the same name wins. A base clip that plays an action of the base's own Model file doesn't cross: give the base that animation as a clip source. |
| **render** | Without a `height` of its own, the character is the base's height (its `height`, or the Project's) times its rig's height over the base's: the height of the file that carries each armature, in the rest pose, as imported (the base's rigged file, when it has one). |
| every Stage | A parameter the character doesn't set takes the base's value, then the default; but never `render` `height` or `model`'s `facing` and `generator`. `show` says where each value comes from (`param_sources`) and marks the base's Decisions and clip sources (`from_base`). It gives each Stage's Decisions as recorded (`decisions`, what `undo` steps through) and as the Stage reads them (`decisions_as_read`: one clip per name, without the removed ones). |

A Stage that reads a built Stage of the base (`rig` and `render` read its `rig`) is needs-input until that is done, with
`kiripix run <base> <stage>` as its command; `run --all` builds a base before the characters made from it. `clips copy` stays,
for characters that share clips but not a skeleton.

**A Model built from a parameter file** (M4, [0224](../backlog/m4/0224-m4-a-model-built-from-a-parameter-file.md)). A
Project may have a **generator**: a Blender script of its own, with the files it reads, named under
`[character.generators.<name>]` in `kiripix.toml` (`script`, and `library`: files and folders; all paths in the Project).
Kiripix holds no parts and no game content: it runs the script and reads what it wrote.

- A character's **parameter file** (`.toml` or `.json`) is stored in `src/parameters/` under its own name, by `kiripix new
  character <name> --from-parameters <file>` (with `--base <character>` when its body is a base's) or `kiripix import <id>
  <file> --role parameters`. It is the Source: nothing is picked, and it may be edited in place. A character has a parameter
  file or imported Models, never both (`import.model_or_parameters`).
- `model` runs `<Blender> --background --factory-startup --python <script> -- <args.json> <result.json>`. `args.json` holds
  `parameters` (the file), `library` (the settings' paths, absolute) and `model` (a `.glb` to write). The script writes the
  Model there and, into `result.json`, `materials` (names), `parts` and `eyes` (text, or a list of names) and `height` (the
  Model's height over its base body's). Then `model` normalises the Model as it does an imported one; `model.json` keeps
  what the generator said as `generated`. With several generators in a Project, `model`'s `generator` parameter names one.
- The input hash of `model` covers the parameter file, the script and every file of the library (Python's own caches left
  out), so a change to any makes the Model stale, and only the Models that generator builds.
- A value the character doesn't set is, in order: the generator's (`render` `eyes`, `palette` `parts`, and the `height`
  ratio, times the base's height or the Project's), then the base's, then the default.
- A generator that fails is `model.generator_failed`, with the script and its last 20 lines; one that ends without its
  Model or its JSON says which is missing.

**Wearables** (ticket 0290; M5). A part of a character's dress is its own Asset of Kind `wearable`, made with
`kiripix new wearable <name> --body <character>`; `body` is in its `asset.toml`, and a body that is missing, is itself a
Wearable or isn't a character (a sprite has no Model to hold out), is `wearable.body_unknown`. Recipe: **model → rig → render → palette → finish → sheet → export**, the
character's without `clips`: the body's clips, camera, cell and pivot are used, not copied, so the Wearable's frames land
on the body's, pixel for pixel. `render`'s input hash holds the input hashes of the body's `model`, `rig`, `clips` and
`render` (the last one fixes the cell), so a change to any of them makes the Wearable stale through the Stage graph, and
`status` names the body; a change to the body's `palette`, `finish` or `sheet` does not. A Wearable whose frames don't fit the body's cell is `wearable.outside_cell` (error, naming the frames; its
fix is the body's `cell_margin`, a `render` parameter that keeps room round the poses). No Command removes or renames an Asset yet; when
one does, it refuses a body that has Wearables (`wearables_of` lists them). `model` puts the Wearable's meshes on the body (turned and scaled by the body's own
`model_root`, never by their own height); `rig` checks the Wearable's armature against the body's by bone name (the body's
armature drives it); `render` is the body's render with the body as a holdout, so the Wearable holds only the pixels that show
(its depth and normal passes are the body's, for the game to stack by depth), and records its render seconds. Each of the three
waits, needs-input, until the body's Stages it reads are built, and a body whose rig came from Mixamo is refused
(`wearable.body_rigged`). `sheet` and `export` (0293) are the character's on the body's cell, with a depth atlas and the `order` parameter; §9 has the export. Design: [0152](../backlog/m5/0152-m5-character-layers.md).

**Background NPCs** (M6, [ADR 0015](adr/0015-a-background-npc-is-a-choice-not-a-render.md), accepted 2026-11-20; the
Owner's answers in [0336](../backlog/m6/0336-m6-npc-variants-from-a-base.md)). A background NPC is a choice, not a render: an Asset of Kind `npc`
names a base character, Wearables rendered on that base, their stacking order, and one named colour per Part, picked from the
`choices` of the Part's row in the ramp table (`[[character.ramps]]`). It changes nothing else: a different `height` or clip
set is a character made from the base, which renders. Recipe: **choose → export**; the choice is `choose`'s parameters
(`wearables`, `colours`), and export writes one appearance file the game's actor data names. NPCs can be made in bulk from a seed. The speaking cast stay characters with portraits.

`kiripix new npc <name> --base <character>` (ticket [0356](../backlog/m6/0356-m6-npc-kind-and-choose-stage.md)) names the base in
`asset.toml`; a base that is missing, a Wearable, a sprite, itself made from a base, or no Asset ID is `npc.base_unknown`. `choose` has two parameters, both
text: `wearables` (Wearable IDs, comma-separated; they stack over the base by each one's `sheet` `order`, ties by ID, and
`id@25` gives this NPC another order for that Wearable) and `colours` (`part=choice` pairs, such as `hair=auburn,top=red`: a Part of the
ramp table and the name of one of its `choices`; a Part not named keeps the colours it was built with). They are set like any parameter (`kiripix set`) and
are in the input hash unless at their default (empty). `npc.json` (`schema_version` 1; a Stage's rebuilt output, refused when old) holds `base`, `wearables` (`{id, order}`, bottom to top) and
`colours` (by Part in the ramp table's row order, each `{choice, rgb}`). Nothing renders; the input hash holds the base's and each Wearable's
`sheet` and `palette` input hashes and the ramp table (`character.ramps`), so a re-render of the base or of a Wearable, or a change of the table, makes every NPC
on it stale, and `choose` waits (needs-input, with the command that builds it) until they are built. A choice that can't be made is
needs-input and `run` refuses it (exit 3) with `npc.wearable_unknown` (not an Asset, or not a Wearable), `npc.wearable_body` (worn on another body),
`npc.wearable_twice`, `npc.wearable_order`, `npc.colours_invalid`, `npc.part_unknown` (a Part with no row) or `npc.choice_unknown` (the row has no such choice).
`preview --stage choose` draws the stacked, swapped figure with `cast-sheet`'s code (`stack_by_order`, `swap_ramps`), one frame per direction of the base's `idle`.
In the ramp table, `choices` (`kiripix.toml` `schema_version` 12; migrated from 11 as empty) is a table of named ramps, each as long as its row (`ramps.choice_length`),
of Project palette colours (`ramps.choice_not_in_palette`) under a snake_case name (`ramps.choice_name`); `describe project` shows them. Its export is [0358](../backlog/m6/0358-m6-export-npc.md).

The Checks on `choose` ([0357](../backlog/m6/0357-m6-npc-checks.md)) read the built `npc.json` against the Project as it is now, so they find
what changed after the build (the run-time refusals above stop a choice that is wrong when it is made): `npc.wearable_body` (error: a
Wearable the choice lists is worn on another body than the base; the `fix` takes it out), `npc.colour_choice` (error: a Part's built
colour is no longer one of its `choices`; `data.reason` is `part_gone`, `choice_gone` or `choice_changed`, and `data.choices` names the
choices now), `npc.part_unset` (info: a Part with choices that the NPC keeps as built) and `npc.stack` (warning: a Wearable that
stacking by order buries but the depth pass puts in front, in most of its frames; it reuses M5's `stack_by_order` and `stack_by_depth`
on the built `render` frames). `npc.slot_twice` is not built: a Wearable has no slot. Each finding's position is
`{asset, stage: "choose", field: "wearables/<id>" or "colours/<part>"}`, with the same names in `data`.

**NPCs in bulk** ([0359](../backlog/m6/0359-m6-npc-crowd.md)). `kiripix new npc <prefix> --base <character> --count N --seed S
[--wearables <ids or globs>] [--choices part=a,b ...]` makes N ordinary `npc` Assets, `<prefix>_01` … (two digits at least), each with
`choose`'s `wearables` and `colours` written as `kiripix set` writes them; nothing about the crowd is stored. A crowd is the IDs
`npc.<prefix>_<number>`, which `status --match 'npc.<prefix>_*'` and `cast-sheet --match` read. The allowed set is the flags, by default every
Wearable worn on the base and every choice of every Part with choices. A Wearable has no slot, so each NPC wears a random subset of the allowed
Wearables (from none to all), stacked by their `order`; each Part with choices gets one of its allowed choices (`--choices hair=auburn`
narrows that Part, the others stay open). The pick draws from a generator seeded by the seed, the base, the prefix, the NPC's number and the
try, over lists sorted by ID or in the ramp table's row order, so the same seed in the same Project gives the same NPCs whatever the
dict, set or directory order or the hash seed. A pick is judged by 0357's own functions before anything is made (`npc.wearable_body`,
`npc.colour_choice`, and `npc.stack` from the base's and the Wearables' built `render` frames), so the Assets need no build of `choose`;
what isn't rendered can't be judged, and the result says so (`new.crowd_stack_unchecked`, info). A pick with an error or an
`npc.stack` warning, or the same as another NPC on the base, is picked again, 12 tries at most; then the closest is kept and
`new.crowd_unsatisfied` (warning) names why. Refusals, exit 1, nothing made: `new.crowd_incomplete` (no `--base`, `--count` or `--seed`),
`new.crowd_needs_npc`, `new.crowd_reroll_args`, `new.crowd_wearables_unknown`, `new.crowd_choice_unknown`, `asset.duplicate_id`.
`kiripix new npc <id> --reroll [--seed S]` picks that NPC's choice again, other than its own and the other NPCs' on the base, and writes
only that NPC (without a seed, one derived from its current choice, so a repeated re-roll walks on); `--wearables` and `--choices` apply to it too.
`cast-sheet --match <glob>` draws every character, sprite and NPC the glob matches, in ID order, on one sheet; an NPC is its base with its
Wearables stacked and its colours swapped, from its built `choose` (one that isn't built is left out: `cast.npc_not_built`), and an NPC ID
also works in the figure list.

### 6.4 Sprite (2D frames to pixel; M4)

An actor built from imported 2D frames, such as a PixelLab figure, exported exactly as a character is (the game's sprite route,
DEC-012). On PixelLab's free plan a figure is one frame per direction, so a clip of one frame in 4 or 8 directions is the common
case; whole animations import too. Design: [0174](../backlog/m4/0174-m4-sprite-kind.md).

**frames → fit → palette → finish → sheet → export**

| Stage | What it does | Owner input | Checks |
|---|---|---|---|
| **frames** | Cuts the imported sheets (`import --role sheet`: a PNG, or a ZIP of PNGs with at most PixelLab's `metadata.json` at its top, which no frame is read from; stored whole in `src/sheets/`) into `<clip>/<dir>/<NNN>` frames at source resolution. Parameter `directions`: `8` (`s sw w nw n ne e se`), `4` (`s w n e`, the default) or `1` (`s`). A ZIP is read by a naming rule (a direction word, PixelLab's `south`, `south-east`... or ours, in a folder or a file's name; a frame number; the clip is the folder above, snake_case; `idle` for rotations alone). The rule is provisional until the trial on a real export ([0175](../backlog/m4/0175-m4-sprite-pixellab-export-trial.md)). A clip gets fps 8, loop on, and is stationary when it has one frame. | A `sheet` Decision (a PNG's file, clip, layout, directions and frame count; a ZIP's clip renames), a `clip` Decision (fps, loop, stationary) | `frames.direction_missing` (error, never mirrored), `frames.frame_count`, `frames.unknown_direction`, `clips.bad_name`, `clips.duplicate_name` |
| **fit** | Per frame onto the target grid: `grid` (default: `detect_grid`; one scale for every frame) or `downscale` (one Grid for the Asset that brings the reference frame's figure to `height`, line-keeping, for AI images); `chroma` clears a flat background first; the alpha is binary by vote. Measures each frame's feet (`feet_point`), takes a pivot per direction (the median over its stationary frames, else all) at the ground point a body's would be, 0.08 of the figure's height above the feet (the mc03 bodies' shoes below their pivot), the same in every direction, so sprites and bodies share a ground line (M5, [0318](../backlog/m5/0318-m5-sprite-pivot-at-the-ground-point.md); `fit.json`'s `ground`), and places every frame on one cell, the smallest that holds them around the pivot with 1 px to spare for the outline. `align_feet` places each stationary frame by its own feet. Writes `render.json` in the character's schema, with each frame's measured `feet`. | A `pivot` Decision (the pivot itself, no offset), only when the measured one is wrong | `fit.grid_differs`, `fit.alpha_partial`, `fit.height` (info), `fit.cell_grew` (info) |
| **palette** | The character's. A sprite's parts are its colour regions (M5, [0319](../backlog/m5/0319-m5-sprite-palette-by-parts.md)): its colours over every frame grouped by OKLab hue (`hue_gap` degrees apart), the neutral ones one `grey` region, each named by hue (`orange`, `blue_2`) and listed in `palette.json`'s `regions`. `parts` names and joins them as a body's names materials (`skin=orange,top=grey`); each part gets a ramp of `shades` (default 4; the Project's ramp table's length when it has one, and every part must be a row of it, so `ramps-add` takes a sprite's parts too), mapped as a body's: nearest in its own ramp, a ramp with the table's colours by lightness order. (Lightness order onto a fitted ramp was tried on the worker and dropped: a fitted ramp keeps outlier colours, a button's yellow or a near-black, and lightness order pushes a whole class onto them.) With `parts`, the regions are written as the sprite's material pass. Regions in no part take `colors`. No `parts` builds as before. | `parts` | `palette.off_palette`, `palette.ramp_shared`, `palette.sprite_regions` (info, while there are no `parts`) |
| **finish** | The character's; `normals` is `height` by default (a rounded height from the alpha, Sobel; `relief` mixes in lightness), or `flat`; `placement` is `edge`: the source's own dark edge is repainted in the Project's outline colour. `inner_lines` draws between the sprite's parts (M5, [0320](../backlog/m5/0320-m5-sprite-inner-lines-by-part.md)): a region in no part is one of its own, `line_skip` names parts, and with no depth the line is the lower pixel of a border (the right one, side by side); a sprite with no `parts` can't have them (`finish.inner_lines_without_parts`). | — | `normal.size_mismatch`, `palette.off_palette` |
| **sheet** | The character's. `sheet.pivot_drift` compares the frames' measured feet; its fix is `fit align_feet=true`. | — | as the character's, without `sheet.part_vanishes` |
| **export** | The character's: `color.png`, `normal.png`, `character.json`, and the Exporter's files. | — | `export.no_target` |

Nothing is mirrored: a direction a clip lacks is an error, and the game picks the nearest facing. A grey-on-grey figure (a
raccoon) falls into one `grey` region; a painted part mask or a click per part is Later (the Owner's call on 0319).

**Effect parameters (M6, [0362](../backlog/m6/0362-m6-sprite-effect-parameters.md)).** A battle effect is a `sprite` (trial
[0347](../backlog/m6/0347-m6-vfx-trial.md); a `vfx` Kind stays in Later). `fit anchor` puts the pivot at `feet` (the default, the
ground point above), `centre` (the middle of each direction's first frame) or `x,y` in the fitted frame's pixels; a `pivot` Decision
still wins, and `character.json`'s `pivot` (the body's and each clip's, from the cell's top left) is the anchor. `fit effect=true`
(default false) makes the cell every frame's whole area around the anchor, not its opaque box, so a 24 px spark or a 32 px telegraph
keeps its size and centre; `fit.height` and `palette.sprite_regions` stay quiet, `sheet.empty_frame` is a warning (a one-shot may end
blank), and the export has no `normal.png` (`character.json`'s `files` lists `color` only; the CanvasTexture has no normal map). With
`finish outline=false` an effect's cell takes no spare pixel (`finish` cuts the one `fit` leaves), so a 32 px cell stays 32. A `clip`
Decision takes `ticks`, one duration per frame in game ticks (60 a second, as a Loop's), which `render.json`, `sheet.json` and
`character.json` carry on the clip (`clips.ticks_count` when the count differs from the frames'); `fps` stays what it was. Every
parameter at its default builds a sprite as before, byte for byte.

**Partial alpha (M6, [0363](../backlog/m6/0363-m6-alpha-dither-op.md)).** Alpha stays 0 or 255, so a glow's haze (alpha 102 in the
trial's buff) must become a pattern on purpose. `fit alpha` is `vote` (the default: a cell is opaque when at least half its pixels
are, so a haze under half is lost) or `dither` (the colour is the vote's over every pixel with any alpha; the alpha is the cell's mean
alpha, `alpha_coverage`, put through `dither_alpha` with a Bayer matrix of side `alpha_pattern`, 2, 4 (default) or 8, at the frame's
own pixel positions, so every frame of a clip has the same pattern). In every mode `fit.alpha_partial` is a warning on the source
when any cell had partial alpha, naming how many of the cells with any alpha it was, the first frame, and the other mode (a `fix`
for `vote`, an `owner_action` for `dither`); the error on the output's own partial alpha is as before. `fit.json` gets `alpha`,
`alpha_pattern` and `alpha_partial` (per frame: `cells` changed, `of` cells with any alpha) only when there is some, so a sprite
with binary alpha writes the same bytes and no `version` bump is needed.

**Blend and light (M6, [0364](../backlog/m6/0364-m6-export-effect-blend.md)).** The sprite's `export` Stage takes `blend` (`mix`, the
default, or `add`) and `lit` (default true; false draws the sprite unshaded). They say how the game draws it, so they are `export`'s
parameters and change no earlier Stage; at their defaults they are out of the Stage's hash. §9 says what the scene and `character.json`
carry.

### 6.6 Icon (M5)

An item or skill icon on a fixed square of 16, 24 or 32 px: the front half of a Prop, with no footprint and no origin. One Asset
per icon; Godot atlases the exported PNGs itself. Design: [0253](../backlog/m5/0253-m5-icon-kind.md),
[0262](../backlog/m5/0262-m5-icon-kind-and-stages.md).

**brief → source → cutout → fit → palette → finish → export**

| Stage | What it does | Owner input | Checks |
|---|---|---|---|
| **brief** | `size` (16, 24 or 32; 0 takes the Project's `[icon] size`, default 24), `padding` in px (default 1, room for the outline), `notes`. | Writes the brief | `brief.size_invalid`, `brief.padding_too_large` |
| **source**, **cutout**, **palette**, **finish** | The Prop's (one Source, no states): chroma key or matting, the palette once, an optional outline. | Picks a Source | the Prop's |
| **fit** | The Prop's `grid` or `downscale` onto the square less the padding on each side, centred in it; the alpha goes to the grid by vote. `grid.json` is the inner square's, and its `inset` is the padding. | — | `icon.size` (exactly the square), `fit.padded`, `fit.cropped`, `image.partial_alpha` |
| **export** | Leaves `icon.png` (the `finish` image) and `icon.json` (`schema_version` 1, `asset`, `size`) in `out/export/` for the Exporter (§9). | — | `export.no_target` |

### 6.7 Portrait (M5)

A character's dialogue portraits: one Asset per character's set, a neutral image and an **emotion** for each mood (`happy`,
`sad`, ...), all on one canvas with one anchor, so an emotion swap never moves the body. Each emotion is an edit of the neutral
image, not a Look and not a Variant of the Source. Design: [0240](../backlog/m5/0240-m5-portrait-kind.md), the trial
[0241](../backlog/m5/0241-m5-portrait-trial.md); the Kind is [0242](../backlog/m5/0242-m5-portrait-asset-and-emotions.md).

**brief → source → cutout → register → fit → palette → finish → export**

`[portrait]` in `kiripix.toml` holds the canvas (default 192 x 240, the game's) and the optional `anchor` (a pixel of the canvas; the bottom
centre, `(width // 2, height - 1)`, when unset), so every set matches.

| Stage | What it does | Owner input | Checks |
|---|---|---|---|
| **brief** | `width` and `height` (0 takes the Project's `[portrait] canvas`), `anchor_x` and `anchor_y` (-1 takes the Project's anchor, else the bottom centre), `fallback`: the emotion the game shows for one it doesn't know (default `neutral`). Writes `brief.json`: `width`, `height`, `anchor`, `fallback`. | Writes the brief | `brief.larger_than_resolution`, `brief.anchor_outside`, `brief.fallback_invalid` |
| **source** | The neutral image is the Source (a Pick; its ID in the set is `neutral`). An `emotion` Decision declares an emotion ID (snake_case, unique in the set, never `neutral`). `import <id> <png> --emotion <e>` stores a Variant under `src/emotions/<e>/`, and `pick <id> <v> --emotion <e>` records an `emotion_pick` Decision with the neutral Source's hash it was made on. A new neutral Source puts every emotion's Pick in needs-input ("the edit was made on another Source"), as a Look's is. `emotion_remove` and `emotion_rename` change an ID before its first export; after it the ID is frozen (ADR 0003). Builds `source.png`, `emotions/<id>.png` and `emotions.json` (`schema_version` 1, `neutral`, `emotions` in declaration order). | Imports, names, picks. Picking an emotion's Variant among several is the Owner's; an agent may pick a lone Variant | `portrait.emotion_unknown`, `portrait.emotion_unpicked` (needs-input, naming the emotion), `portrait.emotion_duplicate`, `portrait.fallback_unknown` |
| **cutout**, **register**, **fit**, **palette**, **finish** | Built ([0243](../backlog/m5/0243-m5-portrait-recipe.md), [0321](../backlog/m5/0321-m5-portrait-whole-body-emotions.md), [0322](../backlog/m5/0322-m5-portrait-light-rim-check.md)): the cutout per image (a chroma key with a `tolerance` from each image's border, the key's spill, a light rim and small islands off; or matting); `register` `mode` `off` by default, since the game's rules free the pose, the arms and the lean between emotions (`figure` or `outside_face`, outside an optional `face` Decision, a polygon or a brush, for a set whose body stays still); one Grid for the set from the neutral, its scale putting the figure's top row `head_top` (40) px below the canvas top and its lowest row on the anchor's row, transparent where the source has no pixels (`head_top` -1: `Grid.cover`'s fill); the set's own colours (`mode` `set`, `n` 32 up to 256, `outline_colour` kept; or `project`, or `off`); the white rim's specks on the edge cleared (`clear_light_edge`), the outline (`placement` `edge`), and `lock_outside_face` (off by default). | Draws `face`, only if needed | `portrait.misaligned`, `portrait.residual`, `portrait.shimmer`, `portrait.out_of_canvas` (within 2 px of the top, left or right edge), `portrait.light_rim`, `palette.set_error`, `palette.off_palette` |
| **export** | One PNG per emotion (and `neutral.png`) and `portrait.json` in `out/export/` ([0244](../backlog/m5/0244-m5-export-a-portrait.md), §9). | | `export.no_target`, `export.portrait_canvas`, `image.partial_alpha`, `portrait.fallback_unknown` |

## 7. Ops library (first set)

- **colour:**
  - palette load and save;
  - OKLab conversion;
  - nearest-colour mapping;
  - ordered dithering (Bayer 2/4/8);
  - palette extraction (k-means in OKLab, then a manual merge);
  - palette suggestion: new colours for a palette from an image, with the existing colours held fixed, new clusters
    seeded where the palette fits worst, and candidates near an existing or chosen colour dropped;
    from a room or prop, `palette-suggest --asset <id> [--box x,y,w,h]` reads the Asset's Source at its own `fit` Grid
    transform (so the scale is the Asset's, not `--scale`), with the box in target px mapped through it to the Source
    (the whole Asset by default); it needs `fit` built, and refuses a Kind with no `fit` Grid transform. The proposal names
    the Asset and the box, and holds a hash of the Source and the Grid transform, so `palette-add` refuses it once either
    has changed, with the same `--asset ... --box ...` as the fix. An image path still works;
  - palette conformance report;
  - set colours: one set of `n` colours chosen by k-means in OKLab over several images together (each image weighted
    equally, `keep` colours fixed, independent of image order), `map_set` to map each image to it, and a per-image
    error report (mean and 95th percentile) with the colours used.
- **resample:**
  - pixel-grid detection (scale and offset of upscaled pixel art), returning a Grid transform;
  - mapping points, images and masks through a Grid transform (a click maps to the centre of its target pixel);
  - nearest, line-keeping and majority-vote downscale;
  - `alpha_coverage`, a cell's mean alpha (exact integers, half up), and `dither_alpha`, partial alpha into a fixed ordered Bayer 2, 4 or 8 pattern of 0 and 255 (an alpha above `(2M + 1) * 255 / (2n²)` at the pixel's matrix cell is opaque; RGB copied unchanged; `kiripix op dither-alpha`; ticket 0363);
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
- **style:** the outline's density on a figure's silhouette edge (`outline_density`: outline-colour pixels per edge pixel), and
  the pixel scale (`pixel_scale`: the gcd of all colour-run lengths, 2 or more when the image was upscaled). Numbers out, for
  the `style.*` Checks (ticket 0333).

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
| Depth (parallax; a room's `normals`, ADR 0014) | Depth Anything V2 Small (Apache-2.0; trial 0252), ONNX, input 1036 px on the long side or 518 px, recorded in the pin (`depth-anything-v2-small`, `runners/depth.py`; ticket 0340 compared DA3-Small and DA3-Base, Apache-2.0, and kept V2 Small). V2 Base and Large, and DA3 Large and larger, are non-commercial: never added | Manual depth planes; for normals, `mode = off`, or `flatten` and Overrides by hand |
| Inpainting (plate holes) | LaMa | OpenCV Telea or PatchMatch for small holes (OpenCV isn't a dependency yet); an edit API for large ones |
| Image-to-3D (optional) | Decide with Providers (deferred from M3, then from M6), after testing which fit 8 GB | Bought or hand-made models |

ONNX Runtime with CUDA is preferred to keep installs small, with PyTorch where a model needs it. The core works with
no GPU: Runners run on CPU, slower. Because results are pinned, the device that produced one doesn't matter.

## 9. Godot export

Kiripix writes Godot 4 text resources (`.tscn`, `.tres`) and PNGs under `export.godot.root`.

| Asset | Godot output |
|---|---|
| Room | A scene with these nodes: `Sprite2D` Plate; foreground `Sprite2D`s, y-sorted by their y-sort lines or above actors when flagged "always above"; `StaticBody2D` + `CollisionPolygon2D` from the `solid` Mask; `NavigationRegion2D` + `NavigationPolygon` from walkable ∩ reachable; `Marker2D` for Spawns and Exits (with metadata: IDs, targets); `PointLight2D` from light Markers; `GPUParticles2D` stubs from emitter Markers; an `Area2D` per area Marker (M4), with a `RectangleShape2D` the size of its box, `monitoring` and `monitorable` off and collision layer 0, so it never touches physics, and metadata `kiripix_id`, `kiripix_type`, `walkable` and `cell`. **Masks and `room.json` (M4):** the `solid` and `pit` Masks go beside the scene as 1-bit PNGs (`masks/solid.png`, `masks/pit.png`, and each Look's own `solid`), with `room.json`; the scene's root names `room.json` in `metadata/kiripix_room`. The game builds cell data, such as a battle grid, from these exact pixels, not from the simplified collision polygons; Godot's default lossless import keeps them exact for `Texture2D.get_image()`. (`LightOccluder2D` has no source for its shape yet, so it isn't in M2.) `solid` is on collision layer 1 and `pit` is a `StaticBody2D` of its own on layer 2: the game's Body drops layer 2 from its mask while it dashes. Side view: `oneway` → one-way collision; parallax planes → `Parallax2D`. **Looks** (M4): a `Sprite2D` per Look that has a Plate piece in a `Looks` node drawn with the Plate, at its region's box, `visible = false`, with metadata `kiripix_id`, `kiripix_type = "look"` and, when the Look has one, `condition`; each piece over a foreground Layer is a `Sprite2D` child of that Layer's node, so it sorts with the Layer and draws over it, also hidden and with the same metadata; a Look with its own `solid` is a `Node2D` named by the Look under a `LookSolids` node (with the Look's metadata), holding two `StaticBody2D`s on layer 1 (ADR 0013, ticket 0316): `added`, the pixels the Look makes solid, whose `CollisionPolygon2D`s start `disabled = true`, and `cleared`, enabled, the pixels that this Look alone clears. The room's `solid` body holds the room's `solid` minus every pixel some Look clears, so with no Look shown the scene collides exactly as the whole `solid` does. The pixels that several Looks clear form one enabled `Shared_<look>+<look>` body under `LookSolids` for each set of Looks, with `metadata/kiripix_looks` (a `PackedStringArray` of their IDs), so it is off while any of them shows. A Look's whole-Mask body is gone; its PNG (`masks/<look>.solid.png`) stays for the game's grid. Simplified shapes can leave a seam of up to the export's `tolerance` where a cleared body meets the room's; the grid, read from the PNGs, has none. A Look with its own `solid` also has `LookNavigation/<look>`, a `NavigationRegion2D` with `enabled = false` (its walkable ∩ its reachable), and a Look with its own Markers has `LookMarkers/<look>`, a `Node2D` with `visible = false` and the Look's metadata, holding its Markers with the room's node types (a light `enabled = false`), each with `metadata/kiripix_look`. **To show a Look the game** shows every node whose `kiripix_id` is the Look's, shows `LookMarkers/<look>` and enables its lights (emitters are the game's to start), enables `LookSolids/<look>/added` and disables every `cleared` and `Shared_` body that lists the Look, disables `Navigation` and enables `LookNavigation/<look>` (for a Look with one), takes `solid` for its grid as the room's ∧ ¬(the shown Looks' cleared) ∨ (the shown Looks' added) from `masks/solid.png`, `masks/<look>.cleared.png` and `masks/<look>.added.png`, hides a Loop under the Look by its own room data, and decides the draw order where two shown Looks overlap. A pixel any shown Look clears is clear and a pixel any shown Look adds is solid, so the order of the Looks doesn't matter; navigation for two shown Looks that both change `solid` is not exported (§16, open decision 8). When to show a Look is in the game's own room data, not in the Condition. `room.json` carries the same data (`looks`: ID, Condition or `null`, file, box, pieces with their Layer, `solid` and its `collision`, `added` and `cleared` (each `{file, collision}` or `null` without its own `solid`), `navigation` (vertices, polygons and outlines, or `null`) and `markers` as the room's entries; `collision.solid` stays the room's whole `solid`; `scene` gives the shapes of the room's `solid` body, each Look's own cleared pixels and each shared set, `{solid, cleared: {<look>: shapes}, shared: [{looks, collision}]}`), so another Exporter reads it, not the scene. The room's `markers` hold only its own. **Loops** (M4, ADR 0011): a `Loops` node after `Looks`, drawn with the Plate, holds a visible `Sprite2D` per Loop that has a Plate strip, at its region's box; each piece over a foreground Layer is a `Sprite2D` child of that Layer's node. Every Loop sprite has `hframes`, `vframes`, `frame = 0`, a shared unshaded `CanvasItemMaterial` (`light_mode = 1`) and metadata `kiripix_id`, `kiripix_type = "loop"`, `sequence` (a `PackedInt32Array` of frame, ticks pairs), `phase` and, when set, `light`. It is not an `AnimatedSprite2D`, which runs its own clock: the game sets `frame` from its frame counter plus `phase`, through `sequence`. A frame Loop that covers every opaque pixel of its Layer, and is the only frame Loop with a piece on that Layer, takes the Layer's own `Sprite2D` (`moves_layer`): the node keeps its name, sort position and `kiripix_id`, shows the strip with its `offset` at the box, and carries the Loop's metadata and `kiripix_loop`. Any other Layer under a piece of a frame Loop on a Layer shows its remainder (`remainders/<layer>.png`, the Layer with each such piece's frame-0 pixels cleared) with the strips as its children, so the Plate's fill shows where a frame moves away; a colour cycle, and a Plate Loop's piece over a Layer, is a child piece with no remainder. Files: `loops/<loop>/plate.png` and `loops/<loop>/layer.<id>.png` (the distinct frames side by side, wrapping into rows past 4096 px) and, for a cycle, `loops/<loop>/index.png` (8-bit: 0 outside the cycle, i + 1 for its i-th colour). A held Loop is left out, and `export.loop_held` refuses the room while there is one. `room.json`'s `loops` carry ID, form, `source` (`cycle`, `op`, `kit` or `edits`), layer, `moves_layer`, box, the Plate file or `null`, `hframes`, `vframes`, frames, `sequence`, ticks, `rest`, phase, light or `null`, pieces (layer, file, box), and for a cycle the index file, colours and mode; each of its `layers` gains `remainder` (a file or `null`). **Links** (M5, ticket 0267): after `Emitters`, a `Links` node (only when the room has a Link) with a `Node2D` per Link, named by its ID and ordered by ID, at the room's origin, with metadata `kiripix_id`, `kiripix_type = "link"`, `kind` and `two_way`, and two `Marker2D` children, `from` and `to`, at the ends in room pixels. The game moves the actor across by script; navigation and collision are unchanged. `room.json`'s `links` carry ID, `kind`, `from`, `to` and `two_way` and the Manifest lists the Link IDs in `ids.links`, frozen once exported. **Normal maps** (M6, ticket 0342, ADR 0014): for a room whose `normals` Stage has output (`mode = depth`), `export` cuts its one `normal.png` by the alpha of each picture into `normals/<file>` for the Plate (`normals/plate.png`), each Layer (`normals/layer.<id>.png`) and each remainder (`normals/remainders/<id>.png`), and for each piece of a Look and a Loop (`normals/looks/<look>/...`, `normals/loops/<loop>/...`): a piece takes the room's map cut to its box, with no depth call of its own, and a Loop's strip tiles the one cut across its frames, so they share it. Beside each map is a `CanvasTexture` `.tres` of the same name (`normals/plate.tres`: `diffuse_texture` the picture, `normal_texture` the map, no filter set), and the scene's `Sprite2D`s show it in place of the plain texture, as `ext_resource` of the same ID; every node, name and property is otherwise as before (a Loop's sprite stays on its unshaded material, so it is not lit until the game drops it). All the files are in the Manifest; no ID is added. A room with `mode = off` writes none of them and its scene is unchanged. The light's height and energy are the game's to tune to a room, and a normal-mapped Plate reads darker under the same light (trial 0252, finding 4). `room.json` is at `schema_version` 15: `normals` is `null`, or `{plate, layers: {<layer>: file}, remainders: {<layer>: file}, looks: {<look>: {file, pieces: {<layer>: file}}}, loops: {...}}` (version 14: its Exit Markers carry `one_way`, true when no return is meant; the scene is unchanged, the game decides what a one-way Exit does). `room.json` is part of the game's contract from M4: each format change bumps its `schema_version`. |
| Prop | A scene: a `Node2D` root at the origin (the y-sort point), a `Sprite2D` offset so the origin pixel is the root's own place, and a `StaticBody2D` footprint on collision layer 1, with a `CollisionPolygon2D` per convex piece of the polygon, relative to the origin. No body when the polygon is empty. The prop's `export` Stage leaves `sprite.png` and `prop.json` (`schema_version`, `asset`, `size`, `origin`, `collision`) in `out/export/`. The scene instances the sprite as `sprite.png` beside it. No ID is frozen for a Prop without states, so the footprint can be emptied. A Prop with states (6.2) exports one scene: the root `Node2D` at the default state's origin, and one `Node2D` per state named by its ID (the default's included), each with its own `Sprite2D` (offset so its origin pixel is the node's place) and `StaticBody2D` footprint on layer 1. Only the default is `visible` with its polygons enabled; every other state is `visible = false` with its `CollisionPolygon2D`s `disabled = true`. The node carries metadata `kiripix_id` (the Prop's), `kiripix_type = "prop_state"` and `kiripix_state`. The game shows a node and enables its polygons to switch. Files: `sprite.png` for the default, `states/<s>.png` for the others; `prop.json` (`schema_version` 2) adds `default` and `states` (ID, file, size, origin, collision). State IDs are frozen once exported (`ids.states` in the Manifest). |
| Character | `texture.tres` (`CanvasTexture`: the colour atlas as diffuse, the normal atlas as its normal map), `frames.tres` (`SpriteFrames`: one animation `<clip>_<dir>` per clip and direction, such as `walk_sw`, each frame an `AtlasTexture` region of the `CanvasTexture`, at the clip's speed and loop flag), and a scene: a `Node2D` root at the feet with an `AnimatedSprite2D` child `Sprite`, `centered = false`, offset so the pivot pixel is the origin. **A cell per clip (M5, ticket 0304):** a clip with its own larger cell (0303) keeps its regions at that cell, and every frame is padded to one logical cell with `AtlasTexture.margin = Rect2(logical pivot - the clip's pivot, logical size - the clip's cell)`, the logical cell being the smallest that holds every clip's cell with the pivots on one pixel. The scene's one offset is the logical pivot, so the feet stay on one pixel in every animation and the game's loader changes nothing (no per-animation offset on `animation_changed`). A character whose clips share one cell has no `margin` and the body's pivot, as before. **Trimmed cells (M5, tickets 0308, 0309):** `sheet` packs each frame cut to its opaque box, so a frame's `rect` (the `AtlasTexture.region`) is that box and its `offset` is where the box sits in its clip's cell. The same one `margin` restores it: `Rect2(offset + logical pivot - the clip's pivot, logical size - rect size)`, written for every frame except one whose box is its whole logical cell. The normal map is the same `AtlasTexture`'s, so it takes the same region and margin; every frame draws pixel for pixel as the untrimmed cell, with `flip_h` too. `flip_h` mirrors the whole logical cell, so a game that flips and corrects the feet itself reads the cell from the frame texture's size (the logical cell), not from `character.json`'s top-level `cell` (the body's). Both atlases sit beside them. So does `character.json`, copied byte for byte from the `export` Stage (ticket 0289): the game reads its foot events and points there, and its `files` are names relative to it, so it needs no `res://` path. The character's `export` Stage leaves `color.png`, `normal.png` and `character.json` (`schema_version`, `asset`, `files`, `cell`, `pivot`, `atlas`, `directions`, `clips` with each direction's frames as `index`, `rect` and `offset`, `fps`, `loop`, `stationary`) in `out/export/`. The frozen IDs are the animation names. **Part ramps (M4):** `character.json`'s `parts` (each part's name, materials, row, `shared` when its colours are the table's, palette indexes and RGB, dark to light) and `rows` (the table's part names and lengths, in order), and `ramps.png` beside the atlases, one row per part of the Project's ramp table in its order, padded to the longest ramp; a part the character lacks is a transparent row, so a row is the same part on every character. The scene's root names it in `metadata/kiripix_ramps`, with the part names in row order in `metadata/kiripix_parts`. **Points (M5, ticket 0237):** for a character whose `render` has `points`, `character.json` has `schema_version` 5 and each frame of each direction a `points` map, `{name: {x, y, hidden}}`: the pixel that holds the point, in whole px relative to the pivot, y down as Godot draws, carried by `sheet` from `render.json`; the game reads them there, and the `.tres` files and the scene don't change. A character without points keeps `schema_version` 4 and its file byte for byte. **Events (M4, lower priority):** each clip's `events`, such as `foot`, the game frames where a foot plants. |
| Sprite | As a character, under `sprite/`. **Blend and light (M6, ticket 0364):** a sprite whose `export` has `blend=add` or `lit=false` writes `blend` (`"mix"` or `"add"`) and `lit` (a bool) into `character.json`, which is then `schema_version` 8 (a file with neither stays version 7 byte for byte, and so does its scene; a reader migrates a version 7 or older file to `mix` and lit). The scene's `Sprite` (the `AnimatedSprite2D`) then has a `material` that is a `CanvasItemMaterial` sub-resource `effect_material` with `blend_mode = 1` for `add` and `light_mode = 1` (unshaded) for `lit=false`, only the properties that differ from Godot's own defaults, and the offset is, as for every character, the pivot (an effect's anchor, §6.4) so the pivot pixel is the root's own place. The effect's clip IDs are frozen like a character's (`<clip>_<dir>`). The game frees a one-shot (a clip with `loop` false, which ends on its last frame) on `animation_finished`. A sprite exports its clips in the directions it has, so a cone exported as one direction faces as drawn (east); the game turns it, or the sprite has `s w n e`. |
| Icon | No scene: the game's inventory UI loads the texture. `icons/<name>.png` and `icons/<name>.json` (`schema_version`, `asset`, `size`) under the export root, both in the Manifest, copied byte for byte from the icon's `export` Stage (`out/export/icon.png`, `icon.json`). They sit in one `icons/` folder for every icon, not under `icon/<name>/`, so the game can load any icon by name. The icon's ID is its Asset ID (`icon.<name>`), which names its Manifest and is frozen once exported like any Asset's; no other ID is exported. `--prune` removes a deleted icon's files with their `.import` sidecars. |
| Portrait | No scene: the game's portrait UI loads the PNGs and reads `portrait.json`. Under `portraits/<name>/` in the export root: `neutral.png`, `<emotion>.png` for each emotion and `portrait.json` (`schema_version`, `asset`, `canvas`, `anchor`, `fallback`, `emotions`: ID and file, `neutral` first and then the Decisions' order), all in the Manifest, copied byte for byte from the portrait's `export` Stage (`out/export/`). Every image is the canvas's size on the same anchor (`export.portrait_canvas`), with binary alpha, and the fallback names an emotion of the set. The emotion IDs are in the Manifest's `ids.emotions` and frozen once exported: an `emotion_remove` or `emotion_rename` of one is refused before it is recorded (`export.id_frozen`); adding an emotion is fine. `--prune` removes a deleted portrait's files with their `.import` sidecars. |
| Wearable | Under `wearable/<name>/`, laid out as a character's and on its cell, pivot and frame layout: `color.png`, `normal.png` and `depth.png` (16 bit gray, 0 nearest, the body's depth scale), `texture.tres`, `frames.tres` (the body's animation names `<clip>_<dir>`, each frame the same cell of the atlas as the body's), a scene (a `Node2D` and an `AnimatedSprite2D`, drawn offset like the body's), and `wearable.json` (`schema_version`, `asset`, `body`, `order`, `files`, `cell`, `pivot`, `atlas`, `directions`, `clips`, `parts` with their ramps), all in the Manifest. `order` is the default stacking order over the body (0), the `sheet` parameter `order` (default 10); the game stacks by it, or by `depth.png` for an exact result. No outline: the game draws it once on the stack. Refused with `wearable.body_not_exported` until its body is in the game (its Manifest lists it as exported) with the same cell and pivot in its `character.json`; in `export --all` the body counts when it is exported in the same call. The animation names are the clip IDs frozen in its Manifest. `--prune` removes a deleted Wearable's files with their `.import` sidecars. |
| NPC | `npc/<name>/npc.json` (`schema_version` 1, `asset`, `base` and `base_path`, `wearables` (`{id, order, path}`, bottom to top; `path` is the Wearable's exported scene), `colours` by Part (`{choice, rgb}`, the ramp dark to light, as `CharacterSprite.set_colours` takes it)), in the Manifest under its Asset ID (frozen with the Manifest's name; no other ID). No images and no scene: the game draws the base's and the Wearables' exports. Refused with `npc.base_not_exported` or `npc.wearable_not_exported` until each is exported (one exported in the same `export --all` counts); `--prune` removes a deleted NPC's file (M6, ADR 0015, ticket 0358). |

The game instances these scenes and adds its own scripts in its own scenes, so nothing it writes is ever regenerated
over (principle 10).

### The Manifest (ADR 0003)

- **Where:** only in the Godot project, under the export root, committed with the game. It has one file per asset,
  so unrelated assets never conflict in git. A copy in `.kiripix/` is only a cache. Without the game repo at the
  configured path, export and the ID freeze checks refuse rather than guess.
- **Contents:** each asset's ID, every ID it exports (Markers, Layers, clips, node names derived from Masks, a room's Looks and Loops, each in its own list, and a room's Look Markers as `<look>/<marker>` in `ids.look_markers`, left out when empty), its
  files with their hashes, an "exported" flag and a counter that goes up each time its exported hash changes. The
  Manifest also records its schema version and the Kiripix version that wrote it. The game's tests read it. Schema 4 (ticket 0345): `ids.masks` lists every painted Mask a room exported, a file name the game's grid reads, so removing or renaming one is refused (`export.id_frozen`) once it is exported; a schema 3 Manifest is read as it is (what it listed is what it froze) and rewritten once at the next export, and an older Kiripix refuses a schema 4 one. Schema 3 (ticket 0316) added `ids.look_markers`; a schema 2 Manifest is read as having none and rewritten once at the next export, and an older Kiripix refuses a schema 3 one. A room's `ids.markers` lists only its own Markers, so moving an exported Marker into or out of a Look changes its node path and is refused (`export.id_frozen`); `manifest merge` takes the union of the lists.
- **Ownership:** Kiripix overwrites or removes a file only if the Manifest lists it and its current hash matches.
  Each generated text file starts with a `; generated by kiripix, do not edit` comment, but that is a hint for humans,
  not the rule. Godot's `.import` sidecars are never owned: export ignores them, and only `--prune` removes the one of a
  file it prunes.
- **Conflicts with the game's edits:** a hash mismatch (someone saved the scene in the Godot editor) makes export
  refuse and name the file. `--force` backs it up to `.kiripix/backups/<timestamp>/` and overwrites it. An unmanaged
  file already at a target path needs `--adopt`, with the same backup. `--dry-run` lists the two cases separately.
- **Deleting an asset:** no Command does this yet: it means removing the asset's folder. Its files stay in the game until
  an explicit `export --prune`, under the same hash rule and backup. Alone, `--prune` prunes every deleted asset and
  exports nothing; with `--all` it exports, then prunes; with an ID it prunes that deleted asset, and refuses if the asset
  still exists. Pruning a file also removes its Godot `.import` sidecar (backed up with it, under `--force`), then any
  folder left empty. The Manifest never owns a sidecar, since Godot makes it again, so only a pruned file's is touched.
- **Frozen IDs:** once exported, an ID can't be renamed or removed; adding new IDs is always fine. Before the first
  export, IDs can be renamed freely. A y-sort line makes no node, so its Marker ID isn't frozen. A `remove` or `rename` Decision on an exported Loop is refused before it is recorded. Deleting an asset and
  creating one under a new ID is allowed, with a warning if the old ID is still referenced.
- **Branch merges:** when two game branches export the same asset, `kiripix manifest merge` (a git merge driver)
  resolves it: the higher counter plus one, the union of the IDs, and our `files` with theirs in `replacing`, so the next
  export accepts either. Export checks that the driver is configured in the clone, and its finding's `fix` is `kiripix
  manifest install` (`.gitattributes` alone does nothing). The exported images and scenes (`*.png`, `*.tscn`, `*.tres`
  a room's `room.json` and a character's or sprite's `character.json`, under the export root) can't be merged by git either, and the Manifest already accepts either side, so `manifest
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
  so explicitly: `fix: null` plus `owner_action: "…"`. A finding about many pixels also carries `points`, a list of
  `[x, y]` in target px, left out of the JSON when there are none.
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

`accept`, `palette-add`, `ramps-add`, `style-add` and `style-remove` (which choose what the Project's look is), `approve` (which spends the
Project's money on a Provider call, ticket 0381), and any future Command that stands for the owner's own judgement, are **owner-only**. This is a guardrail
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
server is up. The UI refreshes on the `changed` event (§10.6) when an agent changes something.

### 10.5 The CLI

One command, `kiripix` (alias `kpx`), with subcommand groups. Every command takes `--json`.

```
kiripix init [dir]                          new project
kiripix describe project|<kind> [--stage s] Kinds, Recipes, stage parameters, Decision schemas, Checks; --stage gives one Stage
kiripix schema [command]                    JSON Schemas of Command inputs and outputs
kiripix status [--kind room] [--match <glob>]   board: every asset, its stage and state; --match narrows to a district (M6)
kiripix show <id>                           one asset: variants, the pick, each stage's parameters, decisions and images
kiripix new <kind> <id> [--view top|side] [--base <character>] [--from-parameters <file>]   new asset from its recipe; a character on a base, or from a parameter file (M4)
kiripix next <id>                           the next stage and what it needs (a command, or the owner's action)
kiripix queue [--match <glob>] [--kind <kind>]   everything waiting on the Owner: reviews, owner-only inputs and findings with their hand-over notes; findings an agent can fix are counted per Asset, not listed (M6)
kiripix district <glob>                     a district's rooms in ID order (size, furthest built and waiting Stage, queue counts, a cached 1x thumbnail), every Exit with its pairing (paired, one_way, unpaired, outside) and the rooms' Links; a Probe (M6)
kiripix to-paint --match <glob> [--out <dir>]  every prompt and canvas a district needs, in one folder (default .kiripix/to-paint/<date>/): per room waiting on its Source `<nn>-<room>.prompt.txt` (the brief's built prompt), or, mid-`extend`, its next canvas `<nn>-<room>.<side>.png` with the prompt; `index.md` names the file each image comes back as (`<room>.png`, `<room>.<side>.png`, for `inbox`); rooms with no brief are listed under "no brief yet"; records nothing in the Project (M6)
kiripix inbox [--folder <dir>] [--dry-run] | --file <image> --asset <id> [--sides <side>] [--max-residual PX]   file the PNG and JPEG images the Owner made elsewhere (`[inbox] folder`, `inbox/` by default) by their file names, the ones `to-paint` lists: `<room>.png` or `<room>-<anything>.png` (a Kind prefix is optional) is imported as a Variant, `<room>.<side>.png` is joined on as `extend add` does, after writing the canvas record it needs; a name that matches no Asset, or several, stays with `inbox.unmatched` or `inbox.ambiguous`; a failed `extend add` stays with its own finding (exit 2); each filed image moves to `<folder>/imported/<date>/`, so a second run imports nothing; never picks, but names the rooms that now have exactly one Variant with their `pick` command; `--dry-run` changes nothing; `--file` files one image into one named Asset, whatever its name, and doesn't move it (the UI's drop on a waiting room) (M6)
kiripix run <id>|--all|--match <glob> [stage] [--force [--from <stage>]] [--rerun] [--cpu]   run stale and todo stages; --from forces that stage and every one after it; --rerun also re-runs stale Runner calls
kiripix set <id[,id...]> <stage> key=value...   set stage parameters; several Assets, all or none (M5)
kiripix decide <id> <stage> --decision '<json>' | --file d.json [--brief]   record a Decision (validated against the stage's schema); a file may hold a JSON array of Decisions, recorded all or none; --brief leaves out `current`
kiripix override <id> <stage> <png>         record an Override from a painted image
kiripix mask-import <id> <png>              import a painted mask image (the masks Stage's import Decision)
kiripix plate-import <id> <png>             import a Plate image (the layers Stage's plate Decision)
kiripix undo <id> <stage> [--brief]         undo the stage's last Decision
kiripix redo <id> <stage> [--brief]         redo it
kiripix accept <id> <stage>                 confirm a needs-review stage (owner-only)
kiripix extend <id> canvas|add <png>|undo|done|crop [--side east|south|west|north] [--keep N|ACROSS,DOWN] [--box x0,y0,x1,y1] [--size WxH] [--max-residual PX]   the canvas for the next piece of a large room, joining a piece onto it (`--max-residual`, up to 1.0, for a strip the model re-rendered), and the joined image as a Variant (M4); crop writes a crop of the Source at the image model's size for a Look's edit (M5)
kiripix import <id> <file> [--role variant|clip-source|rigged|parameters|sheet] [--look l | --loop l [--frame n]] [--of piece|crop]   set a source from an outside image or model; --role says what a character's or sprite's file is; --look adds an edit Variant of Look l; --loop imports a frame Loop's kit frames, --frame an edit of the Source as frame n (M4); --of says the edit was made on a piece or a crop of the room (M5)
kiripix loop kit <id> <loop> <folder> [--frames N]   write a frame Loop's kit to paint on (M4)
kiripix clips copy <id> --from <character> [--clip c,...] [--replace]   copy another character's clip Decisions and their clip sources (M4)
kiripix gen <id> [-n N] [--provider x] [--prompt "..."] [--look l | --state s | --emotion e | --side east] [--reference png]   paint through a Provider (M6): a room's Source from its brief's prompt, a Prop's or portrait's Source, an edit of the picked Source as Look l, state s or emotion e, or the next `extend` piece from a fresh canvas (kept as candidates, joined by no one: `extend add` joins the one chosen, under 1.0 px for a Provider that re-renders the kept strip); each image a Variant, never picked; the estimate and the month's remaining budget on stderr and in `data` before the call; refused before sending past `max_images_per_call`, `max_calls_per_day` or the budget (`cost.budget_exceeded`, exit 3); with `approve = "each"` writes a pending call and exits 3 (`provider.approval_needed`); the only command that calls Providers
kiripix approve <id> | --list               send a pending call (owner-only): its limits and budget checked again, refused if an input image changed (`provider.call_stale`); its Variants and ledger line stored as `gen` would, the pending call deleted (M6)
kiripix reject <id>                         delete a pending call, sending nothing; not owner-only (M6)
kiripix pick <id> <variant> [--look l | --loop l --frame n]      record the chosen variant; --look picks Look l's edit, --loop --frame a Loop frame's edit (M4)
kiripix check <id>|--all                    run checks (--all includes Project checks), list findings with positions; --all also lists each Asset `next` doesn't call done, with what `next` says (`unfinished`; not a finding, the exit code is the Checks')
kiripix preview <id> [--stage s] [--overlay masks|walkable|reachable] [--region x,y,w,h] [--grid N]
                                            write a preview PNG, print its path
kiripix probe <name> <id> <args...>         run a Probe, such as segment-preview or flood-preview x,y,tolerance ..., or half-cells <mask> (the cells of a room's areas that a Mask half covers), or `style` (M6, no arguments; `data.result` has `asset`, `kind`, `stage`, `built`, `measures` {`outline_density` {outline_px, edge_px, density} or null, `pixel_scale` {runs, gcd, median, run1_share}}, `references` [{asset, kind, stage, built, left_out, measures}], `range` {`outline_density`, `pixel_scale`: {low, high, furthest} or null, over the references other than the Asset}, `limits`, `findings` the `style.*` findings `check` gives)
kiripix style-add <id>                      make an Asset of a Kind with style Checks a style reference in `[style] references` (owner-only, M6); comments kept; `style.reference_unknown` for an unknown ID or another Kind
kiripix style-remove <id>                   take it out again (owner-only); an entry that names no Asset can be removed too
                                            (several flood tries in one call, nothing recorded); every Mask answer
                                            has `pixels` and a bounding box `box`, and `--summary` leaves out `runs`
kiripix cast-sheet <id,id,...> [--clips idle,walk] [--directions s,sw] [--frames N] [--scale 3] [--stack order|depth] [--colours <file>]   a Probe: several
                                            characters or sprites side by side, each at its pivot on one ground line,
                                            from their built sheets, to .kiripix/previews/ (M4). A figure may be a
                                            stack, `character.a+wearable.b+wearable.c` (M6, 0337): the Wearables drawn
                                            over the body by their `order`, or by depth with `--stack depth` (the Op of
                                            0294); a Wearable made for another body is `cast.wearable_body`. `--colours`
                                            is a TOML (`[[figure]]` tables) or JSON file, one entry per figure in order,
                                            each `{part = [[r, g, b], ...]}` dark to light, as long as the Part's ramp:
                                            the game's swap, a pixel in the Part's ramp takes the colour at the same
                                            place, applied to the body's and each Wearable's Parts (a colour off the
                                            palette is `cast.colour_off_palette`, a Part the figure lacks
                                            `cast.part_missing`, warnings); with
                                            --snapshots <label,...>, one row per snapshot label, titled with the
                                            parameters that differ between rows (M5)
kiripix snapshot <id,id,...> --label <name> [--replace]   a Probe: copy the built sheets under a label, in
                                            .kiripix/snapshots/, with the parameters of the Stages they were built from
                                            (a stale Stage is noted); `--list` the labels; `--drop <label>` deletes one (M5)
kiripix export [<id>|--all] [--dry-run] [--force] [--adopt] [--prune]   write to the Godot project
kiripix manifest [merge|install|repair]     the git merge driver, installing it, and the manual fallback
kiripix op <op> <args...>                   one op directly (quantize, conformance, and extend's join: register-piece, match-tone, seam-join)
kiripix op palette-suggest <image> --add N [--scale 2.15] [--min-distance d]   propose up to N colours the palette lacks; writes a proposal under .kiripix/, changes nothing in the palette
kiripix op palette-suggest --asset <room|prop> [--box x,y,w,h] --add N   the same from a built `fit` Asset's Source (§7)
kiripix palette                             the Project palette: its file and every colour (`index`, `hex`, `name`), in file order (M4)
kiripix palette-add <proposal> [--name prefix]   append a proposal's colours to the palette (owner-only); rooms using the palette go stale
kiripix ramps-add <character> --parts a,b [--colours] [--dry-run]   append parts of a character's built palette to the Project's ramp table (owner-only, M4)
kiripix masks-add <name> --colour #RRGGBB --meaning "<text>" [--view top|side]   add a named painted Mask to `[masks.<view>]`, comments kept (an agent may run it, M6): snake_case, not `walkable`, `foreground` or an existing Mask (`masks.name_taken`), its colour not another Mask's or an import colour of the view (`masks.colour_taken`). Kiripix gives it no meaning: `reach` and the walk test ignore it; `describe room` lists every Mask with its view, colour and meaning; a Decision on a Mask later removed by hand fails `masks` as `masks.unknown`
kiripix clips-add <character> --clips a,b [--foot a] [--dry-run]   append clips a character decided and built to the Project's clip table (an agent may run it, M5); `check --all` and `export --all` then run `clips.timing_differs`
kiripix track <id> <stage> --seconds N      log a span of the Owner's active time (owner-only; the UI sends these); appends to the Asset's time.jsonl (M4)
kiripix stats <id>|--all [--since <date>]   the Owner's active minutes, Decisions, undos and redos per Asset and Stage (M4)
kiripix cost [--month] [--since <time>]     Provider spend from the cost ledger (`.kiripix/cost.jsonl`, one line per call sent, with the token counts the Provider reported): by month and by Provider; this month's spend, the cap and what's left; with --since, the calls, cost and tokens since a time, such as an agent's session's start (M6)
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

**The `changed` event** tells the UI what changed in the Project without scanning it. Every process that writes the
Project (a CLI call, `serve`) appends what it wrote, after the write is in place, to its own file
`.kiripix/changes/<pid>-<process start in ms>.jsonl` (`kiripix.core.changes`): one line `{"t", "paths"}` of
Project-relative paths, where a Stage's output is the folder, not each file in it. Every write through `core.atomic`
and core's own renames and removals records itself, and nothing else writes to that file, so no lock is needed. `serve`
lists the folder every 0.3 s, reads each file that grew up to its last complete line, and sends one
`changed` event per tick with new lines: `{"count", "paths" (first 200, sorted), "own"}`. `own` is the subset of `paths`
written only by `serve`'s own process (the Commands it ran); a path an agent also wrote in the same tick is not in it.
`serve` starts at the end of every file, so it answers at once, and it deletes the files of processes that are gone and
over a day old when it starts. Nothing under `.kiripix/`, `.git`, a `.tmp-*` or `.old-*` folder, or a `time.jsonl` is
recorded. A file changed by hand outside Kiripix is not noticed; the UI refreshes when its window gets the focus and
with a Reload button. The files are a record of writes, never of status (ADR 0005).

**What `serve` remembers (ticket 0373).** `status` and `queue` work every Asset out from scratch, about 15 ms an Asset warm. In
`serve`, the Session keeps each Asset's derived state in memory (`kiripix.core.memory`), in layers: its Stage states (what
`status` and `queue` both start from), whether the game is behind (`status`'s `export_command`) and its part of the `queue`.
Each is worked out at most once at a time: two calls that need the same one wait for one computation. Memory only, never a
file (ADR 0005); the hash cache and the Check cache under it stay as they are. The CLI is one process and one call, so it has
none and is unchanged. It is never older than a change Kiripix recorded: every `status`, `queue` and `assets` call first reads
the change files from where the last call stopped (the same record as the `changed` event, with no 0.3 s wait), so a write
recorded before the call began, by whichever process, is seen by it. A recorded path drops what it touches: a path inside an
Asset's folder drops that Asset, every Asset that may read it (the characters and NPCs made from a base, an NPC's chosen
Wearables, a Wearable's body, a body's Wearables) and, for its `asset.toml`, the Assets it names now and named before; a path
outside `assets/<kind>/<name>/` (`kiripix.toml`, the palette, the style references, a file a Check reads) drops everything. A
computation that was running when anything dropped is not kept. The game's files are not recorded (they are outside the
Project), so `status` asks about them on every call (a digest of the export root's files by name, time and size) and works an
Asset's `export_command` out again when it changed. A file changed outside Kiripix is not in the record: the UI's full refresh
(Reload, window focus) sends the same `refresh` token, a string it makes up for that refresh, with `assets`, `status` and
`queue`; the first call with a token `serve` hasn't seen forgets all of it, the others with the same token keep what they work
out. `assets` is the cheap list: each Asset's ID, Kind, name, `base`, `body` and whether it is a style reference, from the
`asset.toml` files alone (no input hash, no status), kept in step with them in `serve`. `status` and `queue` also take `assets`,
a list of Asset IDs (the rows a list shows; an empty list asks for none, and an ID that isn't an Asset is an `asset.not_found`
finding), so the UI can ask for the rows in view first and the rest in chunks.

**MCP** (`kiripix mcp`, stdio) exposes only the Commands tagged for it, at first `status`, `describe`, `next`, `run`,
`set`, `decide`, `check`, `preview`, `export`, `op`, `gen`, `pick`, `cost`.
- **Reviews:** when a stage is `needs-review`, the result says "needs-review: owner must accept" with the preview
  path, so the agent can report back instead of stalling.
- **Results:** JSON plus file paths. Images are returned only when the caller asks (`preview` with `inline=true`),
  because images cost tokens.
- **Spend:** a tool that spends money (`gen`) states each call's estimate (from the Provider's dated price table) and the
  month's remaining budget (`budget_usd_month` less the ledger's spend for the calendar month, UTC) before it sends, on
  stderr and in `data`, and refuses a call whose estimate would cross the cap before sending it (`cost.budget_exceeded`,
  exit 3, `-n` refused whole). Each call sent appends its actual cost (the Provider's reported usage, else the estimate,
  marked so) and the reported token counts to the cost ledger, and states it after the call (stderr, and `usd`, `usage`,
  `month_spent_usd` in `data`); a refused call the Provider still bills is recorded too. With `[providers] approve =
  "each"` (the default) `gen` only writes a pending call (`.kiripix/calls/<id>.json`: the prompt, the input images and
  their hashes, the estimate) and the Owner sends it with `approve` (tickets 0378, 0379, 0381).

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
- The UI refreshes on the `changed` event (§10.6) when an agent changes something. Owner-only calls send the session
  token `serve` gave the browser.
- The Asset list shows from the cheap list (`assets`, §10.6) before any `status` answers; a row's status fills in when it
  arrives, and the UI asks `status` for the rows in view first (by `assets`) and the rest in chunks. A full refresh (Reload,
  window focus) sends one `refresh` token with every call, so `serve` forgets what it remembers of the Project first.

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
  providers/   image API Providers (openai, M6): a prompt and images in, PNGs and their cost out; core keeps the key, the budget and the ledger
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
  image model's own UI (the budget is $0), and Kiripix joins it. No Provider is needed; once generation lands (deferred from M6), `gen` may drive it. The trial
  [0063](../backlog/m2/0063-m2-multi-screen-source-trial.md) found that the join needs three steps. Register: the model redraws
  the kept strip and scales the whole piece by up to about 1 %, so a plain shift leaves a step. Tone: the redrawn strip's
  brightness differs, so match it row by row. Seam: take the least-difference path through the overlap, with a short blend. A
  piece also fails when too little of a subject is in the kept strip, so the tool must let the Owner choose the strip and retry.
  `--keep` takes one number or two, across and down, for a corner's two strips ([0231](../backlog/m4/0231-m4-extend-keep-per-axis.md)).
  A corner piece joins inside the L's bounds, each overlap ending at the piece's own edge, and `done` crops an open margin of
  up to 2 px that a piece registered just inside the image's edge leaves ([0230](../backlog/m4/0230-m4-extend-corner-off-by-one.md)).
  `add` refuses a piece whose registration misses by more than `[extend] max_residual` (0.5 px by default, the most a strip the
  model left untouched misses by), and `--max-residual` on `add` and `inbox` overrides it for one call. A model that re-renders the
  whole canvas, kept strip included (GPT Image), returns the same picture warped by under a pixel, with new texture: a real piece
  registered to 0.66 px and joined with no visible seam. Raised to at most 1.0 px, the limit joins such a piece and `add` warns
  `extend.strip_repainted` (the residual, the gain, the seam's difference), so the Owner looks at the seam; a strip from another
  scene (1.34 px or more, or too few patches to fit) and a strip with part of its layout moved (1.2 px for 2 px) still fail
  ([0377](../backlog/m6/0377-m6-extend-joins-a-re-rendered-strip.md)).
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

**M5: the game's next needs, then character layers.** Re-planned on 2026-11-16 from the game's list at the M4 gate
([0236](../backlog/m5/0236-m5-the-games-next-needs.md), which records each item's result and the Owner's choices). The game
is at its M03 and needs layers only at its M11, so its nearer needs go first:
- **Things held in the hand** (the game's M03 phone idle, M05–M06 weapons and the instrument): named points per frame (a hand,
  the head, a socket) recorded by `render` and exported in `character.json`
  ([0237](../backlog/m5/0237-m5-render-records-named-points.md)), then a trial of 0170's (a) attach against (c) a layer, with a
  grip that sits in the hand and the cell rule ([0238](../backlog/m5/0238-m5-held-things-trial.md)).
- **A Project clip table** (`[[character.clips]]`) and `clips.timing_differs`, so every body plays one timing
  ([0239](../backlog/m5/0239-m5-project-clip-table.md)).
- **A `portrait` Kind** (the game's M04): one Asset per character's set, each emotion an image-model edit of the neutral image,
  with one fit and the set's own colours (principle 6's exception), the head's place fixed on the canvas and the body free to
  change between emotions ([0240](../backlog/m5/0240-m5-portrait-kind.md); a trial first; [0321](../backlog/m5/0321-m5-portrait-whole-body-emotions.md)).
- **A Prop's states**, any number of them: the laneway's bins standing and toppled ([0257](../backlog/m5/0257-m5-prop-states.md)).
- **Speed and upkeep:** the test suite (80–90 minutes at the M4 gate) builds its rooms and characters once per module, and
  Kiripix starts faster ([0275](../backlog/m5/0275-m5-tests-build-a-room-once-per-module.md) to
  [0277](../backlog/m5/0277-m5-start-faster-pydantic-and-typer.md)); a change to a Stage's code makes it stale through a
  version it declares ([0278](../backlog/m5/0278-m5-a-stage-code-change-makes-it-stale.md)); settling an area's cells, and
  `palette-suggest` from a room, as one Command each (0279, 0280); the UI's missing clip controls and points (0282, 0284).
- Inner lines where a part crosses itself, at a depth step inside one material ([0246](../backlog/m5/0246-m5-inner-lines-at-a-depth-step-op.md),
  [0247](../backlog/m5/0247-m5-finish-inner-lines-at-a-depth-step.md)); `set` on several Assets and labelled snapshots for
  setting trials across a cast ([0248](../backlog/m5/0248-m5-snapshots-for-trials-across-a-cast.md)); the room first pass as a
  workflow ([0249](../backlog/m5/0249-m5-room-first-pass-workflow.md)); the M4 gate's findings (0232, 0233, 0235, 0250).
- **Answers the game needs before its M09–M10:** the tileset trial with no code
  ([0251](../backlog/m5/0251-m5-tileset-trial.md)) and normal maps for painted rooms from a depth Runner
  ([0252](../backlog/m5/0252-m5-environment-normals-trial.md)), both trials; the `icon` Kind (the game's M08,
  [0253](../backlog/m5/0253-m5-icon-kind.md)); a trial of suggesting a room's foreground Layers
  ([0286](../backlog/m5/0286-m5-suggest-foreground-layers-trial.md)).
- **Last, for the game's M10–M11:** Looks with their own Markers, two at once and `reach` per Look (the rest of open decision 8,
  [0254](../backlog/m5/0254-m5-looks-markers-combining-and-reach.md)); traversal Links
  ([0255](../backlog/m5/0255-m5-traversal-links.md)); and character layers, below. They stay in M5 (the Owner, 2026-11-16).

**Character layers** were added on 2026-11-11 for the game's customizable MC (its DEC-052, needed by its M11): hair styles
and outfits rendered once each as layers over a body, with the body as a holdout, on the body's clips, camera, frames and
pivots, so the cost adds per layer and no combination is rendered. A trial comes first
([0153](../backlog/m5/0153-m5-character-layer-trial.md)); the work is [0152](../backlog/m5/0152-m5-character-layers.md).
The two bodies are base Models built by Claude in headless Blender
([0164](../backlog/m4/0164-m4-claude-built-base-models-trial.md)), and a character made from a base shares its rig and clips,
so it needs no Mixamo round trip of its own ([0165](../backlog/m4/0165-m4-characters-share-a-base.md), built in M4; §6.3).

**M6: rooms at chapter scale, style that holds, NPCs from bases.** Re-planned by the Owner on 2026-11-18, before its
tickets are split. The game's top risk is room throughput: its M15–M16 needs about 30 Chapter 1 rooms at final art, at about
one room per game milestone today, and its M17 needs the chapter's NPCs. M6 serves those needs. Generation and agents move
out (below). Split into tickets on 2026-11-19 ([0324](../backlog/m6/0324-m6-rooms-at-chapter-scale-style-npcs.md),
with the Owner's open questions; the gate is [0338](../backlog/m6/0338-m6-gate.md)). The Owner's notes:
- **Rooms at chapter scale.** Three parts:
  - **A review queue:** every `needs-review` Decision and failed Check across all Assets, in one keyboard flow, so the Owner
    can approve many rooms' first passes in one sitting.
  - **First passes without the Owner:** the room first-pass workflow
    ([0249](../backlog/m5/0249-m5-room-first-pass-workflow.md)), run over a list of rooms. Each room stops where it needs the
    Owner, and the review queue collects those stops.
  - **The batch view for whole districts**, moved here from Later: a chapter's rooms are coming in.
- **A style match Check across Kinds.** The game's high risk is that 3D characters, painted rooms and imported sprites don't
  match. The Check scores an Asset against reference Assets the Owner picks: palette use, the range of value and saturation,
  outline density, pixel scale and light direction. It uses deterministic Ops. Principle 3 ("enforced by checks, not by
  memory"), and needed before generation makes Assets in bulk.
- **NPC variants from a base:** a background NPC made from a base character ([0165](../backlog/m4/0165-m4-characters-share-a-base.md)),
  its layers ([0152](../backlog/m5/0152-m5-character-layers.md)) and its ramp swaps, with no new render. The Owner's answers
  ([0336](../backlog/m6/0336-m6-npc-variants-from-a-base.md), 2026-11-20): an Asset of a new Kind `npc` holds the choice
  (an ADR, 0355), it changes only Wearables and colours, colours are named `choices` in the ramp table, NPCs come in bulk
  from a seed once one works, and the speaking cast stay characters. Tickets 0355 to 0360.
- ~~Maybe the tileset recipe.~~ **Not in M6:** the tileset trial
  ([0251](../backlog/m5/0251-m5-tileset-trial.md), 2026-11-19) chose painted rooms for chapter 1; the recipe stays under
  "Later" (below).
- **Added on 2026-11-19 by the Owner, for the game's M06–M10:** room Sources in bulk (the brief renders the prompt without a
  Provider; `to-paint` and `inbox`; 0348 to 0351); normal maps for painted rooms, approved after the trial 0252 (a `normals`
  Stage between `masks` and `palette`, off by default; ADR 0014; 0339 to 0343); named terrain Masks exported for the game's grid (0344 to 0346); and a
  trial of battle effects as sprite sheets (0347). The last two move here from Later.
- **Battle effects, as built in M6** (the Owner's verdict on trial 0347, 2026-11-20): an effect is a `sprite` with parameters, not a
  `vfx` Kind (that stays in Later). M6 builds `sprite` effect parameters (an anchor, an exact cell, no figure rules, a blank last
  frame, per-clip ticks; 0362), an Op that dithers partial alpha with the `fit.alpha_partial` finding on the input (0363) and the
  export of an effect's blend, light mode and anchor (0364). Frames come from a Pixelbolt recipe imported as a sheet (the hit
  spark and the summon puff are accepted this way); the recipe is kept beside it in `src/`, with no Node in Kiripix. The buff glow,
  the sound-wave cone and the telegraph have no route yet. The rest (effect Ops, a Pixelbolt atlas import, the UI player) waits for
  the game to confirm the first effects.

**Generation and agents, deferred** (moved out of M6 by the Owner on 2026-11-18; moved from M4 on 2026-11-08 and from M5 on
2026-11-11). Not in a milestone yet. Each part, with the Owner's view:
- **The MCP adapter** (§10.6), with its tool selection tuned on the agent acceptance test and on M2's first-pass trial
  ([0062](../backlog/m2/0062-m2-claude-first-pass-trial.md)). Its value next to the CLI is unproven: agents already drive
  Kiripix through the CLI and `describe`.
- **PixelLab:** delayed, because its sprite generation has been unsatisfactory so far.
- **An image API Provider** (OpenAI's GPT Image, the Owner's choice of 2026-11-23, §16) with prompt templates, the style bible, the cost ledger and the
  budget: nice to have, not urgent. It brings `gen --look` ([0143](../backlog/m6/0143-m6-gen-a-look-edit.md)), `gen` for a
  portrait's emotions and a Prop's states, and `gen` driving `extend`. The Owner's aim for `extend` (2026-11-16, after
  [0134](../backlog/m4/0134-m4-trial-room-extended-both-ways.md)) is that Kiripix writes the prompt, generates the base image,
  writes a canvas per side, has the image API paint each, repeats, and joins, with the Owner approving intermediate results.
- **The image-to-3D trial** ([0144](../backlog/m6/0144-m6-image-to-3d-trial.md)), which compares local Runners with a
  Provider, so it goes with the Provider.
- **A trial of local generation** (inpainting and outpainting for rooms, portraits) as a Runner, to keep `gen` at $0. The
  Owner doubts it gives good results on this machine, and expects it to need at least 16 GB of VRAM (the machine has 8 GB).
  Worth a trial once higher priorities are done, not before.

**Later:** side view (side-view Masks: one-way, ladder; the parallax split with depth; platform reachability; the lowest
priority, moved here from M7 on 2026-11-11), maybe the tileset recipe (autotile rules; see below; not before the game's chapter 2), "promote to Prop" for a room's foreground Layer, renaming exported
IDs with aliases. (VFX sheets, normal maps for painted backgrounds and custom named Masks moved to M6 on 2026-11-19.) (Battle backgrounds were dropped on 2026-11-08: the game fights in the room, and its DEC-048 rejects
separate battle maps.)

**The tileset recipe, estimated on 2026-11-08, not planned.** The game compares painted rooms with a modular kit for its
dungeons in its M09 (its ISS-017), and grid battles cluster in dungeons. A minimal recipe is a Kind `tileset`: brief → source
→ fit → palette → tiles (slice to tiles, dedupe, an edge-match check) → terrain (peering bits per tile, a Decision) → export
(a `TileSet` `.tres` with a terrain set and a physics layer), with props on top from the prop recipe. That's about 8–10
tickets and 2–3.5M tokens, close to M2's props plus a heavy UI for tagging peering bits. The unknown is the art: whether the
free image model can paint a tile sheet that tiles and matches the painted districts.

**The trial's answer (0251, 2026-11-19): paint only for chapter 1; tiles are a "maybe" for later.** The model paints floors,
wall faces and whole rooms in the ch01 style. It won't lay out a kit: corners came back as whole little rooms, and each
image was a different dungeon. A corridor cut from one painted room matched in style, and the battle grid read better on it.
But 59 of its 88 joins showed a seam, from the room's baked light, and its walls repeated clipped doors and lights. Chapter 1
(to the game's milestone 20-30 or so) uses painted rooms. With a good tile sheet, tiles could make procedurally generated
dungeons in chapters 2-10, so the estimate stays here. A later try needs a sheet painted for tiling: even light, plain wall
strips with doors and lights as props, and every piece from one image.

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
4. Image-to-3D: which local Runner fits 8 GB well enough, a Provider, or none (with Providers; deferred from M3, then from M6).
5. ~~Which API provider comes first~~: decided 2026-11-23 by the Owner: OpenAI's GPT Image, through the OpenAI API, for
   the painted work (room Sources, `extend` pieces, Looks, Props and their states, portraits and their emotions), within
   `[providers] budget_usd_month` ($10 in the art Project). Its pieces re-render the kept strip, so `extend add` joins them
   under `--max-residual 1` ([0377](../backlog/m6/0377-m6-extend-joins-a-re-rendered-strip.md)). Sprites and their
   animations are still open ([0354](../backlog/m6/0354-m6-provider-research-actors.md)); the study is
   [0353](../backlog/m6/0353-m6-provider-research.md).
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

   **What trial 0134 found (2026-11-16),** on the tutorial battle's laneway, `room.ch01_002_laneway`: four pieces (NW, then
   east, south and the corner), a Source of 2407 x 1343 px and a room of 1120 x 624, about 3 screens.
   - **The corner works:** registered against two edges, the residual is 0.23 px (0.24 and 0.11 for the east and south
     pieces), and no seam shows after `fit` and `palette`, even next to a blurred piece. At first `extend add` refused it,
     because a rescaled piece ends a pixel inside the image, and `--keep` was one number for both axes; after
     [0230](../backlog/m4/0230-m4-extend-corner-off-by-one.md) and [0231](../backlog/m4/0231-m4-extend-keep-per-axis.md) the
     four pieces join through `extend` alone (corner residual 0.225 px), and `done` crops the 1-px margin a registration
     leaves.
   - **SAM 2 at 2.35x squeeze:** small objects segment as well as on a one-screen crop (IoU 0.85 to 0.98). Larger ones (a
     car, a van, a puddle) come back in part from a click, and whole from a `box` on the whole image, as on a crop. A crop
     isn't needed; use a box for anything bigger than about 40 target px.
   - **Collision is light:** 291 `solid` and 20 `pit` pieces, about 100 per screen, so the lighter collision export isn't
     needed. `reach` 1.4–1.7 s, the `export` Stage 0.3–0.5 s, `kiripix export` 3.7 s, a 53 KB scene.
   - **The palette** needed 12 colours for this room (and a few more for its warm light), so a new kind of room grows the
     palette; `palette-suggest --min-distance 0.025` reached the Owner's mapping error target of 0.015 with the fewest colours.
   - **The Owner's time:** about 25 minutes making the four pieces, most of it drawing canvases in Paint, which
     `extend canvas` already does; then 19 minutes in the UI after Claude's first pass through the CLI, which the Owner judged
     very good, including Mask fixes the walk test found.
   - **A closed gate** between a yard and the laneway is `solid`; opening it in the game is a Look taking collision away
     (open decision 8), left to the game's ticket for the scene.
8. **Room Looks beyond one picture and their own collision** (§6.1, M4). Settled: a Look can add collision and take it
   away. Its `solid` starts as the room's, an `erase` clears it, and the game swaps the room's `solid` for the Look's while
   it shows. Not settled: whether Looks stack or combine (an unbuilt station with the lamps off, Lost-and-Found's
   `relight`); whether a Look changes walkable, navigation and `reach` (rubble cleared; the laneway's back gate, whose yard
   `reach` reports as an island because it reads the room without its Looks); whether a Look has its own Markers, such as
   a light that goes off with an unlit Look; and whether a soft edge is allowed with binary alpha. The laneway and the
   game's R6 now need all but the soft edge: ADR 0013, accepted (tickets 0314 to 0317). (2026-11-08: a boss phase that moves a
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
     the body, the exploration clips or the outfits; one character holds them all, by clip name. The weapon is attached in the
     frames of the clips that hold it, at a socket bone `grip_r` (decided 2026-11-18 in
     [0238](../backlog/m5/0238-m5-held-things-trial.md), after [0170](../backlog/m4/0170-m4-weapon-in-a-battle-clip-trial.md)):
     not a layer, whose stack the trial found barely different but which loses the inner lines where the thing crosses the body and
     costs a render and an Asset per thing and body. A clip that outgrows the body's cell gets its own; a class weapon has a ramp
     row, so a skin or hair swap never reaches it.
   - **Four character Assets at the game's M03** (2 bodies x 2 outfits) each decide their clips. A character can be made
     from a base since 2026-11-14 (M4, [0165](../backlog/m4/0165-m4-characters-share-a-base.md), ADR 0012); before that, and
     still for characters that share clips but not a skeleton, `kiripix clips copy` copies clip Decisions between them
     ([0171](../backlog/m4/0171-m4-copy-clips-from-a-character.md); chosen 2026-11-12), and each body's second outfit is
     modelled on the first's rigged file, so it needs no Mixamo trip.
   - **Camera:** `top34_8` for every character; the game changed its own rule to match.
   - **Outfits are whole-body variants** until hair styles and outfits become **layers** (M5,
     [0152](../backlog/m5/0152-m5-character-layers.md)), rendered with the body as a holdout.
   Still open, for M5's trial: outfits that change the silhouette (a long coat), the outline and the normal map per layer or in
   the game, and how Kiripix holds a layer.

## Changes since v0.4

- M6 split into tickets, 2026-11-19: 0324 (spec, with questions for the Owner) to 0338 (gate). A review
  queue, hand-over notes, a `--match` scope and districts; a style trial before the style Check; NPCs from a base wait on
  the Owner's answers in 0336. Added the same day for the game's M06–M10: room Sources in bulk (0348 to 0351), room normal
  maps (0339 to 0343), named terrain Masks (0344 to 0346), and a battle-effects trial (0347).
- The tileset trial (0251), 2026-11-19, by the Owner: painted rooms for the game's chapter 1; the tileset recipe leaves M6
  and stays a "maybe" for later chapters (§14).
- M6 re-planned, 2026-11-18, by the Owner: rooms at chapter scale (a review queue, first passes without the Owner, the batch
  view), a style match Check across Kinds, NPC variants from a base, and maybe the tileset recipe. Generation and agents (MCP,
  PixelLab, an image API Provider, image-to-3D, a local generation trial) move out of M6 and wait without a milestone.
- M4, 2026-11-14: a character can be made from a base character (ADR 0012, 0165), and a Model can be built from a parameter
  file by a generator of the Project's own (0224); both in §6.3. `kiripix.toml` is at schema version 6
  (`[character.generators]`), `rig.json` at 2 (each bone's parent, and the rig's height).
- M4, 2026-11-12: rooms that move (0183), decided by the Owner. Loops are a `loops` Stage of their own, not animated Looks.
  A `pulse` may brighten a light source's own pixels, never the surfaces around it (the game's Option A). Particles draw opaque
  palette colours. Cycles are baked into frames. `loop.flash` is an error. When a Look over a Loop shows, the game hides the
  Loop by its ID. A Loop may name a light Marker to flicker in step. §6.1 and §9 have the details, and ADR 0011 records the Stage (0212).
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
