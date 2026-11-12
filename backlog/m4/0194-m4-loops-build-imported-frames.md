---
status: todo
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0193-m4-loop-kit-and-import.md, 0192-m4-frame-ops.md]
---

# M4: the `loops` Stage builds kit frames and edit frames

Part of [0183](0183-m4-ambient-animation.md), route (c). Spec §6.1 (Looks: the edit pipeline). Part B follows 0193's Part B and
is cut with it.

## Part A: kit frames

- A `frames` Loop with `source = "kit"` takes the imported frames as they are (they are on the target grid already). Any pixel
  off the palette maps to the nearest palette colour and raises `loop.off_palette` with the count, as a warning here: the
  Owner's editor may have added a near-miss. It stays an error if more than 1 % of the frame's pixels are off (set by 0184).
- Pixels changed outside the region are cut away and reported by `loop.outside_region` (warning), with the box of each patch.
- On a Loop with `layer = <id>`, a kit frame's alpha is the Layer's alpha for that frame, so motion past the Layer's
  silhouette works: where the frame's alpha is 0 and the Layer's still alpha was 1, the Plate's fill shows.
- A palette change remaps kit frames with the `palette` Stage's mapping and puts them in `needs-review`.

## Part B: edit frames

- Each picked edit frame goes through the shared edit pipeline from 0189 (resize, register, fit, optional regrade, map the
  whole edit, cut to the region), as a Look does.
- Per frame: `loop.misaligned` (error) and `loop.drift` (warning), with `look.misaligned`'s and `look.drift`'s limits.
- On a Loop with `layer = <id>`, an edit frame has no alpha of its own, so it is cut by the Layer's still alpha.
  `loop.past_layer` (warning) counts the pixels of change that fall outside it.
- `loop.flicker` (warning, new): pixels that change between consecutive edit frames outside the part the Owner meant to move
  (outside the union of the frames' `difference` against frame 0, grown by 1 px). Above a share of the region (set by 0184),
  the edits disagree, and its `owner_action` suggests a kit instead.

## Acceptance criteria

- [ ] CLI seam: kit frames with one off-palette pixel and a stray stroke outside the region raise the two findings and build;
      on a Layer Loop, a frame that moves past the silhouette shows the Plate's fill.
- [ ] CLI seam: a palette change remaps kit frames into `needs-review`.
- [ ] CLI seam (Part B): two edit frames, one shifted by 2 target px, raise `loop.misaligned` on that frame only; an edit
      that redraws the whole region raises `loop.flicker`.
- [ ] `loop.seam`, `loop.still` and `loop.flash` from 0189 apply to imported frames unchanged.

Budget: 150–250k tokens (Part A alone: 80–140k).
