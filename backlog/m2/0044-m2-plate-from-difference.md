---
status: done
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

- [x] A fixture full image and plate image give the expected Layers, with no Runner call logged.
- [x] Noise outside an object leaves the Plate equal to the fit image there, and `layers.recompose_mismatch` passes.
- [x] A plate image of the wrong size is `needs-input`, and `next` says why.
- [x] Undoing the `plate` Decision returns to the state before it, by `run`.

## Notes

- `difference` (OKLab, default 0.05, 0-1) is a new param of `layers`. The Layers Stage's input hash changes with it.
- Click semantics on this path: a positive click takes the connected region of the target-mapped difference under it
  (then `grow`, only where partial); a negative click right after it drops the region it is on. A click on no region is
  `needs-input`, naming the click (and `difference`). Unclicked regions stay in the Plate.
- With a `plate` Decision and no clicks, the Plate is the fit image. The latest `plate` Decision wins.
- With no Runner call, the Stage lands in `done`, not `needs-review`: review waits only on a Runner's result.
- Tests: tests/cli/test_layers_difference.py.
- After review (2026-11-05): a click on no region of the difference is `needs-input`, and `next` names the click, not a
  failed run. `needs_input` works the difference out for that, only when a `plate` Decision exists.
  `layers.json` is read through one reader, which refuses an old `schema_version`.
