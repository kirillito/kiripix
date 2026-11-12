---
status: todo
milestone: M4
agent: ui-engineer
type: ticket
parent: 0174-m4-sprite-kind.md
depends_on: [0179-m4-sprite-recipe.md]
---

# M4: the UI for a sprite: import, the frame strip, the pivot

Spec §11. Part of [0174](0174-m4-sprite-kind.md). **No new screen:** everything here extends one that exists. Every action is
one Command.

## What to build

- **`frames`:** the import drop with `ImportRole` `sheet` (PNG or ZIP); the imported sheets listed with their names; for a PNG
  with no `sheet` Decision, a small form (clip, rows or columns, the directions in order, the frame count) that is one `decide`.
  The `clip` Decision's form (fps, loop, stationary) is the character's clips screen form where it fits; otherwise a form from
  `describe`. `frames.direction_missing` shows as a finding a person can read (ticket 0093's style).
- **`fit`, `palette`, `finish`, `sheet`:** the frame strip, onion skin, direction picker and clip player of `frameScreen.tsx`
  ([0115](../m3/0115-m3-ui-frame-strip-and-player.md)), for a sprite's Stage names. The direction picker greys out the
  directions a 4- or 1-direction sprite doesn't have.
- **The pivot:** on `fit`, the pivot drawn as a cross on the frame; a click sets it (one `pivot` `decide`, for the chosen
  direction, or all with a modifier key); `Ctrl+Z` undoes it. A `sheet.pivot_drift` finding jumps to its frame, as it does for a
  character.

## Acceptance criteria

- [ ] Playwright, on the synthetic fixtures: drop a ZIP and see its frames on `fit`; drop a PNG sheet, fill the form, see the
      frames; click a pivot and see it move; step a clip and switch directions by key.
- [ ] No canvas smoothing; zoom stays integer.
- [ ] `npm run build` passes.

Budget: 120–200k tokens.
