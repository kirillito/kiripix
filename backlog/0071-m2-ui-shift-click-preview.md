---
status: done
milestone: M2
agent: ui-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0070-m2-shift-click-subtracts-from-the-mask.md]
---

# M2: the UI previews what a shift-click takes away

Spec §11. After [0070](0070-m2-shift-click-subtracts-from-the-mask.md).

## What to build

- On the masks and layers screens, Shift-hover asks `segment-preview` for the click alone (`x,y`, positive), as 0070's
  negative click is segmented, and tints only the part of it that is in the current Mask or Layer, in `SUBTRACT_TINT`.
  `lastObject` in `maskScreen.tsx` and its copy in `layerScreen.tsx` go away.
- The hint says: "Click an object to add it; Shift-click an object to take it away."
- "Nothing to take away from: click an object on this Mask first" goes away; a Shift-hover over an empty part of the Mask
  shows no tint.

## Acceptance criteria

- [x] Playwright with the fake segmenter: Shift-hover over two overlapping objects tints their overlap; a Shift-click there
      records one negative `click`, and after `run` the overlap is gone from the canvas.
- [x] Shift-hover over a part of the Mask that a flood made tints it.

## Notes

- The layers screen refuses a Shift-click on a Layer that no positive click has lifted yet, as `layers` does (0070): "Nothing to take away from: click an object to lift it into <layer> first." Nothing is recorded. The masks screen has no such refusal, since a Mask can have floods and strokes (the Owner, 2026-11-05).
