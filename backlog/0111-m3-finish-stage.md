---
status: todo
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0110-m3-character-palette-stage.md, 0109-m3-outline-op.md, 0107-m3-character-palette-and-normal-ops.md]
---

# M3: the character's `finish` Stage: outline and normal map

Spec §6.3 (finish) and ADR 0004. Stories 11 and 12 of [0097](0097-m3-characters.md).

## What to build

- The outline, by the method from [0106](0106-m3-outline-method-trial.md) and the Op from [0109](0109-m3-outline-op.md),
  painted after mapping in the palette colour `outline_colour` (a palette index; refused if it isn't in the character's
  subset or the Project palette, as the Owner prefers). `outline = none` is allowed.
- The normal pass quantised to `normal_levels` and encoded for Godot with [0107](0107-m3-character-palette-and-normal-ops.md)'s
  Ops, cut by the final colour frame's alpha, so outline pixels get a normal too (pointing at the camera) and the two images
  line up pixel for pixel.
- `normal.size_mismatch` from [0108](0108-m3-sheet-ops-and-checks.md), on every frame.
- Outputs in `render`'s layout: `colour` and `normal` per frame.

## Acceptance criteria

- [ ] CLI seam, on the fake: `run` writes both images per frame; changing `outline_colour` rebuilds `finish` down, not
      `palette`.
- [ ] Every colour pixel is on the palette, and every normal frame is exactly its colour frame's size and alpha.
- [ ] An `outline_colour` outside the palette fails the Stage with a finding that names the valid range and has a `fix`.
