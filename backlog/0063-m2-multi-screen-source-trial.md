---
status: done
milestone: M2
agent: none
type: trial
parent: 0037-m2-layers-and-props.md
---

# M2: trial: can a multi-screen Source be made for the game's art?

Spec §16 (open decision 7), and the game's DEC-024 and ISS-016. The Owner needs the answer before M3, and only they can judge
the art. A main session helps with the Kiripix side and the numbers, with no subagent and no new code. If the trial needs a
tool that doesn't exist, joining the pieces for example, do it by hand and record that as a result.

A free-tier image of 1,376 px covers about one screen, at about 2.15 Source px per target px. A 1280 x 368 room needs a Source of
about 2,750 px across.

## What to do

1. **Extend:** take the harbour painting, `references/harbor-view.jpeg` in the game repo, and extend it to the right in Nano
   Banana, twice or until it's wide enough, generating each piece from the edge of the last. Join the pieces by hand on their
   overlap. Note the generations and the time it took.
2. **Higher resolution:** generate the same scene once with a higher-resolution model, if a modest cost allows. Note the cost,
   and whether it paints finer pixels or only bigger ones.
3. **Run each through Kiripix:** a new 1280 x 368 room, with `import`, `pick`, then `fit` and `palette`. Try `fit` in grid mode,
   then `downscale`. Make a few SAM 2 clicks on small objects.

## What to record, in this ticket

For each method:
- **Consistency:** do the horizon, perspective, light and scale hold across the width, against 52 px characters?
- **The join:** is it visible after `fit` and `palette`?
- **Pixel density:** do the painted pixels stay close to one size? Does grid mode still fit, or is `downscale` needed?
- **Click to segment:** how much coarser is it at this width, and which objects does it miss?
- **Time and cost,** per room.
- **Limits in the rest of Kiripix:** canvas zoom and scrolling, collision piece count, `reach` time.

## Acceptance criteria

- [x] At least the extending method tried on one real scene, and the results above recorded.
- [x] The Owner's call is written into spec §16, open decision 7: which method for continuous rooms, or Exits only.
- [x] If extending works: the spec's M4 entry for the preprocessing tool stays, with what the trial learned about it. If it
      doesn't, that entry is removed.
- [x] Any Kiripix limit that blocks the chosen method is filed as a ticket.

## Results (2026-11-06)

Measured by a main session, up to the Owner's run below.

**Generation.** Nano Banana, free tier, from a 1376 x 768 canvas: a strip of the original kept, the rest flat grey to fill.
- Harbour, east: failed, several tries. The Grille building is barely in frame at the right edge, so there's too little to
  continue.
- Harbour, south: worked in one generation: 1376 x 1150, about 1.5 screens tall.
- Subway (`subway-lower-bay.jpeg`), east: worked in one generation: 2185 x 768, R4's width (1024 target px) from one piece.
  The new middle fixture is lit but throws no light pool; fix it with an Override, or keep it as a dead light.
- Cost: $0 (free tier). The higher-resolution model wasn't tried.

**The join.** No Kiripix tool; a scratch script, in three steps, all needed:
1. Register. The model redraws the kept strip and draws the whole piece slightly larger: the subway piece 1.17 % wider and
   1.25 % taller, the harbour piece 0.15 %. Undone by an affine fit to edge patches across the overlap (residual 0.3 px).
   A plain shift left a 3-5 px step in the track bed.
2. Tone. The redrawn strip is darker in places (the yellow edge strip, the floor); a per-row gain from the overlap,
   smoothed, matches it.
3. Seam. The least-difference path through the overlap, blended over 6 px. The subway's lands behind a pillar.

The joined Sources are `references/subway-lower-bay-wide.png` and `references/harbor-view-south-tall.png` in the game repo.

**Scale across the join (subway).** Wall tile pitch 22.6 px in both; floor tile pitch 46.5 against 47.6; painted pixel 2.87
against 2.93 Source px; pillar spacing in the original's range. Within 2 % before the registration above removes most of it.

