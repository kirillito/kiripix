---
status: todo
milestone: M6
agent: ui-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0344-m6-mask-add.md]
---

# M6: UI: paint any of the Project's Masks

Spec §11 (masks screen: "letters switch tools and Masks") and §14 (M6). Part of
[0324](0324-m6-rooms-at-chapter-scale-style-npcs.md).

## The gap

The masks screen starts on `solid` (`web/src/maskScreen.tsx`) and offers the Masks it knows. A named Mask
([0344](0344-m6-mask-add.md)) needs to be pickable, tinted and toggled like the others.

## What to build

- The Mask picker lists every painted Mask of the room's view from `describe` (not a list in the UI), each tinted in its
  `colour` from `kiripix.toml`, with its `meaning` as the tooltip. Number keys or letters pick them, in the order the
  Project lists them.
- Each Mask's overlay can be toggled, so `cover` is painted with `solid` showing underneath.
- The cell grid overlay, when the room has a battle area, shows which 32 px cells a named Mask half-covers, as it does for
  `solid` (M4's area screen), so the Owner paints whole cells.

## Acceptance criteria

- [ ] Playwright against a real `kiripix serve`: a Project with `cover` added shows it in the picker; a brush stroke on it
      records one Decision on `cover`, and `solid` is untouched.
- [ ] `npm run build` passes.
