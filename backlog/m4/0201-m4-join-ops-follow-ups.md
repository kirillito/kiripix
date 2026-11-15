---
status: done
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
depends_on: [0135-m4-join-ops.md]
---

# M4: join Ops: a code per failure, cancellable, and a corner join end to end

Found in the review of [0135](0135-m4-join-ops.md) (2026-11-12).

## What to build

- **A code per failure.** `op register-piece`, `match-tone` and `seam-join` report every `ValueError` from the Ops as one code,
  `join.failed` (`kiripix/commands/join_ops.py`, `_refused`). Give each cause its own stable code, for example
  `join.no_overlap` (the piece doesn't overlap the base), `join.too_few_patches`, `join.overlap_too_narrow`,
  `join.no_shared_pixels`, and a `fix` or `owner_action` that fits it. "Too few textured patches… register by hand" is
  probably an `owner_action`. Today every fix is the Command's `--help` (changed from a fixed `--overlap east:200`, which was
  often the wrong side).
- **Cancellable.** `seam_join` and `match_tone` loop over every row in Python, and `register_piece` makes three passes over
  up to 48 × 12 patches per strip, so a piece several thousand px tall takes more than a second (ticket 0031). Ops can't
  import core: give the long Ops a chunk callback (or split them into chunks the Command drives), and have the Commands
  check `context.cancel` between chunks and between load, compute and save.
- **`Overlap.parse`.** Move `parse_overlaps` out of the Command into ops, next to `Overlap`, so a later `extend` Command
  reuses it. The Command keeps only the finding.
- **A corner join end to end.** 0135 tested registering a corner piece against two overlaps, but not joining it, which is
  two `seam_join` calls, one per neighbour. Add a golden test for it, and say in `describe` (or the Commands' help) that a
  corner piece is seamed once per overlap.
- **The glossary.** "piece", "base", "Overlap" and "join" appear in codes, messages and the CLI but have no entry in
  GLOSSARY.md. Add them, short, and check the Commands' text uses them as defined.

## Acceptance criteria

- [x] CLI seam: each failure has its own code, with a `fix` or `owner_action` that fits it.
- [x] A cancel during `op seam-join` on a large synthetic pair stops within a second and leaves no output file.
- [x] Golden: a corner piece joined to two neighbours.

Budget: 100–180k tokens.

## Result (2026-11-14)

- **A code per failure.** The Ops raise `JoinError(reason, message)`, a `ValueError` subclass in `kiripix/ops/join.py`. The
  Commands turn it into `join.<reason>`: `join.no_overlap`, `join.overlap_width` (the overlap is wider than the images),
  `join.too_few_patches`, `join.overlap_too_narrow` and `join.no_shared_pixels`. The argument errors (`no_overlap`,
  `overlap_width`, `overlap_too_narrow`) have the Command's `--help` as `fix`; `join.no_shared_pixels` has the
  `op register-piece` command for that pair as `fix` (since the review of 2026-11-14); `join.too_few_patches` has an
  `owner_action` (register by hand). Any other `ValueError` (a bad blend or sigma,
  a wrong image type) is still `join.failed`. All exit 1, like `image.partial_alpha`.
- **Cancellable.** `register_piece`, `match_tone` and `seam_join` take `chunk`, a callable run per patch (register), every 64
  rows (tone, seam). The Commands pass `context.cancel.check` and also check between load, compute and save, so a cancel leaves
  no output file. `kiripix/core/extend.py` already checks between its own steps; it doesn't pass `chunk` yet.
- **`Overlap.parse`** is in ops, next to `Overlap`; the Command's `parse_overlaps` keeps only the `join.overlap_invalid` finding.
- **A corner join.** `op seam-join`'s summary and the module text say a corner piece is seamed once per overlap, and that
  `register-piece` takes both.
- **Glossary:** Base, Piece, Overlap, Join.
- Tests: `tests/cli/test_join_failures.py` (6, including the cancel on a 16000 x 800 pair through `serve`),
  `test_a_corner_piece_is_seamed_once_per_neighbour` in `tests/golden/test_join_ops.py`.
- For the Owner to review: `tests/golden/expected/join_corner.png`.
