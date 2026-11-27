---
status: todo
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

- [ ] Golden seam: a strip from a small made-up Loop (a few moving pixels over a patterned room) is clear wherever a frame equals
      frame 0, pixel-exactly.
- [ ] CLI seam: a room with a Loop rebuilds after the bump; its Loop's findings are the same as before; a Loop crossing a foreground
      Layer cuts its piece with the same rule.
- [ ] `lint-imports` and `mypy` pass.