**Through Kiripix.** Rooms `room.trial_subway_wide` (1024 x 320, R4's size) and `room.trial_harbor_south` (640 x 528) in the
art Project, palette as `harbor_front` (bayer8, orphan 2).
- **Grid mode doesn't fit** either: no exact grid in an AI painting, so detection gives 1x and `fit.size_mismatch`. The
  painted pixel (about 2.9 Source px) isn't the Source-to-target ratio (2.13-2.15) anyway. `downscale` is needed, as for
  `harbor_front`.
- **The join is not visible after `fit` and `palette`** in either room. Pixel density looks even across it.
- **Kiripix limit found: `downscale` scales each axis on its own, silently.** The subway's 2185 x 768 into 1024 x 320 gave
  2.13 across and 2.40 down, an 11 % squash, with no finding. `harbor_front` has the same, at 3 % (2.15 against 2.09).
  Worked around by cropping each Source to the brief's aspect before import (subway rows 40-723; harbour the top 1135
  rows). Filed as [0081](0081-m3-downscale-keeps-one-scale.md).
- Station-name text is illegible at the target size in every bay, the original's included. That's the scale, not the join.
- **SAM 2 at this width (reasoning, not measured):** its encoder stretches the image to 1024 x 1024, so the subway's
  2185 x 683 is squeezed 2.1x across and stretched 1.5x down. Clicks should be coarser across than on a one-screen room.
  The harbour's 1376 x 1135 is near square, so about as before.

## The Owner's run (2026-11-06)

Measured from the art Project and the game repo. `room.trial_subway_wide` went through `export`; `room.trial_harbor_south`
stopped at `place`, with no Spawn, no `reach` and no export.

| | `trial_subway_wide` | `trial_harbor_south` | `harbor_front` (one screen, for comparison) |
|---|---|---|---|
| Size | 1024 x 320 | 640 x 528 | 640 x 368 |
| `solid` coverage | 12.0 % | 3.3 % | 45.5 % |
| `solid` islands (4 px or smaller) | 31 (13) | 13 (0) | 96 (58) |
| `pit` coverage | 10.7 % | 0 | 0 |
| Convex collision pieces | 396 `solid`, 134 `pit` | not exported | 1,533 `solid` |
| `reach` | 0.56 s | not run | 0.38 s |
| `export` | 0.47 s | not run | 10.4 s |
| Scene file | 80 KB | not exported | 227 KB |
| SAM 2 clicks; median, longest | 20; 0.05 s, 0.27 s | 20; 0.05 s, 0.41 s | not compared |

- **No limit from the width in `reach`, `fit`, `palette` or `export`.** None of them took long at 1024 px.
- **The piece count isn't settled.** The subway's Masks are test Masks: 87 % of the wall above the tiled band (rows 0-60) is
  reachable, because the pillars and upper wall aren't `solid`. So 530 pieces is a lower bound. Pieces follow the Mask's edges,
  not the room's width: 209 of the 396 `solid` pieces are 16 px² or smaller. `harbor_front` has fewer pixels and three times the
  pieces.
- **Unreachable island:** 871 spots in the subway at (103, 77), behind the "Lower Bay" sign, inside the tiled band. Also the far
  track bed (38,300 spots), correct for a far side of a pit.
- **The scene has no room size.** The exported `.tscn` holds the Plate, bodies, Navigation and Markers, but no size or camera
  limits. The game can read the size from the Plate's texture. A scrolling camera needs that on the game side.
- **Canvas:** panning exists but the Owner couldn't find it, and zoom loses the place. Filed as
  [0082](0082-m3-ui-canvas-navigation.md).

## The Owner's judgments (2026-11-06)

- **Decision:** expect about as many multi-screen rooms as single-screen ones. Extending from the edge is the method for now.
- **Consistency:** acceptable for now. These were single generations, with no retries or added instructions, so flaws like the
  subway's middle light can be fixed room by room.
- **SAM 2:** pretty accurate, and no worse than on a one-screen room. Drawing Masks with it was a bit slow. Queueing clicks for
  different segments worked.
- **Time:** about 10-15 minutes in total, including extending with the image model. That's the Owner's estimate, with prompts and
  Sources prepared with a session's help, so a room done alone may take longer.
- **Large rooms aren't being worked on yet,** so 0082 stays in M3.

**Left open:** no wide room has complete Masks, so the real piece count and `export` time at this width are unknown. The first
production wide room will show them. The harbour room never reached `reach` or `export`. `harbor_front`'s 1,533 pieces and 10.4 s
came from Mask tool problems since fixed, so it isn't a guide. The Owner expects far fewer pieces, even in wide rooms, with Claude's
help and the polygon tool.
