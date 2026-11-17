---
status: done
milestone: M4
agent: character-pipeline
type: trial
parent: 0161-m4-characters-after-the-m3-gate.md
depends_on: [0213-m4-render-cel-band-edge.md, 0215-m4-finish-inner-lines.md]
---

# M4: trial: how strongly a character's normal map should light it in Godot

Spec §1 (a Sea of Stars-like look) and §6.3 (finish: the normal pass). Left over from the trial
[0160](0160-m4-flatter-character-look-trial.md), 2026-11-13. The Owner chose the shading and the inner lines
([0213](0213-m4-render-cel-band-edge.md), [0215](0215-m4-finish-inner-lines.md)) and wants to deal with the normal map
afterward, in Godot first.

In 0160's Godot capture (idle frame, one `PointLight2D`, mc03 male, normals flattened toward the camera) a full-strength
normal map lights each pixel by its facing, so a lit figure reads as a shaded solid beside a flat painted room. At 0.5 the
side toward the light stayed brighter without the bright specks. At 0 the light only tinted the figure. The rooms are never
re-lit (the game's lighting option A), so the figure should not look more 3D than the room it stands in. That capture
flattened the finished normal pass in numpy, outside Kiripix, and did not use the new look.

## What to find out

On the new look (`band_edge=0.62`, `band_smooth=1.5`, `inner_lines=dark`, from 0213 and 0215), on the mc03 bodies:

1. **Where to flatten the normal.** Three places, each rendered and captured the same way:
   - **In the game:** the `CanvasTexture`'s own normal map unchanged, and a lower light `height` or a lower energy on the
     `PointLight2D`, or a `normal_strength` on the sprite's material. Costs Kiripix nothing.
   - **In `finish`:** a `normal_strength` parameter that lerps each normal toward `(0, 0, 1)` and renormalises, as the 0160
     capture did. Needs a ticket and changes the exported `normal.png`.
   - **In `render`:** the same on the normal pass, so `depth` and the others are unaffected.
2. **What strength.** 1, 0.75, 0.5, 0.25 and 0, under the lights of 0160 (left, right, a lamp in the middle) and under the
   game's own lights if there is a room with one.
3. **Whether the lit side still tells the direction.** At low strength the light should still brighten the side it comes from
   in all 8 directions, and not wash the figure out.
4. **Whether it holds in motion.** Walk and attack, not only the idle frame. A normal that flickers between frames shows here.
5. **Whether `normal_levels` matters.** Today the pass is quantised to 8 values per axis. Try 4 and 16 at the chosen strength.

## How

- Reuse `C:\Homespace\urban-mystery-club-art\.kiripix\trials\0160-flat\` (gitignored): `godot/capture.gd`, `godot.py` and the
  variants. Add the new look as a variant, and capture walk and attack frames as well as idle.
- The game's own scene, `res://art/kiripix/character/<name>/<name>.tscn`, is the thing that ships: capture it as the game
  builds it where it differs from the trial's `Sprite2D`, so a light setting found here works there.
- Sheets at 5x with the strength and the light in each caption, not 1x.

## What to record, in this ticket

- The sheets and captures, with their paths.
- The Owner's choice: where the strength lives (game, `finish`, or `render`) and its default. If it is `finish` or `render`,
  a ticket to build the parameter. If it is the game, a note for the game's repo with the light settings.

## Acceptance criteria

- [x] The sheets and captures above, their paths listed here.
- [x] The Owner's choice recorded, and the build ticket filed or the game's note written.

## Results (2026-11-15)

All in `C:\Workspace\urban-mystery-club-art\.kiripix\trials\0217-normal\` (gitignored). Nothing in `kiripix/`, the art Project's
Assets or the game changed. **The 0160 harness (`...\trials\0160-flat\`) is not on disk** (the path in "How" also says
`Homespace`; the machine has `C:\Workspace`). So this trial has its own small harness, written fresh, with the same method as 0160.

**Harness**
- `proj/`: a scratch copy of the art Project with only `mc03_male_clothes01` and `mc03_female_clothes01`, built from their
  Decisions through `kiripix run` with the new look: render `band_edge=0.62 band_smooth=1.5`, finish `inner_lines=dark`
  (plus the Assets' own `bands=2 shadow=0.22 eyes=eyes`, finish `outline_colour=195 eyes=stamp`). Then `kiripix export` into
  `godot/` (the trial's own Godot 4.7.2 project, 640 x 520, Compatibility, nearest). So the scenes captured are the
  game's own exported `<name>.tscn` (`AnimatedSprite2D` over `frames.tres` over the `CanvasTexture`).
- `variants.py`: the two numpy places. Copies of the export folder with another `normal.png`: `finish_s<S>` (the finished,
  quantised pass lerped toward (0, 0, 1) and renormalised, so the quantised facets stay) and `render_s<S>` (the render's
  normal pass flattened first, then the real finish steps: quantise, encode, cut by colour). `levels_{render,finish}_s0.5_l{4,8,16}`.
  The rebuild of the shipped atlas from the render pass at strength 1 is pixel-exact (0 differing pixels, both bodies).
- `godot/capture.gd`: the grid capture, one row per variant, each row with its own `PointLight2D` (its own light mask bit).
  The **game place** is a canvas_item shader on the sprite: `NORMAL_MAP = normalize(mix((0,0,1), n, normal_strength))`, on the
  unchanged normal atlas. It needs nothing from Kiripix. 0160's lights: warm (1, 0.88, 0.7), energy 1.3, height 40, ambient 0.55,
  left, right, lamp in the middle. **The game's own light**: the `living_kitchen` window preset (`#ffd9a0`, energy 1.6, radius 44,
  height 30, ambient `#b4a698`), one light up and left of each figure. It is the only room with a real light on actors.
