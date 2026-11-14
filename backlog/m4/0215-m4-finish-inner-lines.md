---
status: todo
milestone: M4
agent: character-pipeline
type: ticket
parent: 0161-m4-characters-after-the-m3-gate.md
depends_on: [0214-m4-inner-lines-op.md]
---

# M4: `finish` draws inner lines at part borders

Spec §6.3 (finish). Chosen by the Owner in the trial [0160](0160-m4-flatter-character-look-trial.md), 2026-11-13: variant
`24_cel_s_lines_d`, the lines in a darker colour of the part. The Op is [0214](0214-m4-inner-lines-op.md); the shading half of
the look is [0213](0213-m4-render-cel-band-edge.md).

## What to build

- Three parameters on the character's `finish`:
  - `inner_lines` (choice: `off`, `outline`, `dark`; default `off`). `outline`: the line is `outline_colour`. `dark`: the
    line is a darker palette colour of the part it is drawn on (`line_colours`).
  - `line_skip` (str, default empty): what gets no line, comma-separated by material name. `a+b` is the border between two
    materials; a single name is every border of that material. For the mc03 bodies: `dragon+tee,sole+shoes`. A name that is
    not one of the materials in `render.json` is refused with a finding that lists them.
  - `line_darkness` (float, 0 to 1, default 0.55): with `dark`, how much darker than the dark colour of the part the line is.
- Order in `_run_finish`: the eyes, then the inner lines, then the outline. The line is painted only on pixels inside the
  mask of the render. It never paints over a pixel the eyes painted, and the eye materials (the `eyes` parameter of `render`)
  never get a line.
- The colours of the line are chosen once, over all the mapped frames, before the first frame is painted. Check the cancel
  token in that pass as in the frame loop.
- `finish.json` records what was drawn: the mode, the skipped borders, and with `dark` the line colour of each material
  (index and RGB). Bump `FINISH_SCHEMA_VERSION`.
- The normal pass does not change: a line pixel keeps its normal.
- **With palette `parts`, `inner_lines=dark` is refused** for now: a line colour is outside the ramp of its part, so the
  colour swap in the game would not recolour it. The finding (`finish.inner_lines_with_parts`) has the fix
  `kiripix set <character> finish inner_lines=outline`. [0216](0216-m4-inner-lines-with-part-ramps.md) lifts this.
- `palette.off_palette` on `finish` still passes: every line colour is a Project palette colour.
- With `inner_lines=off` the frames are byte-equal to what `finish` writes now. The Owner accepts that declaring the
  parameters makes every existing character stale once (2026-11-13).

## Out of scope

- Setting the look on the characters of the art Project. The Owner sets `inner_lines=dark line_skip=dragon+tee,sole+shoes`
  on the mc03 bodies.

## Acceptance criteria

- [ ] CLI seam, on the character fixture: with `inner_lines=outline` a border pixel between two materials has the colour of
      the outline, and it is the farther one; with `dark` it has the colour `finish.json` lists for its material; with `off`
      the frames are byte-equal to a run without the parameter.
- [ ] `line_skip` drops the named border and keeps the others; an unknown material name fails with a finding that lists the
      materials.
- [ ] `inner_lines=dark` with `parts` set exits with `finish.inner_lines_with_parts` and its fix.
- [ ] With `eyes=stamp`, no stamped eye pixel is changed by a line.
- [ ] `uv run pytest`, `uv run lint-imports` and `uv run mypy` pass.
