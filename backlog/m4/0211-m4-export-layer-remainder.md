---
status: done
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

- [x] CLI seam: a `sway` on a region of a Layer, and two kit Loops on another Layer, export a remainder for each Layer.
      `room.json` matches the scene.
- [x] Byte check: the remainder with every strip's frame 0 over it equals the exported Layer. In a later frame, a pixel the
      Loop moved away is transparent in both, so the Plate's fill shows.
- [x] A room with no such Loop exports as before, apart from `schema_version`.
- [ ] In Godot 4.7, the part-Layer sway shows the Plate's fill where the plant moved away (done once, by hand, recorded
      here).

Budget: 60–120k tokens.

## Result (2026-11-14)

- `ROOM_SCHEMA_VERSION` is 9: each `layers` entry gains `remainder` (`remainders/<layer>.png`, or `null`).
- **The remainder** is written by the `export` Stage (`_write_remainders` in `kiripix/recipes/room.py`): the Layer with the frame-0
  alpha of every frame Loop piece on it cleared (to RGBA 0), cut at each Loop's box. The Layer's `Sprite2D` takes it (the
  `layer_<id>` resource points at it; the node, its position and offset are unchanged), and every strip stays a child piece.
  The Layer's own file is still exported and in the Manifest, as is the remainder. The Exporter copies `remainders/` beside the scene.
- **Deviation from the ticket, settled.** A Layer's own `Sprite2D` still takes a Loop's strip (`moves_layer`) only when that Loop
  covers the Layer (0195's rule) and is the only frame Loop with a piece on that Layer. If a second frame Loop (a kit Loop over
  the Layer, say) also touches it, the sprite can't show both strips, so neither takes it: `moves_layer` is false for both, the
  Layer gets a remainder with both regions cleared, and both strips are children. (0195's rule took the first Loop by ID and
  left the other's moved-away pixels showing.)
- Colour cycles, Plate Loops and a room with no frame Loop on a Layer are unchanged apart from `schema_version` and
  `remainder: null`; no `remainders/` folder is written then.
- Tests: `tests/cli/test_export_layer_loops.py` gains a part-Layer `sway` and two kit Loops on one Layer, each with the byte check
  (remainder plus every strip's frame 0 equals the exported Layer; the region is transparent in the remainder, including pixels a
  later frame moved away) and a room with no such Loop; the first test no longer has a kit Loop on the lamp. Schema counts are 9
  in `test_export.py` and `test_export_layers.py`.
- Left for the Owner: the Godot 4.7 by-hand check (the part-Layer sway shows the Plate's fill where the plant moved away).
