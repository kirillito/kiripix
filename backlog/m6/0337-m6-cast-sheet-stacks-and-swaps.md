---
status: done
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

- [x] Golden seam: the swap Op on a small fixture with two Parts, pixel-exact; a pixel of another Part is untouched.
- [x] CLI seam: a stack of a test body and two Wearables matches the stack Op's output in the sheet, and a Wearable of
      another body is `cast.wearable_body`.
- [x] CLI seam: a colour file swaps one Part on one figure and leaves the next figure as built.
- [ ] Spec §10.5's `cast-sheet` line updated (done); the contract sample covers a stack (not yet: the sample is still `sprite.npc`; `tests/cli/test_cast_stack.py` covers stacks).

## Result

- **`swap_ramps`** (`kiripix/ops/swap.py`): the game's swap as a pure Op; several swaps apply together on the input colours, alpha is kept, a ramp of another length is a `ValueError`. No swap code existed from M5.
- **`cast-sheet`** (`kiripix/commands/probes.py`, `kiripix/core/cast.py`): a figure may be a stack `character.a+wearable.b+wearable.c` (M5's `stack_by_order`/`stack_by_depth`, not a copy). The body is the first, each Wearable's `order` comes from its built `sheet.json`, ties by ID. New options `--stack order|depth` and `--colours <file>` (TOML `[[figure]]` tables or JSON list; fewer entries than figures leave the rest as built). Parts and ramps are read from each Asset's built `palette.json`. Labels read `character.a+wearable.b ~skin`; cells have `swapped`.
- **Findings:** errors `cast.wearable_body` (names the Wearable, its body and the figure's), `cast.stack_body`, `cast.stack_wearable`, `cast.colours_length`, `cast.colours_invalid`, `cast.snapshot_depth`; warnings `cast.colour_off_palette`, `cast.part_missing`, `cast.no_depth`, `cast.wearable_cell`.
- **Tests:** `tests/golden/test_swap.py` (new golden `tests/golden/expected/swap_ramps.png`, 12 x 6, not worth eyeballing), `tests/cli/test_cast_stack.py` (hand-written sheets and palettes).
- Spec §10.5's `cast-sheet` line updated.

For the Owner:
- The contract sample (`tests/cli/test_contract.py`) still uses `sprite.npc`, now with `--stack depth`: a sample needs `findings == []`, and hand-written stack sheets are stale (`cast.sheet_stale`). The stack itself is covered in `test_cast_stack.py`, not by the schema sample.
- Snapshots keep no depth atlas, so a stack from `--snapshots` is by order; `--stack depth` with it is `cast.snapshot_depth`. Keeping the depth atlas in a snapshot is a small follow-up if wanted.
- Snapshots of a stack take their Parts' ramps from the live `palette.json`, as the snapshot holds no palette.
