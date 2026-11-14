---
status: todo
milestone: M4
agent: character-pipeline
type: ticket
parent: 0161-m4-characters-after-the-m3-gate.md
depends_on: [0215-m4-finish-inner-lines.md]
---

# M4: inner lines in a darker colour of the part, on a character with part ramps

Spec §6.3 (palette, finish). Asked for by the Owner, 2026-11-13. [0215](0215-m4-finish-inner-lines.md) refuses
`inner_lines=dark` when `palette` has `parts`: the colour of the line is a palette colour outside the ramp of its part
([0147](0147-m4-character-palette-ramps.md), [0150](0150-m4-palette-ramps-per-part.md)), so when the game swaps the ramp of a
part the line keeps the old colour. This ticket makes the two work together.

## To decide first

Which of these, with the Owner (the mc03 bodies have no `parts` today, so nothing waits on it):

1. **The line is the darkest colour of the ramp.** No new colour; the swap recolours it. But the shadow band of a 2-colour
   ramp is that same colour, so a line inside a shadow disappears.
2. **The ramp grows by one step for the line.** Each part with lines gets a ramp one longer, its first colour kept for the
   line only. The swap recolours it. The ramp table of the Project
   ([0168](0168-m4-palette-reads-the-ramp-table.md)) and the swap in the game must know the extra step, and the palette needs
   one more colour per part.
3. **The line keeps a fixed colour** (as `outline` does), and the finding becomes a warning that the swap will not recolour
   it.

## What to build

- The option chosen, in `palette` and `finish`, with `finish.inner_lines_with_parts` removed or narrowed to what is still
  refused.
- `palette.ramp_shared` and `finish.outline_in_ramp` still hold: no line colour is in the ramp of another part.

## Acceptance criteria

- [ ] The decision recorded here.
- [ ] CLI seam: a character with `parts` and `inner_lines=dark` builds through `finish`, and the colours of the line are as
      the chosen option says.
- [ ] `uv run pytest`, `uv run lint-imports` and `uv run mypy` pass.
