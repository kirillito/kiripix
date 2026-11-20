---
status: todo
milestone: M6
agent: imaging-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0339-m6-adr-room-normals-stage.md, 0340-m6-depth-runner.md]
---

# M6: the room's `normals` Stage

Spec §6.1 and §14 (M6), placed and shaped by [the ADR 0339](0339-m6-adr-room-normals-stage.md). Part of
[0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Ticket 2 of 0252's outline; the trial's prototype
(`backlog/m5/0252-trial/`) is the reference.

## What to build

- **The Stage**, at the place the ADR fixes, with `mode` `off` (default: `done`, no output, no Runner call) or `depth`.
- **With `depth`:** the [depth Runner](0340-m6-depth-runner.md) on the Source, the depth mapped through the Grid to target
  pixels, filled per Layer under its alpha (as the trial's masked fill), then Sobel, `strength`, `deadzone` and quantised to
  `levels`. The trial's values are the defaults. Output: `plate.normal.png` and `<layer>.normal.png` for each foreground
  Layer, RGB normals in Godot's convention (the trial's), the room's size, and never palette-mapped.
- **Ops** for the pure parts (the masked fill, Sobel to normals, quantise) in `kiripix/ops/`, with no I/O. Reuse the
  character `finish` Stage's normal quantise if it fits.
- **Decisions:** `flatten` (a brush or polygon in target pixels: the normal faces the camera inside it) and an Override to
  paint normals by hand, both on the target grid.
- **Checks:** `normals.not_flat_walkable` (warning: a walkable pixel whose normal tilts more than a threshold, which the
  trial sets; its fix is a `flatten` Decision over the area), `normals.size` (error).
- A change to the Layers or the Grid makes the Stage stale through its input hash. A palette change doesn't.
- `describe room` lists the Stage; `preview --stage normals` shows the normal image, and `--overlay lit` shows the Plate lit
  from a fixed corner, so a session judges the Stage without Godot.

## Acceptance criteria

- [ ] Golden seam: the Ops on a small fixture (a box on a floor), pixel-exact.
- [ ] CLI seam: a test room with `mode=off` is `done` with no output, and nothing else on the room rebuilds when the Stage
      is added (input hashes unchanged).
- [ ] CLI seam: with `mode=depth` and the stub Runner, a normal image per Layer; a `flatten` takes a tilted walkable area
      out of `normals.not_flat_walkable`; a palette change leaves the Stage `done`.
- [ ] Run on `ch01_dungeon_r01` in the art Project: the Owner's eye on `preview --overlay lit` against the trial's capture.
