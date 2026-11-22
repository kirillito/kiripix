---
status: done
milestone: M6
agent: imaging-engineer
type: trial
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
---

# M6: trial: battle effects as sprite sheets, and where their frames come from

Spec §14 (Later until 2026-11-19: "VFX sheets (the game's battle skills and its M18)"). Part of
[0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Prototype code stays in `backlog/m6/0347-trial/` or the scratchpad,
not in `kiripix/`. The game's side: its M06 (`../urban-mystery-club/docs/backlog/m6/0062-m06-props-phases-boss.md`:
placeholder sparks, shake and landing), the Jazz Musician's sound attacks and buffs (M06-12), the Beast Master's summon
(M05-15), and its M18 (the Lady's VFX).

## The question

Battle effects in the game are placeholders. What does one effect need to look right beside the 52 px cast and the painted
rooms? Which route makes its frames at $0 and in the Owner's time? And how much of it does Kiripix already do?

## What to do

1. **The list:** with the game's M06 tickets, five effects that span the need: a hit spark (small, 4–6 frames), the Jazz
   Musician's sound wave (a cone of cells), the summon's puff, a buff's glow on a unit, and a telegraph on a target cell.
   Record each one's size, frames, and whether it's lit by the room's lights or glows (additive, unshaded).
2. **The hypothesis first:** an effect is a `sprite` (spec §6.4) with `directions=1`, no outline, `normals=flat`, and the
   Project palette or a few glow colours. Try it through the existing Commands. Note every gap: an outline it can't skip, a
   palette it shouldn't use, alpha that must stay partial for a glow, a pivot that isn't feet.
3. **Routes for the frames**, each on at least two effects:
   - (a) the image model's own UI: a strip of frames on a flat background, imported as a sheet (if
     [0353](0353-m6-provider-research.md)'s desk table finds a Provider that makes effect strips, its free credits too);
   - (b) a kit hand-painted at target size, as a room Loop's kit is;
   - (c) Ops: frames made from one painted frame by whole-pixel Ops (scale, fade by palette steps, `shimmer`), as Loops do;
   - (d) a procedural renderer driven by a recipe (added 2026-11-20 from the research briefings in `.research/`):
     [Pixelbolt](https://github.com/skulitom/Pixelbolt) (MIT code, Node 20+, no GPU, no image API) renders particles, sparks,
     smoke, fire, fluids and emissive maps from an editable JSON recipe, on a fixed palette and pixel grid, with a set frame
     count and loop, and writes PNG frames, APNG and an atlas with frame durations. Claude writes the recipe with the Project
     palette and the effect's size; the frames import as a `sprite` sheet like route (a)'s. Record whether a recipe's frames
     sit better beside the painted rooms than the image model's, how many recipe edits an effect took, and whether the emissive
     map is useful for the `add` blend. Check the licence of the release used (the briefings' version numbers are
     second-hand), and keep it out of the project's dependencies: it's run by hand or `npx` in the trial folder.
   A Blender route (particles at the characters' camera) is named, not tried, unless the Owner asks.
4. **In Godot:** each effect as an `AnimatedSprite2D` over a test room, with blend `add` and `mix`, lit and unlit. Capture a
   GIF of each beside a character.
5. **The Owner's view** on the GIFs: which route per kind of effect.

## Acceptance criteria

- [x] The five effects, the routes tried, and the Owner's minutes per effect, in a table here (route (a) was not run; its minutes carry over with the three open effects).
- [x] The verdict: the `sprite` Kind with parameters, or a `vfx` Kind of its own, with the reason. If route (d) wins for a kind
      of effect, say whether Kiripix should import its output as it is or keep the recipe as a Source (a recipe is
      deterministic, so it could be rebuilt like a Blender render).
- [x] The build tickets filed, with `agent:` and `depends_on`, listed here and in 0324's order. Spec §14 says what M6 builds.
- [x] The game told what to expect in its export (the files, the blend mode, the pivot): section 7, and 0364 repeats it for the game.

## Result (DRAFT, run 2026-11-20 by the imaging agent; the Owner has not seen it)

Everything is in [0347-trial/](0347-trial/) (its `.gitignore` leaves out the Pixelbolt clone, 42 MB, and Godot's cache). Nothing is
in `kiripix/`. Reading the pictures: each GIF is the Godot scene at 2x nearest neighbour, four quadrants (add and mix blend, unlit
and lit) beside Sanjay over the annex kitchen plate: `0347-trial/gifs/<effect>.<route>.gif`. Strips (4x nearest, on the room's
dark colour): `0347-trial/previews/<effect>.<route>.strip.x4.png`; one still of four of them: `previews/stills_check.png`.
Godot 4.7.2 was found at `C:\Homespace\[software]\Godot` (not on PATH; the tests need `KIRIPIX_GODOT`), so these are real
captures (`--write-movie`), not strips. Scene: `godot_project/main.gd`, run by `capture_gifs.py`. Lit versus unlit differ little in
the kitchen (the plate already bakes its light and my test light is weak): judge add versus mix on the GIFs.

### 1. The five effects (the game's cell is 32 px; the cast is 52 px; Sanjay's cell is 78 px)

| Effect | Size, frames | Blend | Lit or glow | Pivot | Game need |
|---|---|---|---|---|---|
| hit spark | 24x24, 5 (+1 blank) | add | glows (unshaded) | cell centre | at the unit's chest; replaces `BattleView`'s `SPARK_*` rects (0062) |
| sound wave | 96x64 or 96x96, 8 to 10; a cone 3 cells long, 4 facings | add | glows | the caster's end, left middle | the Jazz Musician's `blast` cone (M06-12) |
| summon puff | 48x48, 8 to 10 | mix | lit (smoke takes the room's light) | the ground point, 34 px down | the Beast Master's summon (M05-15) |
| buff glow | 48x64, 8 to 12, loops | add | glows | the unit's feet (ground ellipse) | `groove`, a buff on a unit (M06-12) |
| telegraph | 32x32, 4, loops | mix (add reads as a hot square) | glows, unshaded | centre of a 32 px cell | `skill.boss.charge` and `slam` cells (0061, 0062) |

### 2. The `sprite` hypothesis, through the existing Commands

`new sprite`, `set frames directions=1`, `set finish outline=false normals=flat`, `set palette colors=24`, `import --role sheet`,
a `sheet` Decision (`rows`, `["s"]`), `run`, `export` into a scratch Godot project (`0347-trial/scratch_project`, a copy of the
art Project's `kiripix.toml` and `style/`; export target `0347-trial/godot_project`). It runs end to end for four effects (hit
spark, buff glow, telegraph, sound wave; the puff is the same path) and exports `frames.tres`, `color.png`, `normal.png`,
`character.json` and a bare `AnimatedSprite2D` scene. So the hypothesis holds as a pipeline. Gaps, each measured:

1. **Partial alpha vanishes silently.** The buff glow's haze (Pixelbolt `#FEDA4366`, 2,379 of 3,301 non-clear pixels, 72 %) was
   dropped by the `fit` vote (102 reads as clear) and no finding was raised: `fit.alpha_partial` looks at the already binary
   output. The rule says partial alpha is a finding, and an effect needs its glow body, so it needs an Op that turns partial
   alpha into ordered dither on purpose, and the finding on the input.
2. **The pivot is a figure's ground point** (0.08 of the height above the lowest row): spark (11,18) in a 23 px cell, telegraph
   (16,29) in 34, sound wave (73,59) in 98x66 where the caster end was at (-6,32). There is a `pivot` Decision, but no
   parameter, and the default is wrong for every effect.
3. **The cell grows 1 px each side "for the outline"** even with `outline=false` (23 for 24 px, 34 for 32): a telegraph does
   not stay on the game's 32 px cell.
4. **An empty frame is an error** (`sheet.empty_frame`): a one-shot's last frame is blank in Pixelbolt's spark, as it should be.
5. **No blend, no lit or unlit, no per-frame ticks in the export.** The scene is a bare `AnimatedSprite2D` (fps 8, loop on by
   default; a `clip` Decision sets fps and loop, so that part is fine). Pixelbolt's per-frame `duration` has no place, and the
   game must set `CanvasItemMaterial.blend_mode` and `light_mode` itself with nothing to tell it which.
6. **Figure rules that mean nothing for an effect:** `fit.height` (info, "target 52 px"), `palette.sprite_regions` (info), and a
   flat `normal.png` written and unused. Noise, not blockers.
7. **Directions:** `directions=4` exists, so a cone can be `s w n e`, or the game turns the east one by 90 degrees (whole pixels).
   Only `1` was tried.
8. **Palette:** all four used 2 to 9 Project colours and `off_palette` stayed quiet; Pixelbolt's colours were typed from the
   Project palette by hand and nothing checks that except Kiripix's `palette` stage, which worked as the guard.

### 3. The routes (I did b, c and d; (a) needs the Owner)

| Effect | (a) image model (Owner) | (b) hand-painted kit | (c) Ops from one painted frame | (d) Pixelbolt recipe |
|---|---|---|---|---|
| hit spark | prompt ready; minutes ____ | **good.** 5 frames of 12x16 painted as text grids, 1 pass | not tried | **good.** preset `slash-hit` pared down, 0 edits; star, ring, 7 flecks, 3 Project colours; livelier than (b) |
| sound wave | prompt ready; minutes ____ | not tried | **good.** one painted cone of arc bands, `scroll` dx=3 over 6 frames, 2 frames faded by palette steps; arcs travel outward inside a cone 3 cells long. They shear a little (a radial scroll would be exact) | **poor.** 3 versions, 3 edits, never a cone: `slash` is a crescent whose tail chases its head to one end, `ring` is a full circle, there is no cone mask |
| summon puff | prompt ready; minutes ____ | not tried | **weak.** one painted 13x9 puff, integer scale 1x to 3x, fade by palette steps, `shimmer`: a blob growing, and `cycle.ramps` led the cream through amber (yellow in the middle frames): a ramp Op must stay in the colour's own family | **good.** 1 edit (the first violet ring was too big). Dithered smoke that breaks up, sparks; best of the three |
| buff glow | prompt ready; minutes ____ | not tried | **ok.** one painted ellipse ring, `shimmer`, a 1-step pulse, 8 frames loop; clean but no sparks or haze | **good, with a caveat.** 1 edit (a haze layer). Ring, rising motes and a body of partial alpha, which Kiripix drops (gap 1) |
| telegraph | prompt ready; minutes ____ | **best.** 4 frames of corner brackets stepping in plus a checker fill, 30 lines, exact on the 32 px cell | not tried | **ok.** 3 edits (2 schema slips, then density): a plain `rect` and `dither` recipe, not an effect |

Route (d), Pixelbolt 0.19.0 (clone at commit 15ed867 in `0347-trial/pixelbolt`, run with `node bin/pixelbolt.js`; Node 24;
zero dependencies; nothing installed, nothing added to Kiripix). **Licence: MIT, "Copyright (c) 2026 PixelForge contributors"**
(`LICENSE` in the clone; the package says `"license": "MIT"`), so shipping its output is free; its code is not shipped.
- *Beside the painted rooms?* Hard-edged, dithered, on the palette: as good as (b) and better than (c)'s blobs, for particle
  effects (spark, puff, aura). Not for a cone or a cell telegraph. Recipe edits per effect: 0, 3 (failed), 1, 1, 3.
- *Emissive map:* not useful for `add`. It marks the glowing pixels of a lit sprite (a lantern's flame kept bright under scene
  lights); `add` plus unshaded needs no pass. It would matter for a lit `mix` prop with a glowing part (a brazier).
- *Source or import?* Draft: **import its output as it is** (a sprite sheet) and keep the recipe beside it as a note. Keeping
  the recipe as a Source (a Stage that runs Pixelbolt like Blender) lets Claude edit an effect on request and renders in under
  a second, but adds a Node dependency, a second pinning story (ADR 0004) and wins only on particle effects. Revisit if three or
  more effects are edited more than twice.
- *Route (a):* prompts in [0347-trial/route-a-prompts.md](0347-trial/route-a-prompts.md). Expect `fit mode=downscale`, a magenta
  chroma key and a re-roll per effect. *Blender route:* named, not tried.

### 4. In Godot

All ten GIFs (five effects x the two routes tried): `add` reads right for the spark, cone and glow, and blows the puff out (the
puff is right in `mix`); `mix` is right for smoke and the floor telegraph. Lit effects take the room's `CanvasModulate`, unlit ones
do not: the puff belongs lit, the spark and glows unlit.

### 5. DRAFT verdict: the `sprite` Kind with parameters, not a `vfx` Kind (yet)

The pipeline already ran end to end, and the gaps are parameters (1 to 6), one Op (alpha dither) and a few export fields. A
`vfx` Kind would copy `frames, fit, palette, sheet, export` and differ in defaults and in what export says (blend, lit). Keep `vfx`
in Later; reopen it if M18's Lady needs effects that attach to or layer on a unit, which a sprite does not model.

### 6. Proposed build tickets (not filed; the Owner decides)

| # | Title | agent | depends_on |
|---|---|---|---|
| P1 | `sprite` effect parameters: `anchor` (centre or x,y; feet stays the default), exact cell with no outline spare pixel when `outline=false`, effect mode silences `fit.height` and drops `normal.png`, a one-shot may end blank, per-clip `ticks` | imaging-engineer | none |
| P2 | Op `dither_alpha` (ordered dither of partial alpha to 1-bit, deterministic, golden-tested) and `fit.alpha_partial` raised on the input in `grid` mode instead of the silent vote | imaging-engineer | none |
| P3 | Effect Ops from one frame: `ramp_fade` that stays in the colour's own ramp, a `pulse` for glows, a radial `scroll` for cones, with goldens | imaging-engineer | none |
| P4 | Export: `character.json` of an effect carries `blend`, `lit` and `anchor`; the scene writes the `CanvasItemMaterial`; the Manifest freezes the clip IDs; the game is told (section 7) | godot-export | P1 |
| P5 | Import a Pixelbolt render: `import --role sheet` reads its atlas JSON (per-frame ticks, anchor) into a `sheet` Decision; recipe kept in `src/`; no Node in Kiripix | core-engineer | P1 |
| P6 | UI: the sprite player shows an effect on the room plate in `add` and `mix`, lit and unlit | ui-engineer | P4 |
| P7 | The Project's own kit for a telegraph and a hit spark (`0347-trial/b_kit` is the start) | imaging-engineer with the Owner | P1 |
| P8 (maybe) | Trial: a Pixelbolt recipe as a Source stage | imaging-engineer | P5, the Owner |

### 7. What the game should expect in its export

- Files (as a sprite today): `sprite/<name>/<name>.tscn`, `frames.tres`, `color.png`, `character.json`; with P1 no `normal.png`.
- Blend: `add` for the spark, cone and glow; `mix` for the puff and telegraph. Today the game sets the `CanvasItemMaterial`; with P4
  the scene does, from `character.json`.
- Lit or unlit: unshaded (`light_mode = 1`, as the rooms' Loops are) for glows; lit for the puff.
- Pivot: today a figure's ground point (wrong for an effect); with P1 the effect's own anchor (centre for spark and telegraph, the
  caster end for a cone, the feet for the buff). A cone is exported facing east; the game turns it by 90 degrees or we export `s w n e`.
- A one-shot ends on its last frame; the game frees the node on `animation_finished`.

### 8. Owner's minutes per effect

(a) not run, blank in the table above. (b), (c), (d) cost the Owner nothing but review: about 5 minutes for the ten GIFs.

(Superseded by the Owner's verdict below.)

## The Owner's verdict (2026-11-20)

1. **Routes.** Accepted: the **hit spark** and the **summon puff**, both route (d) (a Pixelbolt recipe, its frames imported as a
   sheet). **Open, no route found yet:** the **buff glow**, the **sound-wave cone** and the **telegraph**. Left to try, not tried
   now: for the buff glow, route (a) with its prompt, or another (d) recipe whose body is already dithered (gap 1); for the
   cone, route (a) with its prompt, or another (d) recipe from `beam` or the `wave` source (the `slash` and `ring` layers made
   no cone); for the telegraph, route (a) with its prompt, or a (d) recipe that draws the brackets with a `grid`. The prompts are
   in [0347-trial/route-a-prompts.md](0347-trial/route-a-prompts.md). These three carry over to a follow-up after the game
   confirms the first effects.
2. **Verdict: the `sprite` Kind with parameters.** `vfx` stays in Later.
3. **Pixelbolt: import only**, the recipe kept beside the sheet in `src/`. No Source Stage, no Node in Kiripix. P8 is not filed.
4. **Filed:** P1 as [0362](0362-m6-sprite-effect-parameters.md), P2 as [0363](0363-m6-alpha-dither-op.md) and P4 as
   [0364](0364-m6-export-effect-blend.md) (after 0362). P3, P5, P6 and P7 are not filed; they follow the game's confirmation of
   the first effects (P5, importing a Pixelbolt atlas, is the one the accepted routes want first).
5. Spec §14 and 0324's Order are updated.
