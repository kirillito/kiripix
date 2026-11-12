---
status: done
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0161-m4-characters-after-the-m3-gate.md
depends_on: [0148-m4-render-material-pass.md]
---

# M4: a Check says when a small part vanishes from some frames

Spec §6.3 (checks). Found at the M3 gate ([0117](../m3/0117-m3-gate.md)), 2026-11-11, and seen through M3: mc02's eyes
disappear in some frames. At 52 px an eye is about one pixel, so whether a pixel's centre lands on it changes from frame to
frame, and `palette` may then merge what's left into the skin.

The Owner's fix is in the Model: bigger, anime-style eyes, as in Sea of Stars or Chrono Trigger. This ticket makes the
problem visible, so the Owner knows which parts and frames to fix without looking through every frame.

## What to build

- With the material pass of [0148](0148-m4-render-material-pass.md), count each material's pixels per frame, after
  `finish` (so after `palette` and the outline).
- `sheet.part_vanishes` (warning): a material seen in most frames of a clip and direction but missing, or under a threshold,
  in others. The finding names the material, the clip, the direction and the frames. Its `owner_action` says to make the part
  bigger in the Model or raise the character's `height`.
- A parameter for which materials to watch, defaulting to all. A part that is meant to turn away, such as the eyes facing
  `n`, is expected to vanish in whole directions, so only frames that differ within a direction are flagged.

## Acceptance criteria

- [x] CLI seam, on the fake: a material missing from 2 of 10 frames in one direction gives one `sheet.part_vanishes` naming
      those frames; a material missing from every frame of a direction gives none.
- mc02: the finding lists the frames where the eyes go missing, and none after the Owner's bigger eyes. Moved to
  [0197](0197-m4-mc02-bigger-eyes.md) (2026-11-12): it needs the art Project and the re-modelled Model.
