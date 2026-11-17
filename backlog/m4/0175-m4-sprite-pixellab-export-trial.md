---
status: done
milestone: M4
agent: character-pipeline
type: trial
parent: 0174-m4-sprite-kind.md
---

# M4: trial: a real PixelLab export, taken through by hand

Part of [0174](0174-m4-sprite-kind.md). No Kiripix code: this trial answers what the `sprite` Recipe's import and `fit` must
handle, on a real file, before [0178](0178-m4-import-a-sheet.md) and [0179](0179-m4-sprite-recipe.md) are built.

## Input

A PixelLab export of a figure the game makes in its M3 (changed 2026-11-13; not Sanjay: his sprites are built from the 3D
Model, so he is no sprite case). Either:

- a **raccoon from the fight**, or
- the **animal services person** who tries to catch the raccoons.

The Owner picks one and provides both the ZIP and the PNG sheet export, if PixelLab offers both: a figure on a canvas of the
game's size (56×56 unless the game says otherwise), idle in 4 or more directions, steered to the 30° view. If neither is made
yet, any PixelLab figure in 4 directions will do. A raccoon is the better test of `fit` (a low, wide body, not a standing
figure), the person the better test against `[character] height` 52; if the Owner can provide both, take the raccoon first.

## What to find out

- **The ZIP's layout:** folder and file names for rotations and for an animation, the direction words, frame numbering, any
  metadata file. Write it down as the naming rule 0178 and 0179 implement.
