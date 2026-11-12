---
status: todo
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

- [ ] CLI seam: a room with a Look over a Layer and a `solid` exports those nodes, hidden and disabled, with metadata. A Look
      with no Condition exports with `condition: null` in `room.json` and no `condition` metadata.
- [ ] Godot 4.7 loads the scene with no errors (a session check, recorded here).
- [ ] Removing an exported Look is refused by the ID freeze.
