---
status: done
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

- [x] CLI seam: a room whose area has three ambiguous cells (30 %, 52 % and 70 % `solid`) gets two fills and one clear, and
      `place` then raises no `area.ambiguous_cells`.
- [x] `--dry-run` changes nothing. `undo` on `masks` undoes it.
- [x] Contract sample. Spec §6.1 mentions the Command.

## Result

- `kiripix area-settle <room> <area> [--rule majority] [--dry-run]` (`kiripix/commands/area.py`). For each ambiguous cell it
  records `polygon` Decisions on `masks` in one atomic append: a cell with `solid` and `pit` together at half or more is
  filled on the Mask covering it most; any other is erased on each Mask that touches it (so a cell on both takes two Decisions).
  `undo` on `masks` steps back one Decision at a time (the journal has no batch entry).
- It needs `masks` built and `done` (`area.masks_not_built`, fix `kiripix run`), an existing area (`area.unknown`) with a `cell`
  (`area.no_cell`). The result lists each cell: position, Mask, coverage, fill or clear.
- `area.ambiguous_cells` now has `fix: kiripix area-settle <room> <area>` and no `owner_action`.
- Code: `room.py` gains the public `current_area` and `ambiguous_cells`. Tests: `tests/cli/test_area_settle.py`, a contract
  sample, and `test_area.py`'s finding test. Spec §6.1 (`place`) names the Command.
- Review fixes: the spec and the Command say "one `polygon` Decision per cell and Mask" (a cleared cell touched by both `solid`
  and `pit` takes two); `ambiguous_cells` in `room.py` is the one public function (no forwarder). The test uses 5 px cells at
  28 %, 52 % and 68 % (7, 13 and 17 of 25 pixels), so none sits on the half tie, and the dry-run test checks the masks journal
  file is unchanged.
