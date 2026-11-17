---
status: todo
milestone: M5
agent: qa-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: tests on the real Blender for the render script's newer paths

Spec §6.3 (render), ADR 0010. From [0203](../m4/0203-m4-stamped-eyes-blinks-and-still-clips.md)'s "Open": "The real Blender
path (`eye_groups`, `posed_eyes`, `seen_eyes` in `render_frames.py`) was run on mc03 in a scratch Project, not in a marked
Blender test." The same is true of other M4 paths. The fake Blender covers the Stages, not `render_frames.py` itself.

## What to build

Tests marked `blender` (the marker exists; they're skipped without Blender 5.2.x), on a small committed test Model (a few
hundred faces, rigged, two materials and two eye materials, in LFS), each running the real `render` through the CLI:

- **Eyes:** `render eyes=...` records both eyes in every frame, and an eye facing away is marked unseen in the back views.
- **The material pass:** materials numbered by name from 1, as 0148 does.
- **Transitions** (0218): a 3-frame transition renders, and its first and last frames match the two clips' poses within a
  pixel of the mask.
- **`still` and `speed`:** the frame counts `render.json` reports.
- **Points** ([0237](0237-m5-render-records-named-points.md)), once it lands: a point on the hand bone lies inside the hand's
  mask in every frame.
- **The base's height ratio** (0165): a character on a scaled copy of the base's rig renders at the expected height.

Keep the Model and clip short so the marked tests run in under two minutes on the Owner's GPU. Record the time.

## Acceptance criteria

- [ ] The tests pass with Blender 5.2.x and skip cleanly without it.
- [ ] Their time recorded here and in `docs/test-speed.md`.
