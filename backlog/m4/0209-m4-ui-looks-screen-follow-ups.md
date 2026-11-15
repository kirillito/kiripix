---
status: done
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

- [x] Playwright against `kiripix serve`: in a Project whose `palette` setting points to a moved file, the place and loops
      screens show its swatches.
- [x] Playwright: draw a difference box. The previewed region equals the region the Look has once the Decision is recorded
      and built.
- [x] Playwright: import two edits for one Look, pick the first from the list, and the toggle shows it.

Budget: 80–150k tokens.

## Result (2026-11-15)

- **Palette:** `projectPalette()` in `web/src/api.ts` calls the `palette` Command. The place screen's swatches and eyedropper and the
  loops screen's take their colours from it; `paletteColours` and the `style/palette.gpl` file reads are gone.
- **Difference:** the preview comes from the `look-difference` Probe (`lookScreen.tsx`), debounced by 150 ms, so a tolerance drag asks
  once it settles. The client-side OKLab comparison is removed. `LookTool` exposes `data-look-preview` (the previewed pixel count).
- **Variants:** the selected Look lists its edits from `show`'s `looks` (`look-variant-<name>`, the pick marked). A click is one
  `pick --look` (`pickEdit` in `App.tsx`). Dropping an edit still imports and picks it.
- Tests: `web/e2e/looks-follow-ups.spec.ts` (4): both screens' swatches from a moved palette file; the previewed region equals the
  region the built Look holds (the `region` Mask's pixel count); two edits imported, the first picked from the list, the toggle shows it.
  `looks`, `emitter` and `loops` specs still pass. Screenshots: `web/test-results/looks-difference-preview.png`, `looks-variants.png`.
- Note: `looks.json`'s `changed` counts pixels whose colour moved, not the region's pixels, so the test compares the region.
