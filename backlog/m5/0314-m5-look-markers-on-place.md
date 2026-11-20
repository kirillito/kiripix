---
status: done
milestone: M5
agent: core-engineer
type: ticket
parent: 0254-m5-looks-markers-combining-and-reach.md
depends_on: [0269-m5-adr-looks-markers-combining-reach.md]
---

# M5: a Look's own Markers, walkable and clear on `place`

[ADR 0013](../../docs/adr/0013-a-look-has-its-own-markers-collision-and-reach.md), decisions 1, 2 (`look.overlap`) and 4.
Part of [0254](0254-m5-looks-markers-combining-and-reach.md). Spec §6.1 (Looks, `place`).

## What to build

- **The graph:** `place` gains `looks` upstream (room is ... → looks → loops → place). A Look edit makes `place` stale.
- **A Marker's `look`:** a `marker` Decision on `place` may name a `look`. Only a light, an emitter or an interactable may
  (`marker.look_type`, error); a `look` that names no built Look is refused (`marker.unknown_look`, error, with the undo).
  Marker IDs stay one set over the room and its Looks (`marker.duplicate_id`). A new Decision with the same ID and type
  moves a Marker into or out of a Look. A Look's Marker is checked as any Marker, against the Look's `solid` and walkable.
- **`markers.json` schema 3:** each Marker has `look`, a Look ID or `null`, always written. A schema 2 file is refused,
  naming the rebuild (`kiripix run <asset> place`).
- **Per Look with its own `solid`:** `place` writes `looks/<look>/walkable.png` and `looks/<look>/clear.png`, derived from
  the Look's `solid` and the room's `pit` as the room's are.
- **`look.overlap`:** a new `looks` Check, a warning naming both Looks, where two Looks' regions overlap. `looks.json` stays
  at schema 1.
- **Versions:** `place` 2 → 3; `looks` bumps only if what it writes changes (a new Check alone doesn't).
- Spec §6.1: the `place` row's Owner input (a Marker's `look`) and outputs; the `looks` row's new Check.

## Acceptance criteria

- [x] CLI seam: a light placed with `look: <id>` is written to `markers.json` with that `look`; every other Marker has
      `look: null`.
- [x] A `look` on a Spawn, Exit or area is refused (`marker.look_type`); one naming no built Look is refused
      (`marker.unknown_look`), and the Decision isn't recorded.
- [x] A Marker ID used by the room and a Look is `marker.duplicate_id`; re-deciding the same ID and type moves it.
- [x] A Look that erases part of the room's `solid` gets `looks/<look>/walkable.png` and `clear.png` with that part walkable;
      a Look without its own `solid` gets neither.
- [x] Two Looks with overlapping regions give `look.overlap` (warning) naming both.
- [x] A schema 2 `markers.json` is refused, naming the rebuild. Editing a Look makes `place` stale.

## Result

- **Built.** `place` has `looks` upstream (a Look edit makes it stale). The `marker` Decision takes `look` (a Look ID). `decide`
  refuses a `look` on a Spawn, Exit, area, y-sort line (`marker.look_type`) or naming a Look with no pick (`marker.unknown_look`)
  before recording it (`kiripix/core/lookmarkers.py`, run from `decide` and `redo`); `place` reports both too, as errors with
  the undo, for a pick undone later. `markers.json` is schema 3: every Marker has `look`, a Look ID or `null`. A schema 2
  file is refused, naming `kiripix run <asset> place`. For each Look whose `looks.json` entry has a `solid`, `place` writes
  `looks/<look>/walkable.png` and `looks/<look>/clear.png` (the Look's `solid` and the room's `pit`, as the room's are) into
  its output folder. `look.overlap` (warning, naming both Looks, at the overlap's box) is a new `looks` Check, reading the pieces'
  alpha.
- **Versions.** `place` 2 to 3. `looks` is unchanged (a Check alone); `looks.json` stays at schema 1. `markers.json` schema 2
  to 3 (refused when old, rebuilt by `place`).
- **Export.** `room.json` is unchanged for now: `export` keeps only the room's own Markers (those with `look: null`) and
  leaves `look` out of them, so the Look's Markers wait for ticket 0316.
- **Spec.** §6.1: the `place` row (Owner input, outputs, Checks), the `looks` Checks and the line saying `place` and `reach`
  read the room without its Looks.
- **Tests.** `tests/cli/test_look_markers.py` (one test per criterion); `test_place.py` expects schema 3.
