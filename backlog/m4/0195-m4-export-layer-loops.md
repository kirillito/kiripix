---
status: todo
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

- [ ] CLI seam: a room with a `sway` Layer Loop and a kit Plate Loop exports both; the Layer's node keeps its sort position;
      `room.json` matches.
- [ ] Byte check: frame 0 of the Layer's strip equals the exported Layer, and the Plate under it is unchanged.
- [ ] CLI seam: a strip over 4096 px wraps into rows; one over 4096 × 4096 raises `export.loop_too_large`.
- [ ] In Godot 4.7, the exported kitchen's moving Layer sorts in front of and behind the stand-in body correctly while it
      plays (done once, by hand, recorded here).

Budget: 100–180k tokens.
