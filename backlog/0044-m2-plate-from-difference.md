---
status: todo
milestone: M2
agent: imaging-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0038-m2-core-for-layers.md, 0043-m2-layers-stage.md]
---

# M2: Layers from a difference

Spec §6.1 (layers, path a) and §7. Story 6 of [0037](0037-m2-layers-and-props.md). Follows D5 in [0037](0037-m2-layers-and-props.md).

## What to build

- The `plate` Decision that `plate-import` records, naming a stored image by hash. The image must have the Source's size;
  otherwise `needs-input`, with an `owner_action`.
- The difference is taken on the Source, then mapped to the target through the Grid transform (ADR 0004). A `difference`
  parameter sets its OKLab threshold.
- Layers per D5. No Runner call on this path, so `needs-input` never says "Runner not run yet".
- Plate pixels: the plate image, mapped by the Grid transform, inside a Layer's hole; the fit image's everywhere else. So
  generation noise outside the objects can't break recomposing.
- `grow` applies here too: partial means a target pixel whose Source cell is partly in the difference.

## Acceptance criteria

- [ ] A fixture full image and plate image give the expected Layers, with no Runner call logged.
- [ ] Noise outside an object leaves the Plate equal to the fit image there, and `layers.recompose_mismatch` passes.
- [ ] A plate image of the wrong size is `needs-input`, and `next` says why.
- [ ] Undoing the `plate` Decision returns to the state before it, by `run`.
