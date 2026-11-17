---
status: todo
milestone: M5
agent: ui-engineer
type: ticket
parent: 0240-m5-portrait-kind.md
depends_on: [0243-m5-portrait-recipe.md]
---

# M5: UI: the portrait's screens

Spec §11. Part of [0240](0240-m5-portrait-kind.md). Built on the Commands of [0242](0242-m5-portrait-asset-and-emotions.md) and
[0243](0243-m5-portrait-recipe.md), with no logic of the UI's own.

## What to build

- **An emotion strip:** every emotion of the set as a thumbnail, with its pick, its status and its findings. Import and pick
  an emotion's Variant from it, as the Looks screen does.
- **Flip in place:** the selected emotion over the neutral at the canvas's size, toggled by a key, so the Owner sees anything
  that moves. `portrait.shimmer`'s boxes are drawn on it.
- **The `face` region:** drawn with the Looks' polygon and brush tools.
- `fit`, `palette` and `finish` reuse the Prop's screens where they can.

## Acceptance criteria

- [ ] Playwright: on a built fixture portrait, the strip shows each emotion, a key flips it over the neutral, and a drawn
      `face` region is recorded as a Decision.
- [ ] `npm run build` passes.
