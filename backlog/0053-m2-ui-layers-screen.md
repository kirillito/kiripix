---
status: todo
milestone: M2
agent: ui-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0043-m2-layers-stage.md, 0044-m2-plate-from-difference.md]
---

# M2: the UI layers screen

Spec §11 (Layers and masks). Stories 1, 2, 5 and 6 of [0037](0037-m2-layers-and-props.md).

## What to build

- A hand-written screen in the masks screen's style, reusing its canvas and `CanvasTool`: click-to-segment with the
  `segment-preview` Probe on hover, shift-click subtracting, a Layer list with its ID field, toggles for each Layer, the Plate
  and the hole, and the `grow` parameter from `describe`.
- Each click is one `decide`. A `run --rerun` is the screen's primary action, shows progress, and can be cancelled. A
  `needs-review` Stage opens with a before and after, and Accept as its primary action.
- D1's trim gesture: one Command on release.
- `plate-import` by drag-and-drop or a file picker.
- The UI holds no logic: hole, grow and Plate all come from Command outputs.

## Acceptance criteria

- [ ] Playwright with fake Runners: hover records nothing; a click records one Decision; the primary action leads to
      `needs-review`; Accept gives `done`, and the Layer can be toggled.
- [ ] Playwright: `plate-import` gives Layers with no Runner call.
- [ ] Measured on a real room the way [0059](0059-m2-slow-click-to-segment.md) measured `masks`, and recorded in this
      ticket: the time from hover to preview on the layers screen, warm and straight after a rebuild.
