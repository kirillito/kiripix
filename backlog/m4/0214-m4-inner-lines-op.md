---
status: todo
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0161-m4-characters-after-the-m3-gate.md
---

# M4: an Op that finds the inner lines of a character

Spec §6.3 (finish). Chosen by the Owner in the trial [0160](0160-m4-flatter-character-look-trial.md), 2026-11-13: variant
`24_cel_s_lines_d`. Hand-drawn sprites outline parts against each other (collar, cuffs, waist); the silhouette outline alone
leaves the inside soft. This ticket is the pure Op; [0215](0215-m4-finish-inner-lines.md) uses it in `finish`.

## What to build

In `kiripix/ops/character.py`, pure (arrays in, arrays out):

- `inner_lines(material, depth, skip) -> mask`: a boolean (H, W) mask of the pixels of the line.
  - `material` is the material pass (0 background, else the index of the material), `depth` the depth pass (larger is
    farther).
  - A border is two 4-neighbours with different materials, both not 0. The line is the pixel of the two that is **farther
    from the camera**; on a tie, the lower or the right one. So the nearer part keeps its pixels.
  - `skip` holds what gets no line: a pair of indexes (no line between those two materials) or one index (no line on any
    border of that material).
  - Where the material changes against the background there is no line: that belongs to the outline.
- `line_colours(frames, materials, palette, darkness) -> {material index: palette index}`: the colour of the line per
  material, chosen once for a character so it never flickers. For each material: its darkest colour among those with at least
  5 % of its pixels over all the mapped colour frames, times `darkness` in linear light, then the nearest Project palette
  colour (the same distance `quantize` uses, OKLab). A material with no pixels has no entry.
- The reference is `inner_lines` in `C:\Homespace\urban-mystery-club-art\.kiripix\trials\0160-flat\options.py`. It measured
  the nearest colour in linear RGB; use OKLab here, as the rest of the palette code does.

Painting the mask is the job of the Stage, not of the Op.

## Acceptance criteria

- [ ] Golden seam: a small fixture with three materials at different depths. The golden shows the line on the farther side of
      each border, none against the background, and none on a skipped pair or a skipped material. Enlarged and captioned for
      the Owner to review, not at 1x.
- [ ] Unit cases at the same seam: a depth tie puts the line on the lower or right pixel; `line_colours` returns the same
      colours whatever the order of the frames; every colour it returns is a palette colour.
- [ ] Both are exported from `kiripix.ops`. `uv run lint-imports` and `uv run mypy` pass.
