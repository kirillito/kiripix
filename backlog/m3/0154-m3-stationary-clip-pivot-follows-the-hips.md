---
status: done
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
---

# M3: a stationary clip's pivot follows the hips, so the idle jitters by 1 px

Spec §6.3 (render, sheet) and the gate's "the feet stay at the scene's origin: no swimming in idle, and `sheet.pivot_drift`
passes on every stationary clip" ([0117](0117-m3-gate.md)). Found while preparing the gate, 2026-11-11.

## The gap

`character.mc02`'s first full run fails `check` with 179 `sheet.pivot_drift` errors, all on `idle`, all 1 px on x, in `sw`,
`w`, `ne` and `e` from about frame 11 or 60 on.

The cause is in `render_frames.py`: for a clip without `root_motion`, each frame's pivot is the root bone's head projected to
the ground (`under`), seen by the camera. Mixamo's idle sways the hips, so that point wanders: on `s` it spans x 38.896 to
39.137 and y 71.622 to 71.764 over the 100 frames. `sheet` rounds each pivot to a whole pixel (`_round` in
`character_sheet.py`) and places the frame by it, so wherever the sway crosses a half pixel the **whole sprite shifts by 1 px**.
In Godot that is the swimming the gate tests for, and the feet, which Mixamo keeps planted, are what move on screen.

The finding's fix, `kiripix run character.mc02 finish --force`, doesn't change anything: the pivots come from `render`.

## What to build

- In a `stationary` clip, every frame's pivot is the ground origin the camera orbits (the cell's pivot), not the point under
  the hips, so the feet stay where the render put them and nothing is shifted. A clip that is neither stationary nor
  `root_motion` keeps today's behaviour. (Alternative, if the Owner prefers it: measure the pivot from the feet. More work, and
  needs a rule for a pose with a foot lifted.)
- `sheet.pivot_drift`'s fix names the Stage that makes the pivots, not `finish`.
- `render` reuses unchanged clips (0119), so check that a stationary clip with old pivots is re-rendered or its pivots rewritten;
  `render.json` may be refused as old instead (CLAUDE.md, data files through M3).

The Owner chose the ground origin (2026-11-11).

## Acceptance criteria

- [x] CLI seam, on the fake: a stationary clip whose root moves sub-pixel reports one pivot for every frame, and `sheet` passes
      `sheet.pivot_drift`.
- [x] mc02 re-run: no `sheet.pivot_drift`, and every idle frame has the one pivot (39, 68), so `sheet` places them all alike.
      Re-run in a scratch copy of the art Project, not in the art Project itself (see below).
- [x] `sheet.pivot_drift`'s fix names `render`.

## How it was built

- `render.py`: a `stationary` clip's frames get the cell's pivot instead of the one Blender reports. A kept clip (0119)
  gets it as well, so a render.json that kept the hips' pivots can't carry them forward. `root_motion` clips already had the
  cell's pivot, because the camera follows the root. Any other clip still reports the root.
- `render.json` went to schema 2 (with 0155), and its format is now a Stage input of `render` (`render.format`, a computed
  setting like the Blender version, ADR 0010). So an older render is **stale**, and so is everything after it: `run`
  rebuilds the chain. Before this, `render --force` with new code changed the frames but not `render`'s input hash, so
  `palette` and the rest stayed `done` on the old frames. The format version is also in each clip's reuse key, so no old
  clip is kept.
- `sheet.pivot_drift` and `sheet.frame_overflow` now name `kiripix run <asset> render --force`. `frame_count` and
  `empty_frame` still name `finish`.
- The fake Blender sways the root 0.6 px on odd frames while a `blender-sway` file exists. A `render-format` file stands in for
  an older Kiripix's format.
- mc02, rebuilt from its art Project state in a scratch copy: `render` came up stale on its own, and `render`, `palette`,
  `finish` and `sheet` took 90 s, 27 s, 33 s and 2 s. `check` then had no `sheet.pivot_drift` or `sheet.frame_overflow`, only
  the known `clips.root_motion` warning. The art Project itself is untouched, and shows `render` stale until you run it.
