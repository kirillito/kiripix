---
status: todo
milestone: M4
agent: godot-export
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0185-m4-emitter-shape-direction-colours.md, 0140-m4-export-masks-and-room-json.md]
---

# M4: export an emitter's shape, direction and colours

Part of [0183](0183-m4-ambient-animation.md), route (a). Spec §9 (room export). Doesn't depend on the trial (0184).

## What to build

- The emitter's node (`Emitters/<id>`, as today) keeps its place, `emitting = false`, `metadata/emitter`, `kiripix_id` and
  `kiripix_type`, and gains, when set:
  - `metadata/shape_type` (`"point"`, `"line"`, `"box"`, `"polygon"`) and `metadata/shape` (`PackedVector2Array`, relative to
    the node: a line's two ends, a box's four corners clockwise from top-left, a polygon's points);
  - `metadata/direction` (`Vector2`, relative to the node);
  - `metadata/colours` (`PackedColorArray`, opaque).
  A box is written as its four corners, so the game reads every shape as one polygon. Unset fields write nothing, so an old
  scene's emitter is unchanged.
- The node type stays `GPUParticles2D`. The game draws dust with a `Node2D` of its own (`world/fx/dust_motes.gd`), so changing
  the node type is a question for the game's wrapper, not this ticket.
- Exports from `room.json` only, as the rest of the scene does.

## Acceptance criteria

- [ ] CLI seam: an exported room with an emitter of each shape type; the scene's metadata matches `room.json`, the
      coordinates are relative to the node, and the colours are opaque.
- [ ] A room with an emitter and no new fields exports its emitter node byte-identical to before.
- [ ] In Godot 4.7, a scratch script reads `shape`, `direction` and `colours` from the exported bedroom's emitter (done once,
      by hand, recorded here).

Budget: 60–120k tokens.
