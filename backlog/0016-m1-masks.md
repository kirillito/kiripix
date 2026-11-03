---
status: done
milestone: M1
agent: imaging-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0015-m1-fit-and-layers-pass-through.md, 0011-m1-decision-journal.md]
---

# M1: Masks without ML

Spec §4 (importing a painted mask image), §6.1 (masks), §7 (masks) and ADR 0001. User story 12 of
[0010](0010-m1-room-end-to-end.md).

## What to build

- Ops (`masks`): flood fill by colour region; brush strokes; splitting a painted colour image into binary Masks (the
  nearest defined colour from `[masks.<view>]`, plus the `import` table); cell-grid quantise. Pure, golden-tested.
- The room's `masks` Stage replays its Decisions in order onto the Plate's size: `flood` (a new point Decision, added
  to the Stage's schema), `brush`, and `import` (a new Decision naming a painted PNG stored under `decisions/` by
  hash). Output: one 1-bit PNG per painted Mask of the room's view. `snap_cell` applies the cell grid.
- `click` Decisions belong to SAM 2 ([0020](0020-m1-pinned-runner-calls-sam2.md)); until then a `click` makes the
  Stage `needs-input` with "not implemented until 0020".
- `mask.not_binary` on any Mask that isn't 1-bit. Derived Masks are never painted.
- With no Decisions the Stage is `done` with empty Masks, and `next` points the owner at painting `solid`.
- The `preview --overlay masks` test from [0014](0014-m1-check-and-preview.md).

## Acceptance criteria

- [x] Golden tests: a flood at a point, a brush stroke and an erase, a painted image with the `#FFFF00` import colour
      split into `solid`, and a cell snap.
- [x] `decide` a flood, then `undo`, then `run`: the Mask is empty again.
- [x] An imported painted image with a stray off-colour pixel snaps it to the nearest defined colour.
