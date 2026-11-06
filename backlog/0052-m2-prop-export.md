---
status: done
milestone: M2
agent: godot-export
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0051-m2-prop-finish-and-footprint.md, 0047-m2-export-room-layers.md]
---

# M2: the prop's export

Spec §6.2, §9 and ADR 0003. Story 13 of [0037](0037-m2-layers-and-props.md). Follows D9 in [0037](0037-m2-layers-and-props.md).

## What to build

- The prop's `export` Stage leaves engine-free outputs in `out/export/`: the sprite and `prop.json` (schema_version, Asset,
  size, origin, collision shapes through `collision_shapes`).
- Godot: a scene per §9, with a `Sprite2D` drawn so that the origin is the scene's origin, and a `StaticBody2D` footprint on
  collision layer 1, relative to the origin. No body when the polygon is empty.
- Add `prop` to `_FILES_BY_KIND` and `EXPORTERS`. Stop `_current_ids` and `read_room` assuming `room.json`. `export --all` and
  the ownership, `--force`, `--adopt`, `--dry-run` and freeze rules all apply with no special case.
- Fix the texts that say "only rooms" or "every room".

## Acceptance criteria

- [x] A prop exports into a temporary Godot folder: the scene's text has the nodes and an offset from the origin, and the
      Manifest lists its files.
- [x] Editing the scene refuses; `--force` backs it up.
- [x] `export --all` exports rooms and props together, and Exit pairing still looks only at rooms.
- [x] `next` names `kiripix export prop.<id>` until the game has it.
