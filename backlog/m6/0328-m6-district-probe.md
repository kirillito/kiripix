---
status: done
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

- [x] CLI seam: a district of three test rooms, two paired by Exits and one pointing outside, gives three rooms in ID order,
      three thumbnails, and each pairing state.
- [x] CLI seam: a second call with nothing changed writes no thumbnail.
- [x] `district` has a sample in `tests/cli/test_contract.py`.
- [x] Spec §10.5 lists it.

## Result

`kiripix district <glob>` (kiripix/commands/district.py), a Probe, MCP exposed. It records nothing; it writes only the
thumbnail cache. Non-room Assets in the glob are left out with `district.not_a_room` (info); a glob that matches nothing is
`match.none`.

JSON `data`:

- `rooms[]`, in ID order: `asset`, `width`, `height` (px, from the brief), `tiles_wide`, `tiles_high`,
  `built` (`{stage, status, reason}` of the furthest Stage with a build, or null), `waiting` (the first Stage that isn't
  done, same shape, or null), `queue` (`{review, input, finding, agent_fixable}`, from `build_queue(...).by_asset`),
  `thumbnail` (a path relative to the Project, or null), `thumbnail_stage` (`export`, `palette`, `fit` or `source`) and
  `thumbnail_reason` (why none: a room with no built Source).
- `exits[]`, by room then Exit ID: `room`, `exit`, `side` (from the brief's `exits`, or null), `target_room`,
  `target_exit`, `pairing` (`paired`, `unpaired`, `outside`), `code` (`exit.not_paired`, `exit.no_exit` or `exit.no_room`
  when not sound) and `reason`. `outside`: the target room isn't in the district; the Project's pairing rule is run on it
  and `code`/`reason` are set if it fails, else null.
- `links[]`: `room`, `id`, `kind`, `two_way`, `start`, `end` (`place`'s `from` and `to`, as [x, y]).

The pairing rule is the one `exit.not_paired` uses: it was lifted into `_pairing` in kiripix/export/checks.py, which
`pairing_findings` and the new `exit_pairings` both call. Thumbnails are a 1x copy of the latest built image, as
`.kiripix/previews/<asset>.thumb.<stage>.<input hash>.png`; an older one of the Asset is removed. A second call writes none.

**`one_way` is never given yet.** An Exit's `target_exit` is required and nothing in a Marker says "no return is meant", so
there is nothing to derive it from. The state is reserved in the documented values. The owner decides how a one-way Exit is
marked (a Marker field is a `place` schema and version change); `unpaired` stands until then. The Owner chose a
Marker field on 2026-11-20: [0352](0352-m6-one-way-exit.md). `pairing` is a Literal type now.

Timing (art Project, 6 rooms, warm, `district "room.*"`): about 1.7 s; the first call after a pause 32 s (cold disk). Linear
in rooms, so about 2.8 s for 10; the cost is the per-room Stage hashes and the Exit pass, which reads each room's Decisions.
