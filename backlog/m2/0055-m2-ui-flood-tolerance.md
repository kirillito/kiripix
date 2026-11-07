---
status: done
milestone: M2
agent: ui-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0036-m2-flood-does-nothing-on-a-painted-plate.md]
---

# M2: the flood tolerance slider

The UI half of [0036](0036-m2-flood-does-nothing-on-a-painted-plate.md). Follows D6 in [0037](0037-m2-layers-and-props.md).

## What to build

- A slider on the masks screen, shown with the flood tool, range and default per D6. Each flood records its value as
  `tolerance` in its one `decide`. It reads the range from `describe` where it can. Moving it records nothing.
- A flood that fills almost nothing shows 0036's finding in the panel, and clicking it jumps to the point.

## Acceptance criteria

- [x] Playwright: a flood at the slider's value records one Decision with that `tolerance`.
- [x] Playwright: moving the slider alone records nothing.
- [x] Playwright: a flood on a one-pixel region shows the finding.
