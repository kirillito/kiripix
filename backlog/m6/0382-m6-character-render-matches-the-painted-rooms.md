---
status: todo
milestone: M6
agent: character-pipeline
type: ticket
---

# M6: characters rendered the way the GPT Image rooms are painted

Spec §2 (principle 3: one look across Kinds), §6.3 (`render`, `palette`, `finish`). The Owner, 2026-11-24: the GPT Image rooms
(`annex_bedroom`, `annex_living_kitchen`) are the target and are not to be changed. The characters must come up to them. The
flat look stays: the Owner has already rejected a softer, more 3D render (plain Lambert, more bands) as "too 3D-like, and
still not matching the background". So this ticket is about *how* a flat character is coloured, not about making it rounder.

## What's wrong now

Measured on 2026-11-24, mc03_female (idle, s) placed in both annex rooms:

- `render`'s toon shading ([render_frames.py](../../kiripix/blender/render_frames.py) `shade`) multiplies the Diffuse Color by
  a darker factor per band. So the shadow is the base colour darkened toward mud, while the rooms shift the shadow toward
  cool blue-grey and the light toward warm. The room prompts ask for "shadows cool blue-grey; only the sun patch is warm".
- One outline colour (palette 195) everywhere. The rooms outline each object in a dark shade of its own colour.
- 14 colours in the frame, 4-step ramps for `skin` and `hair`, `palette colors = 16`. The rooms use about 280 of the 300 palette
  colours. A room object the character's size (the closet, the door) has 3 to 5 tones per surface plus a highlight; a
  character part has 2 or 3.
- No contact shading: arms against the body, under the hair, between the legs all read as one flat patch.

## What to build

1. **Hue-shifted toon shading.** The shadow band moves toward a cool colour and the lit band toward a warm one, instead of
   only darker or lighter. Parameters on `render`, such as `shadow_hue` (a colour or a hue and strength) and `light_hue`, with
   defaults that give today's output, so no character changes until it's set. The bands stay hard: still flat.
   With parts and the Project ramp table, the shift has to live in the ramp's colours, since the game swaps a part's ramp
   whole. Say in the Result how a hue-shifted ramp is made for a part (`ramps-add`, or derived) so a swap still works.
2. **Longer ramps.** Allow a part's ramp up to 6 to 8 colours: shadow, core, lit, highlight, and one or two steps between.
   `bands` is capped at 4 now; lift the cap, or add a highlight band (a small specular or rim cut) as one more step. Check what
   a longer `[character.ramps]` row does to Wearables, NPC variants (0336) and `character.json`, and migrate if a data
   file's format changes.
