---
status: done
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

- [x] The tests pass with Blender 5.2.x and skip cleanly without it.
- [x] Their time recorded here and in `docs/test-speed.md`.

## Result

Added `tests/cli/test_blender_render.py` (7 `blender` tests, through the CLI in a temporary Project), the Model
`tests/fixtures/characters/render_model.glb` (LFS by the existing `tests/fixtures/**/*.glb` pattern) and its generator
`tests/fixtures/make_render_model.py` (run with `blender -b --factory-startup --python tests/fixtures/make_render_model.py`;
`-- <folder> <stem> <scale>` writes a scaled copy, which the height-ratio test uses). The Model: about 270 quads (616
triangles), Mixamo bone names under `root` with a hand bone on each arm, materials `cloth`, `eye_iris`, `eye_white`, `skin` (a
flat patch of each eye material on each side of the face), actions `idle` (frame 1 is the rest pose) and `walk` (frames 1
and 13 are opposite poses, the middle of them the rest pose). It is `.glb` as the existing rigged fixtures are.

Tests: the Model opens as described; eyes (both recorded in every frame of every direction, the right one first, the
normal toward the camera in the front views and away in the back views, the eye materials in the material pass at the front
and absent at the back); the material pass (indexes 1 to 4 by name, 0 for the background); a 3-frame transition (the middle
frame is the rest pose to 4 px of the mask, the first is nearer its clip than the other, and the last likewise); `still` (6
frames reduced to 3 in the test, all identical) and `speed` (half the frames); a point on `mixamorig:RightHand` (inside the
mask in every frame of every direction, on the skin material when not `hidden`, moving with the arm); the base's height
ratio (a character on the 0.8 copy of the base's rigged file renders at 42 px against 52, its mask 0.8 as tall). Six of the
tests read one render shared in a module fixture, because Blender runs are the cost.

Time (Windows, Blender 5.2.3, `--cpu`, the machine shared with other agents): 202 to 246 s for the file, over the goal of two
minutes, which was for the Owner's GPU; not measured there. Recorded in `docs/test-speed.md`. They skip cleanly with
`KIRIPIX_BLENDER` pointing nowhere or without Blender on PATH (7 skipped, with the reason). `uv run mypy` is clean.

No bug found in `render_frames.py`; the real Blender path gave what the fake one is built to give.

Spec ambiguities: (1) the ticket says a 3-frame transition's first and last frames match the two clips' poses "within a
pixel of the mask", but with `length: 3` the blend positions are 0.25, 0.5 and 0.75 (spec and 0218), so no frame is an end
pose. The test checks what holds: the middle of two opposite poses is the rest pose to a few pixels, and each end frame is
nearer its own clip. (2) "An eye facing away is marked unseen": `render.json` has no seen flag, only the eye's camera-space
`normal` and `depth`; `finish` decides from them. The test checks the normal's sign and the material pass. (3) Blender here
is not on PATH (it is in `C:\Program Files\Blender Foundation\Blender 5.2`), so the tests ran with `KIRIPIX_BLENDER` set.
