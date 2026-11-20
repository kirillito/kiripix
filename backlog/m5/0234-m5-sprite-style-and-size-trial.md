---
status: done
milestone: M5
agent: imaging-engineer
type: trial
---

# M5 trial: PixelLab sprites beside 3D characters: size and style

Found at the M4 gate ([0142](../m4/0142-m4-gate.md), 2026-11-16): in Godot, beside the four mc03 bodies, "some of the sprites
from PixelLab are too small, and we need to deal somehow with the difference in style". Milestone M5 is a placeholder.

## What the gate saw

- **Size:** `sprite.animal_control_worker` is 42 px tall (`fit.height`) against the bodies' 52; `sprite.raccoon` 34 px. Both
  came from PixelLab rotations at its 52 and 40 px canvases ([0175](../m4/0175-m4-sprite-pixellab-export-trial.md)). `fit`
  `grid` never rescales, and `downscale` can't make a figure taller.
- **Style:** the bodies are 3D renders with 2 cel bands (`band_edge` 0.62, smoothed), a dark inner line per part, the
  palette's ramps and normals from the Model. A PixelLab figure has its own shading, its own outline (kept by
  `placement=edge`, recoloured to 195), more colours per part and "pillow" normals from its silhouette.

## Options to try (on the worker and the raccoon, next to mc03 in a ch01 room and in the kitchen)

1. **Bigger source, then `downscale`:** ask PixelLab for a larger canvas (64, or 96–128 px), then `fit mode=downscale
   height=52` (the raccoon at its own height). Kiripix's downscale and palette then set the pixel scale, which may also pull
   the style toward the rooms'.
2. **Steer PixelLab with the 3D look:** its `init_image` from a body's `model` still (`still.png`, DEC-044), so the pose,
   camera and proportions match the 3D route.
3. **Flatten in Kiripix:** `palette colors` lower (fewer shades per sprite, nearer 2 bands), an inner line by colour
   regions where a sprite has no materials, and the `flat` normals choice against `height`.
4. **Move people to the 3D route:** the Project already builds NPCs from a base Model (`npc_*`, 0224/0227); the sprite route
   could be kept for creatures (the raccoon, the "Waiting Ones"), where a 3D Model is the expensive part.

## What to record

- Sheets at 1x and 4x, each option beside mc03_male_clothes01 and mc03_female_clothes01, and a Godot capture under a
  `PointLight2D`.
- Owner time per sprite for each option, and PixelLab cost (DEC-004: $0 budget).
- The Owner's choice, and a build ticket for each part chosen.

## PixelLab requests (prepared 2026-11-19; for the Owner)

No Kiripix code. Init images are in [0234-trial/pixellab/](0234-trial/pixellab/), made from the `idle` frame 0 of each
direction (`work/finish/color/idle/<dir>/000.png`), not from `still.png`: the still is a T-pose, so it gives the camera and
proportions but the wrong pose.

### What changes the targets

- **The bodies are taller than 52 on screen.** `height = 52` is the Model's standing height times cos(elevation). The
  visible idle figure, hair to shoe with the outline, is **56 to 60 px** (mc03_male_clothes01: s 59, e 57, n 56;
  mc03_female_clothes01: s 58, e 55, n 56). `fit mode=downscale` measures the visible idle `s` figure, so a worker of the bodies'
  height needs **`height=58`**, not 52. The gate's "42 against 52" is really 42 against about 58.
- **PixelLab's figure fills about 0.78 of its canvas** (worker 40–42 on 52, raccoon 31 on 40). The figure must be taller than
  the target, because downscale only shrinks (`fit.too_small`). So the Owner's planned **64 px canvas gives a figure of about
  50 px, too small for 58**. The worker needs 96 to 128 (about 75 to 100 px). The raccoon on 64 gives about 50, enough for its
  own target (34 now).
- **The camera:** `top34_8` has an elevation of 30°. PixelLab's "high top-down" is about 35° and "low top-down" (used for both
  exports so far) about 20°. Ask for **high top-down**.

### What PixelLab offers (its docs, read 2026-11-19; the pricing page was not reachable)

- **Create 8-directional sprite (Pro):** up to 168×168, and takes a reference or style image. It **needs a Tier 1
  subscription**, which DEC-004's $0 budget rules out unless the Owner decides otherwise.
- **Rotate:** canvases of 16, 32, 64 or **128** only, and takes an **init image** (strength 0–900; 300–600 keeps the shape
  while letting it redraw). Whether the free trial includes it is not documented; the remaining generations are shown on the
  account page.
- The tool behind the two existing exports (`template_id` "mannequin" / "cat") and its size limit on the free trial: unknown.

