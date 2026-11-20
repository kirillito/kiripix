---
status: done
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0234-m5-sprite-style-and-size-trial.md
---

# M5: a sprite's pivot at the ground point, as a body's

Found by [0234](0234-m5-sprite-style-and-size-trial.md)'s Godot capture ([lineup_4x.png](0234-trial/godot/lineup_4x.png)):
at the same position, `sprite.animal_control_worker` and `sprite.raccoon` stand about 5 px higher than mc03_male_clothes01
and mc03_female_clothes01.

## Why

- A body's pivot is the ground point the camera orbits, under the body's centre (`render`, `BOTTOM_RATIO` 0.1: y 67 in
  its 78 cell). In the 30° view its shoes reach about 6 px below it on screen.
- A sprite's pivot (`fit`, ticket 0179) is the centre of its lowest two rows, so its shoes are 1 px below it.

## What to build

- `fit` places a sprite's pivot where a body's would be: above the measured feet by the body's rule, scaled to the figure
  (about 0.1 × the figure's height, or the Project camera's own number if `render` derives it), and the same in every
  direction. A creature (the raccoon) gets the same rule unless a `pivot` Decision says otherwise.
- `fit`'s record says the offset it used. The cell grows if the pivot needs room below the feet.
- Bump `fit`'s `version` (what it writes changes), and name the bump in the Result.

## Acceptance criteria

- [x] A CLI test on the `demo`/sprite fixture: the pivot sits the rule's px above the lowest opaque row.
- [x] Re-run 0234's capture: the worker's, the raccoon's and the bodies' shoes share a ground line within 1 px.

## Result (2026-11-19)

- `fit` puts each direction's pivot `GROUND_RATIO` × the figure's height above its measured feet (the figure: the median opaque
  height of the stationary frames over every direction, so the offset is one number for all of them; halves round up). With
  `align_feet` the frame's own feet are raised the same. A `pivot` Decision is the pivot itself, with no offset, so the
  Decisions already made keep their effect. The cell grows below the feet by itself (it holds every frame round the pivot).
- **The ratio is 0.08, not 0.1.** Measured on the built `idle` sheets (visible bottom, outline included), the mc03 bodies'
  shoes are 4 to 5 px below the pivot in `s`, 2 to 6 in `se`, `e`, `sw` (the female's `e` is 1). At 0.1 the worker (58 px)
  stood 6 px down, 1 to 2 px lower than the bodies in `s`; at 0.08 it is 5, within 1 px of both in `s` and `sw`. The raccoon
  (32 px) is 3. A body's offset changes with the direction (its feet move in the 3D view) and a sprite's can't, so `se` and `e`
  stay 1 to 4 px apart.
- `fit.json` gains `ground` (`ratio`, `figure`, `offset`); its `pivots` are now the pivots, not the feet.
- **`fit`'s `version` is bumped to 2** (sprite Recipe), so every sprite's `fit` and everything after it is stale.
- Tests: `test_the_pivot_sits_the_ground_share_of_the_figure_above_the_feet_in_every_direction` (CLI), and the pivot-Decision
  test's measured pivot moved up 1 px.
- Checked in a scratch copy of the two sprites (the art Project untouched), beside the bodies' built sheets on one ground line:
  [worker_parts_lines_s_x5.png](0319-trial/worker_parts_lines_s_x5.png),
  [worker_parts_lines_4x.png](0319-trial/worker_parts_lines_4x.png).
- **The Godot capture (2026-11-19, with the Owner's go):** both sprites rebuilt in the art Project (the worker with
  `palette parts=skin=red,hair=orange,top=yellow,bottom=purple`, `finish inner_lines=outline`) and exported
  (`kiripix export`: the worker wrote `.tscn`, `color.png`, `character.json` and its new `ramps.png`; the raccoon its `.tscn` and
  `character.json`; nothing backed up). A one-off script (scratch only, nothing added to the game) set up 0234's scene: the gate's
  `CanvasModulate` and `PointLight2D`, the four 44 px apart at `idle` frame 0:
  [godot/lineup_1x.png](0319-trial/godot/lineup_1x.png), [godot/lineup_4x.png](0319-trial/godot/lineup_4x.png) (laneway above,
  kitchen below; `s` light left, `s` light right, `se`, `sw`); full frames `godot/<room>_<n>_<dir>_full.png`. A second pass on a
  flat background measured each figure's lowest pixel below its ground point in px (`godot/ground_<dir>.png`):

  | | s | se | e | sw |
  |---|---|---|---|---|
  | mc03_male_clothes01 | 5 | 4 | 3 | 6 |
  | mc03_female_clothes01 | 4 | 2 | 1 | 6 |
  | worker | 5 | 5 | 5 | 5 |
  | raccoon | 3 | 3 | 3 | 3 |

  Before this ticket a sprite stood +1 in every direction, so 4 to 5 px too high in `s`.
- **Against the criterion:** the worker is within 1 px of both bodies in `s` and `sw`, and of the male in `se`. The female
  stands up to 4 px apart in `se` and `e`: her feet move with the direction and a sprite's offset can't. The raccoon (32 px, 3)
  is within 1 px of the female in `s` and 2 px above the male: a shorter figure gets a smaller offset, by the rule. That
  criterion is the Owner's to call: a fixed offset for every figure (5 for the raccoon), or the rule as it is.
- **Owner (2026-11-19): accepted as it is.** The raccoon's smaller offset stays. Watch for it in the next PixelLab tests.
