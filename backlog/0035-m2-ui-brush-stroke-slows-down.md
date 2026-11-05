---
status: done
milestone: M2
agent: ui-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: a brush stroke slows down the longer it gets

Found by the Owner at the M1 gate ([0029](0029-m1-gate.md)): holding the brush for a long stroke gets slower as the line
grows, so they drew in short segments. Their strokes ran up to 362 points.

## The bug

`MaskTool.draw` ([maskTool.ts:222-225](../web/src/maskTool.ts#L222-L225)) redraws the whole stroke on every frame: each
pixel along the path, then a `fillRect` for each pixel of its disc. A frame's cost grows with the stroke's length and the
radius squared, so a long stroke with a wide brush gets slower and slower. The browser isn't the limit.

## What to do

Stamp only the new part of the stroke onto an offscreen canvas at target resolution, and draw that canvas in one
`drawImage` each frame, as the Mask overlays already do.

## Acceptance criteria

- [x] A frame's cost during a stroke doesn't grow with the stroke's length.
- [x] A stroke still records one brush Decision on release, with the same points as before.
- [x] The Playwright mask tests still pass.