### The runs to make (8 directions each, idle rotations, ZIP export)

| # | Figure | Option | Canvas | PixelLab input | Then in Kiripix |
|---|---|---|---|---|---|
| A | worker | 1 | 128 (else 96) | the same prompt as before, high top-down | `fit mode=downscale height=58` |
| B | raccoon | 1 | 64 | the same prompt as before, high top-down | `fit mode=downscale height=34` |
| C | worker | 2 | 128 | init `init_mc03_female_clothes01_<dir>_128.png` (figure ×2, 116 px), strength about 400 | `fit mode=downscale height=58` (exactly ×2 back) |
| D | worker | 2 | 64 | init `init_mc03_female_clothes01_<dir>_64.png` (figure ×1, 55–60 px) | `fit mode=grid` (no rescale) |

- Prompts used before: worker "Animal control service worker, wearing grey overalls, carrying a metal wild animal trap.
  Female, fat, large head. Facing south, top-down 3/4 view"; raccoon "North American raccoon, all four paws on the ground,
  with grey, black and white fur. Top-down 3/4 view."
- C and D: one init per direction if the tool rotates per direction; else the `south` one. The male `south` inits are there
  for comparison only. [preview_mc03_female_clothes01_idle_8dirs_x4.png](0234-trial/pixellab/preview_mc03_female_clothes01_idle_8dirs_x4.png)
  shows the eight inits.
- The raccoon has no 3D body to steer it, so option 2 doesn't apply to it.
- Drop each ZIP in `C:/Workspace/[assets]/0234/` named `<A..D>_<figure>.zip`, and note the tool, the settings and the
  generations or credits spent. That is the "PixelLab cost" row this ticket records.

### Owner's limits and the front candidates (2026-11-19)

- The Owner's PixelLab can't take reference images, and an 8-direction run has a 64 px canvas at most. So **option 2 is out**
  and runs A, C and D above are void; option 1 is at 64.
- Four front views of the worker on 64 canvases (`urban-mystery-club/references/pixel-lab/pixellab-Animal-control-service-worker--*.png`)
  are **54 to 60 px tall**, the bodies' own height, so they need `fit grid`, with no rescale. Compared beside mc03_male and
  mc03_female_clothes01 in [front_candidates_1x.png](0234-trial/front_candidates_1x.png) and
  [front_candidates_4x.png](0234-trial/front_candidates_4x.png) (left to right: mc03 male, mc03 female, then …133311,
  …159609, …181255, …244526):

| Candidate | Height | Colours | Read |
|---|---|---|---|
| …133311 (green cap) | 58 | 24 | flattest shading, nearest the bodies' bands; faces the camera most squarely; **the pick** |
| …159609 | 60 | 50 | painterly face and hair, turned to screen right |
| …181255 (yellow shirt) | 58 | 60 | most rendered (highlights, many shades), furthest from the bodies |
| …244526 (red cap) | 54 | 25 | flat like the pick, but turned well to the side, so a poor `south` |

### The 64 px rotations (2026-11-19)

