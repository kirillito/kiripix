---
status: done
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0234-m5-sprite-style-and-size-trial.md
---

# M5: a sprite's palette by parts, a few shades each

Found by [0234](0234-m5-sprite-style-and-size-trial.md): a PixelLab sprite has more shades per part than a 3D body (the worker
35 colours a frame, against the bodies' ramps of 4 per part). Lowering `palette colors` doesn't fix that, it greys it
([colors_16_12_8_x4.png](0234-trial/colors_16_12_8_x4.png)). One colour budget for the whole Asset keeps the shades that cover the most pixels, so the
small hues go first: at 12 the cap loses its green; at 8 the hair, skin and shoes go grey.

## What to build

- A sprite has no materials, so its parts are **colour regions**: the frame colours grouped by hue and chroma (OKLab), across
  all frames, so one part keeps one name in every direction. The groups are proposed by the Stage, then named and merged by
  `parts`, as a body's `parts` names its materials (for example `skin,hair,cap,top,bottom,shoes,trap`).
- Each part gets its own ramp of `shades` (default 4, as the Project's `[character] ramps`), dark to light, mapped by
  lightness inside the part, so the shading flattens toward the bodies' bands while every hue stays.
- The ramps can join the Project's ramp table (`ramps-add`), so the game's swap shader works on a sprite too.
- Bump `palette`'s `version`. An Asset with no `parts` builds as today.

## Open questions (for the Owner before building)

- Grouping by hue alone fails for a grey on grey figure (the raccoon, the worker's overalls against the trap). Is a painted
  part mask (`mask-import`) the fallback, or a click per part in the UI?
  **Owner (2026-11-19): neither for now.** Hue grouping and `parts` only; the greys are one `grey` region. A mask or a click
  is a follow-up ticket if the result isn't good enough.

## Acceptance criteria

- [x] Golden test on the Op: a made-up figure with three hues and many shades each comes out with `shades` per hue.
- [x] 0234's worker with `parts` and `shades=4`, beside the bodies at 1x and 4x, and in the Godot capture.

## Result (2026-11-19)

- Op `colour_regions` (in `kiripix/ops/sprite.py`): every opaque colour of every frame, the neutral ones (OKLab chroma under
  0.025) one region, `grey`; the others cut round the hue circle wherever two neighbours are more than `hue_gap` degrees
  apart. A region is named by the hue word nearest its mean hue (`red`, `orange`, `yellow`, `green`, `cyan`, `blue`,
  `purple`, `pink`), `_2`, `_3` by size for the same word. `region_labels` turns a frame into its region pass (a colour not
  seen goes to the nearest one's region).
- The sprite's `palette` (`sprite_palette_stage`) lists the regions in `palette.json`'s `regions` and, while it has no
  `parts`, says so in `palette.sprite_regions` (info). New parameters `parts` (regions, joined with `+`, named with `=`),
  `shades` (default 4) and `hue_gap` (default 8). With `parts`, the regions are the sprite's materials: the Stage writes
  `material/<clip>/<dir>/<NNN>.png` and its `render.json` lists them, then it is the body's palette (part ramps, the
  Project's ramp table and its rule that every part is a row of it, `part_lines`, `palette.ramp_shared`). Regions in no part
  take `colors`. No `parts` builds the same frames as before. The Stage now reads `character.ramps`.
- **`hue_gap` default 8, not the 20 first written.** On the worker, 20 gives orange (skin, hair and shoes together), green,
  purple and grey ([worker_regions_hue20_x4.png](0319-trial/worker_regions_hue20_x4.png)); 8 splits off red (skin), orange
  (hair and shoes), yellow (the shirt), green (the cap) and purple (the overalls). `parts` can join regions but not split
  them, so the finer default is the safer one.
- **Mapping, as a body's:** nearest in the part's own ramp; a ramp with the table's colours by lightness order. Lightness order
  onto a fitted ramp was tried and dropped: the fitted ramps keep outlier colours (the buttons' yellow in `top`, a near-black
  in `bottom`), and lightness order put a whole class of the shirt on the yellow and of the overalls on the black.
- **`palette`'s `version` is bumped to 3** (sprite Recipe), so every sprite's `palette` is stale.
- Worker in a scratch copy, `parts=skin=red,hair=orange,top=yellow,bottom=purple` (rows of the Project's table; cap and trap
  stay fixed colours): rows flat16 / parts / parts + inner lines, each beside mc03_male and mc03_female_clothes01:
  [worker_parts_lines_1x.png](0319-trial/worker_parts_lines_1x.png), [worker_parts_lines_4x.png](0319-trial/worker_parts_lines_4x.png),
  `s` group at 5x: [worker_parts_lines_s_x5.png](0319-trial/worker_parts_lines_s_x5.png). Skin and hair take the bodies' table
  colours, and the overalls flatten toward the bodies' bands. The hair and shoes share the `hair` ramp (one region), and the
  overalls' darkest shading is in `grey` with the trap, as the open question expected.
- Tests: golden `tests/golden/test_sprite_parts.py` (new image `sprite_parts_three_hues.png` for the Owner's review) and CLI
  `test_palette_proposes_colour_regions_and_parts_give_each_its_own_ramp_of_shades`.
- The art Project's worker now has these `parts` and `finish inner_lines=outline`, and is exported. The Godot capture is in
  [0318](0318-m5-sprite-pivot-at-the-ground-point.md)'s Result: [godot/lineup_4x.png](0319-trial/godot/lineup_4x.png). Under
  the light the worker's skin and hair read as the bodies' do. The overalls still shade as one rounded blob (`normals=height`).
- After the review: a part named after another region (`parts=red=orange` while `red` is a region) is refused
  (`palette.parts_invalid`), since `finish` could no longer name that region. CLI tests added for that refusal and for a
  sprite's part joining the Project's ramp table (`ramps-add`) and then taking its colours. `fit.json`'s `ground.figure`
  recorded the last frame's height, not the median (the offset was right); fixed (0318).
