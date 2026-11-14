---
status: done
milestone: M4
agent: character-pipeline
type: trial
parent: 0161-m4-characters-after-the-m3-gate.md
depends_on: [0148-m4-render-material-pass.md]
---

# M4: trial: a flatter, more 2D look for characters

Spec §1 (a Sea of Stars-like look) and §6.3 (render, palette, finish). Found at the M3 gate
([0117](../m3/0117-m3-gate.md)), 2026-11-11: "Lighting on character looks amazing, however the result looks too different
compared to scenes background: character is pixelated, but at the same time it looks too 3D-like." The Owner asked for more
optional shading styles, such as cel or toon, to give characters a unified 2D look.

## What may make it look 3D

Before building a shader, find which of these the eye reads as "3D", on mc02 beside a painted ch01_dungeon room in Godot:

- **The texture's own gradients.** mc02's albedo is textured, so `render` has 60 to 80 colours per frame before `palette`
  ([0105](../m3/0105-m3-toon-shading.md)). Painted sprites use a few flat colours per part.
- **Smooth light across a part.** Three bands of half-Lambert follow the surface's curve, which reads as volume.
- **The normal map in Godot.** A `PointLight2D` over the normal map lights the character per pixel, as a 3D surface. The
  rooms are never re-lit (the game's lighting option A).
- **No inner lines.** Hand-drawn sprites outline parts against each other (hair, face, sleeves); the silhouette alone
  ([0106](../m3/0106-m3-outline-method-trial.md)) leaves the inside soft.

## What to try

Each as an option on the existing Stages, rendered on mc02 in all 8 directions, idle and walk:

1. **Flat parts:** each material's albedo replaced by its mean (or its dominant colour), then the toon bands. Needs the
   material pass of [0148](0148-m4-render-material-pass.md).
2. **Two bands with a hard terminator** and no rim, as cel shading: `bands=2`, the shadow's edge moved toward the light.
3. **Part ramps:** each part mapped to its own 2- or 3-colour ramp ([0147](0147-m4-character-palette-ramps.md)), so a part
   never shows more than its ramp.
4. **Inner lines at part borders:** a line where the material changes (not where depth jumps), in a darker colour of the part
   or the outline colour.
5. **A weaker normal map:** the normal pass flattened toward the camera (a `normal_strength` on `finish`), so 2D lights tint
   the character more than they shape it.

## Preliminary work (2026-11-13)

**Subject: mc03, not mc02** (the Owner, 2026-11-13). Use `character.mc03_male_clothes01` and `character.mc03_female_clothes01`
in the art Project, the game's M03 bodies. mc02's render predates the material pass (0148), so it has no `material/`. The mc03
bodies have one, with 9 materials: dragon, eyes, hair, jacket, jeans, shoes, skin, sole, tee. Both are built through `finish`
with `bands = 2`, `shadow = 0.22`, the light at -45°/35°, `outline_colour = 195`, `eyes = stamp`, and no palette `parts`.

**The harness**, in `C:\Homespace\urban-mystery-club-art\.kiripix\trials\0160-flat\` (gitignored), run with
`C:/Homespace/kiripix/.venv/Scripts/python.exe`:

- `albedo-project/`: a scratch copy of the art Project with only the two bodies, rendered with `render shadow = 0`. So its
  colour pass is each body's unlit albedo, and its normal, depth, mask and material passes are the same as the real render's.
  Each body rendered in 23 to 38 s (408 frames: idle 1, walk 32 or 31, attack 69, × 8 directions).
- `harness.py`: `Asset(name).frames()` gives each frame's passes as numpy arrays (albedo, unit normals in camera space,
  depth, mask, material). `reshade(...)` is `render_frames.shade` re-implemented on them. `build(asset, name, colour_fn,
  normal=..., palette={...}, finish={...}, post=...)` writes a variant's render folder, then runs the **real** character
  `palette` and `finish` on it, through core's `AssetGraph.stage_run` with the upstream folders swapped. `sheets(asset,
  [(label, folder), ...], tag)` writes `sheets/<tag>_4x.png`: idle, walk and attack in the 8 directions on the dungeon room's
  floor. It also writes `<tag>_room_1x.png` and `<tag>_room_4x.png`: the figures standing in `ch01_dungeon_r03`'s Plate.
  `colour_stats` counts colours per frame and per material.
- `trial.py`: the baseline. It rebuilds the shipped look from the albedo and compares it with the Assets' own frames
  (`baseline.json`, `sheets/*_baseline_*`). **Options 1 to 5 are not built yet**: each is a variant on top of this.

**Fidelity:** the re-shade starts from 8-bit albedo and 8-bit normals. After `finish`, 0.17 % (male) and 0.35 % (female) of
the cells' pixels differ from what ships. In the render, 29,222 opaque pixels differ by only 1 or 2 levels, which is rounding.
Only 190 of 227,563 (0.08 %) fall in another band. Side by side, the baseline and the shipped frames look the same.

**First numbers** (mean distinct colours per frame, male; the female is within about 1 colour):

| | per frame | skin | jeans | jacket | hair |
|---|---|---|---|---|---|
| albedo | 39.5 | 8.8 | 7.6 | 6.1 | 5.0 |
| render (2 bands) | 58.9 | 12.8 | 12.9 | 9.8 | 8.0 |
| finish (what ships) | 14.4 | 3.0 | 2.0 | 2.0 | 2.0 |

So the albedo has gradients, but after `palette` each material already has only about 2 colours. Option 1 (flat parts) may
change less than expected. The volume may come more from where the band edge falls: it follows the surface's curve. It may
also come from the normal map in Godot and from the missing inner lines. The sheets should test this, not assume it.

**Not done yet:** the Godot capture. The M3 gate's `C:\Homespace\urban-mystery-club-art\.kiripix\trials\0117-gate\lit.gd`
(mc02, 8 directions, a `PointLight2D` from the left and the right) is the pattern to adapt. It needs the variant exported into
the game project.

## Results (2026-11-13)

All in `C:\Homespace\urban-mystery-club-art\.kiripix\trials\0160-flat\` (gitignored). Nothing in `kiripix/`, the art Project's
Assets or the game changed. `options.py` builds the variants, `closeup.py` and `godot.py` make the sheets. Every variant went
through the real `palette` and `finish`, on both bodies, all 408 frames (12 to 34 s each).

**The variants** (`variants/<asset>/<name>/`):

| Name | What it is |
|---|---|
| `baseline` | what ships, rebuilt from the albedo |
| `1_flat` | each material's albedo replaced by its mean over all frames, then the bands |
| `2_cel` | two bands, the band edge at half-Lambert 0.62 instead of 0.5 |
| `2_cel_s` | the same, on normals smoothed inside the silhouette (a Gaussian, 1.5 px) |
| `3_ramps2`, `3_ramps3` | palette `parts = skin,hair,jacket,jeans,shoes,tee`, ramps of 2, or of 3 with 3 bands |
| `4_lines_o`, `4_lines_d` | a 1 px line where the material changes, on the farther pixel: in the outline colour, or in a darker palette colour of that part |
| `12_flat_cel_s`, `24_cel_s_lines_d`, `124_flat_cel_s_lines_d`, `1234_flat_cel_s_ramps2_lines_d` | combinations |

Option 5 is not a variant: `godot.py` flattens a variant's finished normal pass toward the camera,
`normalise(lerp((0, 0, 1), n, strength))`, with strength 1, 0.5, 0.25 and 0.

**The sheets** (`sheets/`, each for `mc03_male_clothes01` and `mc03_female_clothes01`):

- `<asset>_closeup_a_idle_8x.png`, `_closeup_b_idle_8x.png`, and the same for `walk`: every variant side by side at 8x,
  directions s, se, e and n, captioned. **Start here**; the options differ by a few pixels and are hard to tell apart at 4x.
- `<asset>_options_1_2_4x.png`, `_options_3_4_4x.png`, `_combinations_4x.png`: idle, walk and attack in the 8 directions.
- The same three tags with `_room_1x.png` and `_room_4x.png`: the figures standing in `ch01_dungeon_r03`.
- `<asset>_godot_<set>_<light>_5x.png`: the Godot capture. The sets are `5_normal_strength`, `options` and `combinations`;
  the lights are `left`, `right` and `lamp`.

**The Godot capture:** Godot 4.7.2, windowed, in a project of its own (`godot/`, with the game's display settings: 640 x 360,
Compatibility, nearest filter). It does not go through `export`: `capture.gd` loads each finished idle frame and its normal
frame into a `CanvasTexture` on a `Sprite2D`, which is what the exported `texture.tres` is. The 8 directions stand on the
room's Plate under one warm `PointLight2D` (height 40, energy 1.3), placed left, right, and as a lamp in the middle. The Plate
is left out of the light's mask (rooms are never re-lit) and the sprites are dimmed to an ambient of 0.55. Walk and attack
were not captured in Godot.

**What the sheets show** (Claude's reading; the choice is the Owner's):

- **1, flat parts: almost no change.** `palette` already leaves each part with 2 colours (the table above), so the albedo's
  gradients are gone before the sprite ships. Colours per frame: 14.4 before and after. Not worth a parameter by itself.
- **2, the band edge: the biggest change in the sprite.** At 0.62 the shadow covers more of each part. With the normals
  smoothed it falls as one large shape per part (half the jacket, one side of each leg), not as flecks that follow folds.
  That reads as drawn. Without the smoothing the edge is noisier than the baseline's.
- **3, part ramps: no flatter, and the colours move.** Each part already has 2 colours. Giving each part colours no other part
  may use pushes the tee from cream to mint, and the shoes down to 1 colour. Ramps are for recolouring (0147), not for this.
- **4, inner lines: they separate the parts, and they are heavy at 52 px.** In the outline colour, the collar, cuffs and
  waist read clearly as hand-drawn, but the line takes 1 px from a face 8 px wide. In the part's darker colour it is softer;
  on skin beside the jacket it can look like dirt. Colours per frame rise from 14.4 to about 20 with the darker colours.
- **5, the normal map: the biggest change in Godot.** At strength 1 the light picks out each pixel's facing, so a lit figure
  is a shaded solid beside a flat room. At 0.5 the side toward the light is still brighter, without the bright specks. At 0
  the light only tints the figure, as it would a painted sprite.

**Suggested:** build 2 (`edge` and `smooth` on `render`) and 5 (`normal_strength` on `finish`); offer 4 as an option that is
off by default; drop 1 and 3 for this purpose. `12_flat_cel_s` and `2_cel_s` look the same, so the combination to judge is
`2_cel_s` or `24_cel_s_lines_d` at normal strength 0.5 or 0.25.

**Not tried:** other values of the edge (only 0.62) and the smoothing (only 1.5 px); a deeper `shadow` than 0.22; lines only
at chosen borders (say, jacket against tee, but not hair against skin). In the build, `edge` and `smooth` belong in
`render_frames.shade`, so option 2 needs a re-render; the trial did it on the 8-bit passes.

**The Owner's choice (2026-11-13):** `24_cel_s_lines_d` looks best: option 2 with the smoothed normals, plus option 4 in the
part's darker colour. Start with that. Option 5 comes after, and is first tried in Godot (the game's side), not in `finish`.
Options 1 and 3 are dropped for this purpose. Every new parameter defaults to the look as it is now, and the Owner accepts
rebuilding the characters once. The trial's edge (0.62) and smoothing (1.5 px) are the mc03 values to start from.

The build tickets: [0213](0213-m4-render-cel-band-edge.md) (`band_edge` and `band_smooth` on `render`),
[0214](0214-m4-inner-lines-op.md) (the Op), [0215](0215-m4-finish-inner-lines.md) (`inner_lines`, `line_skip` and
`line_darkness` on `finish`; `dark` is refused with palette `parts`), and
[0216](0216-m4-inner-lines-with-part-ramps.md) (lifts that refusal). No ticket for option 5 until the Godot side is tried.

## What to record, in this ticket

- Sheets of each option and combinations, on mc02 next to a ch01_dungeon room at 1x and 4x, and a Godot capture under a
  `PointLight2D`.
- The Owner's choice: which options become parameters, and their defaults. A follow-up ticket for each one to build.

## Acceptance criteria

- [x] The sheets and captures above, their paths listed here (on mc03, as the Owner asked).
- [x] The Owner's choice recorded, and the build tickets filed.
