---
status: todo
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

- [ ] CLI seam: each failure has its own code, with a `fix` or `owner_action` that fits it.
- [ ] A cancel during `op seam-join` on a large synthetic pair stops within a second and leaves no output file.
- [ ] Golden: a corner piece joined to two neighbours.

Budget: 100–180k tokens.
