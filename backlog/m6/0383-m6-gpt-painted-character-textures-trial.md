---
status: todo
milestone: M6
agent: character-pipeline
type: trial
---

# M6: trial: GPT Image paints a character's texture, and 3D keeps the animation

Spec §2 (principle 3), §6.3 (`model`, `render`), §10 (`gen`, "Spend"). The Owner, 2026-11-24: the GPT Image rooms are the
target and are not to be changed; the characters must reach their level of detail and their palette. Prototype code stays in
`backlog/m6/0383-trial/` or the scratchpad, not in `kiripix/`. Nothing in the art Project is written except through Kiripix
Commands; the trial's own files go in the trial folder.

## The idea

The rooms' detail comes from GPT Image painting. A sprite frame painted by GPT Image would not stay consistent across hundreds
of frames and 8 directions, so it doesn't paint frames. It paints **the Model's texture** once, and the existing pipeline
(`render` → `palette` → `finish`) makes every frame from it, consistent by construction:

1. Render the character large (about 1024 px tall), in its rest pose, **unlit** (Diffuse Color only), from the front, the back
   and both sides, at a flat orthographic camera. Also each view's UV and depth passes, for projecting back.
2. Send each view to GPT Image as an edit, with a room Plate (`annex_bedroom`) as a style reference: paint the same figure,
   same outline and pose, as flat unlit colour in the rooms' style (fabric folds, seams, hair strands, small highlights in the
   colour itself, the rooms' palette feel). **No light and no shadow**: `render` shades it, and a painted shadow would be
   shaded twice. Use `input_fidelity` and a mask of the silhouette.
3. Project each painted view back onto the Model's UV texture in headless Blender (camera projection, the view facing the
   surface most squarely wins, blended at the seams), and save it as a new texture beside the original.
4. Render the usual clips at 51 px with it, through `palette` and `finish`, and compare.

## What to do

1. One character: mc03_female (body only, no Wearable). Steps 1 to 4 above.
2. **The prompt, in ChatGPT, by the Owner** (the Owner, 2026-11-24: free on the subscription, and quick to refine). Put in the
   trial folder the front view, the `annex_bedroom` Plate and two or three prompt wordings, and stop for the Owner. The Owner
   tries them in ChatGPT, refines them there, and puts the results and the winning wording in the trial folder. Nothing in
   this step needs exact alignment: it answers only whether GPT Image paints flat unlit colour in the rooms' style.
3. **Alignment check on the ChatGPT result.** Measure its silhouette drift against the front render (as in step 5). If it
   lines up well enough to project (say so with the figure, and show the projected front on the model), the Owner may make the
   other three views in ChatGPT too, and the trial brings them into the trial folder with no API cost. Otherwise:
4. **The four views through `kiripix gen`**, with the winning wording, the silhouette mask and the Owner's `approve` for each
   call: `gen` sends the view at its own size and maps the result back onto it pixel for pixel, which ChatGPT doesn't. Expect
   4 to 8 calls, about $1 at medium quality; the estimate is printed before each.
   `gen` takes only rooms, Props and portraits (`GEN_KINDS` in `kiripix/core/gen.py`), not a character. Don't change that
   for the trial: import each view as the Source of a scratch Prop (`trial_mc03f_front`, ...) in the art Project, and paint it
   as an edit of its Source with `gen <prop> --state <name> --prompt "..." --reference <plate>` (`--look` is rooms only), so
   the calls are in the art Project's ledger and under its cap. Remove the scratch Props when the trial ends (`kiripix`
   Commands only), and list them in the Result.
5. Measure, on the 1024 px views: how far the repaint's silhouette moves from the render's (px, worst and mean), since that's
   what makes projection seams; and on the 51 px frames: colours used, and whether the detail survives the downscale (the
   colour changes per pixel inside the silhouette, today's against the painted texture's).
6. If 0382 has landed, render with its settings as well; if not, with today's settings. Say which.
7. If it works on the body, try one Wearable (mc03_female_clothes01) the same way, and say whether each Wearable needs its
   own calls or one call can paint the body and its Wearables together.

## What to record, in this ticket

