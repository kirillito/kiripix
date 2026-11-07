---
status: todo
milestone: M3
agent: core-engineer
type: ticket
---

# M3: a Decision that removes a Layer

Spec §6.3 (layers). Found by the Owner at the [M2 gate](m2/0058-m2-gate.md): "there's no way to delete layers now". The `layers` Stage's
Decisions are `plate`, `click` and `trim`. A negative click takes an object out of a Layer, but nothing removes the Layer itself, so
a Layer made by mistake, or no longer wanted, stays until each of its Decisions is undone in order.

## What to build

- A `remove` Decision on `layers` with a Layer ID: the Layer's pixels go back to the Plate, as if it had never been lifted, and the
  Layer's earlier clicks and trims stop counting. A later positive click on the same ID starts a new Layer.
- Its y-sort line and "always above" flag in `place` stop counting with it, and `place`'s Checks don't ask for them.
- Undo and redo work on it like any Decision.
- An exported Layer's ID is frozen (spec §9). Removing it is refused the same way a rename is, and the finding says why.

The UI's part is [0092](0092-m3-ui-layer-screen-legible.md).

## Acceptance criteria

- [ ] At the CLI seam: lift two Layers, remove one; the Plate is as if only the other was lifted, and `place` doesn't ask for its line.
- [ ] Undo brings the removed Layer back.
- [ ] Removing an exported Layer is refused, with a finding that names the freeze.
- [ ] A sample in `tests/cli/test_contract.py` if the Command's input changes.
