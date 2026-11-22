---
status: done
milestone: M6
agent: imaging-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
---

# M6: an Op that dithers partial alpha, and the finding on the input

Spec §7 (Ops) and §6.4. From the trial [0347](0347-m6-vfx-trial.md), gap 1: an effect's glow body of partial alpha (Pixelbolt
writes `#RRGGBBAA`) was 72 % of its pixels and was dropped by `fit`'s majority vote with no finding, because
`fit.alpha_partial` looks at the already binary output. Alpha stays binary (0 or 255); a glow body has to become a pattern on
purpose.

## What to do

- Op `dither_alpha(image, pattern, ...)` in `kiripix/ops/`: an ordered dither (Bayer 2, 4 or 8) of partial alpha into 0 or 255,
  so alpha 102 of 255 becomes about 40 % opaque in a fixed pattern. Pure, deterministic, ties broken by position, RGB copied
  unchanged. Reachable through `kiripix op` and a `fit` parameter `alpha` (`vote`, the default, or `dither`).
- `fit.alpha_partial` is raised on the input in every mode, a warning that names the share of pixels it changed and what
  `alpha=dither` would do. The vote is otherwise unchanged.
- Golden tests: a small fixed input at three alphas, pixel-exact PNGs.

## Acceptance criteria

- [x] The trial's buff glow (`0347-trial/sheets/buff_glow.png`) builds with `alpha=dither` and keeps its haze as a pattern.
- [x] The same sheet with `alpha=vote` still builds and now carries the finding.
- [x] Goldens pass; the import rule holds (`ops` imports nothing else from Kiripix).

## Result

Done 2026-11-21. Spec §7 (resample) and §6.4 ("Partial alpha") say it. No Stage `version` bump.

- **Ops** (`kiripix/ops/resample.py`, exported from `kiripix.ops`): `dither_alpha(image, pattern=4)`, an ordered Bayer 2, 4 or 8
  dither in integers (opaque when `alpha * 2n² > (2M + 1) * 255`, so 0 stays clear and 255 opaque; the position alone picks, so
  there is no tie; RGB copied unchanged), and `alpha_coverage(source, grid)`, a cell's mean alpha (half up), which `fit` dithers.
- **`kiripix op dither-alpha <in> <out> [--pattern bayer2|bayer4|bayer8]`** (new Command; `commands/index.py` regenerated; samples in
  `test_contract.py`, `test_serve.py`; README row). It clears the RGB of a clear pixel in the file it writes.
- **`fit alpha`** (`vote` default | `dither`) and **`fit alpha_pattern`** (2, 4 default, 8). With `dither` a cell's colour is the
  vote's over every pixel with any alpha, its alpha the cell's mean alpha through `dither_alpha` at the frame's own pixel
  positions (the same pattern in every frame of a clip). A bad pattern fails `fit` with `fit.alpha_pattern_invalid` and a fix.
- **`fit.alpha_partial` on the input** (warning, every mode): `fit.json` records `alpha`, `alpha_pattern` and `alpha_partial` (per
  frame, cells changed and cells with any alpha) and the Check reads it. Chosen to write the keys only when some cell had partial
  alpha, so a sprite with binary alpha writes the same `fit.json` bytes (a test checks it) and needs no `version` bump; a sprite
  that has partial alpha gets the keys, and so the finding, when `fit` next runs (its images are unchanged under `vote`; the
  parameters are at their defaults, so it isn't stale). The output-side error is as before.
- **Tests**: `tests/golden/test_alpha_dither.py` (Bayer 4 at alpha 51, 102, 204, golden `alpha_dither_bayer4.png`, enlarged x6;
  density per pattern; coverage), `tests/cli/test_sprite.py` (vote and dither on a made-up haze, binary sprite unchanged, buff glow
  with dither and with vote, bad pattern), `tests/cli/test_ops.py`.

Changed after the batch's code review: **`fit`'s `version` is bumped 2 → 3.** `fit.json` gains `alpha`, `alpha_pattern` and
`alpha_partial` when the source has partial alpha, which is a change to what the Stage writes (CLAUDE.md), and without the bump a
sprite built before this ticket would never show the new `fit.alpha_partial` until someone forced `fit`. Every sprite's `fit` is
stale once; a rebuild of one with binary alpha writes the same bytes as before.
