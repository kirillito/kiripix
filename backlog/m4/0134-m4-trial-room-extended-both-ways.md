---
status: done
milestone: M4
agent: none
type: trial
parent: 0133-m4-rooms-for-grid-battles.md
---

# M4: trial: a room extended in both directions, taken to export

Spec §16, open decision 7. Trial [0063](../m2/0063-m2-multi-screen-source-trial.md) extended one direction per room: the subway east
(1024 x 320, exported) and the harbour south (640 x 528, stopped at `place`). Grid battles make rooms larger than one screen in
both directions (the game's DEC-048), so a corner piece has to join two neighbours at once. 0063 also left the real collision
piece count and `export` time of a large room unknown, because no large room had complete Masks.

A main session helps with the Kiripix side and the numbers, with no subagent and no new code. Use a ch01 room, not
`harbor_front`.

## What to do

1. **Extend** a ch01 painting east, then south, then fill the corner, to about 2 x 2 screens (about 1280 x 736 target px).
   Use 0063's 1376 x 768 canvas, and join with 0063's scratch script (register, tone, seam). The corner registers against two
   edges.
2. **Run it to `export`**, with complete `solid` and `pit` Masks. Let Claude make the first pass through the CLI, on a room with
   many objects, and then fix it in the UI. Add a few Layers, Spawns, Exits, and a box where a battle would be. Draw the box by
   hand: the `area` Marker doesn't exist yet.
3. **SAM 2 at this size:** the Source is about 2750 x 1580 px, squeezed about 2.7x across by the encoder. Click the same small
   objects on the whole image and on a crop of about one screen, cropped by hand. Compare pixels and boxes, as 0076 did.

## What to record, in this ticket

- **The corner join:** the residual after registering against two edges, and whether any seam shows after `fit` and `palette`.
- **SAM 2:** whole image against crop, per object, in pixels and boxes. If the crop is clearly better, file the ticket below.
- **Collision:** pieces per Mask, `export` time, scene size and `reach` time. A lighter collision export
  (one `ConcavePolygonShape2D` per Mask) gets a ticket only if the count is high, roughly more than 600 pieces per screen,
  or if the game's M01-12 measurement finds a cost.
- **The UI at this size:** canvas navigation, and whether the walk test follows the body.
- **The Owner's time,** for the extending and for the rest.

## Acceptance criteria

- [x] The results above are recorded here.
- [x] Each Kiripix limit found is filed as a ticket.
- [x] Spec §16, open decision 7, has the result for rooms extended in both directions.
- [x] The SAM 2 result is recorded, and if the crop is clearly better, the ticket below is filed in M4 for `ml-engineer`. If it
      isn't, the result is recorded and no ticket is filed.

## If clicks are worse: a SAM 2 crop on large rooms (the ticket to file)

The encoder stretches the whole Source to 1024 x 1024 ([sam2.py](../../kiripix/runners/sam2.py)). On a Source of about 2750 x 1580
px, one encoder pixel covers about 2.7 Source px across and 1.5 down, and the decoder's 256 x 256 Mask is just as coarse.
Encoding a window of about one screen gives back a one-screen room's resolution.

- **An optional `crop`** in target px on the click Decision and on `segment-preview` (`--crop x0,y0,x1,y1`), so the Owner in the
  UI (a dragged rectangle, a separate `ui-engineer` ticket) and an agent through the CLI choose where SAM 2 runs. With 0079's box,
  if it was built, the box plus a margin can be the crop.
- **Optionally, an automatic window** when no `crop` is given and the Source is larger than about 1,400 px on either side. The
  windows sit on a fixed grid (for example 1024 px every 512 px), so nearby clicks share one encoding, and the Runner caches a few
  embeddings, not only the last one. Include this only if the trial shows the Owner or Claude would otherwise crop on most clicks.
- **Pinning:** the crop is part of the call's parameters, so a replay is exact. Existing click Decisions keep their whole-image
  call and their pinned results.
- **`segment.cut_by_window`** (warning): the Mask touches an edge of the crop that isn't the image's edge. Its `fix` is the same
  click with a wider `crop`.
- **Acceptance:** this trial's comparison, repeated through the Runner; a probe and the same Decision give the same Mask; an old
  click Decision rebuilds without a Runner call; the cancel token still works during an encode.
- Budget: 200–300k tokens, plus about 100–150k tokens for the UI ticket.

## Results (in progress)

**The room (Owner, 2026-11-16):** not a ch01 dungeon room but the tutorial battle's laneway, `room.ch01_002_laneway` in the
art repo, from four pieces the Owner made in the image model's own UI: `references/ch01-002-laneway01..04.jpeg` in the game
repo (NW, NE, SW, SE). The NE piece came out a little blurred. The Owner made the canvases by hand
(`ch01-002-laneway01_extend_*`), keeping a quarter of the canvas, 344 px across and 192 px down, with a red fill.

### The join

| Piece | How | Residual | Scale (x, y) | Gain | Seam (length, mean difference) |
|---|---|---|---|---|---|
| NE, east | `extend add`, `--keep 344` | 0.239 px | 0.99922, 0.99961 | 0.998–1.031 | 977 px, 1.94 |
| SW, south | `extend add`, `--keep 192` | 0.110 px | 1.0, 1.00046 | 0.904–1.041 | 1733 px, 1.00 |
| SE, corner | scratch script, the same Ops | 0.227 px (155 patches, both edges) | 0.99897, 1.00036 | 1.010–1.062 | 989 px and 1537 px, 1.46 and 0.00 |

- `extend canvas` wrote the same strips as the Owner's hand-made canvases (mean difference 1.4 of 255, which is the JPEG).
- **The corner didn't join through `extend add`** ([0230](0230-m4-extend-corner-off-by-one.md); fixed, and the four pieces then
  joined through `extend` alone: corner residual 0.225 px, the same 2407 x 1343 image, 97 % identical, no hand crop). The NE piece registered
  767 rows tall, at y 1, so the notch's top edge is one row above the SW piece's top: the corner's south overlap came out
  769 rows against a 768-row piece. With the origin moved a row, the registered piece (1374 px, scale 0.999) ends 1 px short
  of the image's east edge, and the east overlap is 1375 px. `Overlap.placed` measures a corner piece's overlap to the
  base's far edge, so a corner joins only when the registered piece ends exactly on both outer edges. The scratch script
  ([0134-trial/corner_join.py](0134-trial/corner_join.py)) cropped the base to the piece's extent and ran the same Ops; the joined
  image had one transparent row (y 0 over the NE piece), cropped by hand: the Source is **2407 x 1343**.
