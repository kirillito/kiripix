---
status: todo
milestone: M1
agent: imaging-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0013-m1-room-brief-import-pick.md]
---

# M1: fit, and the layers pass-through

Spec §6.1 (fit), §7 (resample) and ADR 0004. User story 11 of [0010](0010-m1-room-end-to-end.md).

## What to build

- Ops (`resample`): pixel-grid detection returning a Grid transform (scale and offset); mapping points, images and
  Masks through a Grid transform (a click maps to the centre of its target pixel); nearest and mode-filter
  downscale; integer upscale. Pure, golden-tested.
- The room's `fit` Stage: `mode = grid` detects the grid (or uses `scale` and the offsets when set) and samples one
  pixel per cell; `mode = downscale` uses the mode filter. Output: the fit image at the brief's exact size, and the
  Grid transform as JSON. `fit.size_mismatch` when the result isn't the brief's size, with a `fix` naming the
  parameter to change.
- The `layers` pass-through: outputs the fit image as the Plate with no foreground Layers, and needs no owner input.
  Its `available_from` moves to M1.
- `palette` declares `upstream = ["layers"]` (see [0010](0010-m1-room-end-to-end.md)).
- `next` gives `kiripix set <id> fit …` for a size mismatch.

## Acceptance criteria

- [ ] Golden tests: grid detection on 2×, 3× and 4× upscaled pixel art with offsets; mode-filter downscale; point
      mapping through a Grid transform.
- [ ] A room imported from a 4× upscaled 480×272 image fits exactly, and `layers` is `done` with the same image.
- [ ] Changing `fit.mode` makes `fit` and everything below it `stale`.
