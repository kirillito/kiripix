---
status: done
milestone: M2
agent: imaging-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0038-m2-core-for-layers.md, 0043-m2-layers-stage.md]
---

# M2: `palette` with Layers

Spec §6.1 (palette), §7 (compose) and ADR 0004. Story 7 of [0037](0037-m2-layers-and-props.md).

## What to build

- `palette.png` is the whole composite mapped once and cleaned of orphans, as now, and stays the Stage's `image`, so an
  Override paints over the composite.
- In the hook from [0038](0038-m2-core-for-layers.md), after Overrides: `layer.<id>.png` is that image cut by each alpha, and
  `plate.png` is that image outside the hole, plus the inpainted area mapped separately with the same parameters (the same
  Bayer phase) and cleaned only within the hole.
- Implement `layers.recompose_mismatch` in `_check_palette`, replacing the comment there. Check `plate.png` and each Layer
  for `palette.off_palette`.
- With no Layers: `plate.png` is byte-identical to `palette.png`.
- `export` keeps its behaviour until [0047](0047-m2-export-room-layers.md).
- `palette` still doesn't read `masks`.

## Acceptance criteria

- [x] Golden-style CLI test: after `palette`, Plate + Layers recompose exactly to `palette.png`, with every pixel on the palette.
- [x] A palette Override over a Layer shows in that `layer.<id>.png` and still recomposes.
- [x] A Mask edit doesn't make `palette` stale.
- [x] A palette change rebuilds without any Runner call or `needs-input` (ADR 0004).

## Notes

- The work is in `kiripix/recipes/room_palette.py`; `common.map_to_palette` is the shared map-and-clean step. The Stage's
  run writes `palette.png` and a working `plate.png` (the inpainted area mapped separately, orphans cleaned only inside
  the hole); the `after_overrides` hook cuts `layer.<id>.png`, copies `layers.json` and sets `plate.png` to the overridden
  `palette.png` outside the hole. With no Layers it copies `palette.png` byte for byte.
- The hole is the union of the Layer files' alpha from `layers`, as `layers.recompose_mismatch` there reads it.
- A palette Override that paints inside a hole shows in the Layer, not in the Plate's filled area.
- After review (2026-11-05): the Plate's fill is quantized on its own, and its orphans are cleaned among the pixels
  `plate.png` will hold around them; only pixels inside the hole change.
