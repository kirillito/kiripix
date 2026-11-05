---
status: done
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

- [x] Golden tests: a room split by a wall, a gap one pixel narrower than the footprint, and a dash across a gap.
- [x] An Exit behind a wall reports `reach.unreachable_marker` and `check` exits 2; erasing the wall with a brush
      Decision and re-running clears it.

## Notes

- **A room with no Spawn or Exit** (the question [0018](0018-m1-place-and-walkable.md) left): `reach` is `needs-input`,
  so `run` stops there and `next` tells the Owner to place one. The flood has nowhere to start, and that is what finally
  prompts for Markers.
- **Which Markers:** only Spawns and Exits, the ones `place` requires on walkable ground. "Cut off" means outside the
  largest group of Markers that reach each other; a tie goes to the group with a Spawn, then to the earliest Marker. So
  a Spawn and an Exit split by a wall report the Exit, not both. A Marker off walkable ground is always reported, beside
  `marker.not_walkable`.
- **`step` defaults to 1, not the 4 first declared.** A flood that hops on a lattice can miss a gap the Body fits only at
  one exact offset, so moving a Spawn by a pixel could flip the verdict. Step 1 is exact and takes about 0.2 s per flood on
  a 480 x 270 room. A longer step still works: it never crosses a wall, and the Mask comes out whole.
- **A dash crosses a `pit`, never `solid`** (the Owner's decision, 2026-11-03). `pit` is a new painted Mask of the top
  view: the Body can't walk on it, and it is part of what walkable and the narrowest gaps avoid. A dash crosses up to
  `dash` px of it along an axis. In spots that is a jump of up to `dash` plus the footprint's size, since a footprint
  clears a pit only by its own size more, and the footprint may touch no `solid` on the way. The Mask is called `pit`
  because a `Gap` in the reach Ops is a way through `solid`. A project whose `kiripix.toml` has no `pit` still works.
- **The narrowest gaps** come from `solid`, not walkable, because a gap too narrow for the Body leaves no walkable spot to
  find. Reported: at most 3, narrower than twice the Body, open at both ends, and one per passage at its narrowest.
- **Outputs:** `work/reach/reachable.png`, the union of the floods, and `work/reach/report.json`.
- **Contract additions:** `Position` gained `width` and `height` for an island's bounding box, and `next` now carries
  warnings as well as info findings.
