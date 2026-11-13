---
status: done
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
---

# M4: join Ops: register, tone and seam a piece onto a Source

Spec §14 (M4) and §16 (open decision 7). Trial [0063](../m2/0063-m2-multi-screen-source-trial.md) found that a join needs three
steps, and all three are needed. [0134](0134-m4-trial-room-extended-both-ways.md) adds corner pieces. Pure Ops in `kiripix/ops`:
numpy in and out, no I/O.

## What to build

- `register_piece(base, piece, overlaps)`: estimates scale and shift (no rotation) from edge patches across each overlap. A
  corner piece has two overlaps, and both constrain the fit. Returns the transform and its residual in px. An image model
  rescales a piece by up to about 1.25 % (0063).
- `match_tone(base, piece, overlap)`: a smoothed gain per row for a join on the east or west side, or per column for one on
  the north or south side, from the overlap. Returns the toned piece and the range of the gain.
- `seam_join(base, piece, overlap, blend)`: the least-difference path through the overlap, blended over `blend` px (0063 used
  6). Returns the joined image and the seam.
- The numbers each Op returns are what a finding reports: the residual, the range of the gain, and the seam's length.

## Acceptance criteria

- [x] Golden tests: a synthetic piece scaled by 1.2 % and shifted registers within 0.5 px; a corner piece with two overlaps; a
      tone step is removed; the seam follows a band of low difference.
- [x] 0063's subway join, rebuilt from its pieces in the game repo (`references/`), has a residual of 0.5 px or less. Record it
      here; the game's references aren't copied into Kiripix's tests.
- [x] `kiripix op` runs each Op.

Budget: 250–350k tokens.

## Notes (2026-11-12)

Built in `kiripix/ops/join.py`, with findings in `kiripix/checks/join.py` and the Commands `op register-piece`, `op match-tone`
and `op seam-join` in `kiripix/commands/join_ops.py`. Goldens and tests: `tests/golden/test_join_ops.py`.

- **An `Overlap`** lays the piece on the base: `side` of the base, `width` px of the edge covered, `offset` along it. On the
  command line it is `side:width[:offset]`, comma-separated for a corner piece (`east:200,south:120`). It is only the first guess.
- **A fourth Op, `resample_piece`,** carries the piece onto the base's pixel grid (bilinear; a painted Source before `fit`, so
  smooth interpolation is right here) between `register_piece` and `match_tone`. `op register-piece --output` writes it and
  returns the Overlaps of the resampled piece, to pass on. The registration is not applied by the other two Ops.
- **Registration:** per-axis scale and shift, from normalised-correlation patches (24 px) in luminance, so a tone step doesn't
  matter; three passes (reach 16, 4, 2 px), each on the piece resampled with the last result; outlier patches trimmed. The
  residual is the rms distance between the patches and the fit. An axis whose patches are less than 64 px apart (a narrow strip
  gives no spread across it) takes the other axis' scale; the corner piece's second overlap is what fixes it.
- **Tone:** one scalar gain per row (column), the ratio of summed RGB in the overlap, both sums smoothed with a Gaussian
  (`sigma` 24 px), applied to the whole piece. Only one overlap is taken.
- **Seam:** dynamic programming, at most 1 px across per step, cost the mean absolute RGB difference of the two pixels either
  side of the cut; pixels with colour in only one image cost more than any difference. Ties go straight, then left, then right.
  The blend ramp is clipped inside the overlap. `Seam` holds the points, length, mean difference and both origins.
- **Corner join limit:** `seam_join` takes one overlap and a path running the join's length. A corner piece is registered
  against two edges in one call, but joined in two calls (one per neighbour), the second on the first's result. Where the
  two overlaps meet, the pixels of the first join are the piece's own, so the second seam sees zero difference there. Not
  tested end to end; the trial 0134 will show whether it shows.
- **Findings (warnings):** `join.residual_high` (over 0.5 px), `join.gain_wide` (gain outside 0.8 to 1.25),
  `join.seam_costly` (mean difference over 12). Errors: `join.overlap_invalid`, `join.failed` (too few textured patches, the
  overlap too narrow), `image.partial_alpha`.
- **0063's subway join** (game repo `references/inspirations/subway-lower-bay.jpeg` as the base, `references/tests/subway-lower-bay-extended-east-1.jpg`
  as the piece, `--overlap east:557`, any width from 541 to 565 gives the same): scale 0.9884 x 0.9877 onto the base's grid (the
  piece is 1.17 % wider and 1.25 % taller, as 0063 measured), shift (826.0, 4.16), **residual 0.30 px over 255 patches**, the
  same as 0063's 0.3. Tone gain 0.95 to 1.10; the seam is 966 px long with a mean difference of 1.6; the joined Source is
  2237 x 768 (0063 cropped it to 2185). Nothing was copied into Kiripix. An overlap guess 16 px off or more (573) fails the
  first pass (residual 1.65, with a warning), so a guess must be within about 16 px.
