---
status: done
milestone: M5
agent: ui-engineer
type: ticket
parent: 0253-m5-icon-kind.md
depends_on: [0262-m5-icon-kind-and-stages.md]
---

# M5: UI: the icon's screens

Spec §11. Part of [0253](0253-m5-icon-kind.md).

## What to build

- The icon's Stages reuse the Prop's screens (`source`, `cutout`, `fit`, `palette`, `finish`), with the square drawn on `fit`.
- The status board lists icons under their Kind, as it does every Asset.

## Acceptance criteria

- [x] Playwright: a fixture icon opens on the reused screens, with the square drawn on `fit`.
- [x] `npm run build` passes.

## Result

- `web/src/propScreens.tsx`: `IconSquarePanel` and a draw-only `SquareTool`, shown on an icon's `fit` screen. The square is the image's
  edge (gold); the padding is a dashed inset, read from `grid.json`'s `inset`. No Decision, no Command: it only draws.
- `web/src/App.tsx`: renders the panel for kind `icon` on `fit`. Every other icon Stage already rendered from `describe`; the status
  board already groups every Asset under its Kind, so icons needed nothing there. There is no footprint screen, because the icon has no
  such Stage.
- `web/e2e/icon.spec.ts`: a fixture icon lists under `icon`, opens on `source`/`cutout`/`fit`/`palette`/`finish` with no footprint, and
  `fit` shows the square (inset 2, 16x16 image). Screenshot: `web/test-results/icon-fit.png`.
- `npm run build` passes; the new spec passes.
