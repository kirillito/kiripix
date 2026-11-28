---
status: done
milestone: M6
agent: qa-engineer
type: ticket
---

# M6: repair three tests left behind by other tickets

Found while running the sprite and import tests for [0401](0401-m6-import-a-pixelbolt-atlas.md) on 2026-11-27. None of the three
fails because of 0401; each tests something another change moved.

## The failures

1. `tests/cli/test_import_sheet.py::test_a_sprite_takes_no_pick` expects `pick.no_stage`, but `pick` on a sprite now goes to
   0390's `gen_sprite.pick` and answers `pick.unknown_variant`. Decide from 0390 what `pick` of a sheet's name on a sprite should
   say, and test that (or rename the test to what it now checks).
2. `tests/cli/test_sprite.py::test_the_buff_glow_builds_with_dither_and_keeps_its_haze` and
3. `tests/cli/test_sprite.py::test_the_buff_glow_builds_with_vote_and_carries_the_finding` read
   `backlog/m6/0347-trial/sheets/buff_glow.png`, which was removed with the trial folders on 2026-11-27 (trial outputs don't belong
   in the repo). Replace it with a fixture made in the test (a small glow: a solid core inside a partial-alpha haze, as `haze()` in
   the same file builds), keeping what the tests check: `dither` keeps the haze, the vote drops it and raises the finding.

## Acceptance criteria

- [ ] The three tests pass, and no test reads a file under `backlog/`.
- [x] Nothing outside `tests/` changes, unless a failure turns out to be a real defect: then say so here and stop.

## Result

Done 2026-11-27, in `tests/` only; none of the three was a real defect.

1. `test_a_sprite_takes_no_pick` is now `tests/cli/test_import_sheet.py::test_a_sheets_name_is_no_image_candidate_to_pick`. Since
   0390, `pick` on a sprite picks one of its generated image candidates (`gen_sprite.pick`), and an imported sheet's name is none of
   them, so `pick.unknown_variant` is the right answer. The test checks the code, its `fix` (with no candidates yet:
   `kiripix gen <id> --image --prompt "<what to paint>"`) and that the sprite's files don't change.
2. and 3. The two buff glow tests in `tests/cli/test_sprite.py` build their sheet with `glow()`, made in the test: four 24 px frames,
   a solid core growing a pixel a frame inside a round haze whose alpha falls from 220 to about 30 at its rim (a graded haze,
   not `haze()`'s flat 102). The checks are unchanged: `dither` keeps the haze as opaque pixels, the
   vote drops it and raises one `fit.alpha_partial` warning. `GLOW` and its path into `backlog/` are gone.

Left for the Owner (why the first criterion stays unticked): `tests/cli/test_sound.py::test_the_asphalt_recording_slices_into_single_steps` still reads the Owner's own
recording, `backlog/m6/0398-trial/shoes-walk-road-asphalt-hard.flac` (skipped when it's absent). It's outside these three and tests a
real recording on purpose, so it wasn't replaced; moving the recording out of `backlog/` (with the test's path) or accepting the
exception is the Owner's call.
