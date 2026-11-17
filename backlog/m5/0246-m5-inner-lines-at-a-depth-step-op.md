---
status: todo
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: `inner_lines` also draws at a depth step inside one material

Spec §6.3 (finish), §7. Part of [0236](0236-m5-the-games-next-needs.md), item 13. The Op is
[0214](../m4/0214-m4-inner-lines-op.md); [0247](0247-m5-finish-inner-lines-at-a-depth-step.md) uses this in `finish`.

## The gap

`inner_lines` draws only where two materials meet. An arm over its own torso in a one-material top, or one leg over the
other, gets no line. The art repo's workaround (the game's 0088) makes every sleeve and the right trouser leg a material of
its own in `chargen`. That works, but every Model has to do it, and a part then spans more materials.

## What to build

In `kiripix/ops/character.py`, pure:

- `inner_lines(material, depth, skip, depth_step=None)`: with `depth_step` set, a border is also two 4-neighbours of the
  **same** material (not 0) whose depths differ by more than `depth_step`. The line is the farther pixel, as now, with the
  same tie rule. `skip` drops a material's depth borders too.
- The unit of `depth_step` is the depth pass's. The Stage converts from pixels (0247), so the Op takes a plain threshold.
- A depth step against the background is still the outline's, never a line.

## Acceptance criteria

- [ ] Golden seam: a fixture with one material folded over itself (a near strip across a far one, depth step 3) gets a line
      on the far side of the crossing at `depth_step` 2, none at 4, and none where depth changes smoothly (a slope of 1 per
      pixel). Enlarged and captioned for the Owner.
- [ ] Without `depth_step` the output is identical to today's (the existing goldens pass unchanged).
- [ ] `uv run lint-imports` and `uv run mypy` pass.
