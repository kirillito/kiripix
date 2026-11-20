---
status: done
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

- [x] The images and numbers above (Results, below).
- [x] The verdict recorded here and in spec §14, and the game told (its ISS-017).

## The Owner's verdict (2026-11-19)

**Paint only for chapter 1.** Chapter 1 likely runs to the game's milestone 20-30. The tile corridor "looks OK", but it
has too many visible seams, and its walls are a mess of door pieces, clipped lights and the like.

**Tiles stay a "maybe" for later.** With a good tile sheet, tiled rooms have value: they could make procedurally generated
dungeons. That isn't on the roadmap now. Chapters 2-10 may try a dungeon built this way. The recipe isn't re-estimated
and no spec ticket is filed. Spec §14 keeps the estimate, with this verdict and what a good sheet needs (below).

**What a later attempt needs, from this trial:**
- **A sheet painted for tiling:** flat, even light, with nothing baked in that runs across tiles. The floor seams here
  were all baked light.
- **Plain wall strips:** doors, lights and pipe bends as separate props (the prop recipe) or as rare variant tiles, not
  painted into every wall.
- **Every piece from one image.** Pieces from separate images don't match: wall widths and wall tops change on every
  try. Corners for the inside of a turn have to come from the same picture as the walls they join.
- The free image model as tried here won't lay out a kit of pieces. A paid model, a PixelLab tileset tool or
  outpainting from one room are untried.

## Results

Run by the main session with the Owner, 2026-11-19. All code and images are in [0251-trial/](0251-trial/) (its
[README](0251-trial/README.md) has the steps). Kiripix and the art Project were not changed. `fit` and `palette` ran in a
scratch copy of the art Project. The Owner's verdict is still to come.

### 1. The tile sheet: 9 minutes of the Owner's time, 12 tries, 3 prompts

| Prompt | Tries | Minutes | Kept | What came back |
|---|---|---|---|---|
| A tile sheet: floor, variants, wall face and top, inner and outer corners, on a strict grid | 3 | 2 | `grid.jpg` | A painted room with a 10 x 10 grid drawn over it. The floor slabs fill the cells, but the walls (75 px wide against 102 px cells) and an inner block don't follow the lines. |
| A 4 x 4 grid of named pieces, separated by magenta lines | 4 | 3 | `grid1-3.jpg` | Always 896 x 1200, so 4 columns came out as 5 rows: the cells are 221 px wide and 222-262 px tall. Rows 1-2 (floor, wall face) are usable in all three. Rows 3-5 (the corners) are whole little rooms about 2 x 2 cells, with the lines drawn across them. One try had almost all diagonal walls. |
| 3a: one small square room; 3b: a plus-shaped junction | 5 | 4 | `grid4-7.jpg` | Each image holds together, but each is a different dungeon. grid4 is a clean room with mitred corners. grid5 and grid6 are junctions with different wall widths and wall tops. grid7 is a room with four pillars. |

The prompts are in the table. The style reference was `ch01_dungeon_r01`'s Source. **What the model does:** it paints floors,
wall faces and whole rooms in the ch01 style well. It won't lay out a kit of pieces, whatever the prompt. Wall thickness,
corridor width and wall-top detail change on every try, so pieces from two images don't match.

### 2. Fit and palette

grid4 was cut as a 9-slice on its own wall lines (walls 2 tiles, the top wall 3 tiles as its face shows, floor 16 x 15).
grid5 was resampled whole, and grid2's four floor cells to one tile each. All are at 3 source px per game px (the ch01 rooms
are at 2.16, ISS-016's free-tier range is 2.2-2.9). Kiripix then ran `fit mode=downscale scale=3` and `palette` with the room
settings (strength 0, orphan_size 0) to the Project's palette. `palette.mapping_error` fired on grid5 only (0.0202, over
0.016): its dark blue void isn't in the palette.

### 3. The corridor and its seams

A screen of 40 x 22 tiles (640 x 352): a corridor 4 tiles (2 battle cells) wide runs right, turns down, turns right again.
An autotile rule picks each tile from its neighbours. Three kits:
- **A:** grid4 only. It has no convex corners (the inside of a turn), so those fall back to a wall piece.
- **B:** grid4, with grid5's convex corners.
- **C:** B, with grid2's floor tiles.

A seam is an edge between two tiles that weren't neighbours in their Source. It **shows** when at least 4 more of its 16
pixel pairs differ by over a palette step than the pairs just inside the tiles do. (A palette step is the median OKLab
distance from a palette colour to its nearest neighbour: 0.0207.)

| Kit | Edges between non-neighbours | Seams that show | Where |
|---|---|---|---|
| A | 88 | **59** | 49 floor-floor, 5 wall-wall, 5 at the convex corners |
| B | 97 | **64** | 49 floor-floor, 5 wall-wall, 10 at grid5's corners |
| C | 438 | **105** | 85 where grid2's floor meets grid4's wall foot, 5 wall-wall, 15 at grid5's corners |

- **The floor seams come from baked light.** grid4's floor is lighter near its top wall than near its bottom wall. Where
  the two halves meet in a 4-tile corridor, a lighter line runs along it (`out/corridor_A_seams_3x.png`, in red). A tile
  kit needs flat, even lighting. A painted room's lighting is part of its look.
- **The walls repeat as a 16-tile strip.** The door and the lights repeat every 256 px, and a strip cut short of its
  repeat shows (the 5 wall-wall seams).
- **grid5's corners don't match grid4's walls** (B, C): a different wall top and a thinner bottom wall. **grid2's floor
  doesn't match anything** (C): its 8 px slabs and lighter colour show at every wall foot.

### 4. The comparison

`out/compare_1x.png` and `compare_3x.png`: kits A and B beside the lower 400 x 352 of `ch01_dungeon_r01`, with
mc03_female_clothes01 (idle, facing south) on each, and the 32 px battle grid. One panel per kit and room is in
`out/compare_{A,B,C,room}_{1x,3x}.png`.
- **The grid reads better on the tiles.** The corridor's walls fall on cell lines by construction (4 tiles = 2 cells), so
  each cell is all floor or all wall. In the painted room the grid crosses walls and stairs mid-cell.
- **The look:** the tile corridor is lighter and greener than r01, which is darker with yellower light. It reads as the
  same world, not the same room.
- **Cost:** `stats` has no tracked minutes on the dungeon rooms (tracking came later). Decisions: r01 59, r02 46, r03 137.
  The recorded figures are 75 minutes for r03 by hand (M2 gate,
  [0058](../m2/0058-m2-gate.md)) and about 15 minutes for a room with Claude's first pass (M3 gate,
  [0117](../m3/0117-m3-gate.md)). The kit here took the Owner 9 minutes of prompting, without the terrain tagging a
  `TileSet` would need, and its corridors would cost a layout each, not a painting.

### Paths

- Sheets: `0251-trial/input/grid*.jpg`. Palette-mapped: `0251-trial/work/pal_{g4,g5,g2floor}.png`.
- Corridors: `0251-trial/out/corridor_{A,B,C}.png`, with seams marked at 3x: `corridor_{A,B,C}_seams_3x.png`.
- Comparison: `0251-trial/out/compare_1x.png`, `compare_3x.png`. Numbers: `0251-trial/out/results.json`.
