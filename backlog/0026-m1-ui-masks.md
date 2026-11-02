---
status: todo
milestone: M1
agent: ui-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0025-m1-ui-shell.md, 0024-m1-warm-sam2.md]
---

# M1: the UI masks screen

Spec §11 (Rules, Stage screens). User story 31 of [0010](0010-m1-room-end-to-end.md).

## What to build

- A canvas widget for the masks Stage: brush (with `[ ]` for its size), erase, flood and click-to-segment tools.
  Letters switch tools and Masks. Mask overlays with an opacity control.
- Every gesture is one Command on mouse release: a stroke is one `decide` brush, and a click is one `decide`.
- Click-to-segment previews on hover through `segment-preview`; shift-click subtracts.
- Importing a painted Mask image by drag and drop.
- `Ctrl+Z` and `Ctrl+Shift+Z` call `undo` and `redo`.

## Acceptance criteria

- [ ] Playwright: a brush stroke records exactly one Decision, and `Ctrl+Z` removes it from the canvas.
- [ ] Hovering over an object shows a preview without writing to `decisions/`.