- `cap.py`, `run_all.py` (sheets), `metrics.py` (numbers, `metrics.json`).

**Sheets** (`sheets/`, 5x, each row captioned with the place, strength, light, height and levels; both bodies, prefix
`mc03_male_clothes01_` or `mc03_female_clothes01_`, suffix `_5x.png`). Captures at 1x are in `captures/` (same names, with a `.json` spec each).
- `<place>_idle_<light>`: place `game`, `finish` or `render`; light `left`, `right`, `lamp` or `game`. Rows are strength 1, 0.75,
  0.5, 0.25, 0; columns are the 8 directions, idle frame 0. **Start with** `game_idle_left` and `game_idle_lamp`.
- `<place>_walk_<light>` and `<place>_attack_<light>` (light `left` or `lamp`): the same rows, columns 8 consecutive frames of walk
  (direction se) or of attack (se, frames 4 to 11).
- `game_height_<light>`: the game place's other knob, the light's height 30, 40, 80, 160, 320 on the unchanged normal.
- `levels_{idle,walk}_{left,lamp}`: `normal_levels` 4, 8, 16, in the render order then the finish order, at strength 0.5.

**Numbers** (male; the female is within a few percent; `metrics.json`). Lit-side contrast is the mean luminance of the half of
the figure toward a left light, minus the other half, over the figure's mean, averaged over 8 directions (game place, the 0160 left light):

| strength | 1 | 0.75 | 0.5 | 0.25 | 0 |
|---|---|---|---|---|---|
| lit-side contrast, left light, mean | 0.46 | 0.41 | 0.36 | 0.26 | 0.08 |
| worst of the 8 directions | 0.17 | 0.12 | 0.07 | -0.01 | -0.16 |
| lit-side contrast, right light, mean | 0.34 | 0.29 | 0.23 | 0.13 | -0.06 |
| luminance spread (std / mean) | 0.76 | 0.73 | 0.70 | 0.64 | 0.58 |
| mean lean of the normals from the camera, degrees | 34.7 | 26.6 | 17.4 | 8.2 | 0.3 |

The lean is the finish place; the lit-side contrast falls about linearly with strength, with no knee.

**What the sheets show** (Claude's reading; the choice is the Owner's)
1. **The three places look the same at 1, 0.75 and 0.5 once they are rendered.** The game place and the finish place agree to
   within 0.1 of one level of colour on average (mean absolute RGB difference per pixel, 0.05 to 0.1 at 0.75 and 0.5, 0.02 at
   0.25 and 0), which is the shader's 8-bit rounding. They differ in cost only: the game place needs the shader in the
   game and no rebuild; the finish place changes the exported `normal.png`, so a flattened pass cannot be un-flattened in the game.
2. **`render` differs, and not for the better.** Flattening before the quantise leaves the normals in few values (distinct normals in
   the atlas at 8 levels: 129 at strength 1; 95, 46 and 13 at 0.75, 0.5 and 0.25 for `render`, but 129 for `finish`), and with an
   even `normal_levels` there is no zero level: a flat normal quantises to about (0.14, 0.14), so **`render` at strength 0 is not flat**
   (mean lean 8.7 degrees, 2 distinct values, a constant tilt toward the upper right that lights every figure from one side). The
   finish place at 0 is exactly flat (0.3 degrees, 1 value). So if the strength is built in `render` it needs an odd `normal_levels`
   or the quantise applied before the lerp; that is just the finish place by another name. `render` has no advantage here: the
   normal pass is the only thing it would flatten, and `finish` quantises it right after.
