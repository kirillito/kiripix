---
status: todo
milestone: M4
type: ticket
---

# M4: a cast sheet: several characters side by side

Spec §10 (Probes). From the generator trial ([0164](0164-m4-claude-built-base-models-trial.md)), 2026-11-14.

## The gap

Whether a cast looks "too much the same" is judged with the characters next to each other, at the game's size. `preview`
shows one Asset's Stage. The trial's `chargen/contact_sheet.py` (in the art repo) builds the sheet from each character's
`out/export/`: named clips and directions, a few frames each, every character standing on one ground line, at 1x and 3x.
M03-09 of the game (the 3D MC beside a PixelLab NPC) needs the same picture.

## What to build

- A Probe, `kiripix probe cast --assets character.a,character.b,... [--clips idle,walk] [--directions s,sw] [--scale 3]`,
  that writes one PNG to `.kiripix/previews/` from the characters' built `sheet` or `export` Stage, each at its own pivot
  on a shared ground line, labelled. A sprite Asset (a PixelLab figure) can stand in the row too.
- Read-only, as every Probe is. A character that isn't built is a finding, and the others are still drawn.

## Acceptance criteria

- [ ] CLI seam: two built characters give one PNG with both at their pivots on one line; the JSON lists the cells.
- [ ] An unbuilt character is named in a finding and left out.
