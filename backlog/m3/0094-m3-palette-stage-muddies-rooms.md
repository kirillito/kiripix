---
status: done
milestone: M3
agent: imaging-engineer
type: ticket
---

# M3: the `palette` Stage turns rooms muddy

Spec §7. Found by the Owner at the [M2 gate](../m2/0058-m2-gate.md): after `palette` the rooms "look like poorly compressed JPEGs" rather than
pixel art, "full of random pixels and unnecessary outlines", even with no dither, strength 0 and `orphan_size` 0. In Godot, r02
looked like "two images stitched together at the wrong places" around x = 220.

## What was seen (2026-11-07)

`room.ch01_dungeon_r02`, palette `bayer8`, `orphan_size` 2, the Project's 64-colour `style/palette.gpl`. The Source, `fit` and the
`palette` Plate compared side by side around x 150-330, y 60-200:

- **`fit` is faithful:** the teal-grey wall and the floor's soft light pool look like the Source.
- **`palette` isn't:** the teal-greys map to bands of brown, green and blue, and the pool's gradient breaks into hard-edged blotches.
  The seam the Owner saw is one of these band edges. It's there with the Godot light off, and none of the inpainted pixels show outside
  the Layers, so it isn't LaMa or the light.
- **`fit` adds dark edges** around the lockers that the Source doesn't have, which may be the "unnecessary outlines".

The dark dungeon rooms use a narrow range of colours that the 64-colour palette barely covers. Whether that's all of it, or the
mapping and dither also add noise, isn't known yet.

**`palette-suggest` (2026-11-07),** mean OKLab error of the nearest-colour mapping, before and after the suggestion. The three
dungeon rooms' `fit` images side by side, `--scale 1`; the subway reference at the default scale:

| Image | Asked | Got | Error before | After |
|---|---|---|---|---|
| r01 + r02 + r03 `fit` | 16 | 9 | 0.0302 | 0.0204 |
| r01 + r02 + r03 `fit` | 32 | 18 | 0.0302 | 0.0179 |
| `subway-lower-bay.jpeg` | 32 | 15 | 0.0241 | 0.0176 |
| the same, on the palette plus the dungeon 18 | 32 | 16 | 0.0212 | 0.0168 |

With the dungeon 18, r02's teal-grey wall and floor stay teal-grey instead of breaking into brown, green and blue bands, and r01 and
r03 lose their brown cast. So the palette is most of the cause on these rooms. The suggestions spend 3 to 5 colours on near-blacks
(`#000000`, `#000005`, `#010000`, `#000405`) that are 0.03 or more apart in OKLab but look the same: the distance rule may want a
lightness weight near black.

## What to do

1. **Measure.** For the three `ch01_dungeon` rooms, the mapping error per pixel in OKLab, from `fit` to `palette`, with the current
   palette and with it grown by `palette-suggest` ([0077](../m2/0077-m2-grow-the-palette-from-an-image.md)) by 16 and 32 colours. Each with
   no dither, and with `bayer8`. Record a table and side-by-side images here.
2. **If the palette is the cause:** a Check on `palette` that warns when the mapping error is high, with a `fix` that runs
   `palette-suggest`, so the Owner sees it before the room looks wrong in the game.
3. **If the mapping or dither is the cause:** fix it in the Op, with golden images of a dark gradient and a teal-grey wall.
4. **The dark edges from `fit`:** find which `downscale` step adds them, and remove them unless the Source has them. Coordinate with
   [0081](0081-m3-downscale-keeps-one-scale.md), which changes the same Op.

## Findings and what was built (2026-11-07, imaging-engineer)

Measured on the three `ch01_dungeon` Source images, fitted to their briefs (400x560, 560x416, 640x368), with the Project's
64-colour palette and the suggestion (`suggest_palette`, `--add 32`, `min_distance` 0.02, on the three `fit` images stacked;
it returned 16 colours with the new `fit`, 18 with the old). Mean OKLab distance from `fit` to the mapped image, strength 1.

