---
status: done
milestone: M6
agent: imaging-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
---

# M6: a frame Loop's strips keep only the pixels that differ from frame 0

Spec §6.1 (`loops`) and ADR 0011. F1 of the trial [0402](0402-m6-pixelbolt-room-loops-trial.md), filed by the Owner's request on
2026-11-27.

## The gap

A frame Loop's strip repaints every pixel of its box, and the Loop's sprite is unshaded. Where a light brightens the Plate under
part of the box, Godot draws the room's own pixels, unlit, over the lit Plate: a visible dull rectangle, by day and at night (0402,
finding 4: steam over a kettle under a window's light). It is not Pixelbolt's doing: any Loop (a kit, an edit, an Op) has it, and
particle-like Loops show it most, because most of their box is the room. The Owner turned a Loop down for it.

In 0402's scratch Godot project, making the pixels of frames 1 to N that equal frame 0 transparent removed the rectangle in both
lights and left the moving pixels as bright as before (a steam Loop kept 667 of 5,280 pixels; a drip 22 of 2,592).

## What to do

- In the `loops` Stage (`kiripix/recipes/loops.py`), each frame of a Loop's strip is transparent (alpha 0) wherever its pixel equals
  the room's pixel there (frame 0, RGBA exactly); the pixels that differ are kept as they are. This holds for every way a Loop's
  frames are made (an Op, a kit, an edit) and for the piece a strip cuts for a foreground Layer it crosses.
- A pixel that goes from the room's colour to another and back is kept on the frames where it differs, and clear on the others.
- `room.json`'s Loop entries don't change (box, frames, timing); only the strips' pixels do. Bump the Stage's `version` and name it in
  the Result: every room with a Loop is stale once.
- The Loop's checks still read the whole frame (the wrap, the flash rate, frame 0 is the room), so a check's answer doesn't change.
- Spec §6.1 says a strip holds only the pixels that change.

## Acceptance criteria

- [x] Golden seam: a strip from a small made-up Loop (a few moving pixels over a patterned room) is clear wherever a frame equals
      frame 0, pixel-exactly.
- [x] CLI seam: a room with a Loop rebuilds after the bump; its Loop's findings are the same as before; a Loop crossing a foreground
      Layer cuts its piece with the same rule.
- [x] `lint-imports` and `mypy` pass.

## Result

- New Op `clear_unchanged` (`kiripix/ops/frames.py`, exported from `kiripix.ops`): every pixel of a frame that equals frame 0, RGBA
  exactly, becomes (0, 0, 0, 0), and so does a kept pixel with alpha 0 (clear is one value); a differing pixel is kept; frame 0 is
  all clear.
- **Scope, decided in review (the Owner's pick):** the `loops` Stage applies it to a frame Loop **on the Plate**, in every piece it
  cuts (the Plate's piece and the piece for each foreground Layer it crosses), whatever made the frames (an Op, a kit, an edit, an
  atlas). A frame Loop **on a Layer** keeps whole frames, as before: its piece is cut to the Layer's pixels already, so it never
  paints the room's Plate over a lit Plate, and its frame 0 is the region export clears from the Layer's remainder (ticket 0211), so
  a pixel a frame moves away from shows the Plate's fill. The first pass cleared every frame Loop but a `sway`, and that brought back
  0195's ghost on a Layer (a moved-away pixel showed through). A colour cycle isn't a frame Loop and is unchanged.
- The checks, `moving`, the seam and the flash rate still read whole frames, so `loops.json` and `room.json` Loop entries are
  unchanged.
- **Version bump:** the `loops` Stage's `version` is 2 (`kiripix/recipes/room.py`). Every room with a Loop is stale once; after the
  rebuild a Plate Loop's strips are clear where they equal the room, and a Layer Loop's are byte for byte as before.
- ADR 0011 ("Frame 0 is always the room") and spec §6.1 say so.
- Tests: golden `tests/golden/test_loop_strip.py` (`expected/loop_strip_changed_only.png`); CLI `tests/cli/test_loop_strips.py`
  (a Plate shimmer crossing a Layer: every piece clear where a frame equals the room; the findings are those the code before 0403
  gave for the same room, `loop.texture` only, with smaller strips; a forced rebuild gives the same). Plate-Loop expectations
  changed ("frame 0 is the room" is now "frame 0 is clear, a kept pixel differs from the room") in `test_loop_edit_build.py`,
  `test_loop_frame_ops.py` (shimmer), `test_loop_kit_frames.py` and `test_import_atlas_loop.py`. The Layer-Loop tests are unchanged.
