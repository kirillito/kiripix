---
status: todo
milestone: M4
agent: none
type: trial
parent: 0119-m4-room-looks.md
---

# M4: trial: what does an image model's edit of a room really change?

Spec §6.1 (Looks). A main session helps with the numbers, with no subagent and no new code. Its results set `register`'s
limits, `look.drift`'s tolerance and whether `regrade` should default to `none`.

## What to do

Use a ch01 dungeon room, not `harbor_front`. The Owner makes three edits of its Source with the image model they use, each
with "Edit this image. Keep everything exactly the same except: …":
1. a door shut (or open);
2. a lamp or torch unlit;
3. an object removed or broken.

For each edit, measured with numpy in a scratch script, outside the part meant to change:
- **Size:** what came back, against the Source's size.
- **Registration:** the scale and shift that best map it onto the Source after the resize, in Source px and in target px.
- **Drift:** after resize, registration, `fit` and `palette` (by hand, or with `kiripix op`), how many target pixels change
  outside the intended region, and where. How much of it is compression noise, and how much is redraw?
- **Light:** does the whole room's light shift, and would a regrade fitted outside the region fix it or undo the Look?
- **Region:** does a difference with a tolerance pick out the change cleanly (a lamp's glass, a door leaf)?
- **Noise:** at what crop size the edit's noise starts to show after `palette`.

## Acceptance criteria

- [ ] Three edits measured, the numbers recorded in this ticket.
- [ ] A recommendation for `register`'s limits, the drift tolerance and `regrade`'s default, written into 0122.
