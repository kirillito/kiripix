---
status: todo
milestone: M5
type: trial
parent: 0236-m5-the-games-next-needs.md
---

# M5: trial with no code: can the free image model paint a tile sheet that tiles?

Spec §14 ("The tileset recipe, estimated on 2026-11-08, not planned"). Part of [0236](0236-m5-the-games-next-needs.md), item 9.
The game's ISS-017 (`docs/DECISION_LOG.md`) and M10-01: painted rooms against a modular tile kit for the dungeon corridors
(C1, R5), on cost, look and grid readability. Done by the Owner and the main session: about 100k tokens, no code in
`kiripix/`.

## Why now

The recipe is 8–10 tickets (2–3.5M tokens), and it only makes sense if the art works. The game needs the answer before its
M09–M10.

## What to do

1. **A tile sheet:** with the Owner, prompt the free image model for a dungeon corridor tile sheet (floor, wall, wall top,
   inner and outer corners, two or three floor variants) in the ch01 dungeon rooms' style, on a 16 px grid (the Project's
   `tile`). Record the Owner's minutes and the prompts.
2. **Fit and palette** it with Kiripix as it is: import it as a Prop or a room, `fit` on the 16 px grid, then `palette` to the
   Project's palette.
3. **Tile it:** a scratch script (in `backlog/m5/0251-trial/`) slices the 16 px tiles and assembles a test corridor of about
   one screen, with turns, from a hand-written layout. Count the seams that show: tile edges that don't match their
   neighbour by more than a palette step.
4. **Compare** it with a painted ch01 dungeon room at 1x and 3x, with a 52 px character on both and the cell grid drawn over
   them (32 px battle cells). The Owner judges the look, how readable the grid is, and the cost against a painted room
   (`stats` on a ch01 room).

## What to record, in this ticket

- The sheet, the corridor and the comparison, with their paths.
- The seam count and the Owner's minutes.
- **The Owner's verdict for the game's ISS-017:** tiles for corridors, paint only, or a mix. If tiles win, re-estimate the
  recipe from spec §14 and file its spec ticket. If not, record it in spec §14 and close.

## Acceptance criteria

- [ ] The images and numbers above.
- [ ] The verdict recorded here and in spec §14, and the game told (its ISS-017).