- The prompts tried in ChatGPT and which wording won; which views came from ChatGPT and which from `gen`, and why; the `gen`
  calls (IDs, cost from the ledger).
- The silhouette drift figures and how the projection handled it: seams, the sides, under the arms, the top of the head that
  no view sees squarely.
- A sheet for the Owner, enlarged 4x (nearest), each panel captioned: the original texture and the painted one, and the 51 px
  frames (idle and walk, s, e, n) in `annex_bedroom` and `annex_living_kitchen`, today's against the trial's. Path given here.
- The cost per character (and per Wearable) and the Owner's time per character.
- A recommendation: go (with follow-up tickets: a Command that runs the views, the calls and the projection; where the
  painted texture lives as a Variant; how `render` picks it up and what that does to its input hash), or no-go and why.

## Notes

- This is the first use of GPT Image on characters. [0353](0353-m6-provider-research.md) left character sprites to
  [0354](0354-m6-provider-research-actors.md); this trial uses GPT Image for a texture, not a sprite, and its result goes
  back to 0354 as evidence either way.
- Only `gen` reaches OpenAI. No test calls it (the Owner, 2026-11-23: tests cost $0).

## Acceptance criteria

- [ ] The table, the sheet and the recommendation above, with the Owner's go or no-go recorded.
- [ ] Every `gen` call is in the art Project's cost ledger; total API spend stated (or $0 if every view came from ChatGPT).

## Result (part 1: the free dry runs, up to the Owner stop in step 2)

Built by the character-pipeline agent, 2026-11-24. No `kiripix gen`, no API call, no money. Everything is in `backlog/m6/0383-trial/`
(`uv run python backlog/m6/0383-trial/run_part1.py <scratch folder>` reruns all of it; Blender 5.2.3 headless). The art Project is
`C:\Workspace\urban-mystery-club-art` here (0382 wrote `C:\Homespace\...`). Nothing in it was written: the Model was opened read-only from
`assets/character/mc03_female/work/model/model.blend` and never saved; `git status --short` there is empty.

- **The Model has no texture to project onto.** `mc_f_base_a` (14848 vertices, 22258 triangles) has four materials, skin, underwear, hair and
  eyes, each a Principled BSDF whose base colour is one flat colour multiplied by a vertex colour attribute `paint` (grey 0.45 to 1). No image
  texture anywhere in the file. A front view holds 63 distinct colours: **it is nearly flat colour**, so GPT Image must invent every detail.
- **Its UVs can't take a painted texture.** It has five UV layers; the render one (`UVMap`) is mirrored and stacked: 24% of its triangles are
  wound clockwise and 59% of the covered texels are covered by both senses (the other four layers are worse or empty). Projecting onto it would
  paint both sides of every mirrored pair. So `project_views.py` makes a fresh unwrap (`kpx_paint`, Smart UV Project, 66 deg, no overlap: 377 of
  976,651 texels doubly covered) and saves `model_uv.blend` beside the original. It is shredded into hundreds of islands and uses 23% of the
  2048 x 2048 layout, about one texel per view pixel (3.3 mm2 a texel, 3.8 mm2 a view pixel). It works, but a cleaner unwrap (fewer seams)
  is a follow-up if the trial goes on; it doesn't affect the projection, which is per texel.
- **Rest pose: a T-pose**, arms straight out, 1.736 wide, 2.0 tall, the feet on z = 0. Canvas **1024 x 1536** (2:3; `OpenAIProvider.fit_size`
  returns it unchanged, 1.57 MP in range), the figure 1024 px tall at 512 px per unit, feet at y = 1279, 256 px margin above and below, the
  arms from x = 68 to 955 (68 px margin each side, so the arms fit with little to spare). Background (160, 160, 160). The Model faces -Y; its
  left is +X (checked on the LeftHand bone).
- **Side views.** The arms point along the view axis, so each is a small patch on the shoulder: about 1,800 px, 1.5% of the silhouette, hiding
  the torso behind it. The far arm is completely hidden. The upper and lower faces of the arms (and the top of the head) face none of the four
  views squarely.
