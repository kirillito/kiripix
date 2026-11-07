---
status: done
milestone: M2
agent: imaging-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0050-m2-prop-stages-to-palette.md]
---

# M2: the prop's `finish` and `footprint`

Spec §6.2, §7 (cleanup). Stories 12 and 13 of [0037](0037-m2-layers-and-props.md). Follows D9 in [0037](0037-m2-layers-and-props.md).

## What to build

- An `add_outline` Op: transparent pixels 4-adjacent to opaque ones take one colour, clipped at the canvas. Golden-tested.
  M3 reuses it.
- `finish`: the outline when `outline` is on, in the palette colour at `outline_colour`; an index outside the palette is a
  `StageFailure` naming the palette's size.
- `footprint`: the existing Decision. `needs-input` with an `owner_action` until there is one. `prop.no_origin` is
  implemented. An origin outside the image, or a polygon of 1 or 2 points, is a finding. An empty polygon means no collision.
  Output: `footprint.json` and the sprite.
- No foreground split: D9 defers it.

## Acceptance criteria

- [x] Golden test for the outline, on an edge-touching shape.
- [x] With `outline` on, every pixel is still on the palette and alpha still binary.
- [x] No footprint: `next` names the Owner's action. After `decide`, `run` gives `done`, and moving the origin rebuilds only
      from `footprint` down.
- [x] A bad palette index fails with a message that gives the valid range.

## Notes (2026-11-04)

- `add_outline(rgba, colour)` is in `kiripix/ops/cleanup.py`; golden `add_outline.png` (in `tests/golden/test_chroma.py`).
- `finish` writes `finish.png` and runs the palette conformance Check on it. `footprint` takes the latest `footprint` Decision and writes
  `footprint.json` and `sprite.png`. Besides `prop.no_origin`, it has `prop.origin_outside` and `prop.footprint_too_small` (owner actions).
