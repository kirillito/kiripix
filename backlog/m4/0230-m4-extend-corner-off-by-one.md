---
status: done
milestone: M4
agent: core-engineer
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
---

# M4: `extend add` joins a corner only when the pieces land exactly on the image's edges

Found in trial [0134](0134-m4-trial-room-extended-both-ways.md) (2026-11-16), on the first real corner piece.

`add_piece` (`kiripix/core/extend.py`) builds each corner Overlap with `Overlap.placed(side, base.shape, piece.shape, origin)`,
which measures the overlap to the base's far edge: `bw - x` for east, `bh - y` for south. For a single side that's right. A
corner piece lies inside the L-shaped image's bounding box, so the overlap is right only when the piece ends exactly on both
outer edges. Real pieces are rescaled by up to about 0.1 %, and two things went wrong:

1. **The canvas origin.** The east piece registered 767 rows tall (scale 0.9996, at y 1), so `_corner` put the notch's top
   one row above the south piece's top. The canvas origin was y 575, and the south overlap was 769 rows against a 768-row
   piece: `join.overlap_width`, reported as `extend.registration_missed`. The canvas Kiripix writes has this origin too.
2. **After registration.** With the origin at y 576, the registered corner piece is 1374 px wide at x 1033, and the image is
   2408 px wide: an east overlap of 1375 px against a 1374 px piece, the same error.

In both cases the registration itself was fine: a scratch script that cropped the base to the piece's extent before the two
`seam_join` calls joined it with a residual of 0.23 px over 155 patches, and no seam shows after `fit` and `palette`.

Also seen: a piece that registers at y 1 (or x 1) leaves a transparent row (or column) on the image's outer edge, and
`done` then warns `extend.holes_remain` for 1031 px. A Source with a one-px transparent margin is poor; cropping that margin
(or replicating the edge) belongs with this fix.

## What to build

- A corner's Overlaps come from where the registered piece actually lies: each overlap ends at the piece's far edge, not the
  base's. The joined image keeps the base's size; any pixel only the base has stays the base's.
- The canvas origin of a corner comes from the notch's two inner edges as they are, including a row or column a rescaled
  piece leaves short.
- A transparent outer row or column left by a registration at 1 px (no picture beyond it on that edge) is cropped when `done`
  imports the image, or `done` reports it as its own finding with a fix. Pick one, and say which in the result.

## Acceptance criteria

- [x] CLI seam: a corner whose east piece is a row short, and a corner piece rescaled by 0.1 % so it ends 1 px inside the
      image, each join with no `extend.registration_missed` and give the expected size.
- [x] The existing exact-fit corner test still passes.
- [x] Trial 0134's four pieces (game repo `references/ch01-002-laneway01..04.jpeg`, `--keep` per [0231](0231-m4-extend-keep-per-axis.md))
      join through `extend` alone; the residual is recorded here.

Budget: 60–120k tokens.

## Result (2026-11-16)

- **The overlaps.** A corner piece registers, tones and seams on the base cut at the piece's far edge on each side
  (`_within` in `kiripix/core/extend.py`), and the joined region is pasted back, so the image keeps the base's size and
  every pixel outside the piece's extent stays the base's. A resampled corner piece reaching past the base is clipped
  to it. One-sided pieces join as before.
- **The canvas origin.** `_corner` reads the notch's inner edges across the whole notch (the median transparent depth of
  its columns, then of its rows), not from the outermost row and column alone. A notch a row taller because a piece came
  up short stays a row taller: the canvas sits on the notch as it is, and the overlap fix absorbs the one row.
- **The open margin: cropped.** `done` crops each side's outer rows or columns with transparent pixels, up to 2 px deep,
  when the next line inward is whole except for its last 2 px at each end (those belong to the margin across it). An
  unfilled corner is deeper, so it stays and `extend.holes_remain` still reports it. The result gives `cropped`, px per
  side (`{"south": 1, "east": 1}`), and the text says so.
- Tests: `tests/cli/test_extend.py`: an east piece a row short (origin 79, joined 400 x 240, `done` crops 1 px south to
  400 x 239, no holes); a corner piece rescaled by 0.999 (residual 0.014 px, `done` crops 1 px south and east to 399 x 239,
  no holes); an open L is not cropped.
- **Trial 0134's four pieces through `extend` alone (2026-11-16, in a scratch room, deleted after):** east `--keep 344`
  (residual 0.239 px), south `--keep 192` (0.110), then `canvas --side east,south --keep 344,192` (origin 1032, 575, no hand
  edit) and the corner: residual **0.225 px**, scale 0.99896 x 1.00028, gain 1.010–1.062, seam 2527 px, mean difference
  1.45. `done` cropped 1 px north and 1 px east, giving 2407 x 1343 with no transparent pixels, the size of the Source the
  trial joined by script and cropped by hand; 97 % of its pixels are identical to it (mean difference 0.016 of 255, along
  the corner's seam path).
