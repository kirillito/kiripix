---
status: todo
milestone: M6
agent: ui-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0334-m6-style-references-and-wiring.md]
---

# M6: UI: an Asset's style beside its references

Spec §11 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Reads
[0334](0334-m6-style-references-and-wiring.md)'s `probe style`; no logic in the UI.

## What to build

- **A style panel** on the screen of the Stage that the style Checks measure: each measure as a small bar showing the
  references' range and the Asset's mark in it, out-of-range ones marked. Clicking a `style.*` finding opens it.
- **The references side by side:** the Asset's image beside the closest and furthest reference's, at the same whole-number
  zoom, so the Owner judges by eye what the numbers say.
- **Picking references** (Owner only): "Make this a style reference" and "Remove reference" on any supported Asset, calling
  `style-add` and `style-remove` with the session token. The status board marks reference Assets.

## Acceptance criteria

- [ ] Playwright against a real `kiripix serve`: making two test Assets references shows a third's bars, with an
      out-of-range measure marked and its finding shown.
- [ ] `npm run build` passes.
- [ ] An eye check by the Owner on one character, one sprite and one room, noted here.
