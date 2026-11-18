---
status: done
milestone: M5
agent: imaging-engineer
type: trial
parent: 0236-m5-the-games-next-needs.md
---

# M5: trial: can Kiripix suggest a room's foreground Layers?

Spec §6.1 (`layers`), §1 (goal 2). Prototype code stays in `backlog/m5/0286-trial/`, not in `kiripix/`. Runs without the
Owner until the last step.

## Why

On the laneway, `layers` was 9.2 of the Owner's 19.2 minutes in the UI. After Claude's first pass, the Owner added two Layers
for the poles, which the first pass couldn't know to lift. A foreground object is one an actor can walk behind: tall, standing
on walkable ground, with `solid` at its foot and not over its top. Masks and the painting may be enough to find most of them.

## What to do

1. On the built ch01 rooms in the art Project, read-only (the laneway, the dungeon rooms; not `harbor_front`), take the
   Owner's own foreground Layers as the answer key.
2. Prototype a suggester from what Kiripix already has:
   - from `solid`: the components whose painted object extends above them, using a colour region grown up from the foot (the
     flood Op) or SAM 2 with a box over the component;
   - from the painting: tall thin objects (poles, lamps) with SAM 2 automatic masks.
3. Score it against the key: how many of the Owner's Layers it finds (IoU over 0.7), and how many false ones it suggests per
   room.
4. If it finds most of them with few false ones, write up what a Probe (`probe layer-suggest`) would return: boxes and the
   `box` Decisions to record, which the Owner accepts or ignores in the UI.

## What to record, in this ticket

