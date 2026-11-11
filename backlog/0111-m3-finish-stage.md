---
status: done
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0110-m3-character-palette-stage.md, 0109-m3-outline-op.md, 0107-m3-character-palette-and-normal-ops.md]
---

# M3: the character's `finish` Stage: outline and normal map

Spec §6.3 (finish) and ADR 0004. Stories 11 and 12 of [0097](0097-m3-characters.md).

## What to build

- The outline, the 1 px silhouette the Owner chose (Q2 of 0097) and the Op from [0109](0109-m3-outline-op.md),
  painted after mapping in the palette colour `outline_colour` (a palette index; refused if it isn't in the character's
  subset or the Project palette, as the Owner prefers). `outline = none` is allowed.
- The normal pass quantised to `normal_levels` and encoded for Godot with [0107](0107-m3-character-palette-and-normal-ops.md)'s
  Ops, cut by the final colour frame's alpha, so outline pixels get a normal too (pointing at the camera) and the two images
  line up pixel for pixel.
- `normal.size_mismatch` from [0108](0108-m3-sheet-ops-and-checks.md), on every frame.
- Outputs in `render`'s layout: `colour` and `normal` per frame.

## Acceptance criteria

- [x] CLI seam, on the fake: `run` writes both images per frame; changing `outline_colour` rebuilds `finish` down, not
      `palette`.
- [x] Every colour pixel is on the palette, and every normal frame is exactly its colour frame's size and alpha.
- [x] An `outline_colour` outside the palette fails the Stage with a finding that names the valid range and has a `fix`.

## Done

- Params: `outline` (bool, default true), `outline_colour` (index into the Project palette, default 0), `placement`
  (`outside` | `edge`, default `outside`), `normal_levels` (1 to 256, default 8). Upstream is `palette` and `render` (the
  normal pass stays in `render`'s folder).
- **Default placement: `outside`.** It keeps the silhouette's pixels and matches Props ([0109](0109-m3-outline-op.md)). Its
  cost is no line where the character touches the frame's edge; `render`'s cell leaves the feet at least
  `ceil(0.1 * height)` px above the bottom and 0.4 * height above the head, so no change to render/fit was needed. A pose that
  reaches the cell's edge loses its outline there; sheet's `sheet.frame_overflow` already guards the cell.
- `outline_colour` is valid across the whole Project palette (0 to N-1), not only the character's subset, so an outline may add
  one colour the subset lacks; the finish Check `palette.off_palette` is against the Project palette. An index outside it fails
  the Stage with `finish.outline_colour_unknown` and the fix `kiripix set <id> finish outline_colour=0`.
- Output: `color/<clip>/<dir>/<NNN>.png` and `normal/<clip>/<dir>/<NNN>.png` (render's folder names, `color` not `colour`),
  `render.json` (copied, frame list and pivots) and `finish.json` (levels, outline colour and placement).
