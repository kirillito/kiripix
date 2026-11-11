---
status: todo
milestone: M4
agent: character-pipeline
type: trial
parent: 0097-m3-characters.md
---

# M4: trial: transitions between clips

Spec §6.3 (clips, render). Found at the M3 gate ([0117](../m3/0117-m3-gate.md)), 2026-11-11: an idle character that attacks
snaps from the idle pose into the attack's first frame, with nothing between.

Mixamo exports each animation on its own and doesn't blend between them, so the transition has to be made after. Three
places it could be made:

1. **A transition clip, rendered by Kiripix:** a `transition` Decision on `clips` names a `from` clip and frame, a `to` clip
   and frame, and a length in game frames. Blender blends the two poses over that length (per-bone interpolation, as the NLA
   does), and `render` renders it as its own clip, such as `idle_to_attack`, exported like any other. Its frames are few
   (3 to 5 at 12 fps), so it costs little.
2. **In the game, with no new frames:** the game plays the attack from a later frame, or holds a "ready" frame first. Cheap,
   but it can't make a pose that isn't in either clip.
3. **In Blender before Kiripix:** the Owner makes the blended action in Blender and imports it as a clip source. That works
   today, but it's manual for every pair.

## What to do

1. On mc02, make `idle_to_attack` and `attack_to_idle` with option 1, as a prototype in the trial's own folder (a Blender
   script over the rigged file, not in `kiripix/`). Try 3 and 5 frames.
2. Lay out before/after sheets per direction, and a GIF of idle → attack → idle with and without the transitions.
3. Record whether the Owner wants option 1 built, and how the game picks the transition (the game's animation state machine
   is the game's; Kiripix only names the clips).

## Acceptance criteria

- [ ] The sheets and GIFs for 3 and 5 frames, their paths listed here.
- [ ] The Owner's choice recorded here, and a ticket for the build if option 1 is chosen.
