---
status: todo
milestone: M2
agent: core-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: what Layers need from core and Commands

Spec §5 (Overrides), §6.1 (layers, palette), §10.5, and ADR 0004.

## What to build

- A `StageSpec` hook that runs after core paints the Stage's Overrides and before its Checks, on the same output folder.
  `palette` needs it so that a palette Override reaches the Layers cut from the image
  ([0045](0045-m2-palette-with-layers.md)). A Stage without the hook behaves exactly as today. Its unpainted hash and
  stamp don't change meaning.
- `kiripix plate-import <id> <png>`: stores a Plate image under `decisions/imports/` by its hash and records the `layers`
  Stage's `plate` Decision, the same way `mask-import` works. A Kind with no such Stage refuses with a finding, as
  `mask_import.no_masks_stage` does. Add it to the UI's REST upload path if `mask-import` needs that (0032).

The `plate` Decision's schema and its use are [0044](0044-m2-plate-from-difference.md). Declare only what this Command needs.

## Notes

The `segment-preview` Probe needs no change for the layers screen: it finds the first Stage with a `segment` hook, and that
hook needs only `fit` and `source`, which are built before either Stage.

## Acceptance criteria

- [ ] On the `demo` Kind: a Stage with the hook sees its image with the Overrides painted, and its Checks see what the hook wrote.
- [ ] `plate-import` stores the image by hash, journals one Decision, and importing the same image twice stores one file.
- [ ] `plate-import` on a Kind without the Stage exits 1 with a finding that has a `fix`, and writes nothing.
- [ ] A sample in `tests/cli/test_contract.py`.
