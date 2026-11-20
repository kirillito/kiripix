---
status: done
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

- [x] CLI seam: the exported `.tres` of a fixture has each frame's region at its packed rect and its margin restoring the cell.
- [x] Real-Godot test (skipped without Godot): every frame drawn from the trimmed export matches the untrimmed one, and the
      feet stay on one pixel.

## Result

**Built.** `character_frames` (`kiripix/export/godot.py`, which the Wearable export also uses) writes each frame's `region` as its packed `rect`
and one `margin = Rect2(offset.x + left - pivot.x, offset.y + top - pivot.y, width - rect.width, height - rect.height)`, with `left`, `top`,
`width`, `height` from `logical_cell` and `pivot` the clip's. It is left out only when all four are 0 (a box that is its whole logical cell). A
frame with no `offset` (a record that predates 0308) reads as 0, 0. The normal map is the same `AtlasTexture`'s, so it takes the same region and
margin; nothing else changed in the scene. Spec section 9's Character row updated (trimmed cells; `offset` in the frames).

**Version.** No new bump: `export` is already 2 -> 3 (character) and 3 -> 4 (Wearable) in this uncommitted batch (0308), and this change lands in
the same batch.

**Tests.** CLI seam (`tests/cli/test_export_cell_per_clip.py`): a fixture whose finished frames have a different cleared border each, so
every frame has its own rect and offset: its `.tres` regions are the packed rects and every margin restores the logical cell. Real Godot 4.7.2
(marked, OpenGL window): every frame of every `_s` animation drawn from the trimmed export equals the finished untrimmed cell placed with the
pivot at the root (alpha and colour), so the feet stay on one pixel. `test_export_character.py`'s Godot probe now asserts the padded frame size
(78 x 78, `get_size()`), no longer the trimmed region. Goldens: the writer fixture `wide()` gave its `attack` frames 16 x 16 rects in a 24 x 20 cell
(a rect that didn't fill the cell, which now means a trim), so it now has 24 x 20 rects (its goldens `frames_wide.tres` and `hero_wide.tscn` are
byte-unchanged); new `frames_trimmed.tres` (golden, to review) from a trimmed fixture.

### Review follow-up (2026-11-18)

- A frame's `offset` is read as required (`frame["offset"]`): every record that reaches the writer is version 7 (`character.json`
  migrates, an old `wearable.json` is refused). The writer goldens' frames now carry `offset` 0, 0, as a version 7 record does.
- Spec §9 now says that `flip_h` mirrors the whole logical cell, so a game that corrects the feet itself reads the cell from the
  frame texture's size, not from `character.json`'s top-level `cell`.
