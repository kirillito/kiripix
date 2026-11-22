---
status: done
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

- [x] A table here: each measure x each Asset, matched and mismatched, with the Stage measured.
- [x] Per measure: kept or dropped, for which Kinds, and its threshold against the references (the "set by 0332" values).
- [x] Light direction's verdict for rooms stated plainly, even if it's "not measurable on a painting".
- [x] The Owner's verdict recorded, with the date.
- [x] The measure's time per Asset, so 0334 knows whether a cache is needed.

## Result (draft, 2026-11-20, imaging-engineer; the Owner's verdict is still open)

Prototype: `backlog/m6/0332-trial/measure.py` (the measures, numpy only, deterministic; reads the art Project, writes
`results.json` and `images/`) and `report.py` (the table, `spread.txt`, the sheets). Run `uv run python
backlog/m6/0332-trial/measure.py`, then `report.py`. Nothing in `kiripix/` changed and nothing in the art Project was written.

### The set, and where it differs from the ticket

- Figures, measured on the **finish** Stage's colour frame (the exported `color.png` cell, clip `idle`, direction `s`, cut to
  its opaque box) and its normal frame: the mc03_male and mc03_female bodies, the mc03_male_clothes01 Wearable, the raccoon.
- Rooms, measured on the exported **Plate** (`plate.png`, after `palette`) and the exported Layers: ch01 dungeon r01, r02, r03.
  **The laneway has no full Plate in `out/export/`** (only `looks/back_gate_open/plate.png`, a 107 x 179 patch), so #5 is its
  foreground Layers composited in name order on transparent. Its palette-use and light numbers are not comparable with the
  dungeon Plates'. `harbor_front` is left out as asked; the two `trial_*` rooms have no output.
- Prop: the Project has no built Prop (`street_lamp` has only a Source and a pinned cutout, no `out/`). The two **bin Layers**
  of dungeon r02 and r03 stand in, cut from the room's export. They test the measures at a Prop's size, not on a Prop Stage's
  output.
- Portraits left out, as the ticket says.
- Mismatches built: #11 raccoon at 2x (nearest), #12 mc03_male with the outline off (outline pixels on the silhouette removed,
  inner ones repainted from the commonest neighbour), #13 and #14 the raccoon with OKLab chroma x1.8 and x4, not re-mapped,
  #15 the raccoon and #16 the body mirrored (normals mirrored too), #17 r02 and #18 the laneway mirrored.
  **A room from another image model's style: skipped.** The art Project holds none (`style/refs/` is empty, and no room is
  marked as from another model), and the Owner can't be asked mid-run.

### The table (every measure x every Asset)

Columns: share of pixels not exactly a palette colour; share of the 300-colour Project palette used; total-variation distance
of the colour-use histogram from the mean of all matched Assets'; OKLab L span (p5 to p95); OKLab chroma p95, over opaque
pixels; outline-colour (palette 195) pixels per silhouette-edge pixel; median and gcd of all colour runs (rows and columns) of
the box-cropped image; share of colour changes at an even offset; light as the pooled within-Layer correlation of lightness
with x and y, outline pixels left out (lit-left > 0: lighter on the left; lit-top > 0: lighter on top); seconds for all
measures on that Asset. All columns, with the normal-pass fits, are in `backlog/m6/0332-trial/table.md`.

