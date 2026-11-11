---
status: done
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0104-m3-render-stage.md, 0107-m3-character-palette-and-normal-ops.md]
---

# M3: the character's `palette` Stage

Spec §6.3 (palette) and ADR 0004 ("`palette` means the same thing in every Recipe"). Story 10 of
[0097](0097-m3-characters.md).

## What to build

- The Stage reads every colour frame from `render`, chooses one subset of the Project palette for the whole character with
  [0107](0107-m3-character-palette-and-normal-ops.md)'s Op, and maps every frame to it, with the same `dither`, `strength` and
  `orphan_size` parameters as a room's `palette`.
- It writes the mapped frames in `render`'s layout and the chosen subset (`palette.json`, `schema_version`, the colours by
  their palette index).
- Normal, depth and mask passes are not mapped; the Stage passes the frame list on for `finish`.
- `palette.off_palette` runs on every frame, and a finding names the clip, direction and frame.
- Checks the cancel token between frames.

## Acceptance criteria

- [x] CLI seam, on the fake renderer's frames: `run` maps every frame; every pixel is in the subset; alpha only 0 or 255.
- [x] Changing the Project palette makes `palette` stale and everything below it, and leaves `render` alone.
- [x] Changing `orphan_size` rebuilds only `palette` down.