The Owner's exports, both 64×64, "high top-down", 8 rotations, no animation:
`urban-mystery-club/references/pixel-lab/Animal_control_service_worker_wearing.zip` (it replaces the 2026-11-16 file of the
same name; that one is kept as the Project's imported copy in `assets/sprite/animal_control_worker/src/sheets/`) and
`North_American_raccoon_all_four2.zip`. Sheet beside mc03 (rows: mc03_male, mc03_female, worker, raccoon; s, se, e, ne, n,
nw, w, sw): [rotations_64_1x.png](0234-trial/rotations_64_1x.png), [rotations_64_4x.png](0234-trial/rotations_64_4x.png).

| | Height | Width | Colours | Edge | Clean |
|---|---|---|---|---|---|
| worker | **57–58** in all eight (bodies 54–60) | 22–41 | 24 (s), 35 (others) | dark (35,34,46) with brown (75,41,7) at the hair and shoes, so it isn't a full line | no stray pixels, no partial alpha; `south` uses no colours the others don't; the chosen front survived as `south` |
| raccoon | **50–52** | 48–53 | 15–26 | a full dark line (15,13,12) in all eight | the same |

- **Worker:** the size gap is closed by the canvas alone. It needs `fit grid`, with no rescale, and the feet shift per direction
  (bounding-box centre x 29.5 to 35.5), which `fit` already pivots. The trap stays in her right hand through the turn. The style
  gap remains: 35 colours against the bodies' few bands, a softer, more rendered face, and a partial outline. That gap is
  option 3's job.
- **Raccoon:** now 50–52 px tall, almost the worker's height, and chibi (a big head and eyes, sitting up in `s`). For
  "the raccoon at its own height" it needs `fit mode=downscale height=<h>` (34 was its size at the gate: a scale of about 1.5).
  Its style is further from the bodies than the worker's (a cartoon face and a thick line).

### Re-imported and built (2026-11-19)

Owner's choices: the raccoon at **32 px**; the new exports **replace** the old ones.

- Old sheets moved out of the Project (not deleted) to `C:/Workspace/[assets]/0234-old/` (`animal_control_worker_2026-11-16.zip`,
  `raccoon_2026-11-16.zip`). They couldn't be snapshotted: their `sheet`s were stale against today's Kiripix
  (`snapshot.not_built`).
- Imported: `sprite.animal_control_worker` sheet `59ac90046d2e93a5`, `sprite.raccoon` sheet `c496b6e60d0e5719`.
- `kiripix set sprite.raccoon fit mode=downscale height=32`; the worker kept `fit mode=grid`. Built through `sheet` with the
  Asset settings as they were (`palette` colours 16, `finish` outline 195 at `placement=edge`, `normals=height`), and exported
  (`kiripix export <asset>`: no file refused, nothing backed up).
- Findings: worker `fit.height` info (58 px against the Project's 52, the bodies' visible height) and `fit.cell_grew` (cell
  53 × 60, `s` reaches 6 px further left, the trap); raccoon `fit.height` 32 = 32.
- Built, beside mc03 (rows: mc03_male, mc03_female, worker, raccoon; s, se, e, ne, n, nw, w, sw):
  [built_64_1x.png](0234-trial/built_64_1x.png), [built_64_4x.png](0234-trial/built_64_4x.png).

| | Height | Colours (all eight) | |
|---|---|---|---|
| mc03_male_clothes01 | 56–60 | 31 | |
| mc03_female_clothes01 | 54–60 | 24 | |
| worker | 57–58 | **17** (35 per frame in the source) | the palette pass flattened the face and the overalls toward the bodies' bands; the outline is the bodies' 195 |
| raccoon | 31–32 | **17** | the mask, eyes and tail rings survive the ×1.6 downscale |

- **Option 1 at 64 px is enough for size:** the worker matches the bodies with no rescale, and the raccoon comes down cleanly.
- **Option 3 is partly in already:** `palette colors=16` is what pulled the worker's 35 colours to 17. Lower `colors` and an
  inner line by colour region are still untried.
- **PixelLab cost:** the Owner's free generations (4 fronts + 2 eight-direction runs); $0.
### The Godot capture (2026-11-19)

Godot 4.7.2, the game project, a one-off script (scratch only; it adds nothing to the game) that builds the gate's set: the
room, `CanvasModulate` (0.5, 0.5, 0.58) and a `PointLight2D` (energy 1.4, height 30, the radial ramp of `dev/gate_m4.gd`).
The four stand on open floor, 44 px apart, at `idle` frame 0. First run `godot --headless --path game --import`: a script
run doesn't re-import, and an export that changes `color.png` is drawn from the old import, cut by the new regions.

- [godot/lineup_1x.png](0234-trial/godot/lineup_1x.png), [godot/lineup_4x.png](0234-trial/godot/lineup_4x.png): the laneway
  (top) and the kitchen (below), each: `s` light left, `s` light right, `se`, `sw`. The full frames are in
  [godot/](0234-trial/godot/) (`<room>_<n>_<dir>_full.png`, 640 × 360).
- **The feet don't share a ground line:** the sprites stand about 5 px higher than the bodies at the same position. A body's
  pivot is the ground point under it (`pivot` y 67 in a 78 cell), and its shoes reach 6 px below that on screen (the 30° view).
  A sprite's pivot is the centre of its lowest two rows (y 58, shoes 1 px below). The sprite route needs the same ground point.
- Under the light, the bodies shade by their Model's normals. The worker shades as one rounded blob (`normals=height`).

### Fewer colours (2026-11-19)

Worker and raccoon at `palette colors` 16, 12 and 8, kept as snapshots `colors_16`, `colors_12` and `colors_8` (the bodies
too, unchanged): [colors_16_12_8_x1.png](0234-trial/colors_16_12_8_x1.png),
[colors_16_12_8_x4.png](0234-trial/colors_16_12_8_x4.png) (rows 16, 12, 8; s, se, e).

- **Lower `colors` doesn't flatten, it greys.** One colour budget is shared by the whole Asset, so it keeps the shades
  covering the most pixels and drops the small hues first: at 12 the cap loses its green; at 8 the hair, skin and shoes go grey.
  The shading inside the overalls stays. **16 stays**, and both sprites are back at 16. The export is unchanged: `export`
  wrote nothing.
- What would flatten a sprite toward the bodies is what the 3D route has: **colours per part**. Group the sprite's colours
  into parts by hue (skin, hair, cap, overalls, shoes, trap), then keep 2 to 4 shades per part, like the bodies' ramps of 4.
  Those ramps could join the Project's ramp table, which would also give sprites the skin and hair swap. Then an
  **inner line by colour region** (where two parts meet), as the bodies have by material. Both need code.

### Build tickets

Filed 2026-11-19 with the Owner's go: 1 is [0318](0318-m5-sprite-pivot-at-the-ground-point.md), 2 is
[0319](0319-m5-sprite-palette-by-parts.md), 3 is [0320](0320-m5-sprite-inner-lines-by-part.md). 4 is a trial, run here.

1. **The sprite pivot at the ground point** (imaging-engineer): `fit` puts the pivot where a body's would be, a few px
   above the lowest rows (the bodies: 0.1 × height), so feet share a line in the game. Small.
2. **Sprite palette by parts** (imaging-engineer): hue regions as parts, `shades` per part, ramps the Project table can take.
3. **Sprite inner lines by colour region** (imaging-engineer): `inner_lines` for a sprite, on the borders between its parts.
4. **From the 3D end**, settings to try before any code (render re-runs Blender over every clip, and these are production
   bodies, so only with the Owner's go): more volume, so a body reads less flat beside a PixelLab figure
   (`render shadow`, `band_edge`, `band_smooth` and 4 vs 5 `bands`), kept as snapshots and compared like the colours above.

### From the 3D end: the render trial (2026-11-19)

Run with the Owner's go on mc03_male_clothes01 and mc03_female_clothes01; each variant re-rendered, built and kept as a
snapshot, then today's settings restored (`bands` 4, `shadow` 0.6). The rebuilt bodies match the game's export
(`export --dry-run`: nothing would be written).

- **`bands` 5 is refused:** `render.bands` is 2 to 4 (`set.invalid_value`), matching the Project's ramps of 4. Those two
  variants never ran, and their snapshots were dropped.
- **`shadow` 0.75 against 0.6:** [render_shadow_x1.png](0234-trial/render_shadow_x1.png),
  [render_shadow_x4.png](0234-trial/render_shadow_x4.png) (snapshots `render_base`, `render_shadow75`). Barely
  different: the white shirt goes a shade greyer, and the skirt and trousers a little darker in shadow. The body still reads as
  4 flat steps per part.
- **What caps the 3D end:** each part's colours are its Project ramp of 4 (`[character] ramps`, `palette parts`), so a
  body can never show more than 4 shades of a part, whatever `render` does. A PixelLab figure's softer volume would need
  longer ramps (5 to 6) across the Project. That changes every body's palette and the ramp table the game's swap uses, so it's
  the Owner's call, not a ticket yet.
- The `sheet.part_vanishes` warnings in the run (the `under`, `underwear`, `bottom_r` and `stripe` materials in some `attack`,
  `run` and `phone_in` frames) are there with the restored settings too, so they predate this trial.
- **So the meeting point is on the sprite side:** bring sprites down to the bodies' 4 shades a part
  ([0319](0319-m5-sprite-palette-by-parts.md)) and their lines ([0320](0320-m5-sprite-inner-lines-by-part.md)), rather than
  bring the bodies up.

## Owner's choice (2026-11-19)

- **Option 1, kept:** PixelLab at a 64 px canvas, "high top-down"; a person at its own size (`fit grid`), a creature brought
  to its height by `fit mode=downscale` (the raccoon at 32).
- **Option 2, dropped:** the Owner's PixelLab takes no reference image, and its 8-direction tool needs Tier 1 (DEC-004: $0).
- **Option 3, built by tickets:** [0318](0318-m5-sprite-pivot-at-the-ground-point.md) (pivot), [0319](0319-m5-sprite-palette-by-parts.md)
  (palette by parts) and [0320](0320-m5-sprite-inner-lines-by-part.md) (inner lines). Sprites come down to the bodies' 4 shades a
  part, rather than bodies up to PixelLab's.
- **Option 4, as needed:** people who matter go the 3D route (the `npc_*` base Models); the sprite route stays for creatures
  and minor figures.
- Longer ramps for the bodies (5 to 6 shades): not taken.
- **Owner time:** about 10 minutes for the worker and the raccoon together in PixelLab (4 front tries for the worker, then an
  8-direction run for each), with free generations ($0). The Owner calls it lucky: a worse first try costs more runs, so expect more on average.

## Acceptance criteria

- [x] The sheets and the capture, their paths listed here.
- [x] The Owner's choice recorded, and the build tickets filed.