3. **Direction.** In all 8 directions the lit side stays brighter at 0.75 and 0.5 with the left light (worst direction +0.12, +0.07). At 0.25
   the worst direction is flat (-0.01) and under the right light 0.5 already has one direction that reads as slightly lit from the wrong side
   (-0.04); at 0 the light only tints, and a back-lit direction is darker (-0.16). The figure is not washed out at any strength: luminance
   spread falls only from 0.76 to 0.58. Under the game's own light (radius 44, height 30) the figures differ across strengths (see `game_idle_game`; the capture's rows
   differ by more at each lower strength); the lit-side numbers above were measured for the 0160 lights only.
4. **In motion.** On walk and attack (`*_walk_left`, `*_attack_left`) no row flickers: the normals follow the limbs, and the finish
   place at 0.5 and 0.25 looks as steady as 1. The mean frame-to-frame luminance change falls with strength (walk, game place:
   4.7, 4.5, 4.2, 3.9, 3.7; attack: 4.9, 4.7, 4.4, 4.1, 4.0). It includes the limbs' own movement, so the fall is only the
   lighting's share. The only flicker-like thing is the per-frame facet change on the hands and shoes at strength 1.
5. **`normal_levels` hardly matters at 0.5.** The mean lean is 17.2 to 17.4 degrees for 4, 8 and 16 in the finish order, and the sheets
   look the same; the only visible difference is that 4 shows coarser facets on the jacket and jeans, and in the render order 4 leans
   19.7 degrees with 16 distinct normals (the even-levels tilt of item 2). 16 has 536 distinct normals, 4 has 39, and 8 has 129
   (finish order). No reason to leave 8.
6. **Light height as a substitute (judged from the shading model, not measured; look at `game_height_*`).** Raising the height from 40 to 160 or 320 flattens the figure's shading as the
   strength does, but it also changes the whole figure's brightness with the distance from the light (a lamp far to the side
   lights an unflattened figure unevenly), and a room's light preset sets that height for its own purposes (30 in the kitchen). A
   separate strength on the sprite is cleaner. Lowering `energy` only dims the light: the figure keeps its shaded look.

**Recommendation** (the choice is the Owner's)
- **Where: the game, a `normal_strength` on the character's material** (the shader in `godot/capture.gd`: three lines; `NORMAL_MAP`
  from `NORMAL_TEXTURE`, lerp to (0, 0, 1), normalise). It matches the `finish` place visually, costs Kiripix nothing, keeps
  `normal.png` at full strength for another use, and the Owner can retune it per room or per light without rebuilding the characters.
  Next best: `finish`, applied after the quantise (as here), not `render`. A ticket for `finish` is only worth it if the exported
  `normal.png` must itself be flat, or a game build must avoid a custom material.
- **Strength: 0.5**, then 0.25 if the room is bright. 0.5 keeps the lit side in all 8 directions with a light on either side and drops the
  hard pixel-level facets of 1; 0.25 starts to lose a direction; 0 tints only (as a painted sprite).
- **`normal_levels`: leave 8.** If the strength ever goes into `render`, make the levels odd (7 or 9) so a flat normal stays flat.
- Note for the game's repo, if the game is chosen: `AnimatedSprite2D.material = ShaderMaterial` with the shader above,
  `normal_strength = 0.5`; the lights as the room presets have them (the kitchen window: energy 1.6, radius 44, height 30).

## Owner's choice (2026-11-15)

- **Strength: 0.25** ("looks best in lit rooms"). It overrides the 0.5 recommendation above.
- **Where: the game**, a `normal_strength` shader on the character's material (the recommended place; the Owner named only the
  strength, so confirm if `finish` was meant). No Kiripix build ticket. `normal_levels` stays 8.
- **Note for the game's repo:** `AnimatedSprite2D.material = ShaderMaterial` with the shader from
  `C:\Workspace\urban-mystery-club-art\.kiripix\trials\0217-normal\godot\capture.gd` (`NORMAL_MAP` from `NORMAL_TEXTURE`, lerp to
  `(0, 0, 1)`, normalise), `normal_strength = 0.25`. Lights as the room presets have them (kitchen window: energy 1.6, radius 44,
  height 30). At 0.25 the worst of 8 light directions is about 0 (-0.01), so the lit side may not brighten from one direction
  under a light on that side; check it in a real room.

Not done: the game's own scene was captured through the same exported `.tscn`, but not inside a real room (no Plate, no
Navigation), and the `game` light is the kitchen window only, one copy per figure.
