---
status: todo
milestone: M4
agent: godot-export
type: ticket
parent: 0119-m4-room-looks.md
---

# M4: export a room's Looks

Spec §9 (the Room row, Looks); ADR 0009. Needs [0122](0122-m4-looks-stage.md).

## What to build

- `room.json` schema 3: `looks`, each with `id`, `condition`, `file`, `box`, `pieces` (`layer`, `file`) and `collision`
  (`solid` shapes, as for the room). An old `room.json` is refused and the finding names the rebuild (no production
  rooms through M3).
- **The scene:**
  - a `Looks` `Node2D` drawn with the Plate, holding a `Sprite2D` per Look at its box, `visible = false`, with metadata
    `kiripix_id` and `condition`;
  - each piece as a `Sprite2D` child of its Layer's node (sorted or "always above"), so it sorts with the Layer and
    draws over it; hidden, with the same metadata;
  - a Look's `solid` as a `StaticBody2D` on collision layer 1 whose `CollisionPolygon2D`s start `disabled = true`.
- Node names follow the existing `-`-for-`.` rule. The Manifest records Look IDs; once exported they are frozen.
- A room with no Looks exports byte-identically to today, apart from `schema_version`.

## Acceptance criteria

- [ ] CLI seam: a room with a Look over a Layer and a `solid` exports those nodes, hidden and disabled, with metadata.
- [ ] Godot 4.7 loads the scene with no errors (a session check, recorded here).
- [ ] Removing an exported Look is refused by the ID freeze.
