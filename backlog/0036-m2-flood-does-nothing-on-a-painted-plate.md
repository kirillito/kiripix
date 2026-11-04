---
status: todo
milestone: M2
agent: imaging-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: flood does nothing on a painted Plate

Found by the Owner at the M1 gate ([0029](0029-m1-gate.md)): flood had no visible effect. Its journal on
`room.harbor_front` records 16 tries.

## The bug

Flood fills the region of exactly equal colour on the Plate ([room.py:379-382](../kiripix/recipes/room.py#L379-L382)).
`palette` comes after `masks`, so that Plate isn't palette-mapped yet. A downscaled painting has 79,476 colours, so the
16 floods filled 1 px in 11 cases, 2 px in 4 and 70 px at most. Run on the palette-mapped image (58 colours), the same
points fill up to 3,009 px.

Flood only works today on art that is already flat. No error or finding says so.

## Decision

The Owner decided on 2026-11-04: **a colour tolerance in OKLab**, because exact-colour flood gets worse the larger the
palette. `palette` reads `layers`, not `masks`, and Mask edits must not rebuild it (the spec's changes since v0.2), so
flood can't simply read the palette Stage's output.

The flood Decision gains an optional `tolerance`. It stays deterministic, and the journal replays it exactly. A Decision
without one, old or new, replays with a tolerance of 0, and its data isn't rewritten, so existing Stages don't go stale.
The UI's slider is [0055](0055-m2-ui-flood-tolerance.md); this ticket changes nothing in `web/`. Follows D6 in [0037](0037-m2-layers-and-props.md).

`point_decision` makes every property required ([base.py:238](../kiripix/recipes/base.py#L238)), so `flood` needs its own
`DecisionSpec`, with `tolerance` left out of `required`. The "almost nothing" finding is a warning, and never blocks
export.

## Acceptance criteria

- [ ] A flood on a painted Plate fills a visibly useful region: a golden test on an unflattened fixture.
- [ ] A flood that fills almost nothing gives a finding, so the Owner isn't left guessing.
- [ ] Existing flood Decisions replay to the same Mask.
- [ ] `decide` a flood without `tolerance` is still accepted, and `describe room` documents the field.
- [ ] A flood with a tolerance of 0 fills the same pixels as the old Op, in a golden test.
