---
status: done
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

- [x] CLI seam: two built characters give one PNG with both at their pivots on one line; the JSON lists the cells.
- [x] An unbuilt character is named in a finding and left out.

## Result (2026-11-15)

- A Probe Command of its own, `kiripix cast-sheet <id,id,...> [--clips idle,walk] [--directions s] [--frames 1] [--scale 1]`,
  not `kiripix probe cast`: `probe` is one Command that takes one Asset, and its arguments are positional, so the ticket's
  flags didn't fit it. `kind="probe"`: no lock, nothing recorded; the PNG goes to `.kiripix/previews/cast.<hash>.x<scale>.png`.
- Reads each Asset's `sheet` Stage (`sheet.json` and the colour atlas), so characters and sprites both stand in the row. Every
  cell has its pivot on one ground line; the Assets go left to right in the order given, each labelled with its ID (labels
  aren't scaled). `--clips` defaults to each Asset's first clip; `--frames N` spreads N frames over each clip.
- JSON: `path`, `width`, `height`, `scale`, `ground` (the line's y in the PNG) and `cells` (Asset, clip, direction, index, the
  cell's box and pivot, in PNG pixels).
- Findings (warnings): `cast.not_built` (left out; `fix`: `run <id> sheet`), `cast.sheet_stale` (drawn as last built),
  `cast.cell_missing` (a clip or direction the sheet lacks). Refusals: `cast.not_a_figure` (a Kind without a `sheet` Stage),
  and `cast.empty` (exit 1) when nothing could be drawn, after the findings that say why.
- Work in `kiripix/core/cast.py` and `kiripix/commands/probes.py`. Tests: `tests/cli/test_cast_sheet.py` (7) and a contract
  sample (a built sprite).