- **Keep per axis** ([0231](0231-m4-extend-keep-per-axis.md)): `--keep N` is one number for both axes, so the corner canvas
  for a 344 x 192 strip can't be written; its `canvas.json` was edited by hand.
- **No `done` to take back.** Run by mistake after the failed corner, `extend done` imported the L-shaped image as a Variant
  (it warned `extend.holes_remain`) and closed the pieces; `undo` can't reopen them. Picking the L-shaped Variant made it
  the base again, so nothing was lost. Not filed: the warning was right, and the mistake was the session's.
- **Seams after `fit` and `palette`:** none visible, at the corner either, and the blurred NE piece doesn't stand out at
  target size. It doesn't need making again.

### `fit` and `palette`

- `fit` `mode=downscale` (as on the ch01 dungeon rooms), brief 1120 x 624: 1.4 s. The default `grid` mode left the image at
  full size (`fit.size_mismatch`). `palette` (`dither=none`, `orphan_size=0`): 12.8 s at this size.
- `palette.mapping_error` 0.0188 against the Project palette. The Owner's target is under 0.015.
  `op palette-suggest fit.png --scale 1` (each about 56 s):

  | `--min-distance` | Colours | Error after |
  |---|---|---|
  | 0.03 (default, `--add 16`) | 7 | 0.0161 |
  | 0.025 (`--add 24`) | 12 | 0.0131 |
  | 0.02 (`--add 24`) | 15 | 0.0126 |

  0.025 is proposed: `.kiripix/palette-proposals/fit-f7fb28ca/proposal.json` in the art repo, for the Owner's `palette-add`.

The Owner added the 12 colours; `palette` then rebuilt with no `mapping_error` (11 s).

### SAM 2: the whole image against a one-screen crop

The Source is 2407 x 1343 px, so the encoder squeezes it 2.35x across and 1.31x down. Each crop was 1375 x 757 Source px
(640 x 352 target), cut on the room's own grid (`2407/1120`) and fitted in a scratch room, deleted afterwards; the crop's
Mask was shifted back and compared. Script: [0134-trial/sam_compare.py](0134-trial/sam_compare.py). Each probe is a new
process, so each computed its embedding again: about 6 s per click, on CUDA.

