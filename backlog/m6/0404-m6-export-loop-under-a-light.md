---
status: done
milestone: M6
agent: godot-export
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0403-m6-loop-strips-only-changed-pixels.md]
---

# M6: export: a frame Loop under a room light shows no box in Godot

Spec §9 and §6.1 (`loops`). F2 of the trial [0402](0402-m6-pixelbolt-room-loops-trial.md), filed by the Owner's request on
2026-11-27. [0403](0403-m6-loop-strips-only-changed-pixels.md) makes a Loop's strips clear where they equal the room; this ticket
checks that the exported scene then shows no box under a light, and that nothing in the export undoes it.

## What to do

- A test room (made for the test, a few pixels: a patterned Plate, one light Marker over half of a small Loop's box) exported into
  a scratch Godot project.
- With Godot (`KIRIPIX_GODOT`; skipped without it, as the other Godot tests are), render one frame of the room scene, lit, and check
  that the Loop box's clear pixels show the lit Plate: the pixels around the moving ones match the scene rendered without the Loop.
- Check the Loop's sprite settings the scene writes (unshaded, filter off, the strip's alpha kept) and that an exported strip's
  clear pixels survive the import into Godot (no premultiply or fix-alpha-border artefacts on the edges of the moving pixels).
- If the scene needs a change for it, make it, keep every other exported file byte for byte, and say in the Result what the game
  sees.

## Acceptance criteria

- [x] CLI seam with Godot: the lit render of the test room shows no box around the Loop's moving pixels.
- [x] A room without a Loop exports byte for byte as before.
- [x] `lint-imports` and `mypy` pass.

## Result

- **What the game sees:** a Plate Loop's strip holds only what changes (0403), and the sprite is unshaded, so under a light the
  Plate shows lit wherever the room didn't change: no box, by day or under a dark `CanvasModulate`. Real Godot 4.7.2 (OpenGL, a
  viewport the Plate's size, nearest filter as the game sets it), with a light Marker over the left half of a kit Loop's box: frame
  0 of the Loop draws pixel-identical to the room with the `Loops` node hidden; frame 1 differs only at pixels the strip keeps; the
  light changes the Plate under part of the box (its left half), not all of it. The strip as Godot imports it has the file's alpha
  and its opaque pixels' colours exactly (no premultiply or fix-alpha-border change in what is drawn). The export copies the strip
  byte for byte (asserted); nothing in it fills the clear pixels.
- **Sprite settings** checked, unchanged: `light_mode = 1` material, `hframes`, `vframes`, `frame = 0`, the strip's alpha. The
  scene sets no `texture_filter` on a Loop's sprite (asserted), nor on the Plate's: filter off is the game's project setting, as for
  the Plate.
- **No scene change.** The export code is as before. (A first pass dropped a Layer's remainder when its Loop's frame 0 was clear;
  it went away when review narrowed 0403 to Plate Loops, since a Layer Loop keeps whole frames and its remainder.) So a room without
  a Loop exports byte for byte as before by construction (`kiripix/recipes/room.py`'s export is unchanged, `export` version 6),
  and the test checks it has no Loops node, material or `loops/` folder.
- Tests: `tests/cli/test_export_loop_light.py` (the Godot test, marked, ran with `KIRIPIX_GODOT`; the strip bytes; the no-Loop
  room).
