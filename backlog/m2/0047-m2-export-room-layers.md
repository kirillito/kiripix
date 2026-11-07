---
status: done
milestone: M2
agent: godot-export
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0045-m2-palette-with-layers.md, 0046-m2-ysort-lines.md]
---

# M2: foreground Layers in the room's scene

Spec §9 and ADR 0003. Story 14 of [0037](0037-m2-layers-and-props.md). Follows D3 in [0037](0037-m2-layers-and-props.md).

## What to build

- The `export` Stage copies the mapped `plate.png` and each `layer.<id>.png` to `out/export/`. `room.json` gains `layers`:
  each ID, its file, its sort position or the "above" flag. Bump `ROOM_SCHEMA_VERSION`; `read_room` already refuses an older
  file and names the rebuild.
- `room_scene`: a foreground `Sprite2D` per Layer under a y-sorted parent, with the sprite's position at the sort position
  and its offset cancelling it, so pixels stay where they are; "always above" sits above actors. Node names by the existing
  `-` rule.
- Write in this ticket's Notes what the game must do for actors to sort with these nodes (Godot sorts only inside a y-sorted
  parent). The gate proves it.
- `room_ids` adds each Layer ID, so the Manifest freezes it. A y-sort line makes no node, so its Marker ID stays unfrozen.
- With no Layers, the scene's text is unchanged.

## Acceptance criteria

- [x] A room with two Layers, one flagged above: the scene's text has both nodes with the expected positions, and the
      Manifest lists their files and IDs.
- [x] Removing an exported Layer fails with `export.id_frozen`.
- [x] An M1 room with no Layers, rebuilt and re-exported, writes nothing and leaves the counter alone.
- [x] A foreground PNG the game edited is refused like any other file.

## Notes

- `room.json` is schema 2 and gains `layers`: `[{"id", "file", "above", "y"}]` in the Layers' order (`layers.json`'s, which is
  the order of the first click). `y` is the sort position from `place`'s `sort`, null when `above` is true. `export` copies
  the mapped `plate.png` and each `layer.<id>.png` to `out/export/`; the Exporter writes them beside the scene and the
  Manifest lists them. `room_ids` adds each Layer ID to `ids.layers` (after `plate`).
- Scene: with a Layer that sorts, the root gets `y_sort_enabled = true` and `Foreground` (y-sorted) holds one `Sprite2D` per
  Layer, `position = Vector2(0, y)`, `offset = Vector2(0, -y)`, `centered = false`, `metadata/kiripix_id`. Layers flagged
  above sit in `Above` (a `Node2D`, `z_index = 100`) with no position. Neither parent exists with none of that kind, and with
  no Layers at all the scene's text is the M1 text (the test checks it). A y-sort line makes no node, so its Marker ID stays
  unfrozen.
- What the game must do for actors to sort with these nodes (Godot sorts only among nodes of a y-sorted group): the actors
  need a `y_sort_enabled` parent that is a child of the same y-sorted parent as the room instance, which is then
  `y_sort_enabled` itself. So the World node is y-sorted, holds the room instance (its root is y-sorted when a Layer sorts, and
  so is `Foreground`) and an `Actors` node that is y-sorted; the actors, as children of `Actors`, then sort with `Foreground`'s
  sprites by their global y. An actor's origin, and so its sort y, must be the middle of its footprint: the point `walkable`, the Spawn
  Markers and the walk test all use (decided after review, 2026-11-05). Actors at a z_index below 100
  stay under `Above`. A room with a Layer at y 0 or an actor above y 0 sorts under `Plate`; keep rooms at non-negative y. This
  is what the gate proves with a real Godot.
- Frozen: the freeze reads the built `room.json`, so removing a Layer (undoing its click) is refused at `export` once the room
  is rebuilt; before the rebuild the stale build still lists it. Not proven in a real Godot (not run here).
- Open question: a Layer ID is `[a-z0-9_]+` and so needs no `-` rule; a node under `Foreground` or `Above` is named by the ID.
- After review (2026-11-05): `ROOM_SCHEMA_VERSION` lives in `kiripix.recipes.room` (the export layer imports it). A test
  starts from a schema-1 `room.json`, as an M1 build left it.

### Fixed after the Owner's manual run (2026-11-05)

A room exported once, then rebuilt with a Layer that has neither a y-sort line nor "always above", crashed every `show` and
`status` with `TypeError ... godot.py:113`. Working out whether the game is behind (`export_pending`) builds the scene without
running the checks that refuse `layer.no_ysort` first. `read_room` now refuses such a Layer with `layer.no_ysort` (exit 2), so
the status shows `kiripix export` as pending and `export` says why. Test:
`test_an_exported_room_with_a_layer_left_unsorted_still_shows_and_its_export_is_refused`.