| Palette | Dither | r01 | r02 | r03 |
|---|---|---|---|---|
| current (64) | none | 0.0143 | 0.0163 | 0.0145 |
| current (64) | bayer8 | 0.0165 | 0.0189 | 0.0170 |
| +16 suggested | none | 0.0119 | 0.0100 | 0.0128 |
| +16 suggested | bayer8 | 0.0144 | 0.0129 | 0.0154 |
| +32 asked (16 found) | none | 0.0119 | 0.0100 | 0.0128 |
| +32 asked (16 found) | bayer8 | 0.0144 | 0.0129 | 0.0154 |

Images (deleted 2026-11-12; in git before commit 0504348): r02, x 150-330, y 60-200, 3x. Top row: Source (box mean), `fit` before the fix,
`fit` after. Bottom row: current palette with bayer8, grown palette with bayer8, grown palette with no dither.

- **Two causes, as suspected.** The palette is the larger one (r02 0.0189 -> 0.0129 with the grown palette: the wall stays
  teal-grey). Dither adds about 0.002 to 0.003 on top; with no dither the grown palette shows band edges in the pool of light,
  which bayer8 is there to hide, so I left the mapping Op alone (no fault found in it: nearest colour in OKLab, ties by
  palette order).
- **(Withdrawn, see "The Owner's look" and the candidates below.) The dark edges came from `downscale_mode`.** A painted cell has nearly all-different colours, so there is no mode, and the
  tie went to the smallest packed RGBA value: the one with the lowest red, nearly always the darkest. Fit vs the cell's mean
  colour, mean OKLab distance and mean lightness difference:

  | Room | distance before | after | dL before | after |
  |---|---|---|---|---|
  | r01 | 0.0115 | 0.0083 | -0.0083 | -0.0018 |
  | r02 | 0.0088 | 0.0059 | -0.0062 | -0.0013 |
  | r03 | 0.0164 | 0.0100 | -0.0129 | -0.0012 |

  The tie-break change that this paragraph described was **reverted** (`downscale_mode` and its goldens are as before). Among equally common colours, the one nearest the cell's mean colour (exact integers), then the
  smallest packed value as before. It's still a mode filter, and touches nothing of 0081's grid or cropping work.
- **Check.** `palette.mapping_error` (warning, a `fix` that runs `kiripix op palette-suggest <fit.png> --add 16 --scale 1`) on
  the room and prop `palette` Stages, when the mean OKLab distance from the image the Stage mapped to `palette.png` is over
  0.016. The limit sits between the grown palette's bayer8 errors (up to 0.0154) and the current ones (0.0165 to 0.0189). On a copy
  of r02 it warns with 0.0228 (orphan removal counts in it).
- The near-black duplicates the suggestion spends colours on (`#000000`, `#000005`, ...) are not addressed: that is a lightness
  weight in `suggest_palette`'s distance, a separate decision for the Owner.

Changed: `kiripix/ops/resample.py`, `kiripix/ops/colour.py` (`mapping_error`), `kiripix/checks/palette.py`
(`check_mapping_error`), `kiripix/recipes/common.py`, `room_palette.py`, `room.py`, `prop.py`; tests in
`tests/golden/test_resample.py` (`downscale_painted_wall.png`; `downscale_ratio.png` changed, its one tie now goes to the cell's
middle colour), `test_quantize.py` (`dark_gradient.png`), `test_mapping_check.py`.

## Acceptance criteria

- [x] The measurement table and images are recorded here, with the Owner's look at the grown palette's result (2026-11-07: "looks good", on r02_final.png).
- [x] A golden image of a smooth dark gradient maps without hard bands, with the palette the measurement picks.
- [x] `fit` keeps the Source's thin dark lines continuous and its flat areas even, on golden images (`downscale_thin_line.png`,
      `downscale_soft_shade.png`). (Reworded: the dark lines were the Source's own, see the Owner's look.)
- [x] If step 2 applies, the Check warns on r02 as it stands, with a `fix`.

## The Owner's look (2026-11-07)

On r02_x150-330_y60-200.png (top: Source, old `fit`, new `fit`; bottom: current
palette `bayer8`, grown palette `bayer8`, grown palette no dither): only the Source looks right. The other five are
"extremely noisy and uneven". The old `fit` (top middle) is closest, but the locker door outlines have coloured pixels in
them instead of the Source's continuous dark lines: "this gives a poor quality impression".

