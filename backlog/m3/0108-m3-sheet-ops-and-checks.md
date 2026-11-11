---
status: done
milestone: M3
agent: imaging-engineer
type: ticket
parent: 0097-m3-characters.md
---

# M3: Ops and Checks for the sheet

Spec §6.3 (sheet, Checks) and §7 (compose: atlas packing). Story 13 of [0097](0097-m3-characters.md). Q10 (what "the feet"
are) and Q12 (the atlas's layout) of 0097: ask the Owner first. Ops in `kiripix/ops`, Checks in `kiripix/checks`, pure and
golden-tested.

## What to build

- `pack_atlas(frames, cell)`: frames into a grid of equal cells, in the order given, each frame placed so its pivot lands at
  the same point in its cell. Returns the atlas and each frame's rectangle.
- `feet_point(alpha)`: the pivot measure the Owner chose in Q10, for a pixel-based measure; if the Owner chose Blender's
  ground point, this Op isn't needed and the Check reads the pivots it is given.
- Checks, returning findings with positions:
  - `sheet.pivot_drift`: in a stationary clip, the feet move by more than a tolerance (default 0 px) between frames; the
    finding names the clip, direction and frame.
  - `sheet.frame_overflow`: a frame's opaque pixels don't fit its cell around the pivot.
  - `sheet.frame_count`: a clip and direction has a different number of frames than its clip says.
  - `sheet.empty_frame`: a frame with no opaque pixel.
  - `normal.size_mismatch`: a normal map whose size isn't its colour frame's.

## Acceptance criteria

- [x] Golden tests for `pack_atlas` (pivot alignment, an odd frame count). `feet_point` is not built: Q10 made it unnecessary (the feet are the ground point Blender reports per frame; `sheet.pivot_drift` reads the pivots it is given).
- [x] Each Check has a passing and a failing case, with the finding's code and position.
- [x] `uv run lint-imports` passes: `checks` imports only `ops`.