| Object | Whole: px, box (x, y, w, h) | Crop: px, box | IoU | Whole with a box Decision |
|---|---|---|---|---|
| hydrant | 852, 911,392 28x44 | 848, same box | 0.97 | |
| bike rack | 1005, 896,497 29x64 | 915, same box | 0.85 | |
| hedge | 8203, 801,368 37x256 | 8436, 801,369 37x255 | 0.95 | |
| street sign | 643, 917,115 47x14 | 631, 918,115 46x14 | 0.98 | |
| storm drain | 511, 340,225 30x21 | 525, 340,225 30x22 | 0.96 | |
| shed | 7505, 7,343 73x121 | 7644, same box | 0.98 | |
| lamp | 1399, 1017,20 50x161 | 1692, 1018,14 64x168 | 0.76 | |
| van | 2966, 1053,64 48x68 (top half) | 5570, 1048,64 58x115 (whole) | 0.53 | 5633, 1051,63 55x116 |
| car | 1266, 375,56 40x36 (roof) | 7066, 359,33 73x110 (whole) | 0.18 | 7165, 359,33 80x110 |
| puddle | 2386, 376,208 77x46 (half; the pole's reflection splits it) | 4354, 376,209 146x47 (whole) | 0.54 | 4409, 376,208 146x48 |
| chairs | 3100, 551,419 116x108 (the patio) | 12391, 549,421 117x202 (worse) | 0.23 | 1782, 562,408 67x43 |
| tomato bed | 9617, the whole bed | 362, one plant | 0.04 | |

- **Small objects are as good on the whole image** (IoU 0.85 to 0.98, the same boxes).
- **Three larger objects came back in part on the whole image** (the van, the car, the puddle) and whole on the crop. But a
  `box` Decision on the whole image gives the crop's Mask (within 1–2 %), and it fixed the chairs, which leak on both.
- **Result: the crop isn't clearly better** once the existing `box` is used, so the SAM 2 crop ticket isn't filed. An agent's
  first pass should use a box for anything bigger than about 40 target px.

### The first pass through the CLI (Claude, 2026-11-16)

Recorded from a scratch script ([0134-trial/make_decisions.py](0134-trial/make_decisions.py)), one `decide --file` per Stage:

- **`masks`, 28 Decisions:** a `solid` border; polygons for the house fronts, the fences, the deck stairs, the garden bed and
  the post bases; SAM 2 for the van and car (box), the shed, hedge, hydrant and bike rack (click) and the chairs (box). The
  puddle is the `pit` (box), a hazard inside the battle area; the Owner may prefer it walkable.
- **`layers`, 5:** car and van (box), lamp, hydrant and shed (click); `min_piece=10` drops two specks at the lamp's head.
  The first run took 35 s (five SAM 2 calls and the LaMa fill). The fill behind the car is dark asphalt instead of gravel,
  and the van's and lamp's holes are filled with a ghost of them; the Layers cover them, so this shows only if a Look moves
  or hides one. Not filed.
- **`place`, 12 Markers:** the Spawn `player` at the laneway's west end; four Exits (west, the alley, Major St north and
  south) to placeholder rooms `room.ch01_00N_tbd`; the gate as an `interactable`; the area `battle.tutorial`
  (160,150 to 800,288, `cell` 16, `walkable`) on the laneway; and the y-sort lines `probe layer-stats` gives.
- `layers` waits in needs-review for the Owner's `accept`, so `masks` onward haven't run.

### The Owner's pass in the UI, and the rest

- The Owner accepted `layers` and added two Layers for the poles (`pole1` at the curb, `pole2` the street sign, split
  because they sort at different y), and judged the first pass of Masks very good. Claude then added the poles' y-sort lines
  (`probe layer-stats` gives them ready).
- **The battle area:** `y2` 288 snapped outward to a row of cells on the yard fence (32 cells `area.ambiguous_cells`); with
  `y2` 287 and 10 cells around the puddle and the utility pole settled by majority (a cell at least half solid or pit is
  filled, otherwise cleared: 10 `polygon` Decisions), the area has none.
- **Unreachable on purpose:** the two fenced back yards (`reach.unreachable_island`, 250 x 208 and 113 x 212) and four slivers
  beside the car, the chairs and the fence. Left as they are.
