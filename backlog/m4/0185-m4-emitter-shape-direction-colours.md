---
status: done
milestone: M4
agent: core-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0137-m4-area-marker.md]
---

# M4: an emitter's shape, direction and colours

Part of [0183](0183-m4-ambient-animation.md), route (a). Spec §6.1 (`place`) and the glossary (Marker). The game fills an
emitter Marker with its own particles; today it types the dust's polygon into its own room data
(`../urban-mystery-club/game/data/rooms/room.annex.bedroom.json`). This ticket puts what is drawn on the room into Kiripix, as
areas did for trigger boxes. The game's particle kind, count and seed stay in its data: Kiripix gives an emitter no meaning.

Doesn't depend on the trial (0184).

## What to build

- The `marker` Decision of type `emitter` gets three optional fields, in target px:
  - `shape`: `{"type": "point"}` (the default), `{"type": "line", "x2", "y2"}`, `{"type": "box", "x2", "y2"}` (corners
    inclusive, as an area's) or `{"type": "polygon", "points": [[x, y], …]}` (at least three, closing itself).
  - `direction`: `{"x", "y"}`, a second point. The arrow from the Marker to it is the particles' direction, and its length is
    how far they travel.
  - `colours`: a list of hex colours, each on the Project palette, at most 16.
  A second Decision with the same ID moves or changes the emitter, as for other Markers. Omitted fields keep today's
  behaviour, so existing rooms rebuild unchanged.
- `room.json`: the emitter's Marker carries `shape`, `direction` and `colours` (`null` when unset), and `schema_version` goes
  up. `room.json` is rebuilt output, so an old one is refused (no migration).
- Checks on `place`:
  - `place.emitter_colour_off_palette` (error): a colour not on the palette; its `fix` is the nearest palette colour.
  - `place.emitter_outside_room` (warning): the shape or the direction's end leaves the room.
  - `place.emitter_shape_invalid` (error): a polygon with fewer than three points, or a box or line with zero size where the
    type needs one. The Decision refuses what it can, and the Check catches the rest after a resize.
- `describe room --stage place`: the schema, and text saying that the colours are what the game draws (opaque, decided by the
  Owner on 2026-11-12), so an agent picks them from the room around the Marker.

## Acceptance criteria

- [x] CLI seam on a test room: an emitter of each shape type, a direction, colours; each finding above; a moved emitter and
      `undo`.
- [x] CLI seam: a room with an emitter and no new fields builds the same `place` output as before, apart from the `null`s
      and `schema_version`.
- [x] `describe` shows the schema; the contract sample passes.

Budget: 120–200k tokens.

## Notes

2026-11-12:

- Decided: `markers.json` and `room.json` write `shape`, `direction` and `colours` on every emitter, `null` when unset (as an
  area's `walkable` is always written). `room.json` is schema 4 (an old one is refused); `markers.json` stays at 1. This
  changed `tests/cli/test_place.py`'s expected emitter and the `schema_version` pins in `test_export.py` and
  `test_export_layers.py`.
- Decided: `place` now lists the `palette` setting among its inputs (the colour Check reads it), so a palette change makes
  `place` stale.
- Decided: a `shape` of type `point` is kept as written; unset is `null`, and the game reads both as a point. The Decision
  refuses a polygon of fewer than three points, a line whose end is its start, a box with `x2 < x` or `y2 < y`, an empty
  `colours` list and more than 16 colours. `place.emitter_shape_invalid` runs the same rule on the built file.
- Decided: `place.emitter_outside_room` looks at the Marker's own point, the shape's corners or points and the direction's end,
  but only for an emitter with a shape or a direction, so an old emitter gets no new warning.
- Decided: the colour `fix` is a `decide` command that sets the same Marker with each off-palette colour replaced by its
  nearest palette colour (OKLab); colours compare case-insensitively.
- Open: a `direction` equal to the emitter's own point (zero length) is accepted. Say if it should be refused.
- Open: `kiripix/export` still reads `room.json` by `ROOM_SCHEMA_VERSION` imported from `recipes`, so it follows the bump with no
  edit here; 0186 exports the new fields.
- Tests: `tests/cli/test_emitter.py`.
