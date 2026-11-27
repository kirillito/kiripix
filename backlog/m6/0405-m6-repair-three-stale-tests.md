---
status: todo
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
- [ ] Nothing outside `tests/` changes, unless a failure turns out to be a real defect: then say so here and stop.
