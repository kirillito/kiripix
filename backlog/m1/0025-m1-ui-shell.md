---
status: done
milestone: M1
agent: ui-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0023-m1-serve.md, 0032-m1-rest-transport-and-multipart.md]
---

# M1: the UI shell, status board and parameter panels

Spec §11. User story 30 of [0010](0010-m1-room-end-to-end.md).

## What to build

- Record the framework: draft ADR 0008, "The UI is React with TypeScript and Vite" (the owner's decision of
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
- Ship the built app with the package: the wheel includes `web/dist` as `kiripix/web` (for example hatch
  `force-include`), the last place `serve` looks for it (after `--web`, `web/dist` in the Project and `web/dist`
  next to the package; see [0023](0023-m1-serve.md)).

## Acceptance criteria

- [x] ADR 0008 drafted.
- [x] Playwright: import and pick a Variant, change `fit.mode` in the generated panel, and see the stage bar update.
- [x] Changing a parameter from the CLI while the UI is open updates the UI without a reload.
- [x] `kiripix ui` from an installed wheel (not the checkout) serves the built app.

## Notes

- **A new Probe, `show <asset>`.** No Command gave the UI an Asset's current parameters, its Variants and Pick, or its
  image paths. It is a Command, so an agent gets the same answer; its MCP exposure is hidden until the acceptance test
  asks for it.
- **Packaging is a build hook** (`hatch_build.py`), not a plain `force-include`: `uv sync` builds Kiripix for development
  on machines with no Node, and must work without `web/dist`, while `uv build --wheel` must refuse to build without it.
  Use `--wheel`: a wheel built through the sdist wouldn't find the git-ignored `web/dist`.
- **The Stage screen comes from `describe` and `show`:** a Stage with a `pick` Decision gets the Variant grid; any other
  Stage with both an image and an input image gets the before/after slider, so nothing names `fit` or `palette`.
- **"Failing" means a `failed` Stage,** not a failing Check: Checks run for the open Asset only.
- **The masks and place screens** ([0026](0026-m1-ui-masks.md), [0027](0027-m1-ui-place-and-walk-test.md)) show the input
  image and the generated panel until then.
