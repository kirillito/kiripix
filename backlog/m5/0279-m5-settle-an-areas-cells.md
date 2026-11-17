---
status: todo
milestone: M5
agent: core-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: settle a battle area's ambiguous cells by majority, in one Command

Spec §6.1 (`place`: areas with a `cell`). Found on the laneway twice: trial [0134](../m4/0134-m4-trial-room-extended-both-ways.md)
settled 10 ambiguous cells with 10 hand-made `polygon` Decisions, and the M4 gate ([0142](../m4/0142-m4-gate.md)) settled four
more the same way.

## The gap

`place` lists the cells of an area that a Mask leaves between a quarter and three quarters blocked (`area.ambiguous_cells`,
with points since 0198). The fix is always the same rule: a cell at least half `solid` or `pit` is filled, and otherwise
cleared. But each cell takes a `polygon` Decision on `masks`, written by hand.

## What to build

- **`kiripix area-settle <room> <area> [--rule majority] [--dry-run]`:** for each ambiguous cell of that area, it records one
  `polygon` Decision on `masks`: filling the cell's square on the Mask that half-covers it, or erasing it. It's a writing
  Command, journaled like any Decision, so `undo` steps back through it (one entry per cell, or one batch entry if the journal
  has them).
- `--dry-run` lists what it would do: per cell, the Mask, its coverage and fill or clear.
- The `area.ambiguous_cells` finding gets this Command as its `fix`.
- An agent may run it: the rule is the Owner's standing choice (0134), and the result shows on the walk test like any Mask
  edit. Say so in its `description`.

## Acceptance criteria

- [ ] CLI seam: a room whose area has three ambiguous cells (30 %, 52 % and 70 % `solid`) gets two fills and one clear, and
      `place` then raises no `area.ambiguous_cells`.
- [ ] `--dry-run` changes nothing. `undo` on `masks` undoes it.
- [ ] Contract sample. Spec §6.1 mentions the Command.
