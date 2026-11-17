---
status: todo
milestone: M5
agent: character-pipeline
type: trial
parent: 0152-m5-character-layers.md
---

# M5: trial: render a hair style and an outfit as layers over a body

Spec §6.3 and §16 (open decision 9). Part of [0152](0152-m5-character-layers.md). Prototype code stays in the scratchpad or the
trial's own folder under `.kiripix/`, not in `kiripix/`.

## What to do

1. From mc02 (`c:\Homespace\[assets]\mc02\build_mc02.py`), make a body and two layers as separate objects on one rig: the hair,
   and the jacket with its hood. Add one silhouette-changing piece for question 1 of 0152, such as a long coat.
2. Render the body alone, then each layer with the body as a holdout, at `top34_8` in 8 directions, for `idle`, `walk` and
   `attack`: same cell and pivot.
3. Stack them in a fixed order and compare with a full render of the same character: count the pixels that differ per frame,
   and show where.
4. Try the outline both ways (per layer; once on the stack) and lay them out as sheets for the Owner.
5. Measure the render time per layer against the full body.

## Since the generator trial (2026-11-14)

The generator trial ([0164](../m4/0164-m4-claude-built-base-models-trial.md)) didn't answer 0152's three questions: it
merged every part into one mesh and rendered the whole character. But it gives this trial an easier start than mc02: the
art repo's `chargen/` already builds hair, tops, coats, hats and skirts as parts on mc03's skeletons, so step 1 can build
the body and each layer as separate objects with `chargen/generate.py` instead of from `build_mc02.py`. A long coat and a
hood-like hat are in its library already (question 1). What it showed about bases went to
[0165](../m4/0165-m4-characters-share-a-base.md), which no longer waits for this trial.

## A weapon as a layer: moved to 0238 (the Owner, 2026-11-16)

Steps 6–8 below and the weapon criterion moved to the held-things trial [0238](0238-m5-held-things-trial.md), so (a) or (c)
is settled in M5's first wave, ahead of layers. The game needs a phone in the hand at its M03 and weapons at its M05–M06, two
to four game milestones before layers. Skip steps 6–8 here, and reuse 0238's holdout render if it chose (c).

Also read 0152's "What the game needs from layers": accessories (a backpack whose order flips between south and north), the
six fixed Parts, and layers for generator-built Models.

### As first written (from 0170, 2026-11-15)

M4's trial [0170](../m4/0170-m4-weapon-in-a-battle-clip-trial.md) put a weapon in mc02's `attack` clip as option (a), a mesh
parented to the right-hand bone, and the Owner deferred the choice to this trial. Its results in `backlog/m4/0170-trial/` are the
baseline: 1 m stick, 8 directions at 52 px, the cell 78 to 92 for every clip (+39 percent atlas), no measurable render cost,
outlined for free, attachment materials numbered after the Model's.

6. Render the same stick as a layer over mc02's `attack` (option (c)), with the body as a holdout, and compare with 0170 on:
   the cell and atlas size (does idle stay at 78?), the render cost, the outline where the stick crosses the body's silhouette,
   the palette (in 0170 the stick took one of the body's 16 colours), and depth by direction.
7. **Put the stick in the hand.** In 0170 the stick floated beside the fist: the grip offset and rotation were guesses. Whichever
   way wins, find how the grip is set so the weapon sits in the hand in every frame (an offset and rotation per clip, a grip bone,
   or a socket empty in the Model), and show it on the sheet.
8. Lay out the attack with (a) and (c) side by side, at 4x and as a GIF, like 0170's.

## What to record, in this ticket

- The differing-pixel counts, the sheets' paths and the Owner's view of each.
- The answers to the three open questions of 0152, with the Owner's choice.
- A list of work tickets to file (render, palette, sheet, export, UI), each with its agent, and any change to what the game asked
  for (DEC-052).

## Acceptance criteria

- [ ] The sheets and numbers above, on mc02.
- [ ] The Owner's answers to 0152's questions are recorded here, and the work tickets are filed.
- [ ] The weapon compared as (a) and (c) against 0170, held in the hand, with the Owner's choice and its build ticket.
