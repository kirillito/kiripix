---
status: done
milestone: M6
agent: imaging-engineer
type: ticket
---

# M6: the Layers Check on a `fit.png` of another size is a finding, not a crash

Found by the batch's final e2e run (2026-11-21). Existed before M6.

## The problem

`check_layers` (`kiripix/recipes/layers.py`, about line 576) compares `recompose(plate, layers)` with the upstream `fit.png`.
When `fit.png` was changed by hand to another size (the e2e spec `refresh.spec.ts` writes a 96x64 image over a 48x32 fit),
numpy can't broadcast the shapes and `check`, `next` and `queue` answer `internal.error` ("operands could not be broadcast
together with shapes (64,96) (32,48)"), HTTP 400, for the whole room.

## What to do

- A size mismatch between the fit and the Layers' output is a finding with a stable code (say `layers.stale_size`) whose `fix`
  rebuilds `layers` (`kiripix run <asset> layers`), and the rest of the Check is skipped. Look for the same pattern in the other
  Checks that compare an upstream image with their output (`palette`, `place`) and do the same.
- Normally the input hash makes `layers` stale when the fit changes; this is only the window before the rebuild, or a hand edit.

## Acceptance criteria

- [x] CLI seam: a hand-written `fit.png` of another size gives the finding with its `fix`, exit 2 not 1, and running the fix
      clears it.
- [x] `uv run mypy`, `uv run lint-imports` pass.

## Result

`check_layers` now compares the Plate's size with the fit image's first; a mismatch is the finding `layers.stale_size`
(fix `kiripix run <asset> layers --force`, since the hand edit leaves the input hash unchanged and a plain run skips) and
the rest of the Check is skipped, so `check` exits 2, not 1. No Stage output changed, so no `version` bump.

The same pattern, found in review: `palette` guarded its upstream comparison but not its own (`palette.png` against the
recomposed Plate and Layers), which crashed on a hand-resized `palette.png`; that is now `palette.stale_size` (fix
`kiripix run <asset> palette --force`). `check_loops` compared each Loop's frame 0 with a slice of `palette.png`, which
crashed when the image shrank under the region; that is now `loop.stale_size` (fix `kiripix run <asset> loops --force`),
and frame 0 isn't compared. `place` has no Check that compares an upstream image with its output. The three codes are
declared in their Stages' `checks`. Tests: `test_a_fit_image_of_another_size_is_a_finding_with_a_fix_not_a_crash` in
`tests/cli/test_layers_stage.py` and `test_a_palette_image_of_another_size_is_a_finding_with_a_fix_not_a_crash` in
`tests/cli/test_loops.py`.
