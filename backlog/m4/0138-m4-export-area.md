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

- [ ] CLI seam: the scene has the node, its shape and metadata. Renaming the ID after an export is refused.
- [ ] A `godot` test loads the scene in a headless Godot 4.7 with no warnings, and reads the area's rectangle back.

Budget: 80–150k tokens.
