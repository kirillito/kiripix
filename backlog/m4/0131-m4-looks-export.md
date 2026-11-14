---
status: done
milestone: M4
agent: godot-export
type: ticket
parent: 0127-m4-room-looks.md
---

# M4: export a room's Looks

Spec §9 (the Room row, Looks); ADR 0009. Needs [0130](0130-m4-looks-stage.md).

**The game binds a Look by its ID, not by its Condition.** Urban Mystery Club keeps every Kiripix Marker's behaviour in its own
room data, keyed by ID, with conditions as structured JSON over its Facts (its TECHNICAL §4.2 and §4.6), and it will bind each
Look the same way, as it does lights and interactables. So the Condition is a label for people and for other Exporters
(Phaser, Tiled), never something the game evaluates, and it is optional (decided by the Owner, 2026-11-12). The `kiripix_id`
metadata is what the game reads.

## What to build

- `room.json`'s next `schema_version` (after [0137](0137-m4-area-marker.md) and [0140](0140-m4-export-masks-and-room-json.md), whichever lands last): `looks`, each with `id`, `condition` (the label, or `null`), `file`, `box`, `pieces` (`layer`, `file`) and `collision`
  (`solid` shapes, as for the room). An old `room.json` is refused and the finding names the rebuild (no production
  rooms through M3).
- **The scene:**
  - a `Looks` `Node2D` drawn with the Plate, holding a `Sprite2D` per Look at its box, `visible = false`, with metadata
    `kiripix_id`, and `condition` only when the Look has one;
  - each piece as a `Sprite2D` child of its Layer's node (sorted or "always above"), so it sorts with the Layer and
    draws over it; hidden, with the same metadata;
  - a Look's `solid` as a `StaticBody2D` on collision layer 1 whose `CollisionPolygon2D`s start `disabled = true`.
- Node names follow the existing `-`-for-`.` rule. The Manifest records Look IDs; once exported they are frozen.
- A room with no Looks exports byte-identically to today, apart from `schema_version`.

## Acceptance criteria

- [x] CLI seam: a room with a Look over a Layer and a `solid` exports those nodes, hidden and disabled, with metadata. A Look
      with no Condition exports with `condition: null` in `room.json` and no `condition` metadata.
- [x] Godot 4.7 loads the scene with no errors (a session check, recorded here).
- [x] Removing an exported Look is refused by the ID freeze.

## Result

- `room.json` is at `schema_version` 6. `looks` lists each Look by ID: `id`, `condition` (or `null`), `file` (the Plate piece,
  `looks/<look>/plate.png`, or `null`), `box`, `pieces` (`layer`, `file` = `looks/<look>/layer.<layer>.png`), `solid` (the
  Look's own Mask, `masks/<look>.solid.png`, or `null`) and `collision` (`{"solid": [shapes]}`, `{}` without a `solid`). The
  Look's `solid` is also in `masks` as `<look>.solid`. The `export` Stage reads `looks` (now upstream of it, so it is stale
  until `looks` is built, and a `needs-input` `looks` blocks it); an old `room.json` is refused naming the rebuild.
- The scene: `Looks` (`Node2D`, after the Plate, before the Layers) holds a hidden `Sprite2D` per Look with a Plate piece, at
  its box. Each Layer piece is a hidden `Sprite2D` child of its Layer's node (`Foreground/<layer>` or `Above/<layer>`),
  positioned relative to the Layer's sort line. `LookSolids` (`Node2D`) holds a `StaticBody2D` per Look with a `solid`, on
  collision layer 1, whose `polygon_N` `CollisionPolygon2D`s are `disabled = true`. Every node of a Look has
  `metadata/kiripix_id` (the Look's), `metadata/kiripix_type = "look"` and, only when the Look has one,
  `metadata/condition`. A room with no Looks has none of these nodes, and its Manifest is unchanged.
- The Manifest's `ids.looks` lists the Look IDs (left out of the file when empty). The freeze reads them from the `looks`
  Stage's `pick` Decisions, so a pick undone fails with `export.id_frozen` before anything is rebuilt. Manifest repair merges them.
- Left for the Owner: the Godot 4.7 session check (Godot isn't on this machine). The ticket stays at `review` for it.
- Tests: `tests/cli/test_export_looks.py`; the `room.json` schema counts changed in `test_export.py`, `test_export_layers.py`
  and `test_emitter.py`.

## Closing notes (2026-11-13)

- Checked with Godot 4.7.2 (headless unless noted), 2026-11-13: the scene instantiated into the tree with no errors in the log; every Look piece is hidden and every `LookSolids` polygon is disabled.
