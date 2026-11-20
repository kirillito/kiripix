---
status: todo
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
---

# M6: the cast sheet stacks Wearables on a body and swaps its colours

Spec §6.3 (Wearables, part ramps) and §10.5 (`cast-sheet`). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md);
needed by [0336](0336-m6-npc-variants-from-a-base.md) whichever way its Q1 is answered.

## The gap

`cast-sheet` draws characters and sprites side by side from their built sheets. It can't draw a body with Wearables stacked
on it, or with its colours swapped, so nobody can see an NPC made from parts before the game draws it. The UI's stack preview
on a body's screen (0295) shows one stack at a time, with the body's own colours.

## What to build

- **A figure** in `cast-sheet`'s list may be a stack: `character.body_f+wearable.hair_bob+wearable.coat_long`. The Wearables
  are drawn over the body by their `order` (default), or by depth with `--stack depth`, using the stacking from M5's
  [0294](../m5/0294-m5-wearable-stack-check.md) (the same Op, not a copy). A Wearable whose body isn't the figure's body is
  refused (`cast.wearable_body`), naming both.
- **Colours:** `--colours <file>`, a TOML or JSON with one entry per figure in order, each `{part = [rgb, ...]}`, dark to
  light, as long as the Part's row. The swap is the game's rule: a pixel whose colour is in the Part's ramp in `ramps.png`
  takes the colour at the same place; every other pixel is untouched. It's a pure Op in `kiripix/ops/` (or the one that
  exists, if 0294's code has it), applied to the body and to each Wearable's own Parts. A colour off the Project palette is a
  warning (`cast.colour_off_palette`); a Part the figure lacks is a warning.
- The labels name the stack and the colour entry. Snapshots (`--snapshots`) work with stacks as with plain figures.
- Still a Probe: records nothing, writes only to `.kiripix/previews/`.

## Acceptance criteria

- [ ] Golden seam: the swap Op on a small fixture with two Parts, pixel-exact; a pixel of another Part is untouched.
- [ ] CLI seam: a stack of a test body and two Wearables matches the stack Op's output in the sheet, and a Wearable of
      another body is `cast.wearable_body`.
- [ ] CLI seam: a colour file swaps one Part on one figure and leaves the next figure as built.
- [ ] Spec §10.5's `cast-sheet` line updated; the contract sample covers a stack.
