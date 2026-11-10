---
status: todo
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

- [ ] Golden tests: a synthetic piece scaled by 1.2 % and shifted registers within 0.5 px; a corner piece with two overlaps; a
      tone step is removed; the seam follows a band of low difference.
- [ ] 0063's subway join, rebuilt from its pieces in the game repo (`references/`), has a residual of 0.5 px or less. Record it
      here; the game's references aren't copied into Kiripix's tests.
- [ ] `kiripix op` runs each Op.

Budget: 250–350k tokens.