3. **Outline in the part's own colour (sel-out).** On `finish`: the outline pixel takes the darkest colour of the part it
   borders (from the part's ramp), not one fixed colour, with the fixed colour kept as the option it is today. Inner lines
   (`inner_lines=dark`) the same way. A pixel bordering two parts takes the darker one.
4. **Contact shading.** A darkening one band down where the Model's surfaces meet or almost meet: an ambient occlusion pass
   from Blender, cut to one band step by a threshold, so it gives flat shapes, not a soft gradient. A parameter, off by default.
5. Bump `render`'s, `palette`'s and `finish`'s `version` as each changes what they write; name the bumps in the Result. Golden
   images for any new Op.

## How the Owner judges it

A sheet, enlarged 4x (nearest) with a caption per panel: mc03_female and mc03_male (idle and walk, s and e) in
`annex_bedroom` and `annex_living_kitchen`, at today's settings and with each of 1, 2, 3 and 4 switched on one at a time, then
all together. Path given in the Result. The Owner picks the settings; they go in the art Project's `asset.toml`s, not as new
defaults, unless the Owner says so.

## Acceptance criteria

- [ ] Every new parameter at its default gives byte-identical output to today's (CLI seam test on the test Kind).
- [ ] A part swap still recolours a hue-shifted ramp correctly (CLI seam: swap a part, check every pixel of the part moved to
      the new ramp at the same step).
- [ ] Sel-out outline: golden images for the Op; a pixel between two parts takes the darker part's colour.
- [ ] The Owner's comparison sheet, enlarged and captioned, and the Owner's chosen settings recorded here.
- [ ] Spec §6.3 updated for the new parameters.

## Result

Built by the character-pipeline agent, 2026-11-24. Every new parameter is off at its default and then every byte is today's: checked on mc03_female
against the unchanged code (HEAD's `kiripix` run beside the new one on copies of the art Project: 0 differing pixels in the render frames), in a
marked real-Blender test, and at the CLI seam (no new key reaches Blender or `render.json`, and a parameter set to its default is no input).

- **1. Hue shift** (`render`): `shadow_hue`, `light_hue` (`#rrggbb`), `hue_strength`. `shade` moves a band's colour toward the hue at its own lightness,
  so the hue is in the frame colours and lives in the part's ramp. **How a hue-shifted ramp is made:** with palette `parts` and no `rgb` in the
  table row, `palette` fits the ramp to the rendered colours (derived), so the shadow step is the cool colour; for a part of the Project's ramp
  table with shared `rgb` (skin and hair of the art Project), the table's colours win and the render's hue only decides which step a pixel is on
  (by lightness), so the row has to carry the shift: render a character with the hues and the row unset, then `kiripix ramps-add` it (or edit
  the row's `rgb`). A swap is the existing step-for-step one, so it keeps the shift (CLI test: every pixel of the part goes to the new ramp at the same step).
- **2. Longer ramps:** `bands` 2 to 8 (was 4), and `highlight` / `highlight_gain` add one band above the brightest (a lightened colour); a ramp is
  `bands` colours, one more with a highlight (`render.json`'s `bands`, which `palette` reads). No data format changes, so no `schema_version` or
  migration: `character.json` and `ramps.png` take the longest ramp's width already, NPC variants and Wearables read a ramp's own length. But a
  row of `[[character.ramps]]` fixes the length, and a `choices` ramp of an NPC (0336) must have the row's length, so lengthening a row means giving
  its `rgb` and every `choices` ramp the new length (`palette.parts_differ` says so); a table row of length 4 maps a 7-band render onto 4 steps by lightness.
- **3. Sel-out** (`finish`): `outline_from=part` (default `colour`, today's fixed `outline_colour`). New Ops `sel_out_outline` and `sel_out_paint`
  in `kiripix/ops/selout.py` (pure; goldens `sel_out_outline.png`, `sel_out_notch.png` for the pixel between two parts, `sel_out_lines.png`, in
  tests/golden). A pixel takes the darkest of the own and four neighbouring parts' colours: a part's ramp's first colour (the line step with
  `part_lines`), for a material in no part the colour `inner_lines=dark` chooses. Inner lines too (`inner_lines=outline` and `dark`). With sel-out
  `outline_colour` is only the fallback and may be in a ramp (`finish.outline_in_ramp` is not raised); `finish.json`'s outline gets `from` and `colours`.
  New failure `finish.outline_without_parts` (no materials).
- **4. Contact shading** (`render`): `contact`, `contact_distance` (share of the Model's height), `contact_threshold`. A second 32-sample Cycles render
  of each frame gives the ambient-occlusion pass (the first render and the other passes stay at 1 sample); occlusion at or above the threshold puts
  the pixel one band down. Marked test: it changes pixels on the fixture. It costs about a second render per frame.
- **Version bumps:** `render` 4 to 5 (new keys in the script and args; every Asset's render is stale once, though its bytes don't change), `finish` 4 to 5
  (`outline_from`, the sel-out record). **`palette` is not bumped:** its code and output are unchanged (a longer ramp is the same code with a larger
  `bands`), so nothing is stale there but through `render`. `character.json`, `render.json` and `palette.json` schema versions are unchanged.
- Spec §6.3 (render and finish rows) updated. New parameters are in the Kind's describe; no new Command, so no contract sample.
- **The Owner's sheet** (4x nearest, caption per row, mc03_female left and mc03_male right, each idle s, idle e, walk s, walk e; rows today, control,
  1, 2, 3, 4, all), one file per room:
  `C:\Homespace\urban-mystery-club-art\.kiripix\previews\0382\0382_compare_annex_bedroom.png` and
  `C:\Homespace\urban-mystery-club-art\.kiripix\previews\0382\0382_compare_annex_living_kitchen.png`.
  Built on a scratch copy of the art Project (the art Project's `asset.toml`s, `kiripix.toml` and rooms are not touched; the rooms' exported plate plus
  layers are the background, the annex_living_kitchen has no `work/` here). Notes on the sheet: the table's skin and hair `rgb` are shared and would hide
  every hue, so rows B and 1, 3, 4 use the same Project with those two rows' `rgb` left out (fitted ramps; row B is today's settings that way, as the
  control); row 2 and "all" also give those rows length 7. Idle is the `still` pose and the walk clip was cut to 3 frames (frame 0 is the same pose); the
  walk is the clip's root-motion-in-place. In row 1 the outline colour is a free one (7 female, 10 male) because the fitted hair ramp took 195.
  Settings used: hue `#5a6fa8` / `#ffd9a0`, strength 0.35; bands 6 with highlight 0.9; contact distance 0.06, threshold 0.35.
  **The Owner's chosen settings: not yet picked.**
