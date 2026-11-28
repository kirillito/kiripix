---
status: todo
milestone: M7
agent: none
type: trial
depends_on: [../m6/0331-m6-first-passes-over-a-list-of-rooms.md, ../m6/0325-m6-review-queue-command.md, ../m6/0329-m6-ui-review-queue.md]
---

# M7: a real run: first passes over the ch01 district without the Owner, then one sitting

Moved out of the M6 gate ([0338](../m6/0338-m6-gate.md)) by the Owner, 2026-11-27: it spends Claude tokens (one `claude -p`
session per room) and needs the room Runners' GPU, and the machine the gate ran on has none.

## What to do

- **Setup:** copy `skills/room-first-pass/` (SKILL.md and `batch.py`) to the art Project's `.claude/skills/room-first-pass/`;
  run on a machine with the GPU the Runners need.
- **The run:** `python .claude/skills/room-first-pass/batch.py --match 'room.*'` from the art Project: the six ch01 rooms
  (`room.annex_*`, `room.ch01_dungeon_*`), one session each, in sequence. Every room's `brief` is `todo` or stale (the merged
  template from [0348](../m6/0348-m6-brief-renders-the-prompt.md), and `work/` isn't in git), so each pass starts from `brief`.
  Dry run on 2026-11-27: all six would run. From the M6 gate: r01 and r02 need their `layers` lift run again (fitted before
  the downscale changed; r01 has partial pinned results from a stopped CPU run); r03's `fit` gives 1376 x 768 where the brief
  asks for 640 x 368, and its `layers` waits on the Owner's review of divergent Decisions.
- **One sitting:** the Owner clears the district's queue in the UI ([0329](../m6/0329-m6-ui-review-queue.md)).

## Acceptance criteria

- [ ] Recorded here, per room: its stop, its tokens, its Decisions (from the batch's report in `.kiripix/first-passes/`).
- [ ] The sitting's minutes from `stats --match`, per room, for the record only, not compared with an earlier milestone's.
- [ ] Every finding the run raises is filed as a ticket or accepted in writing.
