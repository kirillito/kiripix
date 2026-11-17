---
status: todo
milestone: M5
agent: ml-engineer
type: trial
parent: 0236-m5-the-games-next-needs.md
---

# M5: trial: normal maps for a painted room from a depth Runner

Spec §8 (Runners: depth), §7 (normals from a depth map), §14 Later ("normal maps for painted backgrounds"). Part of
[0236](0236-m5-the-games-next-needs.md), item 8. The game's ISS-020 (`docs/DECISION_LOG.md`) and M10-02: a flashlight in an
unpowered tunnel, and supernatural glow on walls. Prototype code stays in `backlog/m5/0252-trial/`, not in `kiripix/`.

## Why

The game's lighting (its "Option A") never relights a painted Plate. This is a test the game decides at its M10, not a change
to that rule. A Plate with a normal map in a `CanvasTexture` would let a `PointLight2D` shade its walls.

## What to do

1. **The Runner:** pick a depth model that runs in 8 GB, with its licence confirmed for commercial use and its weights'
   source recorded (spec §8: Depth Anything V2 Small first; check the larger sizes' licences, and anything newer, since the
   choice stays open). Don't add it to the project yet.
2. **Depth to normals:** run it on the Source of a ch01 dungeon room (the stand-in for the game's tunnels), map the depth
   through the room's Grid transform, turn it into normals (Sobel on depth), and quantise them to a few levels. Do it per
   Plate and per foreground Layer, each cut by its alpha.
3. **In Godot 4.7:** the Plate as a `CanvasTexture` with that normal map, under a `PointLight2D` that follows the mouse, beside
   the same Plate without one. A short capture or GIF for the Owner.
4. **Measure** peak VRAM, time per room, and how the normals look at a Layer's edge and on flat painted floors (they should
   stay flat).

## What to record, in this ticket

- The Runner's licence, weights' source, VRAM and time.
- The capture, with its path, and the Owner's view.
- A recommendation for the game's M10: if it's yes, the tickets to file (a depth Runner, a `normals` step for rooms, the
  export's `CanvasTexture` for the Plate and Layers). If it's no, one line in spec §14.

## Acceptance criteria

- [ ] The licence confirmed before anything is downloaded into a Project. Any unclear licence goes to the Owner.
- [ ] The capture and measures above, and the Owner's verdict recorded.
