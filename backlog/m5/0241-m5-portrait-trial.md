---
status: todo
milestone: M5
agent: imaging-engineer
type: trial
parent: 0240-m5-portrait-kind.md
---

# M5: trial: a portrait set, its emotions registered and mapped as one

Part of [0240](0240-m5-portrait-kind.md). Prototype code stays in `backlog/m5/0241-trial/`, not in `kiripix/`. It reads
Kiripix's Ops (`kiripix.ops`) and doesn't change them.

**This prototype is also the game's fallback** for its M04 (the "small script in the art repo"). Keep it runnable from a
folder of PNGs, with a short README, so the game can use it if the Kind isn't built in time.

## What to do

1. **Inputs:** Sanjay's neutral portrait and three emotions (happy, angry, surprised), made by the Owner in the free image
   model as edits of the neutral one (the game's M04-02 and M04-03). If they don't exist yet, any character's set does.
   Record the Owner's minutes per emotion.
2. **Cutout:** chroma key, or BiRefNet if the background isn't flat.
3. **Register** each emotion to the neutral, with the Looks' registration Op, over the whole figure and then outside a
   rough face box. Record the scale, shift and residual for each emotion, both ways.
4. **Fit:** one `downscale` for the set from the neutral, onto 160 x 224 at a bottom-centre anchor. Try one other size if the
   result reads badly.
5. **Colours:** the set gets its own colours, not the Project palette (the Owner, 2026-11-16: portraits have gradients that
   a strict sprite palette can't hold). Choose `n` colours over the four images together (k-means in OKLab), at `n` 16, 32
   and 64, with and without ordered dither, then each image alone, and compare. Find the smallest `n` whose gradients read
   smoothly.
6. **Outline:** 1 px in the characters' outline colour (195), kept among the set's colours.
7. **Measure the shimmer:** per emotion, the pixels outside the face box that differ from the neutral's, with and without
   step 3's registration, and with joint mapping against separate mapping. Then copy the neutral's pixels outside the face
   (`lock_outside_face`) and show the result.
8. **Lay out** the four at 1x and 3x, flipping in place as a GIF, beside mc03 at 52 px and a ch01 room, for the Owner.

## What to record, in this ticket

- The residuals, the shimmer counts and the Owner's minutes per emotion.
- The sheets and the GIF, with their paths, and the Owner's view.
- Answers to 0240's four questions, with the Owner's choice, and any change to 0242–0245 before they start.

## Acceptance criteria

- [x] The numbers and images above (Results, below; the Owner's view of the sheets is still to record).
- [x] The Owner's answers to 0240's questions recorded, and 0242–0245 updated to match.
- [x] The prototype runs on a folder of PNGs, with its README, for the game's fallback.

## Results

Run by the imaging-engineer, 2026-11-18, on Sanjay's set: neutral, happy, angry, surprised, sad and worried (five emotions
where the ticket asks for three), six 896 x 1200 JPEGs on a green that is about (26-40, 233-243, 20-28) after JPEG. All code is
in [0241-trial/](0241-trial/) (`portrait_set.py`, the fallback, with its [README](0241-trial/README.md); `experiments.py`;
`register_check.py`; `layout.py`). It reads `kiripix.ops` only; nothing in `kiripix/` or `tests/` changed. The inputs are copied
there as `input/<emotion>.jpeg`, originals untouched. Output is in `0241-trial/out/`; the figures below are in
`out/results.json`. Status stays todo: the Owner's view and answers are still to come.

### The Owner's time (told by the coordinator, 2026-11-18)

- **Each emotion edit: under a minute.** No retries recorded for any emotion.
- **The neutral base: about 15 minutes**, several prompt changes to settle the look. The main problem was the generator
  drawing an East or Southeast Asian face until the prompt said "Indian Gujarati" and "medium dark skin".

### 2. Cutout

Chroma key with a tolerance: the key colour is the median of the image's border, pixels within 0.06 OKLab of it snap to it
exactly, then `chroma_key` clears them. Kiripix's `chroma_key` is exact, so on its own it would clear almost nothing here (the
green varies by about 5 levels per channel inside an image, and between images: (26,243,20) to (40,233,28)).

- The images carry a **white sticker rim** (about 4 source px, outside the dark outline) and a 1 px green-tinted JPEG blend.
  After the tolerant key alone, `key_fringe` finds about 2,900 pixels per image and the rim is still there. The prototype then
  removes green-tinted pixels within 3 px of the cleared background, then bright unsaturated pixels connected to it within
  10 px (about 17,000 px per image), then opaque islands under 1,500 px (27-183 px per image). `key_fringe` then finds 0
  pixels on all six, and the cut edge is the figure's own dark outline.
- **BiRefNet not run:** no visible fringe is left (checked at 4x on the shoulder), as the brief said.
- Left over: a few white specks at the hair's edge that are part of the figure (about 3 per image). `remove_orphans` would
  take some, but it would take the eye highlights too; left as they are.
- It is slow because `remove_small_pieces` loops in Python: about 10 s per image at 896 x 1200 (the rest of the run is
  seconds).

### 3. Registration, both ways

`register` on the cutouts laid on grey, tiles of 96 px. The Alignment (edit = scale * room + shift, in source px):

| Emotion | Whole figure: scale / shift x, y / residual | Outside the face box: scale / shift x, y / residual |
|---|---|---|
| happy | 1.0000 / -0.01, -0.00 / 0.08 | 1.0000 / +0.00, -0.00 / 0.03 |
| angry (head turned and tilted) | 1.0000 / +0.02, -0.02 / 0.09 | 1.0001, 1.0002 / -0.02, -0.28 / 0.08 |
| surprised | 1.0000 / -0.02, -0.01 / 0.07 | 1.0000, 1.0001 / -0.02, -0.16 / 0.07 |
| sad | 1.0000 / -0.01, +0.00 / 0.06 | 1.0000, 1.0002 / -0.02, -0.19 / 0.07 |
| worried | 1.0000 / +0.00, +0.02 / 0.07 | 0.9999, 1.0002 / +0.00, -0.23 / 0.08 |

- 64-66 textured tiles over the whole figure, 35 outside the box (face box 190,70 to 700,600 in the neutral, drawn by eye).
- **The set needs no registration:** the free image model kept the body where it was, to within 0.3 source px (0.05 target px)
  at the worst corner. `warp_nearest` applies an Alignment only from 0.25 px, so the whole-figure estimates move nothing;
  outside the box only angry's (0.28) is applied, and it moves under half a source pixel. The residual is 0.03-0.09 source px.
- **The turned head of the angry portrait does not pull the whole-figure estimate** (scale 1.0000, 0.06 px worst move): the
  head is a minority of the textured tiles and the fit is robust. Outside the box the y shift settles on -0.16 to -0.28 px
  for four emotions, a small difference from the whole-figure fit, still far under the 0.5 target px (2.7 source px) limit.
- **`register_check.py`: it recovers a known move both ways.** The angry image shifted and scaled on purpose (+6, -4 px; 1.03
  and +9, +5; 0.97 and -12, +14) is found to within 0.3 px in shift and 0.0002 in scale, whole figure and outside the box alike
  (for 1.03, +9, +5: whole 0.9709, (-8.72, -4.86), outside 0.9710, (-8.78, -5.11); wanted 0.9709, (-8.74, -4.85)), residual
  0.08-0.15 px. So registration works on this kind of edit; this set just doesn't need it.

### 4. Fit

One `downscale` for the set: `Grid.cover` for 160 x 224 from the neutral, scale 75/14 (5.357 source px per target px, set by
the height; the 896 x 1200 image is 3:4 and the canvas 5:7), `offset_x` 39 to centre the crop on the neutral's figure (the
figure is at x 128-818, right of the image's centre), `offset_y` 0 (bottom anchored). The whole head, hair and shoulders are
inside; the figure is 129 px wide of 160, its top is 19 px below the canvas's top, and the body is cut at the hands at the
bottom edge, as in the source (`out/set_n32_joint.png`). One other size, 120 x 168 with 24 colours
(`out/other_size_120x168.png`), reads fine but the eyes lose detail; 160 x 224 reads better, so no change is proposed. The
ticket's "try one other size if the result reads badly" is not triggered.

### 5. Colours (the set's own, `set_colours` in OKLab, the outline colour #352625 kept)

Mean over the six images of their mean error, and of their 95th percentile, in OKLab (registration outside the box, which is
no different from none here):

| n | Dither | Joint: mean / p95 | Each alone: mean / p95 (colours over the set) | Joint reads |
|---|---|---|---|---|
| 16 | 0 | 0.0115 / 0.0377 | 0.0103 / 0.0362 (91) | bands; a dark-red cast on the hair, neck and ear |
| 16 | 4 | 0.0155 / 0.0421 | 0.0126 / 0.0527 (91) | a visible screen pattern on the hoodie and skin |
| 32 | 0 | 0.0077 / 0.0261 | 0.0071 / 0.0230 (181) | smooth, close to the unmapped fit |
| 32 | 2, 4, 8 | 0.0126, 0.0127, 0.0128 / 0.032 | 0.0102 / 0.0307 (181), at 4 | the screen pattern on flat areas |
| 64 | 0 | 0.0056 / 0.0191 | 0.0052 / 0.0167 (370) | as 32, no visible gain |
| 64 | 4 | 0.0089 / 0.0214 | 0.0079 / 0.0204 (370) | the pattern, fainter |

- **Smallest n that reads smoothly: 24** (n=20 is passable, n=16 is not), judged on the upper body at 6x
  (`out/n_16_to_32_upper_body.png`, `out/n_comparison_upper_body.png`). Mean error by n: 16 0.0115, 20 0.0097, 24 0.0089,
  28 0.0082, 32 0.0077. **Proposed default: 32**, for margin on a set with more varied skin and light.
- **No dither.** It raises the error and adds a pattern the portrait's soft gradients don't need at 32. Bayer 2, 4 and 8 give
  the same numbers; the choice is the look's.
- Mapped each image alone, the error is a little smaller (0.0071 against 0.0077 at n=32), but the set then holds 181 different
  colours against 32, so a shade can't be matched between emotions. That is what the joint set is for.
- Per image at n=32 joint: mean 0.0072-0.0090, 95th percentile 0.0247-0.0301, 30-32 of 32 colours used. The worried image
  has the highest error.

### 6. Outline

`add_outline`, 1 px, in #352625 (palette index 195), kept in the set (`keep`). The images already have their own dark outline,
4-5 source px (about one target px), so the `outside` placement makes a **doubled edge** about 2 px thick; `edge` (repaint the
silhouette's own border pixels) keeps the figure's size and reads cleaner (`out/outline_placement.png`). The sheets use
`outside`, as the ticket says. The bottom and side edges where the canvas cuts the figure get no outline.

### 7. Shimmer

Pixels outside the face box (the box is 9,600 of 35,840 target px; 12,454 opaque pixels are outside it) that differ from the
neutral's, over the five emotions, at n=32 no dither:

| Condition | Exact differences (total) | ΔE over 0.03 (total, per emotion) |
|---|---|---|
| Fit only, no mapping, registered or not | all of them (12,452-12,462 per emotion: noise) | 3,300 (521-898) |
| Joint set, registered | 48,989 (9,339-10,018 per emotion, about 78 %) | 5,626 (1,015-1,290) |
| Joint set, not registered | 48,989 (the Alignment moves no pixel) | 5,626 |
| Each image mapped alone | 62,281 (every pixel: the colours differ) | 4,746 |
| Joint set, n=16 / n=64 | 50,146 / 54,582 | 8,615 / 4,651 |
| Joint set, dither 4 (n=32) | 29,738 | 7,321 |
| **Joint set, then `lock_outside_face`** | **0** | **0** |

- **The body is re-rendered by the image model each time**, with different noise (median 5-7 levels per channel) and slightly
  different shading lines. `out/shimmer_map.png`: yellow is an exact difference, red is over 0.03 ΔE; the red is the hoodie's
  shading lines, the folds and the sleeve edges, 521-898 pixels per emotion even before any mapping. That is a real flicker
  in the game, not a quantisation artefact: a flip would shimmer through the hoodie.
- Registration changes none of it (the Alignment is the identity here). Joint against separate mapping: the visible shimmer is
  a little higher for joint at 32 (5,626 against 4,746) because the shared palette is coarser (32 against 181 colours); at 64
  it's 4,651 against 4,033. Sharing the palette doesn't stop shimmer; the lock does.
- `lock_outside_face` (the neutral's pixels outside the box, the emotion's inside): 0 differences by construction.
  `out/set_n32_locked.png` against `out/set_n32_joint.png` shows the faces and expressions unharmed (the anger mark, the tear
  and the sweat are inside the box), and no seam is visible at 3x where the box's edge crosses the neck.

### 8. Layout

Mc03 at 52 px is `mc03_female` (the exported `color.png` in `urban-mystery-club-art`, the `idle` clip, direction `s`, frame 0:
57 px tall with the outline); the room is `room.ch01_002_laneway`'s `plate.png` (a 640 x 360 crop at 160,100) with a drawn
dialogue box. The portrait is the n=32 joint set, unlocked (`portraits/`), then locked (`portraits_locked/`, files with
`_locked`).

- 1x: `c:/Homespace/kiripix/backlog/m5/0241-trial/out/sheet_1x.png` (the dialogue frame with the neutral, then the six).
- 3x: `c:/Homespace/kiripix/backlog/m5/0241-trial/out/sheet_3x.png`.
- GIF, the dialogue frame at 2x, the emotion flipping in place, 0.9 s each: `c:/Homespace/kiripix/backlog/m5/0241-trial/out/flip_2x.gif`.
- GIF, the portrait alone, 3x, 0.6 s each: `c:/Homespace/kiripix/backlog/m5/0241-trial/out/flip_portrait_3x.gif`.
- The same four with the lock: `out/sheet_1x_locked.png`, `out/sheet_3x_locked.png`, `out/flip_2x_locked.gif`,
  `out/flip_portrait_3x_locked.gif`.
- **Owner's view: to record.** (My own check on the 1x sheet: the portrait is 224 px tall against the sprite's 57; its pixels
  are the same size as the room's and the sprite's; I could not judge the GIFs' motion, only that they are built from the
  same frames as the sheets.)

### Answers to 0240's four questions (proposed here; the Owner accepted 1, 2 and 4 on 2026-11-18, and on 3 wants more
colours, at least eventually: `n` a parameter up to 256, default 32 for now; see 0240's Answers)

1. **Does registration hold on the free image model's edits, and is a `face` region needed?** Proposal: yes, it holds; on this
   set it moves nothing (worst 0.3 source px, residual 0.03-0.09), and it recovers a deliberate shift of up to 14 px and 3 %
   to within 0.3 px. A `face` region isn't needed for the estimate (the turned head didn't pull it) but is needed for the
   lock (item 2). Keep `register` in the Kind, with `portrait.misaligned`, for edits that do drift; build nothing more for it.
