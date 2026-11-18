---
status: done
milestone: M5
agent: core-engineer
type: ticket
parent: 0255-m5-traversal-links.md
---

# M5: the Link Marker on `place`

Part of [0255](0255-m5-traversal-links.md). `reach` through a Link is [0266](0266-m5-reach-through-links.md).

## What to build

- **A `link` Decision on `place`:** an ID (unique among the room's Markers), `from` and `to` (points in target pixels),
  `kind` (free text, snake_case; `hop`, `climb` and `jump` named in `describe` as examples), and `two_way` (default true).
  `remove` and `rename` like other Markers. The ID is frozen once exported.
- **Checks:** `link.outside` (an end outside the room, error), `link.not_walkable` (an end where the Body's footprint doesn't
  fit, error, naming the end), and `link.same_place` (the ends closer than one tile, warning).
- `show` lists Links with the other Markers. `place.json` carries them, and its `schema_version` is bumped.
- The glossary gets **Link**: _a Marker with two ends on one Room, where an actor crosses by a scripted move (a hop, a
  climb, a jump)_. _Avoid_: portal, traversal, jump point (and Exit, which leads to another Room).

## Acceptance criteria

- [x] CLI seam: a Link between two walkable spots is recorded and shown. An end on `solid` raises `link.not_walkable`, and an
      end past the room's edge raises `link.outside`.
- [x] Contract sample for the Decision. Spec §6.1 (`place`) lists Links.

## Result

- `place` has a `link` Decision (`id`, `from`, `to`, `kind` in snake_case, `two_way` default true). A Link with the same ID moves
  it; undo takes it back. Other Markers have no `remove` or `rename` Decision either, so none was added (needs a decision if wanted).
- Code in `kiripix/recipes/room.py`: `_link_decision`, `_current_links`, `_markers_and_links` (the Stage's `markers` hook: `show`
  and the freeze see a Link as a Marker of type `link`, with `from`/`to` and no `x`/`y`), `_check_links`, `_read_links`.
  Checks `link.outside`, `link.not_walkable` (each names the end) and `link.same_place` (warning, ends under `project.tile`
  apart by distance). A Link sharing a Marker's ID raises `marker.duplicate_id`.
- `markers.json` (the ticket's `place.json`) is `schema_version` 2 with a `links` list (`{id, from, to, kind, two_way}`). A Stage's
  rebuilt output is refused when old: a 1 fails with a finding whose fix is `kiripix run <room> place` (`_read_markers_file`).
  The `place` Stage's `version` is bumped to 2, so every room's `place` turns stale and `status` shows the version reason; the
  Owner's rooms rebuild `place` and the Stages below it (`reach`, `export`). `reach` reads `markers.json` only after `place` has run.
- For 0279: `_place` writes `links`; the ends need `walkable.png` (top view only). `reach` doesn't use Links yet (0266). The
  freeze ignores a Link until 0267 adds `link` to `EXPORTED_MARKER_TYPES`.
- Tests: `tests/cli/test_place.py` (Links section, 6 tests) and `test_the_link_decision_validates` in `test_contract.py`.
  Glossary: Link. Spec: a paragraph under §6.1 place.

The Owner, 2026-11-17: no `remove` or `rename` Decision for Links. Markers have none: a Decision with the same ID moves
a Link, and `undo` takes one back. A Marker-wide `remove`/`rename` is a ticket of its own if the Owner wants one.
