---
status: todo
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

- [ ] At least the extending method tried on one real scene, and the results above recorded.
- [ ] The Owner's call is written into spec §16, open decision 7: which method for continuous rooms, or Exits only.
- [ ] If extending works: the spec's M4 entry for the preprocessing tool stays, with what the trial learned about it. If it
      doesn't, that entry is removed.
- [ ] Any Kiripix limit that blocks the chosen method is filed as a ticket.

## Results so far (2026-11-06)

Measured by a main session; the Owner's judgments and the GPU work are still open, marked **Owner**.

**Generation.** Nano Banana, free tier, from a 1376 x 768 canvas: a strip of the original kept, the rest flat grey to fill.
- Harbour, east: failed, several tries. The Grille building is barely in frame at the right edge, so there's too little to
  continue.
- Harbour, south: worked in one generation: 1376 x 1150, about 1.5 screens tall.
- Subway (`subway-lower-bay.jpeg`), east: worked in one generation: 2185 x 768, R4's width (1024 target px) from one piece.
  The new middle fixture is lit but throws no light pool; fix it with an Override, or keep it as a dead light.
- **Owner:** generations and minutes per piece. Cost: $0 (free tier).

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

**Owner, still to do:**
- Consistency: horizon, perspective, light and scale against 52 px characters.
- SAM 2 clicks on small objects in both rooms, on the GPU machine: which objects it misses.
- Canvas zoom and scrolling at 1024 px.
- A `solid` Mask, a Spawn, then `reach`'s time and the export's collision piece count.
- Your decision, and the spec edits in the criteria above.
