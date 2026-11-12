---
status: todo
milestone: M4
agent: core-engineer
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
---

# M4: an `area` Marker: a box on the room with a stable ID

Spec §6.1 (`place`, `reach`) and the glossary (Marker, Area). The game claims a battle area in the room for each encounter
(its DEC-048, TECHNICAL §4.5). Kiripix stays general: it gives an area no meaning, and the game reads `battle.*` IDs as battle
areas.

Not every area is for standing in. The game's first fight (its M04, the laneway) also needs an `escape.*` area over the fence
that raccoons leave by, and the game may use an area as a trigger (an Exit's walk-in rectangle, spec §6.1) or a camera frame.
Such an area has no walkable pixel, so a walkable rule that applies to every area would block it. The walkable Checks apply
only to an area that asks for them (`walkable`, below; decided by the Owner, 2026-11-12).

## What to build

- A `marker` Decision of type `area`, with `x`, `y`, `x2`, `y2` (a box, corners inclusive, in target px), an optional `cell`
  (px) and an optional `walkable` (bool, default false). With `cell`, the box's edges snap outward to multiples of `cell` from
  the room's top-left corner. A Decision with the same ID and type moves the area, as for other Markers.
- **Any number of areas, any ID.** An area's ID follows the Marker ID rule and is unique among the room's Markers, as for
  every Marker; Kiripix reads nothing into a prefix (`battle.*`, `escape.*` and `trigger.*` are the game's). A thin area is
  fine: a box one pixel wide (`x2 == x`), or one cell wide with `cell`. A box with `x2 < x` or `y2 < y` is refused by the
  Decision, with a message that names the corners.
- `room.json`: the area goes with the Markers, with `walkable`, and `schema_version` goes up. `room.json` is rebuilt output,
  so an old one is refused (no migration).
- Checks on `place`:
  - `area.outside_room` (error): the box leaves the room.
  - `area.no_walkable` (error, only with `walkable = true`): no walkable pixel inside the box. Its `owner_action` names both
    ways out: move the box, or drop `walkable` if the area isn't for standing in.
  - `area.ambiguous_cells` (info, only with `cell`): cells between a quarter and three quarters covered by `solid` or `pit`,
    with their positions and an `owner_action` to make the Mask decide. Kiripix doesn't decide which cells are open; the game does.
- On `reach`: `area.not_reached` (warning, only with `walkable = true`) when no walkable part of the area is reachable from a
  Spawn or Exit.
- The `describe` text and the Decision's schema. The text says what `walkable` asks for, so an agent sets it on a battle area.

## Acceptance criteria

- [ ] CLI seam on a test room: each finding above, an area moved by a second Decision, and `undo`.
- [ ] CLI seam: an area wholly on `solid` without `walkable` (an `escape.*` area over a fence) has no finding; with
      `walkable = true` it has `area.no_walkable`. Two areas with different prefixes and a one-cell-wide area are both accepted.
- [ ] The ID is frozen once exported, as other Marker IDs are (checked once [0138](0138-m4-export-area.md) exports it).
- [ ] `describe room --stage place` shows the schema, and its contract sample passes.

Budget: 200–300k tokens.
