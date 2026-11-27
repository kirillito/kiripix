---
status: todo
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

- [ ] CLI seam with Godot: the lit render of the test room shows no box around the Loop's moving pixels.
- [ ] A room without a Loop exports byte for byte as before.
- [ ] `lint-imports` and `mypy` pass.