So the dark lines are the Source's own, and the new tie-break (top right) loses more of them than the old one. Looking at the
Source at native size, r02 is 1200 x 896 into 560 x 416: scales 15/7 and 28/13, cells alternating 2 and 3 Source pixels. A
line about 2 Source pixels wide straddles two cells wherever it falls off the cell phase, so a per-cell mode keeps it in
neither or both, and the line breaks or doubles. The Source's soft shading gives every cell nearly all-different colours,
so the mode is mostly a tie-break. The bottom row's dither adds noise on top. The goal: continuous one-pixel dark lines and
flat, even areas, as in the Source.

## Downscale candidates (2026-11-07, prototypes only, nothing wired into the Stage)

Prototype script, not in the repo: `C:\Users\Kirill\AppData\Local\Temp\claude\e7ccd5c4395c2f79\ac3f705e-c588-4ca1-bd55-d61d051d0969\scratchpad\proto.py`.
All three use 0081's one scale: r02's 1200 x 896 Source at 15/7 on both axes, the 5 spare rows cropped evenly.
Images, each panel the r02 lockers (fit x 150-330, y 60-200) at 4x nearest neighbour, labelled:
the candidates and
the same through `palette` with the grown palette (the 64 plus 19 suggested), no dither.
First panel is the Source scaled by nearest neighbour to the fit size, second the current fit.

- **A, lines first.** Finds the Source's dark thin pixels (darker than their 9 x 9 neighbourhood by 0.045 in OKLab lightness),
  counts how much of each cell they cover, and keeps a cell as a line only where it covers at least 30 % and is the local
  maximum across the line, so a 2 px line that straddles two cells becomes one pixel wide. Line cells take the line's colour; every
  other cell takes the average of its non-line pixels, so flat areas are smooth. Lines are one pixel wide, but some faint door
  outline segments thin out or vanish.
- **B, cluster pick.** Splits each cell's pixels into a darker and a lighter group at the cell's mean lightness. If the groups are
  clearly different (0.05), the cell takes the dark group's colour when it covers 40 % or more, else the light group's. Other
  cells take the plain average. Lines are mostly continuous but can double to two pixels where both cells of a straddling line
  pass the 40 % bar; flat areas are even.
- **C, average plus sharpen.** The plain average of each cell, then a sharpening pass (the cell minus a 3 x 3 blur of the
  result, added back). No decisions, and the evenest flat areas; lines come out one to two pixels wide, slightly lighter than
  the Source's near-black, with a faint halo.

All three look much closer to the Source than the current fit, which breaks the lines into dots. Through the palette none shows
the old noise; the floor still bands slightly without dither, which is the palette's doing, not the downscale's. The Owner
picks; nothing else of 0081 is done yet.

## Decision and result (2026-11-07)

The Owner picked candidate B (cluster pick): "B has the best results in the image". It is now `downscale` in
[resample.py](../../kiripix/ops/resample.py), the Op `fit` uses in downscale mode (it replaces the per-cell mode filter, and
`downscale_mode` is renamed `downscale`). As prototyped, with one addition for B's known flaw: a 2 px line that straddles two cells
was dark in both, so only the cell with the larger dark share keeps it (ties go to the right or lower cell), judged along the
axis where the line's run of cells is longer; at a crossing nothing is thinned. Goldens: a painted wall with a vertical and a
horizontal 2 px line straddling cells stays one pixel wide and unbroken (`downscale_thin_line.png`), and a soft-shaded wall stays
within the noise of the plain mean (`downscale_soft_shade.png`).

Final comparison on r02, lockers at 4x nearest: r02_final.png. Panels: the Source, the old fit,
the new fit, the new fit through `palette` with the grown palette (the 64 plus 18 suggested), no dither. The floor's bands in the
last panel are the palette without dither, which `bayer8` is there to hide.

[0081](0081-m3-downscale-keeps-one-scale.md) is done with it: one scale on both axes, the rest cropped.
