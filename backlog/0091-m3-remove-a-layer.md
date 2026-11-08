---
status: done
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

- [x] At the CLI seam: lift two Layers, remove one; the Plate is as if only the other was lifted, and `place` doesn't ask for its line.
- [x] Undo brings the removed Layer back.
- [x] Removing an exported Layer is refused, with a finding that names the freeze.
- [x] A sample in `tests/cli/test_contract.py` if the Command's input changes. (No Command input changed: `decide` takes the new Decision.)

## Done (core-engineer)

Tests: `tests/cli/test_layer_remove.py`. The Decision: `kiripix decide <room> layers --decision '{"decision":"remove","data":{"layer":"crate"}}'`.

- A `remove` drops the Layer's earlier clicks and trims from the replay (`recipes/layers.py` `_relevant`), so a removed Layer
  makes no segmentation or fill call, and a later positive click on its ID starts afresh. Pins stay on disk, so undo is free.
  The Runner-calls cache (ticket 0090) is keyed on the journal's current Decisions, so a `remove` changes the key.
- `layers.json` gains `removed` (Layers removed and not lifted again; no schema bump, an older file reads as none).
  `place` reads it and ignores a y-sort line or flag naming such a Layer, so `layer.no_ysort`, `ysort.unknown_layer`,
  `ysort.sloped` and `ysort.extra_line` don't fire for it. A line for a Layer that never existed still errors.
- A `remove` of an exported Layer is refused by `decide` itself (exit 2, `export.id_frozen`, owner_action only), before
  anything is recorded. A `remove` of a Layer nothing lifted is `needs-input`.
- Known gap: `show`'s `sort` before a build still lists a removed Layer's line or flag (it has no built `layers.json`).