| # | Asset | off-pal px | pal used | pal TV | L span | C95 | outline dens | run med | run gcd | even bnd | lit left | lit top | time s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | mc03_male body (idle s, finish) | 0.00 | 0.040 | 0.74 | 0.53 | 0.075 | 1.48 | 1 | 1 | 0.49 | -0.05 | -0.14 | 0.01 |
| 2 | mc03_female body (idle s, finish) | 0.00 | 0.040 | 0.72 | 0.63 | 0.075 | 2.02 | 1 | 1 | 0.49 | -0.17 | -0.54 | 0.00 |
| 3 | mc03_male_clothes01 Wearable | 0.00 | 0.070 | 0.70 | 0.63 | 0.063 | 1.89 | 1 | 1 | 0.47 | +0.04 | +0.03 | 0.00 |
| 4 | raccoon sprite (idle s) | 0.00 | 0.043 | 0.78 | 0.78 | 0.027 | 1.00 | 2 | 1 | 0.52 | -0.31 | +0.35 | 0.00 |
| 5 | laneway (Layers composited; no full Plate) | 0.00 | 0.719 | 0.72 | 0.73 | 0.077 | 0.01 | 1 | 1 | 0.50 | +0.18 | +0.27 | 0.36 |
| 6 | ch01 dungeon r01 Plate | 0.00 | 0.166 | 0.66 | 0.41 | 0.037 | 0.00 | 1 | 1 | 0.50 | -0.13 | +0.10 | 0.23 |
| 7 | ch01 dungeon r02 Plate | 0.00 | 0.109 | 0.57 | 0.44 | 0.039 | 0.00 | 1 | 1 | 0.49 | -0.29 | +0.34 | 0.25 |
| 8 | ch01 dungeon r03 Plate | 0.00 | 0.315 | 0.58 | 0.34 | 0.034 | 0.08 | 1 | 1 | 0.51 | +0.01 | -0.00 | 0.48 |
| 9 | bin Layer, r02 (stand-in Prop) | 0.00 | 0.040 | 0.71 | 0.13 | 0.019 | 0.00 | 2 | 1 | 0.48 | +0.03 | -0.02 | 0.00 |
| 10 | bin Layer, r03 (stand-in Prop) | 0.00 | 0.046 | 0.62 | 0.19 | 0.034 | 0.00 | 1 | 1 | 0.48 | -0.07 | -0.15 | 0.00 |
| 11 | MISMATCH raccoon at 2x pixels | 0.00 | 0.043 | 0.78 | 0.78 | 0.027 | 1.60 | 4 | 2 | 1.00 | -0.31 | +0.35 | 0.01 |
| 12 | MISMATCH mc03_male, outline off | 0.00 | 0.036 | 0.86 | 0.56 | 0.075 | 0.00 | 2 | 1 | 0.51 | -0.04 | -0.11 | 0.00 |
| 13 | MISMATCH raccoon, chroma x1.8, unmapped | 1.00 | 0.000 | 0.50 | 0.78 | 0.048 | 0.00 | 2 | 1 | 0.52 | -0.22 | +0.29 | 0.00 |
| 14 | MISMATCH raccoon, chroma x4, unmapped | 1.00 | 0.000 | 0.50 | 0.77 | 0.111 | 0.00 | 2 | 1 | 0.52 | -0.22 | +0.29 | 0.00 |
| 15 | MISMATCH raccoon mirrored | 0.00 | 0.043 | 0.78 | 0.78 | 0.027 | 1.00 | 2 | 1 | 0.52 | +0.31 | +0.35 | 0.00 |
| 16 | MISMATCH mc03_male mirrored | 0.00 | 0.040 | 0.74 | 0.53 | 0.075 | 1.48 | 1 | 1 | 0.49 | +0.05 | -0.14 | 0.00 |
| 17 | MISMATCH r02 mirrored | 0.00 | 0.109 | 0.57 | 0.44 | 0.039 | 0.00 | 1 | 1 | 0.49 | +0.29 | +0.34 | 0.29 |
| 18 | MISMATCH laneway mirrored | 0.00 | 0.719 | 0.72 | 0.73 | 0.077 | 0.01 | 1 | 1 | 0.50 | -0.18 | +0.27 | 0.45 |

Matched spread, from `spread.txt` (min to max over the matched Assets of the Kind):

