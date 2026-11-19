---
status: todo
milestone: M5
agent: godot-export
type: ticket
parent: 0307-m5-sprite-atlas-size-trial.md
depends_on: [0308-m5-trimmed-cells-in-the-sheet.md, 0304-m5-export-cell-per-clip.md]
---

# M5: export trimmed cells: `AtlasTexture.margin` restores each frame's cell

From the trial [0307](0307-m5-sprite-atlas-size-trial.md) (the Owner, 2026-11-18: build lever B). The trial checked it in
Godot 4.7.2 on `mc03_male`: all 928 frames drawn as `AtlasTexture` with `region` + `margin` from a trimmed atlas are
pixel-identical to the untrimmed cell, plain and with `flip_h`, and lit through a `CanvasTexture` (colour + normal). Its
Godot project is `backlog/m5/0307-trial/godot_check/`.

## What to build

- `frames.tres`: each frame's `AtlasTexture` takes its packed `rect` as `region` and pads it back to its clip's cell with
  `margin` (from 0308's `offset`). The normal map's `AtlasTexture` uses the same region and margin.
- If 0304 chose the `margin` route for a clip's own cell, this is the same mechanism: one `margin` per frame does both.
- Spec §9's Character row updated.

## Acceptance criteria

- [ ] CLI seam: the exported `.tres` of a fixture has each frame's region at its packed rect and its margin restoring the cell.
- [ ] Real-Godot test (skipped without Godot): every frame drawn from the trimmed export matches the untrimmed one, and the
      feet stay on one pixel.
