---
status: done
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

- [x] Playwright: a brush stroke records exactly one Decision, and `Ctrl+Z` removes it from the canvas.
- [x] Hovering over an object shows a preview without writing to `decisions/`.

## Notes

- **Files:** `web/src/maskScreen.tsx` (the panel, key bindings, drop zone), `web/src/maskTool.ts` (the canvas tool),
  `CanvasTool.hover` added to `pixelCanvas.ts`, wiring in `App.tsx`, `web/e2e/masks.spec.ts`.
- **Keys:** `B` brush, `E` erase, `F` flood, `C` click-to-segment; `[` `]` brush size; a Mask by the first letter of its
  name that no tool has taken (`S` solid, `P` pit); `Shift` held makes a click, and its hover preview, negative. `Z`,
  `Space`, `Ctrl+Z`, `Ctrl+Shift+Z` are the shell's.
- **Rebuild:** a Decision changes the Masks only once the Stage has run, so the screen has "Rebuild the Masks after each
  edit" (on by default). With it on, the same action follows a `decide`, `undo`, `redo` or `mask-import` with `run
  <asset> masks`. Only a `click` adds `--rerun`, because it has no pinned result yet and lands in `needs-review` (the
  primary action then becomes Accept); no other edit may re-run a pinned call (ADR 0002). With it off, the Masks show
  after the Owner presses Run. This is two Commands for one edit, which the Owner allowed on 2026-11-04 by amending ADR 0006
  and spec §11. The `run` has its own job ID, so Cancel stops it, and its findings show with the edit's. It doesn't mark the
  screen busy, so quick strokes aren't dropped: the queue keeps them in order.
- **Shortcuts and focus:** a focused checkbox or slider takes no letters, so the shortcuts still work there (`isTyping` in
  `pixelCanvas.ts`, now the one check every screen uses). Space still toggles a focused checkbox, and a slider keeps its
  arrow keys. Text and number fields and selects still take every key.
- **Re-run:** when `next` names a `--rerun` Command for the Stage on screen, the primary action is "Re-run the Runner", an
  explicit `run <asset> <stage> --rerun`. The button follows `next` rather than comparing reason strings.
- **Mask names** come from the built Stage's output files (`solid.png`), since no Command lists the view's Masks before
  a run. Before the first run the panel says to run the Stage. A backend `describe`/`show` field with the painted Masks
  would let the screen work before a run; not needed for M1.
- **Shift-hover** previews the last object's clicks plus the negative one (`segment-preview` with those args), because a
  negative click only means something with the positive before it. With no earlier click on the Mask, a shift-click
  is refused in the panel with a message.
- **Tests:** SAM 2 is the fake Runner of `tests/fixtures`, loaded for the test server only through the harness
  (`Studio.start(true)`, the `segmentingStudio` fixture). The hover test compares `decisions/` and `history.jsonl`
  (sizes, times, contents) before and after the hover.
- **Not checked:** the real SAM 2 on a hover (no weights or GPU in the test run); the ticket 0024 timings cover the backend.
