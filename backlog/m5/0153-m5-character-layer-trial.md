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

## What to record, in this ticket

- The differing-pixel counts, the sheets' paths and the Owner's view of each.
- The answers to the three open questions of 0152, with the Owner's choice.
- A list of work tickets to file (render, palette, sheet, export, UI), each with its agent, and any change to what the game asked
  for (DEC-052).

## Acceptance criteria

- [ ] The sheets and numbers above, on mc02.
- [ ] The Owner's answers to 0152's questions are recorded here, and the work tickets are filed.
