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