- **The PNG sheet's layout:** directions per row or per column, their order, the cell size, gutters.
- **Directions:** that PixelLab's `east` faces screen right, as Kiripix's `e` does (the M3 Q5 rule: from the screen's view).
- **The figure:** its height in px on the 56 canvas (against `[character] height` 52 and the game's 46–58 range); whether its
  edge is a 1 px dark line (which decides `placement = edge` as the default); whether it casts a shadow onto the lowest rows
  (which would put the measured feet in the wrong place); how much it shifts on the canvas between directions.
- **Normals:** the game's `tools/normal_map.py` output and a flat map, side by side in Godot under a `PointLight2D` beside
  a 3D character (Sanjay, `character.mc02`). Which reads better beside the 3D character?
- **Palette:** map one frame with `kiripix op quantize` (or the room's `palette` Op) to the Project palette with 16 colours,
  and note what is lost.

## Output

- A short report in this ticket: the naming rule, the answers above, and an image of the frames before and after the hand fit,
  enlarged, captioned with their sizes.
- A synthetic fixture **description** for 0179: a ZIP in the same layout, with tiny made-up frames (never PixelLab's own
  pixels, so no licence question arises in the repo).
- Any change to 0174's decisions, proposed to the Owner. Don't edit them yourself.

Budget: 30–60k tokens.

## Report (trial run 2026-11-15; status left `todo`)

Inputs: `raccoon.png` (one PNG) and `Animal_control_service_w-Idle.zip` (the animal control worker, idle, 8 directions). No
PNG sheet export and no animation were provided, so the PNG-sheet layout, frame numbering and the `animations/` layout are
**not answered**. Images are in [0175-trial/](0175-trial/); the scripts were scratch only. No Kiripix code was changed.

### The ZIP's layout (the naming rule)

```
Idle/rotations/south.png  south-east.png  east.png  north-east.png  north.png  north-west.png  west.png  south-west.png
metadata.json
```

- The top folder (`Idle`) is the **character's name** (`states[0].character.name`, `folder`), not an animation. Rotations
  are `<name>/rotations/<direction>.png`, full words with hyphens, lower case, no frame number. Every file is a 52x52 RGBA
  PNG, binary alpha (no partial pixels), no scaling to detect (grid scale 1).
- `metadata.json` is **in the ZIP** and lists them: `frames.rotations{direction: path}` and `frames.animations{}` (empty here),
  `character.size` {52, 52}, `directions` 8, `view` "low top-down", `template_id`, `prompt`, `export_version` "3.1".
  Animation paths are unknown; the empty `animations` object suggests `<name>/animations/<anim>/<direction>/frame_NNN.png`, to be
  confirmed on a real animation export. When it exists, `metadata.json`'s `frames` map is the safest source of clip, direction
  and frame order, not the path guess.
- The current `kiripix/recipes/sprite_names.py` already places all eight rotation files correctly (`s`..`sw`, clip `idle`,
  frame 0), by the rule "an innermost folder named `rotations` is no clip".
- **0174 conflict:** "A ZIP holds only PNGs ... a non-PNG is refused at import" would refuse this very export because of
  `metadata.json`. See the proposals.

### Directions

- Eight words as in `PIXELLAB_WORDS`; the order of `metadata.json` is s, se, e, ne, n, nw, w, sw (our compass order).
- **East faces screen right**, west screen left (checked by eye on the enlarged frames: the face profile is on the right in
  `east`, on the left in `west`; the cage hand swings behind). So PixelLab's words map as the rule says (M3 Q5). Mirror
  agreement of the alpha: e vs flipped w 0.93, ne/nw 0.87, se/sw 0.89 (they are not mirrors of each other, which is right for a
  figure holding a cage in one hand: nothing may be mirrored).
- **South is wrong in this export**, by eye and by numbers: (1) the figure does not face the camera. The head is turned to
  screen right with the eyes and mouth looking right, and the body is the same walking 3/4 pose as `south-west` (same raised
  front foot, same cage at screen right), so `south` reads as a south-south-east/south-west blend, not a front view. (2) Its
  outline is a different colour: the dominant edge pixel is (22,14,39) / (26,17,43), and the median edge luminance is 36 against 25
  in the other seven (they use (19,12,35)). (3) Its bounding box is the widest and the furthest right (x 12 to 43, centre 27.5 and
  centre of mass 25.9) while `east` is centred at 23.0. (4) It uses only colours the other seven also use (0 colours of its own),
  so it came from the same palette but was generated apart. `south-east` also has one stray pixel at (17,26) (an isolated grey
  pixel left of the body). A figure-too-different `south` is a source defect that `fit` cannot fix; the fix is regenerating it
  in PixelLab (or a hand edit), so the Owner's action is the finding's `owner_action`.

### The figure

| | canvas | figure height | width | against 52 and 46-58 |
|---|---|---|---|---|
| worker, 8 directions | **52x52** (not 56x56) | 39 to 42 px (s 40, se 40, e 40, ne 39, n 41, nw 40, w 41, sw 42) | 19 to 34 | **below** `[character] height` 52 and below the game's 46-58 range, even with the large head the prompt asked for ("fat, large head"): the height is the bounding box, hair to shoe |
| raccoon | **40x40** | 31 | 31 | a creature: low and wide (31x31), roughly square; nothing to compare with 52 |

- The canvas is the prompt size from `metadata.json` (`size` 52), not a 56 canvas as DEC-044 assumes; and the raccoon's canvas is
  40. So `fit` must take the cell from the sheet's own size (or `height` given), and place onto the Project's character cell;
  the worker's 40 px figure on a 56 cell then has 16 px of free space around it, which is fine for the pivot and outline room.
  `fit.height` (info) would say 40 against 52, a real signal that the figure is small beside the 3D characters.
- **Edge line:** a mostly dark 1 px line, but selective (not on every border pixel): about 70 to 80 percent of the silhouette's
  border pixels are darker than luminance 70 (the dark purples (19,12,35) and (22,14,39), plus some brown at the shoes and a
  mid-grey at the shirt/trousers edge). The cage is drawn as dark wire. `placement = edge` (repainting exactly those pixels) is
  right for the worker, but would leave the lighter 20 to 30 percent of the border as it is; `edge` needs a rule for which border
  pixels count (all of them, or only the dark ones). The raccoon has a dark plum edge too, apparently complete.
- **Shadow:** none in either. The lowest rows are shoe pixels (browns (60,31,18), (68,38,21), (38,23,22)) or the trouser
  hem; no soft or ground-shadow pixels. So the measured feet are the shoes; no `pivot` click needed. The raccoon's lowest two
  rows are the front paws and the tail's tip (8 and 2 px): the "centre of the lowest two rows" lands on the right paws
  (x 15.6 to 19.5 of a 31 px body), i.e. about 3 px off the body's centre. Whether that is right for a creature cannot be said from
  one frame; it is the case a `pivot` Decision is for.
- **Shift between directions (worker):** feet (centre of the lowest two rows) x 21.5 to 32.0 over the eight; bottom row y
  43 to 46 (a 3 px spread); bounding-box centre x 23.0 to 27.5. To put every feet at one pivot the hand fit shifted frames by
  dx -2..+6 and dy +5..+8, so the shift is real and **per direction**: `fit` pivots each frame (or direction) by its feet, as
  0174 decides, and a single shift for the Asset would not do. For a stationary idle with one frame per direction the median
  rule is the frame itself. The `sheet.pivot_drift` Check has nothing to compare within a one-frame clip.
- **Not answerable** from one direction of the raccoon and rotations only: how a walk's feet shift within a direction, the
  stride, the sheet layout of a PNG export, frame numbering.

### The hand fit (images, enlarged x6)

Steps: cut as is (scale 1) -> place each frame on a 56x56 cell with its feet centre at (28, 52) -> palette -> (no outline
change: the source line is kept, `placement = edge` was not applied).

- [trial_before_52px_x6.png](0175-trial/trial_before_52px_x6.png): the eight source frames, 52x52 each (shown on 56x56 grounds), order s, se, e, ne / n, nw, w, sw.
- [trial_after_fit_56px_x6.png](0175-trial/trial_after_fit_56px_x6.png): the same eight on 56x56 cells, a red cross at the pivot (28, 52).
- [trial_palette16_56px_x6.png](0175-trial/trial_palette16_56px_x6.png): after `kiripix op quantize` to the 16-colour palette `[test]/style/palette.gpl` ("Kiripix default", the PICO-8 colours; the only 16-colour palette on the disk).
- [trial_palette_game283_56px_x6.png](0175-trial/trial_palette_game283_56px_x6.png): to the game's art palette (`urban-mystery-club-art/style/palette.gpl`, 283 colours).
- [trial_raccoon_source_pal16_palgame_x8.png](0175-trial/trial_raccoon_source_pal16_palgame_x8.png): the raccoon, 40x40: source, 16 colours, the game's palette.

### Palette

- **16 colours** (strict, no dither): the worker's 43 to 63 colours per frame become **9** (of the 16: only 9 are the nearest to
  anything), the raccoon's 5 become 3. 100 percent of pixels changed (no source colour is in the palette), mean sum of RGB
  error about 65. Lost: all the skin shading (skin becomes orange/pink/white blotches), the grey-lilac overalls collapse to two
  tones (stone and dusk), the dark hair, outline and wire merge to one navy ("night"), the browns merge. The silhouette and alpha are
  unchanged. This palette is a PICO-8 default, so the loss says little about the real one.
- **The game's 283-colour palette**: 34 to 53 distinct colours per frame, mean error about 19 (3 times smaller); the look is kept,
  the skin and the lilac stay. Still 100 percent of pixels changed, since PixelLab's colours are not the palette's. The `palette`
  Stage's `colors` subset (one subset across all frames) was not run (no Project; not part of the trial).
- Alpha is binary in, binary out. No dither was needed to keep the shapes.

### Normals

Done: the game's `tools/normal_map.py` (alpha distance, saturating at 4 px, Sobel, strength 1.6) on `south`, `east` and the
raccoon, and a flat map (128,128,255). Files: `0175-trial/trial_normal_height_{south,east,raccoon}.png`, and
[trial_normals_colour_heightnormal_lit-height_lit-flat_x6.png](0175-trial/trial_normals_colour_heightnormal_lit-height_lit-flat_x6.png)
(columns: colour, height normal, lit with the height normal, lit with flat). **No Godot was available**, so the side-by-side
under a `PointLight2D` beside Sanjay was **not** done, and "which reads better beside the 3D character" is **not judged**. My
own Lambert light (from upper left, ambient 0.35) shows only what the maps contain, not Godot's look:
- the height map is a rounded blob: a bright rim on the lit side and a flat middle (only 20 percent of the opaque pixels of
  `south` are within 3 levels of flat); it darkens one side of the body and gives no detail inside (no face, folds or limbs);
- the cage's wire is treated as many 1 px islands and gets noisy, speckled normals; for the raccoon the tail and ears get
  spiky rims;
- the flat map lights the whole figure evenly (it reads as a flat cut-out, but cannot be wrong or noisy).
The Owner needs to look at both under a light in Godot; the likely answer is that `height` suits a solid figure and `flat` suits
a thin one (the cage), which would argue for a `normals` choice per Asset, as 0174 has, and for `relief` staying optional.

### Synthetic fixture for 0179 (made-up pixels, no PixelLab data)

A generator in the test (not committed images from PixelLab), writing a ZIP in the same layout:
- `Fix/rotations/<8 direction words>.png`, 8x8 RGBA, one flat-coloured block per direction (a 4x5 body, a 2x1 "foot" row at the
  bottom, a different colour per direction and a 1 px dark edge), binary alpha; canvas 8x8; feet at a different x or bottom row per
  direction (shifts of 0 to 3 px, to test the pivot by feet).
- `metadata.json` like the real one (`frames.rotations`, empty `animations`, `character.size` 8, `directions` 8, `export_version`
  "3.1") with a made-up `prompt` and ids.
- Variants: (a) a 4-direction ZIP (`south`, `east`, `north`, `west` only) for `directions = 4`; (b) one rotation missing
  (`frames.direction_missing`); (c) a ZIP with `animations`: `Fix/animations/Walk/<dir>/frame_000.png`..`frame_002.png`
  guessed as above, with a note that the layout is a guess until a real animation export is seen; (d) a x4 upscale (each pixel
  a 4x4 block) for `detect_grid`; (e) a `../evil.png` entry, a non-PNG entry and an absolute path for the refusal tests;
  (f) a frame with one half-transparent pixel (`fit.alpha_partial`); (g) a "bad south" with a different outline colour, a case
  for no Check yet (see below).
- A PNG sheet fixture: 8x8 cells, 4 columns by 2 rows, to test `layout` rows and columns; and a one-frame 4-row sheet.

### Proposed changes to 0174 (for the Owner; not edited)

1. **Allow `metadata.json` in the ZIP.** "A ZIP holds only PNGs" refuses a genuine export. Allow PNGs and one `metadata.json`
   (size limit, no other non-PNG); read its `frames` map when present, else the naming rule.
2. **The top folder is the character's name, not the clip.** Rotations give the clip `idle`; for animations take the clip from
   `metadata.json` or the folder name below `animations/`, made snake_case, as already planned, but say so: the rule must not take
   the top folder (`Idle`) as a clip name, a trap for a character called `Walk`.
3. **The canvas is not always 56.** The worker is 52x52 and the raccoon 40x40: `fit` must place onto the Project's cell from
   the source cell's own size; say that the common cell is the largest source cell or the Project's character cell, and that a
   figure well under `height` (40 against 52 here) is reported by `fit.height` and never rescaled by `grid`. Consider a `scale`
   choice for the owner who wants it bigger (nearest, whole numbers only).
4. **`placement = edge` needs a definition.** The real edge is dark on about 75 percent of border pixels, and coloured elsewhere.
   Either repaint every silhouette-border pixel with the outline colour (loses the coloured edge pixels), or only those darker
   than a threshold (keeps them). Decide, and add the choice as a parameter. For the raccoon the line is complete.
5. **A Check for a frame that does not match its direction** is out of reach; the worker's `south` shows the case (a bad
   direction passes every proposed Check). Keep it an owner judgement, but the frame strip should show the eight directions side
   by side at import so it's seen before the pipeline runs; and add a cheap Check: `frames.edge_colour_differs`
   (info) when one direction's dominant outline colour differs from the others', and `frames.stray_pixel` (info) for an isolated
   pixel (the `south-east` here).
6. **Feet of a creature**: the lowest-two-rows centre was about 3 px off the raccoon's body centre. Keep the median-of-feet rule and the
   `pivot` Decision, but have the first `fit` report the feet it measured (it records `feet`) so a click is easy; no change
   of the rule is justified from one frame.
7. **The Table's "Idle in 4 or more directions"**: the export names the animation `Idle` with 8 rotations only (a still per
   direction, no animation), so "the clip is `idle`" is by convention; 0174 should say that a rotation-only export is a
   one-frame clip `idle` and that the user's animation name is ignored then.
8. **Normals:** keep `height`, `flat`, `pass` as 0174 says; add that the wire/thin parts of a figure should be allowed to
   fall back to flat (e.g. a `normal_min_area`), or simply accept `flat` for such an Asset. Not judged in Godot yet.

Open for the Owner: the Godot side-by-side (normals), a PNG sheet export, and an animation export (the missing layouts).

## Owner decisions (2026-11-15)

- The proposals above are accepted; 0174 is to be updated to match them.
- The canvas is settable in PixelLab: 52 was asked for and a smaller figure came back, so the next export asks for 64 px.
- Animation and PNG sheet exports: not available now (animations cost real money, and the Owner wants the service's value
  confirmed first). The `animations/` layout stays a guess in the 0179 fixture description. Not a blocker for this ticket or
  the M4 gate. The Owner will look for a free way to generate animations.
- Normals in Godot: not compared in this ticket (skipped by the Owner).
