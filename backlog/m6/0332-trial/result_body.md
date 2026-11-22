
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

@@TABLE@@

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

- [ ] Which mismatches matter (2x pixels, outline off, unmapped colours, mirrored light, another model's room): _(open)_
- [ ] Which measures read true: _(open)_
- [ ] Date: _(open)_
