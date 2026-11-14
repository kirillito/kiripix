---
status: done
milestone: M4
agent: godot-export
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0189-m4-loops-stage.md, 0131-m4-looks-export.md, 0140-m4-export-masks-and-room-json.md]
---

# M4: export Loops to `room.json` and Godot

Part of [0183](0183-m4-ambient-animation.md), routes (b) and (c). Spec §9 (room export, Looks). The game plays Loops from its
frame counter, so the export gives frames and a sequence, never a clock.

## What to build

- **Files** beside the scene: `loops/<loop>.png` (the strip), `loops/<loop>.<layer>.png` (each piece), and for a cycle
  `loops/<loop>.index.png`. Lossless import, nearest filtering (as the Plate's).
- **`room.json`** (next `schema_version`; an old one is refused): `loops`, a list of ID, form, layer, box, file, `hframes`,
  `vframes`, frame count, `sequence` (a flat list of frame, ticks pairs), phase, light or `null`, pieces (layer, file, box) and,
  for a cycle, index file, colours and mode.
- **Scene:**
  - A `Loops` node, drawn with the Plate, as the `Looks` node is (the game's wrapper moves both onto the background layer).
  - Per Loop with `layer = plate`: a `Sprite2D` at its box (`centered = false`), the strip as its texture, `hframes`,
    `vframes`, `frame = 0`, visible, an unshaded `CanvasItemMaterial`, and metadata `kiripix_id`, `kiripix_type = "loop"`,
    `sequence` (`PackedInt32Array`), `phase` and, when set, `light`.
  - Each piece: a `Sprite2D` child of its foreground Layer's node, with the same frame layout and metadata, so it sorts with
    the Layer.
  - A Loop with `layer = <id>`: the Layer's own `Sprite2D` takes the strip as its texture, with `hframes`, `vframes` and the
    Loop's metadata. One node, so the Layer and its motion can't come apart.
  - Not `AnimatedSprite2D`: it runs on its own clock, and the game must step frames from its frame counter.
- **The Manifest:** Loop IDs are frozen once exported, and pruned like Look IDs.
- **The game's side** (to raise in the game's backlog, not built here): the room wrapper sets each Loop node's `frame` in
  `_physics_process` from `(frame_counter + phase)` through `sequence`; a dev hook holds every Loop at frame 0 for the Plate test
  and captures; a light named by `light` takes its energy from the Loop's frame.

## Acceptance criteria

- [x] CLI seam: a room with a Plate Loop, a Loop over a Layer and a Loop on a Layer exports the nodes, metadata and files
      above; `room.json` matches the scene.
- [x] Golden or byte check: every strip's frame 0 equals the exported Plate (or Layer) inside its box.
- [x] Prune and ID freeze: renaming an exported Loop is refused, as for a Look.
- [x] In Godot 4.7, a scratch script steps one exported Loop by its `sequence` for 600 ticks, and two runs give byte-identical
      captures (done once, by hand, recorded here).

Budget: 150–250k tokens.

## Result (2026-11-13)

- `ROOM_SCHEMA_VERSION` is 7. `room.json` `loops` (by ID): `id`, `form`, `layer`, `box`, `file` (Plate strip or `null`), `hframes`
  and `vframes` (the strips' columns and rows), `frames`, `sequence` (flat frame, ticks), `ticks`, `phase`, `light`, `pieces`
  (`layer`, `file`, `box`), `index`, `colours`, `mode`. Files are `loops/<loop>/plate.png`, `layer.<id>.png`, `index.png`.
- Scene: `Loops` after `Looks`; a visible, unshaded (`CanvasItemMaterial`, `light_mode = 1`, shared by every Loop sprite)
  `Sprite2D` per Plate strip; each piece a child of its Layer's node, after the Look pieces. Metadata `kiripix_id`,
  `kiripix_type = "loop"`, `sequence`, `phase`, `light` when set.
- Deviation: a Loop with `layer = <id>` is a child piece of that Layer too, not the Layer's own sprite: its strip is cut to the
  box, so replacing the Layer's texture would lose the rest of the Layer. 0195 (Layers that move) should settle this.
- Manifest `ids.loops` (omitted when empty; merge unions it); the freeze reads the `loop` Decisions of `loops`.
- Left for the Owner: the Godot 4.7 by-hand check.
- Tests: `tests/cli/test_export_loops.py`; schema counts in `test_export.py`, `test_export_layers.py`, `test_emitter.py`.

## Closing notes (2026-11-13)

- Checked with Godot 4.7.2 (headless unless noted), 2026-11-13: a scratch script stepped the Plate Loop by `sequence` and `phase` for 600 ticks, hashing each shown frame's pixels; two runs gave the same SHA-256 (`d42364b3…`), frames 0, 1, 2 with 18 ticks a cycle.
