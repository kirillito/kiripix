---
status: todo
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

- [ ] CLI seam on a test room: an emitter of each shape type, a direction, colours; each finding above; a moved emitter and
      `undo`.
- [ ] CLI seam: a room with an emitter and no new fields builds the same `place` output as before, apart from the `null`s
      and `schema_version`.
- [ ] `describe` shows the schema; the contract sample passes.

Budget: 120–200k tokens.
