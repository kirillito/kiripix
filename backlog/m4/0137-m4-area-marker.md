---
status: done
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

- [x] CLI seam on a test room: each finding above, an area moved by a second Decision, and `undo`.
- [x] CLI seam: an area wholly on `solid` without `walkable` (an `escape.*` area over a fence) has no finding; with
      `walkable = true` it has `area.no_walkable`. Two areas with different prefixes and a one-cell-wide area are both accepted.
- [x] The ID is frozen once exported, as other Marker IDs are (checked once [0138](0138-m4-export-area.md) exports it).
- [x] `describe room --stage place` shows the schema, and its contract sample passes.

Budget: 200–300k tokens.

## Notes

2026-11-12:

- Open: the third box (ID frozen once exported) waits for 0138. The freeze code reads every Marker the Stage's Decisions
  place (`StageSpec.markers`), but the Exporter keeps only the types in `EXPORTED_MARKER_TYPES`, so an area's ID isn't frozen
  until 0138 adds `area` there. `status` stays `todo` for that reason.
- Decided: `DecisionSpec` got an optional `problem` hook (excluded from `describe`) for a rule a JSON Schema can't state. The
  `marker` Decision uses it for `x2 < x` / `y2 < y`; core's `decide` reports it as `decision.invalid` naming the corners.
- Decided: `markers.json` and `room.json` hold the snapped box (what the game gets), with `walkable` always written. The
  Decision keeps what was asked. `room.json` is schema 3 (an old one is refused); `markers.json` stays at 1, since a Stage
  rebuilds it from the Decisions and old files hold no area.
- Decided: a cell is ambiguous at a `solid` or `pit` share of 0.25 to 0.75, both included. A snapped box that leaves the room
  (for example a cell of 32 on a room 368 px high) is `area.outside_room`, and its message says it was snapped.
- `area.not_reached` counts ground reached from any Spawn or Exit (not only the main group), and an area with no walkable
  pixel is left to `area.no_walkable`, so one area never gets both. The Probe `reach` doesn't report areas.
- The `marker` schema's "a field belongs to these types" rule is now per field, because `x2` and `y2` belong to `ysort` and
  `area`; `cell` and `walkable` are optional on an area.
- Tests: `tests/cli/test_area.py`; `schema_version` 3 in `test_export.py` and `test_export_layers.py`.
- Confirmed by the Owner (2026-11-12): the ambiguous share 0.25 to 0.75 includes both ends, and a snapped box that leaves
  the room is the error `area.outside_room`, not clipped.

- 2026-11-12, after 0138: `area` is in the exported types, and `tests/cli/test_export_area.py` checks that renaming an exported area is
  refused with `export.id_frozen`. The third box is ticked and `status` is `done`.
