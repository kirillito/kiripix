---
status: todo
milestone: M4
agent: core-engineer
type: ticket
parent: 0127-m4-rooms-for-grid-battles.md
---

# M4: an `area` Marker: a box on the room with a stable ID

Spec §6.1 (`place`, `reach`) and the glossary (Marker, Area). The game claims a battle area in the room for each encounter
(its DEC-048, TECHNICAL §4.5). Kiripix stays general: it gives an area no meaning, and the game reads `battle.*` IDs as battle
areas.

## What to build

- A `marker` Decision of type `area`, with `x`, `y`, `x2`, `y2` (a box, corners inclusive, in target px) and an optional `cell`
  (px). With `cell`, the box's edges snap outward to multiples of `cell` from the room's top-left corner. A Decision with the
  same ID and type moves the area, as for other Markers.
- `room.json`: the area goes with the Markers, and `schema_version` goes up. `room.json` is rebuilt output, so an old one is
  refused (no migration).
- Checks on `place`:
  - `area.outside_room` (error): the box leaves the room.
  - `area.no_walkable` (error): no walkable pixel inside the box.
  - `area.ambiguous_cells` (info, only with `cell`): cells between a quarter and three quarters covered by `solid` or `pit`,
    with their positions and an `owner_action` to make the Mask decide. Kiripix doesn't decide which cells are open; the game does.
- On `reach`: `area.not_reached` (warning) when no walkable part of the area is reachable from a Spawn or Exit.
- The `describe` text and the Decision's schema.

## Acceptance criteria

- [ ] CLI seam on a test room: each finding above, an area moved by a second Decision, and `undo`.
- [ ] The ID is frozen once exported, as other Marker IDs are (checked once [0132](0132-m4-export-area.md) exports it).
- [ ] `describe room --stage place` shows the schema, and its contract sample passes.

Budget: 200–300k tokens.
