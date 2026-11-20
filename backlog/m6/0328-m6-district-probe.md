---
status: todo
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0327-m6-match-scope.md, 0325-m6-review-queue-command.md]
---

# M6: `kiripix district`: a district's rooms, their Exits and what waits

Spec §11 (status board) and §14 (M6, the batch view). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). The UI
over it is [0330](0330-m6-ui-district-view.md).

## The gap

The batch view needs, per room of a district, a picture, a status and the Exits that join it to its neighbours. `status`
gives Stages, `check` gives `exit.not_paired`, and `preview` writes one image at a time. Nothing gives a district at once,
and the Exits' targets are only in each room's `place` Decisions.

## What to build

A Probe (records nothing): `kiripix district <glob> [--json]`, on rooms only (another Kind in the glob is left out, with an
info finding).

- **`rooms`**, in ID order, each with: its size in px and tiles; its furthest built Stage and the Stage it waits at (if any),
  with the status; its counts from `queue` (items by type, and `agent_fixable`); and a thumbnail: the latest built image of
  `export`, else `palette`, else `fit`, else the Source, at 1x, cached in `.kiripix/previews/` by its input hash.
- **`exits`**, every Exit of every room in the district: room, Exit ID, its side (from the brief when it has one), its target
  room and Exit, and its pairing: `paired`, `one_way`, `unpaired` (the reason `exit.not_paired` gives), or `outside` (the target
  isn't in the district; then it's checked against the whole Project, as 0327 does).
- **`links`**, the rooms' traversal Links, as `place` holds them (they stay within a room).

It answers in under 3 s for a district of 10 built rooms with warm thumbnails. A room with no Source has no thumbnail and
says so.

## Acceptance criteria

- [ ] CLI seam: a district of three test rooms, two paired by Exits and one pointing outside, gives three rooms in ID order,
      three thumbnails, and each pairing state.
- [ ] CLI seam: a second call with nothing changed writes no thumbnail.
- [ ] `district` has a sample in `tests/cli/test_contract.py`.
- [ ] Spec §10.5 lists it.
