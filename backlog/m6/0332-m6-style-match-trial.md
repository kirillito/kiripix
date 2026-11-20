---
status: todo
milestone: M6
agent: imaging-engineer
type: trial
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
---

# M6: trial: which style measures tell a matched Asset from a mismatched one?

Spec §2 (principle 3) and §14 (M6, a style match Check across Kinds). Part of
[0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Prototype code stays in the trial's own folder
(`backlog/m6/0332-trial/`) or the scratchpad, not in `kiripix/`. The work tickets [0333](0333-m6-style-measures-and-check.md)
and [0334](0334-m6-style-references-and-wiring.md) take their values marked "set by 0332" from here.

## The question

The Owner's list of measures is: palette use, the range of value and saturation, outline density, pixel scale and light
direction. Which of them, measured on which Stage's output, separate Assets that sit well together in the game from ones
that don't, across Kinds (a 3D body beside a painted room beside an imported sprite)? And what threshold does each need?

## What to do

1. **Pick the set.** From the art Project: the mc03 bodies, a sprite (the raccoon), a Wearable, the laneway and the ch01
   dungeon rooms (not `harbor_front`), and a Prop (the bins). Portraits are left out: they have their own colours by the
   Owner's choice (spec §2, principle 6's exception), and the measure is a question for later.
2. **Make known mismatches**, each one failure the game fears: a sprite imported at 2x pixels; a character with its outline
   off; a room painted with its light from the other side (a mirrored Source); a sprite with saturated colours not mapped to
   the palette; a room from another image model's style, if the Owner has one.
3. **Measure each candidate** on each Asset, deterministically, with numpy:
   - **palette use:** the share of the Project palette used, and how far each colour's use is from the references';
   - **value and saturation:** OKLab lightness and chroma, 5th to 95th percentile, over the opaque pixels;
   - **outline density:** outline-colour pixels per pixel of silhouette edge (a room: per pixel of Layer edge, or left out);
   - **pixel scale:** the detected grid of the final image (expected 1), or the run-length median of its colour runs;
   - **light direction:** from the normal pass and the lightness (characters, sprites with `height` normals), and for a room
     from the lit side of its foreground Layers, if anything works on a painting at all.
4. **Score** each measure: does every mismatch fall outside the matched Assets' spread, with what margin, and does any matched
   Asset fall outside? Name the Stage each Kind is measured on.
5. **Show the Owner** a sheet of the Assets with their numbers. The Owner says which mismatches matter and which measures read
   true.

## Acceptance criteria

- [ ] A table here: each measure x each Asset, matched and mismatched, with the Stage measured.
- [ ] Per measure: kept or dropped, for which Kinds, and its threshold against the references (the "set by 0332" values).
- [ ] Light direction's verdict for rooms stated plainly, even if it's "not measurable on a painting".
- [ ] The Owner's verdict recorded, with the date.
- [ ] The measure's time per Asset, so 0334 knows whether a cache is needed.
