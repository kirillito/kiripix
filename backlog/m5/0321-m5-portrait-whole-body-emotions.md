---
status: done
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0240-m5-portrait-kind.md
---

# M5: the portrait's Stages for whole-body emotions: `register` opt-in, the fit's head top, gestures inside the canvas

Found by closing [0241](0241-m5-portrait-trial.md) ("Answers after the redesign"). The portrait Stages
([0243](0243-m5-portrait-recipe.md)) were built on the trial's withdrawn answers: the body never moves between emotions.
The game's rules ([0240](0240-m5-portrait-kind.md), "Input from the game", its 0091 and DEC-071) free the pose, the
shoulders, the arms, the lean and the head's turn between emotions, and fix the head's place on the canvas.

## Why

- **`register`** lays every emotion on the neutral over the whole figure by default. An emotion with a new pose either
  fails `portrait.misaligned` (scale 0.985-1.015, shift 4 target px) or is moved by a transform fitted to a different pose.
- **`finish`**'s `lock_outside_face` is on by default when a `face` region is drawn, which freezes the body to the
  neutral's.
- **`fit`** takes its scale from `Grid.cover`, which fills the canvas. At 192 x 240 from a 3:4 image that leaves the head
  about 4 px below the canvas top. The rule is about 40 px.
- Nothing checks that a gesture stays inside the canvas. The rule is 2 px to spare at the top, left and right; the bottom
  edge is the waist cut.

## What to build

- **`register` opt-in:** a parameter (for example `mode`: `off` by default, `figure`, `outside_face`). With `off`, the
  Stage passes every emotion through unchanged, records the identity, and gives no `portrait.misaligned`. Its log says
  registration is off. The trial's numbers stay true for a set whose edits keep the body still, which is what the other
  modes are for.
- **`lock_outside_face` default false.** `portrait.shimmer` stays info; shimmer is judged by eye.
- **`fit`'s `head_top`** (target px below the canvas top, default 40): the scale puts the neutral figure's top row there
  and the figure's lowest row on the anchor's row, as now. Where the source has no pixels above the figure, the canvas is
  transparent. `offset_x`/`offset_y` stay for the Owner's own crop. Keep `Grid.cover`'s fill as a choice if it's cheap
  (`head_top` -1, say).
- **A Check, `portrait.out_of_canvas`** (warning, on `fit` or `finish`): per emotion, the opaque pixels within 2 px of
  the top, left or right edge, with a box. The `owner_action` is to remake the emotion with the gesture inside the frame
  (an image's crop is the image model's, not something Kiripix should fix).
- Bump `register`'s, `fit`'s and `finish`'s `version` (their defaults and what they write change), and name the bumps in
  the Result. A Project's existing portraits are rebuilt on the new rules; that's intended.

The fallback prototype, `0241-trial/portrait_set.py` (`set_fit`, `near_edge`), is the reference for the fit and the Check.

## Acceptance criteria

- [x] CLI seam: a fixture set where one emotion's arm is raised (a moved block of pixels outside any face region) goes
      through `finish` with no `portrait.misaligned`, and its arm is where its image put it, not the neutral's.
- [x] CLI seam: after `fit`, the neutral figure's top row is at `head_top` and its lowest row on the anchor's row, and every
      emotion has the same scale (in `fit`'s record).
- [x] CLI seam: an emotion whose figure reaches within 2 px of the left edge gives `portrait.out_of_canvas`; the fixture's
      other emotions don't.
- [x] `register` in `figure` and `outside_face` mode still passes 0243's registration tests.
- [x] A sample in `tests/cli/test_contract.py` for any new finding code. `uv run lint-imports` and `uv run mypy` pass.

## Result

Done 2026-11-19 in the main session (the ticket names `imaging-engineer`; the Owner asked for it in the main session's batch).

- **`register` `mode`** (`off` by default, `figure`, `outside_face`). `off` passes every emotion through (resized to the
  neutral's size, as before), records the identity (scale 1, shift 0, `applied` false), raises neither `portrait.misaligned`
  nor `portrait.residual`, and notes "registration is off". `register.json` now has `mode`. The `face` region is written for
  `finish` whatever the mode; it excludes tiles only in `outside_face`.
- **`finish` `lock_outside_face`** defaults to false. `portrait.shimmer` stays info; its `owner_action` now says nothing is
  needed and the flicker is judged by eye, and names the lock for a set whose body should stay still.
- **`fit` `head_top`** (default 40, -1 for `Grid.cover`'s old fill): `head_top_grid` takes the scale from the neutral's figure
  (its top row to its lowest, onto the canvas rows from `head_top` to the anchor's row), puts row `head_top`'s cell on the
  figure's top row and centres the crop on the anchor's column. Where the crop reaches past the source, every image (and the
  face Mask) is padded with transparent pixels; `grid.json` records `head_top` and `padding` (left, top, right, bottom), and
  its Grid is over the padded source. `figure` gains `top_y`. A scale under 1 or a `head_top` at or below the anchor is a
  `StageFailure` naming the fix. `offset_x`/`offset_y` stay the Owner's crop, in source pixels.
- **`portrait.out_of_canvas`** (warning, on `finish`, the image the game gets, since an `outside` outline adds a pixel): per
  image, neutral included, the opaque pixels within 2 px of the top, left or right edge, counted per edge, with their box.
  `owner_action`: remake the image with the gesture inside the frame.
- **Version bumps:** `register` 1 → 2, `fit` 1 → 2, `finish` 1 → 2 (with 0322's `clear_light_edge`), and the reuse keys'
  `_CODE_VERSION` 1 → 2. Every Project's portraits are rebuilt on the new rules.
- **Tests:** `tests/cli/test_portrait_stages.py`: a raised arm goes through `finish` where its image put it, with no
  `portrait.misaligned` or `portrait.residual`; `fit` puts the neutral's top row at 40 and its foot on row 239 with one scale
  (13/5), transparent where the source has none, and `head_top=-1` gives `Grid.cover`'s 5/2; an arm out to the left on a
  160-wide canvas gives `portrait.out_of_canvas` on that emotion only. 0243's registration and lock tests set
  `mode=outside_face` (and `figure`, parametrised) and the lock with `still_body`, and pass. `test_contract.py` checks the new
  code and parameters in `describe`. The UI's e2e fixture (a 32 x 40 canvas) sets `head_top=-1`. `lint-imports` and `mypy` pass.
- **On the trial's six images** (0241-trial/input, built in the art Project as `portrait.sanjay` at the gate): no
  `portrait.out_of_canvas`.