- **Eyes.** The `eyes` material is 5,894 faces, 1.1% of the surface, the two dark ovals in the face (2,861 px in the front view, colour
  (40, 30, 30)); it is also seen in the side views as a dark notch. `render` has `eyes = "eyes"` and `finish` stamps over it
  (`eyes = "stamp"`), so the painted texture is kept away from it: the prompts ask for the ovals to stay as they are, and a textured render
  leaves the `eyes` material its flat colour (the texture is applied to the other three).
- **Colour is exact (checked, not assumed).** Unlit = Emission of the material's base colour, Cycles at 1 sample with a 0.01 box filter,
  view transform Standard, no dither: my sRGB bytes against Blender's own PNG save of the same render, 182,445 px: 8 px differ, by 1.
  A constant texture (200, 100, 50) comes back as exactly that on every textured pixel (`results/const_texture_check.json`). The colour PNG for
  GPT Image is rendered 3x and averaged (anti-aliased edge, exact inside); masks, UV, depth, normal and material passes are 1x, no filter.
  **Found:** Cycles' *Diffuse Color pass* of a Principled BSDF is not the base colour: up to 0.07 linear lower (mean 0.017 for skin and
  underwear, 0.001 to 0.0003 for hair and eyes), the energy taken by the specular layer. `render` uses that pass, so a painted texture on
  these Principled materials would come out up to about 7% darker in its brightest colours (0.8 linear: skin, underwear). When `render` takes a
  texture the material must be a Diffuse BSDF (or the pass compensated). Not yet tried.
- **`render_views.py`** (bpy): the four views, plus extra review views (45, 135, 225, 315 deg, top). Per view in the scratch folder
  `part1/views/`: colour (AA, on the grey), exact colour, mask, UV pass (16-bit), depth (16-bit, range in `camera.json`), camera-space normal,
  material id, and a `.npz` of the float passes. `camera.json` holds the camera (location, right, up, forward, orthographic, px per unit):
  `px = W/2 + (P - location).right * 512`, `py = H/2 - (P - location).up * 512`, depth = `.forward`. Kept here in `0383-trial/views/`: the four
  colour PNGs, masks and `camera.json`.
- **`project_views.py`** (bpy + numpy): per texel, its place and normal from the UV layer, then each given view tests the shrunk silhouette
  (2 px), the depth pass (tolerance grows with the slope) and the facing cosine; colour is bilinear, weight cos^8, so the view facing most
  squarely wins and equal views blend at the seam. Any subset of the views. A texel no view sees at cos >= 0.2 is filled from the nearest
  squarely seen texels *of the same material* in 3D (voxel growing, 2 cm), then the islands are grown by 8 texels. Writes the texture beside the
  Model's files, plus coverage and winner maps and the stats JSON. 2048 x 2048 takes about 10 s.
- **Not seen squarely** (by surface area, four views, `results/projection_identity_stats.json`): seen at cos >= 0.5: **62.5%**; obliquely
  (0.2 to 0.5): 6.7%; **filled: 30.8%** (2.8% seen only at a grazing angle, **28.0% not seen at all**). Of the filled area, 65% is the head
  (z >= 1.55; 35% of the filled area is above z = 1.8, the top of the head), 20% torso and arms (10% of the filled area is arm beyond x = 0.3: the upper and lower
  faces), 8% legs (inner legs), 6% feet and soles. By material, share of the material that is filled: hair 44%, eyes 51%, skin 31%, underwear 5%.
  Per view, area share of the Model each is usable for (cos >= 0.2 and not hidden): front 29%, back 28%, left 19%, right 19%; seams (a blend of
  two views at 10% or more): front 2.1%, back 1.5%, left 2.0%, right 1.9%. Uncertain: how much of the 28% is geometry nobody sees (the inner side
  of the hair shell, the backs of the eye shapes) and how much is armpit, crotch and scalp that will show in some pose; the head's 65% suggests
  most of it is the hair shell and scalp.
