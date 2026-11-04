---
status: todo
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

- [ ] A room with two Layers, one flagged above: the scene's text has both nodes with the expected positions, and the
      Manifest lists their files and IDs.
- [ ] Removing an exported Layer fails with `export.id_frozen`.
- [ ] An M1 room with no Layers, rebuilt and re-exported, writes nothing and leaves the counter alone.
- [ ] A foreground PNG the game edited is refused like any other file.
