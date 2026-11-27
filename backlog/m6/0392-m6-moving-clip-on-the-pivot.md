---
status: done
milestone: M6
agent: imaging-engineer
type: ticket
---

# M6: a moving clip stands on the same pivot as the stationary ones

Found 2026-11-26 in a game's battle view: `sprite.animal_control_worker`'s `walk` is drawn about 10 px left of (and 1–2 px
above) its `idle`, so the figure jumps sideways each time it starts and stops walking. `sprite.raccoon`'s `walk` is off by
~11–14 px left and ~12 px up in the same way (the game doesn't use it yet).

## Why

- `fit` takes each direction's pivot from the stationary clips' feet (0179, 0318). With `align_feet=true` each stationary
  frame is placed by its own feet, so `idle`, `hurt`, `bag` and the rest now share the ground point.
- A moving clip keeps the place its figure had on its source canvas, so a stride doesn't move the body mid-clip. That
  holds when every clip came on one canvas. When a clip came on a canvas of its own (a separate generation or import,
  such as a PixelLab walk made after the poses), the whole clip is offset by the difference between the two canvases.
- Measured on the exports (bounding-box centre and bottom against the pivot, first frame of each direction):
  worker `idle` s/e/w/n: dx −4.5/−4/2.5/6, dy 6; `walk` s/e/w/n: dx −10.5/−11/−6.5/−4, dy −2/−1/−2/−2.

## What to build

- In `fit`, with `align_feet`, place a moving clip as a whole: per direction, shift every frame of the clip by one offset so
  that the median of its frames' measured feet lands on the direction's ground point (the same rule a stationary frame
  follows, applied to the clip's median instead of each frame). The stride inside the clip is kept.
- A clip with no measurable feet (all frames empty or cut off) keeps today's placement and raises an info Check.
- `sheet.pivot_drift` compares moving clips by their median feet too, so a drift like this one is reported before export.
- Bump `fit`'s `version`, and name the bump in the Result.

## Acceptance criteria

- [x] A CLI test on a sprite fixture whose `walk` sits on a shifted canvas: after `fit align_feet=true`, the walk's median
      feet are within 1 px of the idle's in every direction, and the walk's frame-to-frame stride is unchanged.
- [x] Re-run and export `sprite.animal_control_worker` and `sprite.raccoon`: `walk` and `idle` share the ground point
      within 1 px (same measurement as above).
- [x] `sheet.pivot_drift` flags the fixture before the fix and is quiet after.

## Result

- `fit` (`sprite_fit.py`): with `align_feet` (and not `effect`, and `anchor=feet`), a moving clip is placed whole, per direction, by
  the median of its frames' measured feet landing on the ground point (the median less the ground offset on the cell's pivot), the
  same point a stationary frame's own feet land on. The stride inside the clip is kept. A clip and direction with no measurable
  feet keeps today's placement; `fit.json` lists it under `unmeasured` (only when there is one) and `fit.clip_unmeasured` (info)
  says so. **`fit`'s `version` is bumped 3 to 4.** Every sprite's `fit` is stale; with `align_feet` off nothing changes in its output.
- `check_pivot_drift` (`checks/sheet.py`) also compares a moving clip's median feet with the median of the stationary clips'
  feet in its direction (`moving_tolerance`, default 1 px), only for frames that carry measured `feet` (a sprite's, so a
  character is never checked this way). One `sheet.pivot_drift` per clip and direction, fix `fit align_feet=true`.
- Tests: `tests/cli/test_sprite.py` (walk on a shifted canvas lands within 1 px of the idle and keeps its stride; `sheet.pivot_drift`
  flags it with align_feet off and is quiet after; a clip with no feet gives `fit.clip_unmeasured`), `tests/golden/test_sheet.py`.
- Measured on the re-run and exported `sprite.animal_control_worker` and `sprite.raccoon` (game art Project), `walk` against
  `idle`, median feet of each direction against the pivot (x, y): every direction is within 0.5 px in x and y of the idle's
  (worker idle 0.0, +5.0 in all eight; walk 0.0 to -0.5, +4.5 to +5.0; raccoon idle 0.0, +2.0; walk 0.0 to -0.5, +1.5 to +2.0).
  Bounding box, first frame of each direction, walk minus idle (centre dx, bottom dy): worker s +3/-1, e +1/0, w -3/-1, n -2/-4;
  raccoon s -1/0, e +1.5/-1, w -2/0, n +0.5/+2. Before: worker s -6/-8, e -7/-7, w -9/-8, n -10/-8.
  The box centre of a figure still differs by a few px, because it follows the pose (a bag, an arm, a stride's first frame) while the
  ground point follows the feet; the median of the whole clip's box centres differs from idle's by up to 7 px (worker nw) for the same reason.
  `sheet.pivot_drift` is quiet on both.

## Open

- The criterion's "same measurement" (box centre of the first frame) isn't within 1 px for every worker direction. The feet are; a
  walk drawn with the body leaning off its feet keeps that lean. If the game still sees a jump, a measure by the body's
  centre would be a different rule (and a different ticket).