- **Identity round trip** (unpainted views projected, textured Model re-rendered at 1x, compared with the original 1x render; silhouettes
  identical, 0 px differ): colour distance in sRGB bytes (0 to 441), mean **0.43 / 0.29 / 0.49 / 0.54** (front / back / left / right), share of
  pixels over 8 bytes 0.8% / 0.5% / 0.8% / 1.0%; worst **409 / 342 / 342 / 342**, one pixel at a time at a material border (hair/skin,
  skin/underwear: a texel is one material). Away from material borders (2 px): mean 0.10 / 0.09 / 0.13 / 0.16, over 8 bytes 0.07% / 0.006% /
  0.02% / 0.09%, a few isolated pixels still reaching 342 (about 130 px over 60 bytes in the front view). Where the view faces the surface
  squarely (cos >= 0.75): mean 0.25 / 0.26 / 0.41 / 0.43.
- **Synthetic painting** (a different checker and the view's name per view, `synth_paintings.py`), projected and re-rendered
  (`results/roundtrip_sheet.png`, rows 4 to 6): each view's checker is where that view faces squarely, the others' where they do, seams are
  blends (visible as thin mixed bands), the filled places take the nearest colour of the same material. Colour error against the painting
  where the view faces squarely (cos >= 0.75): mean **9.5 / 4.6 / 6.6 / 5.4** bytes, 12% to 14% of those pixels off by more than 8
  (the checker's own edges, a one-pixel shift); obliquely and grazing the error is large by design, since the four paintings disagree there.
- **`measure_drift.py`**: painted silhouette by flooding the background in from the border (median border colour, tolerance 12, holes
  closed, specks dropped), any size (same aspect resized; another aspect scaled to the height and centred), contour drift worst (Hausdorff)
  and mean in canvas px both ways, a uniform scale and translation fitted by trimmed closest points, overlay PNG, `--write-aligned`.
  `test_measure_drift.py` (stick figure and the real front mask, 16 cases: identity, shifts, scales, white background with noise, 768 x 1152,
  1536 x 1536): all within 0.004 in scale and 1 px (2.5 px for resized paintings) of the known answer; after the fit mean 0 to 0.8 px, worst 0
  to 2.7 px, but 4.2 px for the stick figure painted at 768 x 1152 (2.3 px for the real mask there). Example (`results/drift_overlay_example.png`): a repaint made by scale 0.93 and shift (14, -9) on white: before worst 47.9 px,
  mean 12.7 px, IoU 0.71; after the fit worst 2.6, mean 0.75, IoU 0.98. Contour pixels are whole pixels, so a figure is good to about 0.7 px.
- **What's uncertain.** (1) Whether GPT Image paints flat unlit colour at all: that is the Owner's step. (2) A real repaint drifts locally, not
  only by scale and shift; the fit removes the global part, and the residual (worst/mean after the fit) is what step 5 measures. (3) The
  bright-colour darkening above. (4) The Smart UV unwrap's many seams once the texture holds real detail. (5) `measure_drift`'s background
  flood eats the clothes if the repaint's background is close to the white underwear (tolerance 12 against (236, 236, 236) is safe on white,
  not on a pale grey); it is why the prompts ask to keep the same grey.

**The plate:** `packet/plate_annex_bedroom.png` is the full-size Source, `assets/room/annex_bedroom/src/7bd7ce3dddc3f12a.png` (1392 x 768, the
same file as `work/source/source.png`), not the 336 x 192 Plate (`out/export/plate.png`): the room's painted detail is what GPT Image should
see, and the Plate is its downscale. It is the cutaway room on a black ground, uncropped.

**Waiting for the Owner:** try the three wordings in ChatGPT (steps in `backlog/m6/0383-trial/prompts.md`): attach
`C:\Workspace\kiripix\backlog\m6\0383-trial\packet\front_view.png` first and
`C:\Workspace\kiripix\backlog\m6\0383-trial\packet\plate_annex_bedroom.png` second; save the results as
`C:\Workspace\kiripix\backlog\m6\0383-trial\result_A_1.png`, `result_B_1.png`, `result_C_1.png` (and `_2`, ... for refinements), the winning
wording in `winning_prompt.md` there, and fill the table at the end of `prompts.md`. Then step 3 (the alignment check) follows.
