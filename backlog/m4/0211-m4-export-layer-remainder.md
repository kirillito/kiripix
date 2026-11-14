---
status: todo
milestone: M4
agent: godot-export
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0195-m4-export-layer-loops.md]
---

# M4: a frame Loop that moves part of a Layer: the Layer's remainder

Found in [0195](0195-m4-export-layer-loops.md) (2026-11-13). Spec §9. Today a frame Loop takes the Layer's own `Sprite2D`
only when its box covers the whole Layer, and then only for the first such Loop by ID on that Layer. A `sway` on part of a
Layer (a plant whose pot stays still), or a second moving Loop on the same Layer, becomes a child piece drawn over the full
Layer. The pixels it moves away from still show the Layer, not the Plate's fill. Nothing warns about it, and the Kiripix
preview disagrees with the game.

## What to build

- **The remainder.** For each Layer under one or more frame Loops that don't take its own sprite, export a remainder: the
  Layer with each such Loop's region (its frame-0 alpha) cleared. The Layer's `Sprite2D` takes the remainder, and the strips
  stay child pieces. The Layer's own file is still exported and listed in the Manifest.
- **`room.json`:** next `schema_version` (an old file is refused, naming the rebuild). The Layer's entry names its remainder
  file.
- Colour cycles and Plate Loops are unchanged.

## Acceptance criteria

- [ ] CLI seam: a `sway` on a region of a Layer, and two kit Loops on another Layer, export a remainder for each Layer.
      `room.json` matches the scene.
- [ ] Byte check: the remainder with every strip's frame 0 over it equals the exported Layer. In a later frame, a pixel the
      Loop moved away is transparent in both, so the Plate's fill shows.
- [ ] A room with no such Loop exports as before, apart from `schema_version`.
- [ ] In Godot 4.7, the part-Layer sway shows the Plate's fill where the plant moved away (done once, by hand, recorded
      here).

Budget: 60–120k tokens.
