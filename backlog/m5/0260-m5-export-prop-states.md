---
status: done
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

## From 0258 (2026-11-17)

0258 already added the Manifest's `ids.states` (omitted when empty), its union in `manifest merge` and its comparison in
`check`, with no Manifest `schema_version` bump, as `looks` and `loops` were added before it. Nothing writes it yet: this
ticket does.

## Acceptance criteria

- [x] CLI seam: a Prop with two states exports one scene with two state nodes, the second hidden with disabled polygons, and
      `prop.json` lists both.
- [x] A Prop with no states gives the same scene as today.
- [x] In Godot 4.7 headless: showing the second state's node and enabling its polygons gives its collision (a test scene in
      the test fixtures, if the suite already runs Godot; otherwise recorded here by hand).
- [x] Spec §9's Prop row describes states.

## Result

- `export` Stage (`kiripix/recipes/prop.py`): `prop.json` is `schema_version` 2. A Prop with states adds `default` (the brief's
  `state`) and `states` (ID, file, size, origin, collision; convex shapes per state); the other states' sprites go to
  `out/export/states/<s>.png`. A Prop without states writes the same files as before, only the number differs. The Stage
  now has the `brief` as an upstream too (for the default's ID), so existing Props' `export` rebuilds once.
- Exporter (`kiripix/export/godot.py`, `__init__.py`): with states, a root `Node2D`, then one `Node2D` per state named by its ID
  (the default's included) holding `Sprite` and, when its polygon isn't empty, `Footprint` with `polygon_N`; metadata
  `kiripix_id`, `kiripix_type = "prop_state"`, `kiripix_state`; non-default nodes `visible = false` and polygons `disabled = true`.
  Without states the scene is as before. `states/<s>.png` is a Manifest file.
- Manifest: `ids.states` holds the default's ID and every state's, written by the export. `export/checks.py` (`_current_ids`)
  gained the brief's default state ID next to the declared ones, so the freeze doesn't see the default as removed.
- Spec §9 Prop row describes states.
- Tests: `tests/cli/test_export_prop_states.py` (scene, frozen IDs and stable bytes, a state `remove` refused after export, empty
  state footprint, no-states Prop, and a `godot`-marked test: Godot 4.7 shows the toppled node and enables its polygons and a
  point query then hits it, where it didn't before). `test_export_prop.py` updated for `schema_version` 2.
- The marked Godot test runs with `KIRIPIX_GODOT` set (Godot 4.7.2 at `C:\Homespace\[software]\Godot\`); it is skipped without it.
