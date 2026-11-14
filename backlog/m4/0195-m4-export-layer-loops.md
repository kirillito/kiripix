---
status: done
milestone: M4
agent: godot-export
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0190-m4-export-loops.md, 0192-m4-frame-ops.md, 0194-m4-loops-build-imported-frames.md]
---

# M4: export frame Loops, and Layers that move

Part of [0183](0183-m4-ambient-animation.md), route (c). Spec §9. 0190 exports the scene and `room.json` for Loops; this ticket
covers what frames add.

## What to build

- **A Layer that moves** (`layer = <id>`, from `sway` or kit frames with their own alpha): the Layer's `Sprite2D` takes the
  strip, with `hframes` and `vframes`, and keeps its y-sort position and offset, so its sort line doesn't move with the frames.
  Its frames are drawn over the Plate, whose fill shows where the object moved away. Check that the exported Plate under a
  moving Layer is the filled Plate, not the composite.
- **Strips with alpha:** frame strips keep binary alpha (Plate Loops are opaque inside the region, Layer Loops are not), and
  their import settings keep it lossless.
- **Large strips:** past 4096 px wide, the strip wraps into rows, and `vframes` is set; `room.json` carries both. A strip
  larger than 4096 × 4096 is refused by `export.loop_too_large` (error), with an `owner_action` to use fewer frames or a
  smaller region.
- `room.json`'s Loop entry gains `source` (`cycle`, `op`, `kit`, `edit`), for other Exporters and for the game's budget.

## Acceptance criteria

- [x] CLI seam: a room with a `sway` Layer Loop and a kit Plate Loop exports both; the Layer's node keeps its sort position;
      `room.json` matches.
- [x] Byte check: frame 0 of the Layer's strip equals the exported Layer, and the Plate under it is unchanged.
- [x] CLI seam: a strip over 4096 px wraps into rows; one over 4096 × 4096 raises `export.loop_too_large`.
- [x] In Godot 4.7, the exported kitchen's moving Layer sorts in front of and behind the stand-in body correctly while it
      plays (done once, by hand, recorded here).

Budget: 100–180k tokens.

## Result (2026-11-13)

- `ROOM_SCHEMA_VERSION` is 8: each `loops` entry gains `source` (`cycle`, `op`, `kit`; `edit` is held until trial 0184) and
  `moves_layer`.
- **Deviation from 0190, settled.** The ticket says the Layer's `Sprite2D` takes the strip, but a strip is cut to the Loop's box
  while the Layer's file is full size. Rule chosen: the Layer's own `Sprite2D` takes the strip only when the Loop is a frame Loop
  (`sway`, kit, any frames) on that Layer and its box covers every opaque pixel of the Layer (a `sway` with no region drawn, a
  kit over the whole Layer): `moves_layer = true`, for the first such Loop by ID per Layer. Otherwise the strip stays a child
  piece of the Layer's node (0190), because replacing the texture would drop the rest of the Layer, and keeping the whole
  texture under a part-Layer strip would leave the moved-away pixels showing. Colour cycles on a Layer are always child pieces.
  A part-Layer frame Loop that moves is therefore not yet clean in the game; the fix would be a Layer remainder image, not built.
- The moving Layer's node keeps its name, `position = Vector2(0, line)` (the sort line, unchanged) and `kiripix_id` (the Layer's
  ID); its `offset` is `(box x, box y - line)`, so frame 0 draws the Layer's pixels where they were. It carries the Loop's
  `hframes`, `vframes`, `sequence`, `phase`, `kiripix_type = "loop"` and `metadata/kiripix_loop` (the Loop's ID). The Layer's own
  texture resource is left out of the scene (its file is still exported and in the Manifest).
- The Plate under it is `palette/plate.png`, the filled Plate (a test compares it with the composite). Strips keep binary alpha
  and are copied byte for byte (lossless). Wrapping into rows was already done by `loops` (`STRIP_WIDTH` 4096).
- `export.loop_too_large` (error, `owner_action` only) is an `export` Check on a strip wider or taller than 4096 px.
- Tests: `tests/cli/test_export_layer_loops.py` (4; the over-size one builds 18600 frames and is slow); schema counts 8 in
  `test_export.py`, `test_export_layers.py`.
- Left for the Owner: the Godot 4.7 by-hand check (the moving Layer sorts correctly against the stand-in body while it plays).

## Closing notes (2026-11-13)

- Checked with Godot 4.7.2 rendering in a window (OpenGL), 2026-11-13, on the lamp test room rather than the kitchen: a 200 x 200 stand-in body in `Foreground`, 1 px behind and then 1 px in front of the Layer's line, for each of the 4 sway frames. Behind, all 169 opaque Layer pixels showed the Layer; in front, all 169 showed the body.
