---
status: done
milestone: M4
agent: core-engineer
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
depends_on: [0135-m4-join-ops.md]
---

# M4: `extend`: the canvas for the next piece, and the join into a Variant

Spec §14 (M4) and §16 (open decision 7). The budget is $0, so the Owner makes pieces in the image model's own UI, not through a
Provider. This tool doesn't wait for Providers. From M6, `gen` may drive it.

## What to build

- `kiripix extend <id> canvas --side east|south|west|north [--keep N]` writes the canvas to paste into the image model and prints
  its path. The canvas is the kept strip of the current joined image (`--keep` Source px, default a third of the canvas) and a
  flat fill, at `[extend] canvas` in `kiripix.toml` (default 1376 x 768). The first canvas starts from the room's picked Source.
- `kiripix extend <id> add <png> --side …` registers, tones and seams the piece with [0135](0135-m4-join-ops.md)'s Ops, and reports
  the residual, the gain and the seam. When registration misses its limit, it records nothing and returns a finding. The
  finding's `owner_action` is to keep a wider strip or make the piece again (0063: a piece fails when too little of a subject
  is in the strip).
- `kiripix extend <id> done` imports the joined image as a Variant, so `pick` works as it does for any import.
- The pieces and their sides are kept in the Asset's folder, with an append-only journal, so `undo` (`extend <id> undo`) drops
  the last piece. Every write is atomic, and the cancel token is checked between Ops.
- Spec §10.5 lists the Commands.

The Owner's answer (2026-11-13): the pieces live in a journal of their own in the Asset's folder (append-only, atomic writes),
not as Decisions of the `source` Stage. `extend <id> undo` drops the last piece.

## Acceptance criteria

- [x] CLI seam: a canvas, a piece to the east, a piece to the south and the corner give one Variant of the expected size. `undo`
      drops the last piece.
- [x] A piece that doesn't register gives the finding, and no Variant.
- [x] A contract sample for each new Command.

Budget: 250–400k tokens. A UI for choosing the strip and seeing the seam is another ticket, if the Owner wants one after using this.

## Result (2026-11-13)

One Command, `extend <id> canvas|add <png>|undo|done` (`kiripix/commands/extend.py`, the work in `kiripix/core/extend.py`),
tests in `tests/cli/test_extend.py` and a sample in `tests/cli/test_contract.py`.

- **Journal:** `<asset>/extend/journal.jsonl` (`add`, `undo`, `done` lines, ULID ids); the pieces (`pieces/<hash>.png`), the joined
  images (`joined/<hash>.png`) and the latest canvas (`canvas.png`, `canvas.json`) sit beside it. The live pieces are the `add`
  lines not dropped by an `undo` or closed by a `done`. The base of the next piece is the newest live piece's joined image, or the
  picked Source. `done` imports the joined image as a Variant (not a pick) and closes the pieces, so the next canvas starts from
  the picked Source again.
- **Canvas:** `--side east|south|west|north`, or a corner of two (`east,south`) for a piece that fills the notch of an L-shaped
  image: its canvas holds the two strips either side of the notch. `--keep N` (px, both axes) defaults to a third of the canvas
  along each axis; `--offset N` moves the canvas along the edge. `add` places the piece from `canvas.json`, so it needs a canvas
  of the current image (`extend.canvas_needed`, `extend.canvas_stale`, `extend.canvas_mismatch`, each with a `fix`).
- **`[extend] canvas`** is a new section of `kiripix.toml` (default 1376 x 768), so `schema_version` is 5, with a migration from 4.
- **A miss:** a registration that raises or leaves a residual over 0.5 px records nothing and gives `extend.registration_missed`
  (exit 2) with the `owner_action` this ticket names. A wide gain or costly seam is a warning on a joined piece, as for `op`.
- **A corner** joins in two seams, one per neighbour (0135's limit). `done` with transparent pixels left warns
  (`extend.holes_remain`); it doesn't refuse.
- **Decided on the way:** a piece registered onto the grid unscaled (scale within 0.05 % of 1, shift within 0.02 px of whole) is
  snapped there exactly, and the resampled piece's transparent margin is cut, or rounding noise costs a row and a column.
- The trial 0134 is the test with real pieces; the UI for the strip and seam is still another ticket.
