---
status: todo
milestone: M1
agent: ui-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0023-m1-serve.md]
---

# M1: the UI shell, status board and parameter panels

Spec §11. User story 30 of [0010](0010-m1-room-end-to-end.md).

## What to build

- Record the framework: draft ADR 0007, "The UI is React with TypeScript and Vite" (the owner's decision of
  2026-11-02; Svelte and plain TypeScript were considered; canvas widgets are plain TypeScript classes mounted
  through a `ref`, so hover and brush updates never go through React state). The spec (§11, §12, §16) already
  refers to it. The owner reviews the ADR.
- `web/`: React, TypeScript and Vite, built only on the REST Commands of [0023](0023-m1-serve.md), with no logic of
  its own.
- The layout of §11: the Asset list, the canvas (integer zoom, nearest-neighbour, a "game frame" view), the stage
  panel and the stage bar. The status board, with the "needs me", "stale" and "failing" filters.
- Stage panels rendered from `describe`: parameter-only Stages (brief, fit, palette) need no Stage-specific code.
  Checks run live in the panel; clicking a finding jumps to its position.
- The before/after slider for fit and palette. The source screen's Variant grid, with drag-and-drop import.
- A `needs-review` Stage opens with a before/after, and Accept (with the session token) is its primary action.
- Refresh on the server's "changed" event.
- Playwright for a few flows (§12).

## Acceptance criteria

- [ ] ADR 0007 drafted.
- [ ] Playwright: import and pick a Variant, change `fit.mode` in the generated panel, and see the stage bar update.
- [ ] Changing a parameter from the CLI while the UI is open updates the UI without a reload.