- **The palette's warm light:** the sun patch on the asphalt and the slabs (around 520–760, 140–280) bands, though its mean
  error is only 0.013: the warm greys step about 0.01–0.016 apart, and the asphalt's neutral greys map to browner ones.
  `palette-suggest` on a crop of the patch (`.kiripix/trials/laneway_light_patch.png`): 4 colours at `--min-distance` 0.025
  (0.0140 to 0.0139), 6 at 0.02 (0.0131), 7 at 0.015 (0.0121: `#918A7F` and `#77746E` for the asphalt, `#E9CCA1` and
  `#DBC3A5` for the glow, with `#526D56`, `#4C545F`, `#999654`). The 0.015 proposal is offered to the Owner.

### Collision and export

| Measure | Value |
|---|---|
| `solid` pieces (vertices) | 266 (1047) |
| `pit` pieces (vertices) | 20 (73) |
| Pieces per screen (640 x 360, the room is 3.03 screens) | about 94 |
| Scene | 50.5 KB `.tscn`: 286 `CollisionPolygon2D` in 2 `StaticBody2D`, one `NavigationRegion2D`, 8 `Sprite2D`, 6 `Marker2D` |
| `reach` | 1.4–1.7 s |
| `export` Stage | 0.3–0.5 s |
| `kiripix export` (writing into the game) | 3.4 s, 12 files, `room.json` 93 KB, Plate 494 KB |

Well under 600 pieces per screen, so the lighter collision export isn't filed. `export` warned `exit.no_room` for the four
placeholder Exits (`room.ch01_00N_tbd`) and `export.merge_driver_missing` for the game's clone.

### The Owner's time

- **Making the four pieces:** about 25 minutes, most of it in Paint making each canvas (the kept strip and a rectangle for the
  image model to paint). `kiripix extend canvas` already writes that canvas, so with
  [0230](0230-m4-extend-corner-off-by-one.md) and [0231](0231-m4-extend-keep-per-axis.md) most of the Paint time goes.
- **The canvas fill (the Owner, 2026-11-16):** the grey fill could match the asphalt, so the image model might not see what to
  paint. The fill is now the first of red (the Owner's `#ED1C24`), magenta, green, blue, cyan and yellow that is at least
  0.15 in OKLab from the kept strip's nearest colours (the 1st percentile, so a red leaf or the hydrant doesn't count), else
  the farthest; `extend canvas` reports it as `fill`. All three of the laneway's canvases get red. In
  `kiripix/core/extend.py` (`contrasting_fill`), tests in `tests/cli/test_extend.py` (`test_the_fill_*`).
- **The rest, in the UI:** `kiripix stats`, 19.2 minutes and 82 Decisions in all, after Claude's first pass through the CLI
  (12.9 minutes before the walk-test fixes below: `layers` 9.3, `masks` 2.2, `palette` 1.4, `looks` 0.1).
- **The Owner's idea for M6 (2026-11-16):** with an image API (Nano Banana), Kiripix could drive most of the extending: the
  prompt, the base image, a canvas per side, the calls that paint them, repeating, and the join, with the Owner approving
  intermediate results. Spec §14 already lists `gen` driving `extend` for M6; this trial is the evidence that the steps
  are mechanical and that the joins can be judged by measurement (residual, gain, seam).

### The UI at this size, and the walk test

- **The walk test** followed the Body and was fine. It found Mask gaps, which the Owner fixed in the UI: missing fences, and
  `solid` taken off part of the stairs at the bottom left (that part of the painting looks odd and may be made again in the
  game's own ticket for this scene). After the fixes: 291 `solid` pieces (1141 vertices) and 20 `pit`, about 96 per screen; a
  53 KB scene; `kiripix export` 3.7 s.
- **Canvas navigation:** no problem reported at 1120 x 624.
- **The back gate** from the yard to the laneway is closed, and `solid`, so there is no way through. In the game the player
  should open it. That is a Look taking collision away, which spec §16, open decision 8, leaves open; the bins case there
  was settled by making them Props the game moves. Left to the game's ticket for this scene.
- **The battle area** is fine as a test. For the tutorial the Owner wants it larger, for more tactics such as cover. That
  belongs to the game's ticket for this scene, not to Kiripix.

### Left for the game's ticket for this scene

The real rooms for the four Exits (now `room.ch01_00N_tbd`, `exit.no_room`); a larger battle area; the back gate; the stairs
at the bottom left.