| Measure | figures (4) | rooms (4) | props (2) | all matched |
|---|---|---|---|---|
| off-palette px | 0 | 0 | 0 | 0 |
| palette used | 0.04 to 0.07 | 0.11 to 0.72 | 0.04 to 0.05 | 0.04 to 0.72 |
| palette TV from references | 0.70 to 0.78 | 0.57 to 0.72 | 0.62 to 0.71 | 0.57 to 0.78 |
| L span | 0.53 to 0.78 | 0.34 to 0.73 | 0.13 to 0.19 | 0.13 to 0.78 |
| chroma p95 | 0.027 to 0.075 | 0.034 to 0.077 | 0.019 to 0.034 | 0.019 to 0.077 |
| outline density | 1.00 to 2.02 | 0.00 to 0.08 | 0 | 0 to 2.02 |
| even-boundary share | 0.47 to 0.52 | 0.49 to 0.51 | 0.48 | 0.47 to 0.52 |
| lit-left | -0.31 to +0.04 | -0.29 to +0.18 | -0.07 to +0.03 | -0.31 to +0.18 |

### Score, measure by measure

Margin is how far the mismatch sits outside the matched range.

| Measure | Mismatches it must catch | Result | Verdict |
|---|---|---|---|
| Off-palette share | #13, #14 unmapped colours | 1.00 against 0.00 on all 10 matched: margin 1.00, no matched Asset out | catches them, but **`palette.off_palette` already says it**; no new measure |
| Chroma p95 | #13 (x1.8), #14 (x4) | #13 = 0.048, inside the matched 0.019 to 0.077; #14 = 0.111, outside by 0.034 | **drop**: catches only a gross x4, and a palette-mapped Asset can't exceed the palette's own chroma |
| L span | none built | matched spans run 0.13 (bin) to 0.78 (raccoon), a 6x range by Kind; no mismatch moves them | **drop** |
| Palette used, palette TV | none cleanly | used: 0.04 (figures) to 0.72 (laneway), set by the Kind; TV of the 2x sprite (0.78) equals the raccoon's (0.78); the no-outline body (0.86) is only 0.08 above the matched maximum | **drop** |
| Outline density | #12 outline off | 0.00 against matched figures 1.00 to 2.02: margin 1.00. A 2x sprite gives 1.60, inside the range, so it can't catch #11. Rooms 0.00 to 0.08, bins 0 | **keep for character and sprite only**; left out for rooms and Props; not the Wearable (spec: "No outline: the game draws it once"). mc03_male_clothes01's export does carry the outline colour (1.89), which the spec says it shouldn't |
| Pixel scale: run gcd, even-boundary share | #11 at 2x | gcd 2 against 1 on all 10 matched; even share 1.00 against 0.47 to 0.52 (margin 0.48). Run median 4 against 1 to 2 also separates, but only by one step, and the bins have 2 | **keep, all Kinds**, on the gcd and the even share; drop the run median |
| Light direction | #15 to #18 mirrored | no, see below | **drop** |

### Light direction

- **Rooms: not measurable on a painting, by what I could build.** Two estimators on the exported Layers (correlation of
  lightness with x and y; left-third minus right-third lightness) agree and fail the same way. Mirroring r02 flips lit-left
  from -0.29 to +0.29, but the matched rooms already span -0.29 to +0.18 (laneway Layers +0.18, r01 -0.13, r03 0.01), so the
  mirrored r02 sits next to the matched laneway, and the mirrored laneway (-0.18) sits inside the dungeon rooms' range. A
  dungeon room under a ceiling lamp and an outdoor laneway are not lit from one side, and the vertical component doesn't change
  under a mirror at all.
- **Figures: dropped too, for another reason.** Lit-left over the four matched figures is -0.05, -0.17, +0.04, -0.31 and
  lit-top is -0.14, -0.54, +0.03, +0.35: lightness on a painted body follows the material (hair against skin), not the light.
  Fitting lightness to the normal pass (with and without a fixed effect per hue family) gives a light coefficient near 0 on
  the bodies, and the raccoon's `height` normals come from its alpha, not from its light. A figure's light is a render
  setting (`[character.camera.*] light_angle`), so a settings comparison, not an image measure, is what could check it. I did
  not build that.