2. **Shimmer: is `lock_outside_face` for the first build?** Proposal: **yes.** About 78 % of the body's pixels differ exactly
   between emotions and 521-898 per emotion visibly (the hoodie's linework), because the model redraws the body; one fit and
   one palette mapping don't stop it, and it would show in the game on every line. The lock gives 0. Proposal:
   `lock_outside_face` on by default when a `face` region is drawn; without a region `portrait.shimmer` says so. The region
   must cover everything meant to change (a raised hand or a moved arm sits outside a head box; for such an emotion it's a
   polygon, not a rectangle).
3. **Skin and hair on the ramp table.** Decided by the Owner (2026-11-16): no. What the trial found instead: the set's own
   colours, **n=32** (24 is the least that reads smoothly, 16 bands), **no dither**, one set over every emotion.
4. **The canvas and scale.** Proposal: 160 x 224, bottom centre, the scale from the neutral (5.357 here) by `Grid.cover`, one
   crop for the set. The model's 3:4 leaves the head 19 px below the top and the body cut at the bottom edge, which suits a
   waist-up portrait. The style beside the room and the sprite is the Owner's to judge on the sheets.

### Changes to 0242-0245 (accepted 2026-11-18; made in 0243)

- **0243 `cutout`:** the Prop's chroma key is exact (`chroma_key`), which these JPEGs defeat. Add a tolerance (the key colour
  read from the image's border, a distance in OKLab) and remove the generator's **white rim** (bright unsaturated pixels
  connected to the cleared background, within about 10 px) and the green spill; both are in `portrait_set.cutout`. Probably
  parameters of `chroma_key` or a new Op, since the Prop's Stage would use them too. Opaque islands under about 1,500
  source px go as well; `remove_small_pieces` is too slow at this size (10 s per image), so that pass needs a faster Op.
- **0243 `register`:** keep, `face` none by default; most sets need nothing. The Stage's log says so when it is the identity.
- **0243 `finish`:** `lock_outside_face` in the first build (proposal 2); the outline gets a `placement`, `edge` by default.
  `portrait.shimmer` counts the exact differences and the ones over 0.03 ΔE; the first is 78 % here and means little, the
  second is what shows.
- **0243 `palette`:** default `n` 32, `dither` 0; no change to the Op. Report the colours per image as the trial did.
- **0243 acceptance:** the fixture's shifted-and-scaled emotions work (`register_check.py` confirms it); add a fixture whose
  emotions differ by noise outside the face, as these do, so the lock is tested against what real edits do and not only
  against clean shifts.
- **0242, 0244, 0245:** no change from the trial.
