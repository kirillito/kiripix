---
status: todo
milestone: M1
agent: imaging-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0018-m1-place-and-walkable.md]
---

# M1: reach

Spec §6.1 (reach) and §7 (reach). User story 19 of [0010](0010-m1-room-end-to-end.md).

## What to build

- Ops (`reach`): the footprint flood over walkable at a step size (with a `dash` over gaps when the Body has one); a
  narrowest-gap report. Pure, golden-tested.
- The room's `reach` Stage (top view only; side view stays in M5): floods from each Spawn and Exit, and outputs the
  reachable region as a Mask plus a report.
- Findings: `reach.unreachable_marker` for each Marker not reachable from the others, with its position; an
  unreachable walkable island as a warning, with its bounding box; the narrowest gaps as information.
- Each finding has a `fix` or an `owner_action`: an unreachable Marker usually means a Mask edit, which is the
  owner's.

## Acceptance criteria

- [ ] Golden tests: a room split by a wall, a gap one pixel narrower than the footprint, and a dash across a gap.
- [ ] An Exit behind a wall reports `reach.unreachable_marker` and `check` exits 2; erasing the wall with a brush
      Decision and re-running clears it.
