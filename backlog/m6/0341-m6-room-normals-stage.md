---
status: done
milestone: M6
agent: imaging-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0339-m6-adr-room-normals-stage.md, 0340-m6-depth-runner.md]
---

# M6: the room's `normals` Stage

Spec §6.1 and §14 (M6), placed and shaped by
[ADR 0014](../../docs/adr/0014-a-rooms-normal-maps-are-a-stage-before-palette.md) (from ticket
[0339](0339-m6-adr-room-normals-stage.md)). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Ticket 2 of
0252's outline; the trial's prototype (`backlog/m5/0252-trial/`) is the reference.

## What to build

- **The Stage** between `masks` and `palette` (ADR 0014), with `mode` `off` (default: `done`, no output, no Runner call) or
  `depth`. It reads `layers`, `source`, `fit`, `masks` and the `[body]` setting; only `export` reads it.
- **With `depth`:** the [depth Runner](0340-m6-depth-runner.md) on the Source, at the Stage's `size` parameter (1036 by
  default, or 518; part of the call's key, never lowered from free VRAM). The Runner refuses a size the GPU has no room
  for with a `RunnerError` naming the parameter; the Stage turns it into a finding whose `fix` sets `size` to 518 (or
  `--cpu`). The depth is mapped through the Grid to target pixels, refilled per foreground Layer outside its alpha from
  inside it (as the trial's masked fill), then Sobel, `strength`, `deadzone` and quantised to `levels`. The trial's values
  are the defaults. Output: **one `normal.png`**, the room's size, each pixel the normal of its front-most Layer by the
  Layers' alpha (ADR 0014 decision 4), RGB normals in Godot's convention (the trial's), never palette-mapped. The Plate's and
  each Layer's maps are cut from it at `export` (0342), not here.
- **Reading the pin:** it's a 16-bit greyscale PNG; read it with PIL (mode `I;16`) and `runners.depth.decode`. A thumbnail
  through `load_rgba` shows it white, so the review image is the Stage's own 8-bit picture of the depth.
- **Ops** for the pure parts (the masked fill, Sobel to normals, quantise) in `kiripix/ops/`, with no I/O. Reuse the
  character `finish` Stage's normal quantise if it fits.
- **Decisions:** `flatten` (a brush or polygon in target pixels: the normal faces the camera inside it) and an Override to
  paint normals by hand, both on the target grid.
- **Checks:** `normals.not_flat_walkable` (warning: a walkable pixel whose normal tilts more than a threshold, which the
  trial sets; its fix is a `flatten` Decision over the area), `normals.size` (error). Walkable is derived here with the pure
  Op `place` uses (from `solid`, `pit` and the Body), since `place`'s `walkable.png` comes later. Top view only.
- A change to the Layers or the Grid makes the Stage stale through its input hash. A palette change doesn't.
- `describe room` lists the Stage; `preview --stage normals` shows the normal image, and `--overlay lit` shows the Plate lit
  from a fixed corner, so a session judges the Stage without Godot.

## Acceptance criteria

- [x] Golden seam: the Ops on a small fixture (a box on a floor), pixel-exact.
- [x] CLI seam: a test room with `mode=off` is `done` with no output, and nothing else on the room rebuilds when the Stage
      is added (input hashes unchanged).
- [x] CLI seam: with `mode=depth` and the stub Runner, a normal image per Layer; a `flatten` takes a tilted walkable area
      out of `normals.not_flat_walkable`; a palette change leaves the Stage `done`.
- [x] Run on `ch01_dungeon_r01` in the art Project: the Owner's eye on `preview --overlay lit` against the trial's capture.

## Result

Built by the imaging engineer; the last box (the Owner's eye on `preview --overlay lit`) is open, so the ticket stays `todo`.

**Files.** `kiripix/ops/normals.py` (the Ops), `kiripix/recipes/room_normals.py` (the Stage), the Stage registered in
`kiripix/recipes/room.py`; `kiripix/core/previews.py` and `kiripix/commands/checks.py` (`--overlay lit`); `kiripix/core/graph.py`
and `kiripix/runners/{base,depth}.py` (two small core touches, below).

**Version bumps.** None: the Stage is new (`normals`, version 1) and changes no other Stage's input hash
(`tests/cli/test_room_hashes.py` still passes unchanged; `palette` keeps `upstream=["layers"]`). No `schema_version` change:
`normal.png` and `depth.png` are images, and there is no new data file. `export` is untouched (0342 bumps it).

**What the Stage is.** Between `masks` and `palette`; inputs `layers`, `source`, `fit`, `masks` and the `[body]` setting.
Parameters (each at its default is out of the hash): `mode` (`off` or `depth`, default `off`), `size` (int, 1036 or 518; part of
the call's key), `strength` (60.0 px of height), `deadzone` (0.10), `levels` (3). Decision `flatten`: `{shape: "brush" or
"polygon", points, radius (brush only), erase?, walkable?}`. `walkable` flattens only the walkable pixels in the shape; `erase`
gives the Stage's own normals back; it replays in order. An Override over `normal.png` paints by hand. The Stage's `image` is
`normal.png`.

**Finding codes.** `normals.not_flat_walkable` (warning; one per 4-connected area of walkable pixels whose tilt, the length of
the normal's x and y, is above `TILT_LIMIT = 0.4`; the 8 largest; `position` is the area's box; `fix` is a `flatten` polygon
over the box with `walkable: true`, so a wall in the box is untouched; top view with a `solid` Mask only). `normals.size`
(error, `fix` `run --force`). `preview.no_normals` and `preview.no_image` (a Stage that is off wrote no image). The depth
Runner's out-of-memory failure is `stage.failed` whose `fix` is `kiripix set <asset> normals size=518` (from 1036; at 518 the
message says `--cpu`).

**What 0342 (export) can rely on.**
- `mode = off`: `work/normals/` holds nothing but `.stage.json`. No `normal.png` means `normals: null`.
- `mode = depth`: `work/normals/normal.png`, RGBA, the room's size (`layers`' `plate.png`), alpha 255 everywhere, Godot's
  encoding (R is x, G is y up in the image, B is z toward the viewer, each `(v + 1) / 2 * 255`; flat is 128, 128, 255), never
  palette-mapped, after `flatten` and Overrides. Each pixel is the normal of its front-most Layer (later in `layers.json` is in
  front), the Plate's elsewhere. Cut the Plate's and each Layer's map from it by the alpha of `layers`' `plate.png` and
  `layer.<id>.png` (or the mapped ones in `palette`: the alpha is the same). Under a Layer the Plate's map is the Layer's
  normals, as ADR 0014 decision 4 says.
- `work/normals/depth.png` is a review picture only; export must not read it.
- Padded fit cells (`fit.padded`) get flat normals (the cell mean repeats the last real cell).
- A new depth result is `needs-review`, as any pinned Runner call; `run` stops there, so `export` never sees it half-accepted.

**What 0343 (UI) can rely on.** `kiripix describe room` lists the Stage with the parameters above, the `flatten` Decision (its
entry schema, plus a `problem` for a brush with no `radius` or a polygon with under 3 points) and both checks.
`preview <asset> --stage normals` is the normal map; `preview <asset> --stage palette --overlay lit` (any Stage image) is that
image lit from the upper left (fixed light, ambient 0.35; a flat pixel keeps its colour). `--overlay lit` needs a built
`normal.png` (`preview.no_normals` otherwise, fix `set ... mode=depth`) and warns `preview.overlay_out_of_date` when the Stage
isn't done. A `flatten` finding's `fix` is runnable as printed, and its `position` is the box to draw.

**Core touches (small, outside the imaging area; please look at them).**
- `RunnerError` has an optional `set_param=(name, value)`; `run`'s `stage.failed` finding uses it as the `fix` (`kiripix set
  <asset> <stage> name=value`). Only the depth Runner sets it.
- `_paint_overrides` returns None when the Stage wrote no image (a Stage that is off), instead of failing on the missing file;
  `preview` with no `--stage` skips Stages without an image file.
- The fake depth Runner (`tests/fixtures/kiripix_test_recipes.py`) fails on a `size` above 518 while `runner-out-of-memory` exists.

**Tests.** `tests/golden/test_normals_ops.py` (3 PNGs in `tests/golden/expected/`: `normals_box.png`, `normals_box_layer.png`,
`normals_box_lit.png`; tiny and pixel-exact, and the assertions in the test say what each shows), `tests/cli/test_room_normals.py`
(7 tests), `tests/cli/test_project.py` (the room's Stage list). With `test_room_hashes`, `test_depth`, `test_contract`,
`test_room`, `test_preview_views` and `test_graph`: 266 passed, 2 skipped (no weights). `lint-imports` and `mypy` are clean.

**Run on `ch01_dungeon_r01` (not the acceptance box).** I didn't change the art Project: I ran a copy in the scratchpad. `layers`
there says "Runner input changed" (the pinned Segmenter and Inpainter results against today's Runners; not this ticket) and needs
an accept only the Owner can give, so the Stage couldn't run through the CLI. Instead the same Ops ran on the pinned Layers'
alphas (`out/export/layer.*.png`) with the real depth Runner (on the CPU: no GPU is visible here; 3.6 s; the weights are pulled in
the scratch copy only) and the room's Source and Grid: a 400 x 560 normal map, 44 % of it exactly flat. The lit room, 3x, for
the Owner's eye: `C:\Users\KIRILL~1.BRE\AppData\Local\Temp\claude\2a77692328d6afa9\bb612024-94a6-4b8d-88cc-cf11c46d97a1\scratchpad\lit\lit.x3.png`
(`plate.x3.png` and `normal.x3.png` are beside it).

### Changed after the code review (main session, 2026-11-20)

- `_Runner.failed_param` is cleared at the start of each Stage's Runner calls, so a later `stage.failed` in the same `run`
  never takes an earlier failure's `kiripix set … size=518` fix.
- Open, not changed: at `size=518` the depth Runner's out-of-memory error carries no `set_param`, so its finding's fix is
  `run --rerun` while the message names `--cpu` (a flag, which `set_param` can't express).
- Tests that build a room Stage by Stage now run `normals` too (`test_loops`, `test_loop_kit`), and `test_masks` expects
  `next` to name `normals` after a Mask change: `normals` reads `masks` and comes before `looks`.

**The Owner's eye check, 2026-11-20:** looks fine; the difference is hard to tell exactly.
