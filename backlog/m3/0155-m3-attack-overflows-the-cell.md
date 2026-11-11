---
status: done
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
---

# M3: a pose that reaches past the cell is cut off

Spec §6.3 (render, sheet) and the gate's "every frame ... with binary alpha, and the outline is steady" ([0117](0117-m3-gate.md)).
Found while preparing the gate, 2026-11-11.

## The gap

`character.mc02`'s `attack` fails `check` with 14 `sheet.frame_overflow` errors: `s` frames 0 to 5 and 20 to 24, `se` frames 4
to 6. The lunge puts a foot further toward the camera, so on screen it lands below the cell, e.g. `s` frame 0 spans
(25, 29) to (49, 78) in the 78 x 78 cell.

`render` sizes one square cell for the character, `ceil(1.5 * height)` (`CELL_RATIO`), with the pivot `ceil(0.1 * height)`
px above its bottom (`BOTTOM_RATIO`). With height 52 that leaves 6 px below the feet, and neither number can be changed. The
render's own frame is the same size, so the pixels past it are never drawn: on `s` the foot fills the frame's last row
(6 px of it in frames 0, 3 and 22), so it is cut off there, and the outline has nowhere to go on that side
([0109](0109-m3-outline-op.md)). `sheet` then places each frame by its rounded pivot, which on `attack` ranges y 71.374 to
72.882, so a frame whose foot stops one row short of the edge (`se` frame 5 ends at row 76) is pushed past the cell anyway.
A fixed cell with no slack below the feet can't hold both.

## What to build

One of these; the Owner picks:

1. **A cell sized to the clips** (recommended): `render` measures every frame's projected bounds before rendering (a cheap
   pass with no shading) and makes the cell the smallest one that fits them all plus the outline's 1 px, so no pose is ever
   cut. The cell stays one size for the whole character.
2. **Params on `render`**: `cell` (the ratio, default 1.5) and `bottom` (default 0.1), shown by `describe`, so the Owner widens
   it when `sheet.frame_overflow` says so. The finding's fix names the param.

Either way `sheet.frame_overflow`'s fix names `render` and what to change.

The Owner chose option 1, a cell sized to the clips (2026-11-11).

## Acceptance criteria

- [x] CLI seam, on the fake: a clip that reaches below the default cell is rendered whole, and `sheet` passes
      `sheet.frame_overflow`.
- [x] mc02's `attack` re-run: no `sheet.frame_overflow`, the foot whole and outlined. Re-run in a scratch copy of the art
      Project, as for [0154](0154-m3-stationary-clip-pivot-follows-the-hips.md).

## How it was built

- **Measure, then render.** `render_frames.py` takes `"measure": true`: it opens and poses the rig as the render does, with
  the render's own camera, and returns per clip, direction and frame the mesh's extent in px from the point the camera orbits,
  plus the point under the root. It renders nothing. It counts only meshes that render: the glTF importer leaves a bone
  shape's `Icosphere` in an excluded collection, and the `rigged.glb` fixture's cell grew from 40 to 50 px until the measure
  skipped it.
- **The cell** (`fit_cell` in `render.py`) is the default one (1.5 x height, pivot 0.1 x height above the bottom), **grown,
  never shrunk**, until every clip fits with 1 px to spare on every side for the outline. A clip whose pivot follows the root
  (neither stationary nor root motion) must also fit where `sheet` moves each frame by its rounded pivot. Growing only, not the
  smallest cell the ticket said, keeps characters of one height on one cell size, and leaves a character whose poses already
  fit as it was.
- **Reuse:** each clip in `render.json` keeps its `bounds` and a `measure_key` (what poses it: the clip, rig, Model, camera
  angle, scale, Blender, script, format). A rebuild measures only clips whose key changed, so adding a clip costs one short
  Blender run for that clip. The cell and pivot are in every clip's render key, so a cell that grows renders every clip again.
- **mc02:** the cell stays 78 x 78, but the pivot moves from y 72 to 68. The attack's foot reaches 8.6 px below the feet,
  so it needs 10 px below the pivot. Facing `s`, frame 0's foot now ends at row 75 and its outline at row 76, with row 77
  empty. Bounds per clip (left, top, right, bottom): attack (-32.2, -53.6, 32.2, 8.6), idle (-12.3, -54.1, 12.3, 5.5),
  walk (-18.8, -53.8, 18.8, 7.0). `render` took 90 s with the measure pass (76 s before, on another run).
- `sheet.frame_overflow`'s fix names `kiripix run <asset> render --force`. The fake Blender reports a figure `height` px
  tall, or what a `blender-reach` file says per clip.
- Spec §6.3's `render` row says how the cell is sized and where a stationary clip's pivot is.
