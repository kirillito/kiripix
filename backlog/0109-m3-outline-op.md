---
status: todo
milestone: M3
agent: imaging-engineer
type: ticket
parent: 0097-m3-characters.md
depends_on: [0106-m3-outline-method-trial.md]
---

# M3: the outline Op for characters

Spec §6.3 (finish: "outline consistency across frames"), §7 (cleanup: outline add or strip) and ADR 0004. Story 11 of
[0097](0097-m3-characters.md). Builds what the Owner chose in [0106](0106-m3-outline-method-trial.md).

`add_outline` in `kiripix/ops/cleanup.py` draws a Prop's 1 px outline around its alpha. A character's may need more.

## What to build

- If 0106 chose the post-process edge: `outline_mask(alpha, depth, normal, ...)`, the line Mask from the silhouette and the
  depth and normal jumps the trial settled, with its thresholds as arguments.
- If it chose an in-render method: an Op that cleans the rendered line pass to 1 px and binary, so `finish` only paints it.
- Either way, `paint_outline(rgba, line, colour)`: the line Mask painted in one palette colour, outside or over the
  silhouette as the trial decided. Reuse or extend `add_outline` rather than duplicating it.

## Acceptance criteria

- [ ] Golden tests: a square, a shape touching the frame's edge, and a two-frame case showing a still part's outline unchanged.
- [ ] A Prop's outline is unchanged (its golden tests still pass).
- [ ] `uv run lint-imports` passes.
