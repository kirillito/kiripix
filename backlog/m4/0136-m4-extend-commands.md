---
status: todo
milestone: M4
agent: core-engineer
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
depends_on: [0135-m4-join-ops.md]
---

# M4: `extend`: the canvas for the next piece, and the join into a Variant

Spec §14 (M4) and §16 (open decision 7). The budget is $0, so the Owner makes pieces in the image model's own UI, not through a
Provider. This tool doesn't wait for Providers. From M5, `gen` may drive it.

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

Ask the Owner before building if the pieces fit better as Decisions of the `source` Stage than in a journal of their own.

## Acceptance criteria

- [ ] CLI seam: a canvas, a piece to the east, a piece to the south and the corner give one Variant of the expected size. `undo`
      drops the last piece.
- [ ] A piece that doesn't register gives the finding, and no Variant.
- [ ] A contract sample for each new Command.

Budget: 250–400k tokens. A UI for choosing the strip and seeing the seam is another ticket, if the Owner wants one after using this.
