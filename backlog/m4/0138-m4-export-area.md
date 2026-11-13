---
status: todo
milestone: M4
agent: godot-export
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
depends_on: [0137-m4-area-marker.md]
---

# M4: export an `area` Marker to Godot

Spec §9 (Room).

## What to build

- An `Area2D` named from the Marker's ID, as other Marker nodes are, with a `CollisionShape2D` child and a `RectangleShape2D`
  the size of the box, placed at its centre. It has `monitoring = false`, `monitorable = false`, `collision_layer = 0` and
  `collision_mask = 0`, so it never touches physics. Metadata: `kiripix_id`, `kiripix_type = "area"`, `walkable`, and `cell` when set.
- An area with no walkable pixel (an `escape.*` area over a fence, an Exit's trigger box) exports like any other; nothing in
  the export depends on `walkable` but the metadata.
- The Manifest lists the ID with the other Marker IDs, so the ID freeze covers it.
- Spec §9's Room row.

## Acceptance criteria

- [x] CLI seam: the scene has the node, its shape and metadata. Renaming the ID after an export is refused.
- [ ] A `godot` test loads the scene in a headless Godot 4.7 with no warnings, and reads the area's rectangle back.

Budget: 80–150k tokens.

## Notes

2026-11-12:

- Decided: the `Area2D` sits under `Markers` with the other Marker nodes (no new group node, so a room without areas exports
  byte-identical to before). Its `CollisionShape2D` child is named `Shape`, a stable path like `Markers/battle-yard/Shape`.
- Decided: the position is the box's centre, `x + width / 2`, on the `Area2D`, and the shape child has none. Corners are inclusive,
  so the size is `x2 - x + 1` by `y2 - y + 1`; an odd side puts the centre on a half pixel (`2.5`). The box is the one in
  `room.json`, already snapped to its `cell`.
- Decided: the `RectangleShape2D`'s resource ID is `area_<node name>`, from the ID, not an index, so adding an area doesn't
  renumber the others' resources in the game's diffs.
- Decided: `walkable` is always written as metadata (`true` or `false`); `cell` only when set. Nothing else depends on `walkable`.
- The ID freeze needed only `area` in `EXPORTED_MARKER_TYPES` (it is derived from the node tables in `kiripix/export/godot.py`).
- Tests: `tests/cli/test_export_area.py` (scene text, a re-export writing nothing, rename refused with `export.id_frozen`, a new
  area allowed). The `godot` test is written but skipped here: no Godot 4.7 on this machine (`KIRIPIX_GODOT` unset, none on PATH),
  so it hasn't been run. Run it once where Godot is installed.

