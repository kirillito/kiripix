---
status: todo
milestone: M2
agent: imaging-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: fill a polygon on a Mask in one Decision

Spec §6.1 (masks). Found by [0062](0062-m2-claude-first-pass-trial.md). Claude's first pass filled every wall, pit and object
with `brush` zigzags: 89 strokes across three rooms, 23 of them on r01 only to close the dotted seams a radius-1 stroke leaves.
The trial's only correction was a box over a bench that isn't rectangular, which a polygon would have fitted. The `masks`
description already names "polygon", and spec §6.1 says that it isn't built yet.

## What to build

- An Op in `kiripix/ops/masks.py` that fills a polygon on a Mask, or clears it with `erase`. It's pure and exact: the filled
  pixels are fixed for given points, the edge pixels are included, and a self-crossing polygon follows the even-odd rule. Points
  outside the Mask are clipped.
- A `polygon` Decision on `masks`: `{mask, erase, points}`, with at least three points in target pixels. It closes itself. It
  isn't `on_image`, like `brush` and `border`, so a changed Plate doesn't send it to `needs-review`.
- It replays in journal order with the other Decisions.
- `describe` then tells the truth, and spec §6.1 loses "A polygon tool isn't built yet". This ticket adds no UI;
  [0080](0080-m3-ui-polygon-tool.md) does that.

## Acceptance criteria

- [ ] A rectangle by `polygon` is pixel-identical to the same box filled by hand, with no seam: golden test at the Op seam.
- [ ] A concave polygon (an L, like r03's ticket booth) fills correctly, and `erase` clears it, at the Op seam.
- [ ] CLI seam: `decide`, then `run`, gives the Mask. `undo` removes it. A changed Plate leaves a `polygon`-only `masks` `done`.
- [ ] Fewer than three points is refused with a finding.
- [ ] `room.harbor_front`'s and the three dungeon rooms' journals still replay unchanged: no existing Decision changes meaning.
