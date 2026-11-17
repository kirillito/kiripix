---
status: todo
milestone: M5
agent: core-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: `palette-suggest` from a room, or a box of it

Spec §7 (palette suggestion). Found on the laneway ([0134](../m4/0134-m4-trial-room-extended-both-ways.md), "The palette's
warm light"): a sun patch banded, and the fix was `palette-suggest` on a crop cut by hand into
`.kiripix/trials/laneway_light_patch.png`, at a scale guessed from the default.

## The gap

`kiripix op palette-suggest <image>` takes an image file and a `--scale`. For a room, the right input is the room's own
Source at its own Grid transform, and often only the part that bands.

## What to build

- `palette-suggest --asset <room> [--box x,y,w,h]`: reads the room's Source and its `fit` Grid transform (so `--scale` is the
  room's, not the default), with the box in target pixels mapped through the transform. Without `--box`, the whole room.
- It writes the proposal as now (`proposal.json` names the Asset and the box it was made from, so `palette-add` can tell it's
  current).
- An image path still works as today.
- `palette.mapping_error` findings (or whichever finding reports banding) offer this Command, with the region's box, as their
  `fix`, where they have one.

## Acceptance criteria

- [ ] CLI seam: on a built fixture room, `--asset` with a box gives the same proposal as the old path on a crop of the Source
      at the room's scale.
- [ ] A room whose `fit` isn't built is refused, with `run <room> fit` as its fix.
- [ ] The Command's help and spec §7 say so.
