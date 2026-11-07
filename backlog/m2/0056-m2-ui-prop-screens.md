---
status: done
milestone: M2
agent: ui-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0051-m2-prop-finish-and-footprint.md]
---

# M2: the UI's prop screens

Spec §6.2, §11. Stories 11–13 of [0037](0037-m2-layers-and-props.md).

## What to build

- A prop opens on the shared screens wherever they fit: source, fit, palette, and `finish` from `describe`.
- `cutout`: method and chroma colour from `describe`, a before and after over a checkerboard, and for matting the same
  `--rerun` and Accept flow as layers.
- `footprint`: a canvas tool for the polygon and origin; a drag is one `decide` on release; `prop.no_origin` shows live.

## Acceptance criteria

- [x] Playwright with fake Runners: a prop goes from `import` to a `done` footprint in the UI.
- [x] Playwright: moving the origin records one Decision.
- [x] The room flows' Playwright tests still pass.
