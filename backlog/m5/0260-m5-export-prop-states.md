---
status: todo
milestone: M5
agent: godot-export
type: ticket
parent: 0257-m5-prop-states.md
depends_on: [0259-m5-prop-stages-per-state.md]
---

# M5: export a Prop's states

Spec §9 (Prop). Part of [0257](0257-m5-prop-states.md).

## What to build

- **The scene,** for a Prop with states: a `Node2D` root at the default's origin, and one `Node2D` per state named by its ID,
  each holding that state's `Sprite2D` (offset so its origin pixel is the node's place) and `StaticBody2D` on layer 1. The
  default is `visible = true` with its polygons enabled. Every other state is `visible = false` with its
  `CollisionPolygon2D`s `disabled = true`. Each state node has metadata `kiripix_id` (the Prop's), `kiripix_type =
  "prop_state"` and `kiripix_state`.
- **Files:** `sprite.png` for the default as now, and `states/<s>.png` per other state. `prop.json` (bump `schema_version`)
  gets `default` and `states`: ID, file, size, origin, collision.
- **The Manifest:** the state IDs in their own list, frozen once exported.
- A Prop with no states exports exactly as today, apart from `prop.json`'s `schema_version`.

## Acceptance criteria

- [ ] CLI seam: a Prop with two states exports one scene with two state nodes, the second hidden with disabled polygons, and
      `prop.json` lists both.
- [ ] A Prop with no states gives the same scene as today.
- [ ] In Godot 4.7 headless: showing the second state's node and enabling its polygons gives its collision (a test scene in
      the test fixtures, if the suite already runs Godot; otherwise recorded here by hand).
- [ ] Spec §9's Prop row describes states.
