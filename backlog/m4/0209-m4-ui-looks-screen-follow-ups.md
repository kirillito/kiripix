---
status: todo
milestone: M4
agent: ui-engineer
type: ticket
parent: 0127-m4-room-looks.md
depends_on: [0204-m4-palette-command.md, 0205-m4-look-variants-and-difference-probe.md]
---

# M4: the looks screen's exact difference and Variants, and the palette from its Command

Follows [0132](0132-m4-ui-looks-screen.md) and [0187](0187-m4-ui-draw-an-emitter.md). Spec §11.

## What to build

- **Palette:** the place screen's emitter swatches and the loops screen's swatches and eyedropper take the palette from the
  `palette` Command (0204). No screen reads `style/palette.gpl` any more (`roomScreens.tsx`, `loopScreen.tsx`).
- **Difference:** the preview while dragging the box or moving the tolerance comes from the `look-difference` Probe (0205).
  The client-side OKLab comparison is removed. Calls are debounced so a slider drag doesn't queue one call per pixel.
- **Variants:** the selected Look lists its edit Variants from `show`. Clicking one picks it (`pick --look`), with the
  current pick marked. Dropping a new edit still imports it and picks it.

## Acceptance criteria

- [ ] Playwright against `kiripix serve`: in a Project whose `palette` setting points to a moved file, the place and loops
      screens show its swatches.
- [ ] Playwright: draw a difference box. The previewed region equals the region the Look has once the Decision is recorded
      and built.
- [ ] Playwright: import two edits for one Look, pick the first from the list, and the toggle shows it.

Budget: 80–150k tokens.