### Time per Asset

On this machine, one run, numpy, all prototype measures on the Asset: a figure frame 0.00 to 0.04 s (the first call carries
the numpy warm-up); a dungeon Plate (400 x 560 to 640 x 368) 0.23 to 0.48 s; the laneway Layers (1120 x 624, mostly
transparent) 0.36 s. The cost is my pure-Python run-length loop (0.4 to 0.6 s on a Plate in the first run) and the OKLab pass.
The two kept measures (outline density, run gcd) vectorise, which puts a Plate in tens of milliseconds. **No cache is needed
for figures; for rooms a cache keyed by the output hash is optional** (20 rooms x 0.4 s is 8 s on every `check`, as
prototyped).

### Proposed values for 0333 and 0334 ("set by 0332")

| Value | Proposal |
|---|---|
| Measures kept | `style.outline_density` (character, sprite), `style.pixel_scale` (every Kind) |
| Measures dropped | `style.palette_use`, `style.value_range`, `style.saturation_range` (unmapped colour is `palette.off_palette`'s), `style.light_direction` |
| `style.outline_density` threshold | warn when density < 0.5 (references 1.00 to 2.02; the off case is 0.00), on the finish Stage's colour frame of one clip and direction |
| `style.pixel_scale` threshold | warn when `run_gcd` >= 2, given at least 50 runs (matched: 1; 2x: 2). Even-boundary share > 0.75 is the same test for a clean 2x. Not tested: 3x, or a 2x image edited afterwards |
| Stage per Kind | character and sprite: `finish` colour frame; Wearable: `finish`, pixel scale only; room: the `palette` Plate (`export`'s `plate.png`), pixel scale only; Prop: its export, pixel scale only |
| References | with two kept measures against fixed bounds that hold for all ten matched Assets, 0334's reference list matters little and could shrink to "the Project's other Assets of the Kind" |
| Cache | none for figures; optional for rooms |

### The sheets

`backlog/m6/0332-trial/sheet_figures.png` (figures, bin Layers and the figure mismatches, enlarged nearest-neighbour x4 to x9)
and `backlog/m6/0332-trial/sheet_rooms.png` (the Plates and the two mirrored rooms, nearest-neighbour at 1/2 or 1/3). Each tile
is captioned with its table number and its numbers.

### The Owner's verdict

2026-11-20, the Owner, from the two sheets:

- **Kept:** `style.outline_density` (character and sprite; warn below 0.5, on `finish`'s colour frames) and `style.pixel_scale`
  (every Kind; warn at a run gcd of 2 or more over at least 50 runs; on `finish` for figures, `palette`'s Plate for rooms, the
  Prop's export). These are the "set by 0332" values for 0333 and 0334.
- **Dropped:** `style.palette_use`, `style.value_range`, `style.saturation_range` (they vary by Kind; unmapped colour is
  `palette.off_palette` already) and `style.light_direction` (not measurable on a painting; on figures lightness follows the
  material). A settings Check on the render preset's `light_angle` across characters is a follow-up,
  [0361](0361-m6-light-angle-consistency.md).
- **Mismatches that matter:** 2x pixels, outline off, unmapped colours. A mirrored room and another image model's style stay the
  Owner's eye at review.
- **Wearables have no outline, as built** (the Owner, 2026-11-20, after a correction: a Wearable's `finish` fixes
  `outline = false` and the game outlines the stack once; the 1.89 on `mc03_male_clothes01` was dark ramp pixels equal to the
  outline colour, not an outline). The outline measure is for characters and sprites; a Wearable gets only pixel scale.
- Bins cut from the dungeon Layers stand in for a built Prop; a 3x upscale isn't tested until a real case shows up.
