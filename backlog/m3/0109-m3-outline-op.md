---
status: done
milestone: M3
agent: imaging-engineer
type: ticket
parent: 0097-m3-characters.md
depends_on: [0104-m3-render-stage.md]
---

# M3: the outline Op for characters

Spec §6.3 (finish: "outline consistency across frames"), §7 (cleanup: outline add or strip) and ADR 0004. Story 11 of
[0097](0097-m3-characters.md). Builds the Owner's choice (Q2 of 0097): a 1 px silhouette from the render's object mask.

`add_outline` in `kiripix/ops/cleanup.py` draws a Prop's 1 px outline around its alpha. A character's may need more.

This ticket builds the silhouette alone and is tested on the fixture. The trial [0106](0106-m3-outline-method-trial.md)
confirms it on a real character afterwards; if it wants inner lines (jumps in depth), it adds a follow-up ticket for them.

## What to build

- `outline_mask(mask)`: the line Mask, 1 px and binary, from the render's object mask.
- `paint_outline(rgba, line, colour)`: the line Mask painted in one palette colour. Whether the line sits outside the
  silhouette or on its edge pixels is an argument; [0111](0111-m3-finish-stage.md) picks the default. Reuse or extend
  `add_outline` rather than duplicating it.

## Acceptance criteria

- [x] Golden tests: a square, a shape touching the frame's edge, and a two-frame case showing a still part's outline unchanged.
- [x] A Prop's outline is unchanged (its golden tests still pass).
- [x] `uv run lint-imports` passes.