- The score per room and method, with overlays (suggested against the Owner's) at 1x, and their paths.
- The time per room and VRAM.
- A recommendation: a Probe ticket (with its agent), or "not worth it", with why. The Owner's view of the overlays is the
  only Owner step.

## Acceptance criteria

- [x] The scores and overlays above, on at least three rooms.
- [x] The recommendation and the Owner's choice recorded. If yes, the Probe ticket filed.

## Results

Run 2026-11-18 by `imaging-engineer`, with no Owner step yet. Code: [0286-trial/](0286-trial/) (`suggest.py` the prototype, `run.py` the
scoring and overlays, `common.py`, `look.py` and `dbg.py` helpers). It imports `kiripix.ops.layers.connected_regions`,
`kiripix.ops.masks.flood_region` and the `Sam2` Runner (`sam2.1-small`, Apache-2.0, weights already in the art Project; nothing
downloaded). Kiripix and the art Project were not changed. Run it with
`uv run --project C:/Workspace/kiripix python run.py [room ...]` (`RISE0=1` for the second table); output goes to
`0286-trial/out/`.

**The key:** each room's `out/export/layer.*.png` alpha, the Owner's Layers: laneway 7, `ch01_dungeon_r01` 4, `r02` 5, `r03` 18
(34 in all). The input is the room's `fit.png` (target size, before `palette`) with `solid` and `pit` from `work/masks/`. Hit = IoU
over 0.7 with one Owner Layer. False = a suggestion with no Owner Layer over 0.7 (it may be a good object the Owner chose not
to lift, or a part of a Layer the Owner made from several objects; the key can't tell).

### What the prototype does

- **flood:** each `solid` component (8-connected, 20 px or more, not touching the room's edge, box under 10 % of the room) seeds
  `flood_region` (tolerance 0.04 OKLab) at its top row, limited to a window up to 4 foot heights above. The Layer is the region
  plus the foot.
- **click:** one SAM 2 positive click on the component pixel nearest its centroid; the piece touching the foot, plus the foot.
- **box:** a SAM 2 box over the component, 2 foot heights + 16 px higher.
- **auto:** a SAM 2 point grid (every 20 px, outside `solid`), kept if tall and thin (height at least 36 and 3x the width, width at
  most 24), with `solid` just under its lowest row and under half in `solid`. Duplicates over 0.7 IoU dropped.
- **stand** (added, see the first finding): a SAM 2 point grid (every 16 px, anywhere), kept if compact, 150 px or more, not
  touching the edge, at least 40 % in `solid`, with walkable floor just below the lowest pixel in at least 40 % of its columns.
- For flood, click and box, a first run kept only a suggestion that rises 6 px or more above the foot ("the painted object
  extends above `solid`"); a second run (`_r0`) drops that test.

### Findings that shaped the result

1. **In the dungeon rooms `solid` is one blob.** On r01 and r02 every object touches the walls, so the whole `solid` Mask is one
   component joined to the room's edge, and the component methods return nothing. On r03 only the 9 floor pylons and a few
   benches stand free. A suggester that starts from the components of `solid` works only where the objects stand clear of the walls
   (the laneway).
2. **The "painted object extends above `solid`" test is wrong for what the Owner lifts.** The Owner lifted the car, van, shed and
   hydrant, whose `solid` already covers the whole object. With the test on, click finds 2 of 7 on the laneway; with it off, 5.

### Scores (hits of the key; false suggestions)

| Method | laneway (7) | r01 (4) | r02 (5) | r03 (18) | all (34) |
|---|---|---|---|---|---|
| flood, rise 6 | 0 hits, 4 false | no components | no components | no components | 0, 4 |
| flood, rise 0 | 2, 8 | none | none | 2, 7 | 4, 15 |
| click, rise 6 | 2, 3 (lamp, pole1) | none | none | none | 2, 3 |
| click, rise 0 | **5, 5** (car, hydrant, lamp, pole1, van) | none | none | 2, 7 (planter_se, planter_sw) | 7, 12 |
| box, rise 6 | 0, 6 | none | none | none | 0, 6 |
| box, rise 0 | 2, 8 (car, hydrant) | none | none | 2, 7 | 4, 15 |
| auto (tall thin) | 0, 4 | 0 found | 0 found | 0 found | 0, 4 |
| stand | 4, 25 (car, hydrant, shed, van) | 0, 17 | 3, 16 (bench, extinguisher, machine) | 8, 32 | 15, 90 |
| rise 6 methods + stand | 6, 40 (all but pole2) | 0, 17 | 3, 16 | 8, 32 | 17, 105 |

- Per room, the false suggestions of the best-recall combination run 16 to 40 (about 26 on average), against 4 to 18 Layers the
  Owner made. The suggester is wrong more often than right: 17 hits of 34 against 105 false.
- **Never found:** `pole2` (the street sign, about 7 px wide, over its box), all of r01 (`layer1` is a 26,630 px slab beside the
  left pit, which the Owner cut as one Layer; a candidate on r01 reached IoU 0.3 to 0.7, `near`), and the Layers made of several
  objects: r03's `pylons` (9 objects in one Layer; 8,228 px), `railing_*`, `arms`, and r02's `lockers` (6 lockers in one Layer; the
  suggester finds the lockers one by one, `near`). Grouping is the Owner's choice, and no mask can know it.
- **Tall thin from SAM 2 automatic masks found nothing:** 4 false on the laneway (hedge and fence posts), none elsewhere. The
  two poles that matter (the lamp, `pole1`) were found by a click on their foot component, not by the grid; `pole2` and the
  tall `pole1`-style objects are the narrowest, where SAM 2's 256 x 256 mask (about 4.4 Source px per cell on the laneway) is coarse.
- **Where the false ones come from:** `solid` components that aren't foreground (fences, the bike rack, chairs, the stairs, a
  gate: tall, standing on walkable ground, and the Owner left them in the Plate), and, with `stand`, wall furniture and
  the back wall's mass.
- **Key pixel recall** (the share of the Owner's Layer pixels covered by the suggestions): 96 % on the laneway, 40 % r01, 94 % r02,
  74 % r03 for rise 6 + stand. High, but it's the many suggestions covering the room, not precision.

### Overlays at 1x (target px), the Owner's Layers in red, a hit green, a false suggestion yellow

All in `backlog/m5/0286-trial/out/`, named `overlay_<room>_<method>.png`, rooms `ch01_002_laneway`, `ch01_dungeon_r01`,
`ch01_dungeon_r02`, `ch01_dungeon_r03`, methods `flood`, `click`, `box`, `auto`, `stand`, `combined` (rise 6 methods plus stand),
and `flood_r0`, `click_r0`, `box_r0`. Start with `overlay_ch01_002_laneway_click_r0.png`, `overlay_ch01_002_laneway_stand.png`,
`overlay_ch01_dungeon_r03_stand.png` and `overlay_ch01_dungeon_r02_stand.png`. `look_<room>.png` shows the key in red over
`solid` in blue. Each suggestion's box and reason is in `suggestions_<room>_<method>.json`; the scores are in `summary.json` and
`summary_r0.json`.

### Time and VRAM (RTX 2070 Super, CUDA, one process, ONNX Runtime)

| Per room | laneway (1120 x 624) | r01 (400 x 560) | r02 (560 x 416) | r03 (640 x 368) |
|---|---|---|---|---|
| flood (pure-Python components) | 3.7 s | 1.1 s | 0.9 s | 1.7 s |
| embed + click + box | 3.9 s | 1.4 s | 1.4 s | 2.1 s |
| auto (point grid, about 1,700 decodes) | 31 s | 6.7 s | 6.4 s | 7.7 s |
| stand (point grid every 16 px) | about 25 s | 20.7 s | 24.3 s | about 25 s |

- **VRAM:** the process added 2.4 GB at its peak (1.4 to 3.8 GiB used on the GPU), and 4.7 GB in the first, one-room run (the
  ONNX Runtime arena grows by request, sampled with `nvidia-smi` every 0.1 s; another process was also on the GPU, so the
  figures have some noise). That isn't "modest" beside a depth model (0252). The encoder's input is fixed at 1024 x 1024, so
  the arena, not the image, sets it; the Runner could cap it (`gpu_mem_limit`), which wasn't tried.

### Reading it

- Where objects stand clear of the walls (the laneway), a click on each `solid` component finds 5 of the Owner's 7 Layers, with 5
  other objects the Owner didn't lift (fences, the bike rack, the stairs). That is about the quality of the first pass Claude
  already makes with `layer-stats` and the existing `click` Decision, and the missing 2 are the sign pole `pole2` and the shed, whose foot
  is part of the fence line's component, which joins the room's edge (the `stand` method found the shed).
- Where the objects stand against the walls (the dungeon rooms, which will be most of the game's rooms), no `solid`-based
  method works, and the whole-image point grid gives 1 false suggestion for every hit or worse.
- The key has the Owner's grouping, which no method has. Several of the "false" ones are good objects.

## Recommendation

**Not worth a Probe** as the ticket frames it. It finds under half of the Owner's Layers (17 of 34 with 105 false ones across the
four rooms; 7 of 34 with 12 false ones for click on components) and is wrong most often on the rooms with the most Layers. The Owner
would spend the time on dismissing suggestions, which `layers` already makes cheap, not on finding objects. The 9.2 minutes on the
laneway were mostly the Owner's choices (which objects, which poles to split by y-sort), which the key says no mask answers.

Two small things came out of it, neither filed:

- **A non-ML list** (a `solid` component with a foot box, its height, and whether it stands free) is what the click on a component
  does without SAM 2. Claude's first pass could take it from `probe layer-stats` or `solid` alone. It would need a
  `layer-suggest` Probe of about 100 lines for `imaging-engineer` and no Runner; at 5 of 7 on the one room it works on, the saving is
  a few minutes per laneway-like room. File it only if the Owner wants it for rooms with free-standing objects.
- **The `rise` test** ("the painted object extends above `solid`") shouldn't be a rule: the Owner lifts objects whose `solid`
  already covers them.

The Owner's choice and the Owner's view of the overlays are still to come; the status stays `todo`.

## The Owner's choice (2026-11-18)

**Not worth it.** No Probe ticket, and not the small non-ML list either. The Owner's Layers stay the Owner's step in the UI.
