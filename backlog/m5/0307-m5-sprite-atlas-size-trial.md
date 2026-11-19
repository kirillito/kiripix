---
status: done
milestone: M5
agent: character-pipeline
type: trial
parent: 0236-m5-the-games-next-needs.md
---

# M5: trial: smaller character atlases: fewer frames, trimmed cells, mirrored directions

The Owner, 2026-11-18: "The image size for sprites is important. Right now the number of frames in animations can be cut further.
They're unnecessarily smooth, but the files produced are extremely large. This won't be sustainable on a large set of animations."
Prototype code stays in `backlog/m5/0307-trial/`, not in `kiripix/`.

## What we know

- 0238 measured `mc03_male_clothes01`'s 12 clips: 119 frames a direction, 952 cells of 78 px, a colour atlas of 23.2 MB as RGBA in
  memory, and the normal atlas doubles it (the real sheet of its first 6 clips is 2262 x 2184 px). A figure in `idle` is about 25 x 59 px of its 78 x 78 cell.
- A clip's frame count is already a parameter: its `fps` (and the Project clip table's, 0239). No code is needed to cut frames, only the
  choice per clip.

## What to do

On the four mc03 bodies' real clips:

1. **Fewer frames:** each clip at its current `fps` and at lower ones (for example 12, 8, 6), as GIFs side by side at 1x and 3x for the
   Owner to pick per clip. Record the frames and the atlas size at each.
2. **Trimmed cells:** each frame cropped to its opaque box in the atlas, packed, with `AtlasTexture.margin` restoring the cell in Godot.
   Measure the atlas area and the PNG size against today's, and check in Godot 4.7 that the feet stay on one pixel.
3. **Mirrored directions:** render `s sw w nw n` and mirror `ne e se` in the game (`flip_h`). Measure the saving, and what breaks: an
   asymmetric character (a held thing in the right hand, a side parting), and the normal map's x (it must flip with the frame).
4. **Duplicate frames:** count identical frames (holds, `still`, the ends of a loop) that one region could share.
5. **The PNG itself:** indexed colour (the palette is fixed) against RGBA, and the size on disk against in VRAM.

## What to record, in this ticket

- A table: each lever's saving alone and together, on disk and in VRAM, for the four bodies.
- The Owner's choice of `fps` per clip (then the clip table's values), and which levers to build, with their tickets.

## Acceptance criteria

- [x] The measures and the side-by-side GIFs above, their paths listed here.
- [x] The Owner's choice recorded, and the build tickets filed.

## Result (2026-11-18: steps 1, 2, 4, 5 done; step 3 measured, nothing built; the Owner's choice is open)

Everything is in `backlog/m5/0307-trial/` (scripts, `measures.json`, `mirror.json`, `dupes.json`, `table.md`, `summary.md`, `gifs/`, `sheets/`).
Nothing in `kiripix/`, `blender/`, `tests/` or the art repo changed.

**How.** The art repo's four mc03 bodies (`mc03_male`, `mc03_female`, `mc03_male_clothes01`, `mc03_female_clothes01`) were copied to a scratch Project
in the session scratchpad and built by the real Stages (model, rig, clips, render on the CPU so no GPU lock, palette, finish, sheet), using the
committed code only (a `git archive HEAD` of `kiripix/`, so another agent's edits to `clips.py` or `render_frames.py` don't count). The clips are the
Owner's current clip Decisions: 7 clips plus their transitions (12 clips, 119 frames a direction, 952 cells for `mc03_male_clothes01`, as 0238 found;
the other bodies 928). Two things in the art repo are mid-change, so the scratch copy differs from it: the last Model pick and the rigged file no longer match
(the rig is in `_retired_rigged`), so the scratch pins each Asset's pick to the variant its built `work/model` came from; and the clothes01 bodies'
`palette` `parts` name materials the render doesn't have, so the scratch uses `parts = skin,hair`. Neither changes frame counts or cells; the colour
count may differ a little from the Owner's. The Owner's own `work/sheet` files are the old 3-clip ones.

Disk = `color.png` + `normal.png` as this trial's PNG encoder writes them (the real Stage's files are within a few percent: `mc03_male_clothes01` colour 302 KB,
normal 849 KB). `depth.png` is in `work/sheet` but isn't exported, so it isn't counted. VRAM = RGBA8, width x height x 4 for each of the colour and
normal atlases (what Godot holds for a lossless-imported PNG, whatever the PNG's colour type).

Levers: **A** fewer frames (every clip decided at `min(its fps, cap)`, rendered again by the real Stages in scratch Assets `<body>_f8`, `_f6`, `_f4`);
**B** trimmed cells (each frame cut to the opaque box of either pass, MaxRects packed with a 1 px gap, one layout for colour and normal);
**C** mirrored directions (only `s sw w nw n` stored); **D** duplicate frames share one region; **E** indexed PNG (8 bit, exact palette, transparency).
Today's atlas is a near-square grid of the cells with no empty cells, so the layout alone gains nothing.

### The table (disk / VRAM; the change against "now" in brackets)

| Lever | mc03_male | mc03_female | mc03_male_clothes01 | mc03_female_clothes01 |
|---|---|---|---|---|
| Now (the real atlas, as this trial encodes it) | 1008 KB (+0 %) / 43.2 MB (+0 %) | 1071 KB (+0 %) / 43.2 MB (+0 %) | 1118 KB (+0 %) / 44.6 MB (+0 %) | 1153 KB (+0 %) / 43.2 MB (+0 %) |
| A: fps cap 8 | 867 KB (-14 %) / 39.0 MB (-10 %) | 924 KB (-14 %) / 39.0 MB (-10 %) | 961 KB (-14 %) / 40.4 MB (-9 %) | 993 KB (-14 %) / 39.0 MB (-10 %) |
| A: fps cap 6 | 730 KB (-28 %) / 32.6 MB (-25 %) | 778 KB (-27 %) / 32.6 MB (-25 %) | 826 KB (-26 %) / 33.8 MB (-24 %) | 835 KB (-28 %) / 32.6 MB (-25 %) |
| A: fps cap 4 | 570 KB (-43 %) / 25.6 MB (-41 %) | 606 KB (-43 %) / 25.6 MB (-41 %) | 651 KB (-42 %) / 26.7 MB (-40 %) | 651 KB (-44 %) / 25.6 MB (-41 %) |
| B: trimmed cells | 908 KB (-10 %) / 9.7 MB (-78 %) | 976 KB (-9 %) / 9.4 MB (-78 %) | 1043 KB (-7 %) / 10.4 MB (-77 %) | 1101 KB (-5 %) / 9.9 MB (-77 %) |
| C: mirrored directions | 638 KB (-37 %) / 27.9 MB (-35 %) | 679 KB (-37 %) / 27.9 MB (-35 %) | 703 KB (-37 %) / 27.9 MB (-38 %) | 727 KB (-37 %) / 27.9 MB (-35 %) |
| D: duplicate frames shared | 980 KB (-3 %) / 39.0 MB (-10 %) | 1040 KB (-3 %) / 37.7 MB (-13 %) | 1083 KB (-3 %) / 39.0 MB (-12 %) | 1124 KB (-3 %) / 39.0 MB (-10 %) |
| E: indexed PNG | 411 KB (-59 %) / 43.2 MB (+0 %) | 423 KB (-61 %) / 43.2 MB (+0 %) | 452 KB (-59 %) / 44.6 MB (+0 %) | 454 KB (-61 %) / 43.2 MB (+0 %) |
| B+D+E (no C) | 394 KB (-61 %) / 8.8 MB (-79 %) | 397 KB (-63 %) / 8.3 MB (-81 %) | 436 KB (-61 %) / 9.2 MB (-79 %) | 440 KB (-62 %) / 8.9 MB (-79 %) |
| A cap 8 + B+D+E (no C) | 335 KB (-67 %) / 7.7 MB (-82 %) | 349 KB (-67 %) / 7.2 MB (-83 %) | 371 KB (-67 %) / 8.0 MB (-82 %) | 383 KB (-67 %) / 7.8 MB (-82 %) |
| A cap 6 + B+D+E (no C) | 269 KB (-73 %) / 6.0 MB (-86 %) | 283 KB (-74 %) / 5.9 MB (-86 %) | 304 KB (-73 %) / 6.6 MB (-85 %) | 296 KB (-74 %) / 6.2 MB (-86 %) |
| A cap 4 + B+D+E (no C) | 202 KB (-80 %) / 4.4 MB (-90 %) | 212 KB (-80 %) / 4.0 MB (-91 %) | 237 KB (-79 %) / 5.0 MB (-89 %) | 233 KB (-80 %) / 4.5 MB (-90 %) |
| B+C+D+E | 245 KB (-76 %) / 5.7 MB (-87 %) | 248 KB (-77 %) / 5.2 MB (-88 %) | 273 KB (-76 %) / 6.1 MB (-86 %) | 269 KB (-77 %) / 5.6 MB (-87 %) |
| A cap 8 + B+C+D+E | 198 KB (-80 %) / 5.0 MB (-88 %) | 212 KB (-80 %) / 4.5 MB (-90 %) | 213 KB (-81 %) / 4.9 MB (-89 %) | 235 KB (-80 %) / 4.9 MB (-89 %) |
| A cap 6 + B+C+D+E | 158 KB (-84 %) / 3.7 MB (-91 %) | 171 KB (-84 %) / 3.4 MB (-92 %) | 181 KB (-84 %) / 4.2 MB (-91 %) | 184 KB (-84 %) / 3.9 MB (-91 %) |
| A cap 4 + B+C+D+E | 121 KB (-88 %) / 2.7 MB (-94 %) | 132 KB (-88 %) / 2.6 MB (-94 %) | 149 KB (-87 %) / 3.2 MB (-93 %) | 142 KB (-88 %) / 2.8 MB (-93 %) |

The levers don't add up (B and D, C and D, share cells), so the "together" rows are measured, not summed. Per body and clip: `summary.md`.

### 1. Fewer frames (A)

Frames a direction by fps (`mc03_male_clothes01`; the other bodies are the same):

| Clip | now | 8 fps | 6 fps | 4 fps |
|---|---|---|---|---|
| attack | 12 fps, 19 | 13 | 10 | 7 |
| walk | 10 fps, 8 | 6 | 5 | 3 |
| run | 12 fps, 8 | 5 | 4 | 3 |
| phone | 8 fps, 27 | (27) | 20 | 14 |
| phone_in | 8 fps, 13 | (13) | 10 | 7 |
| phone_out | 8 fps, 17 | (17) | 13 | 9 |
| idle | `still` 16, 8 fps | 16 | 16 | 16 (its frame count is `still`, not the fps) |

The 8 fps cap is -14 % disk and -10 % VRAM, 6 fps -27 % and -25 %, 4 fps -43 % and -41 %. Transitions (2 to 3 frames) don't change. The GIFs play each clip over
the same time, so a lower fps shows as fewer poses, not a slower clip (a looping clip's lower variants run a few percent off the exact rate, because a whole number
of frames fills the loop: walk at 10 fps is 8 frames, at 8 fps 6).

### 2. Trimmed cells (B), and Godot 4.7.2

- A figure fills little of its 78 x 78 cell, so trimming cuts the atlas area 4 to 4.5 times: 2418 x 2340 to 1310 x 969 (`mc03_male`). **VRAM -77 to -78 %** (43 MB to
  10 MB) but **disk only -5 to -10 %**, because PNG already squeezes the empty cells. B is the VRAM lever, E the disk lever.
- Godot check (Godot 4.7.2-stable is on this machine; `0307-trial/godot_check/check.gd` and `check_lit.gd`, OpenGL compatibility driver): `mc03_male`'s 928 frames as
  `AtlasTexture` (`region` plus `margin = (left, top, cell w - w, cell h - h)`) of the trimmed atlas, drawn by an `AnimatedSprite2D` set up as the export does
  (`centered = false`, `offset = -pivot`, root at the pivot). **All 928 frames are pixel-identical to the untrimmed cell, plain and with `flip_h`** (0 differing
  pixels), so the feet stay on one pixel and the pivot rule holds. With a `CanvasTexture` atlas (diffuse plus normal, as the export's `.tres`) and a
  `DirectionalLight2D`, 528 lit renders (every 7th frame, two light angles, flip off and on) equal the whole-cell version: **the normal map trims with its colour, and the
  margin works under `flip_h`.** (`prep_godot.py` writes the data; its folder is not kept.)
- Cost: `character.json` needs a per-frame `margin` next to `rect` (the `.tres` already has one `AtlasTexture` per frame), and a packer in `sheet`. A 1 px gap was
  assumed; nearest filtering needs none.

### 3. Mirrored directions (C), measured, not built

- Saving: 3 of 8 directions stored less: **-37 % disk, -35 to -38 % VRAM** alone.
- What breaks:
  1. **Today's frames are not mirror images.** Flipping `nw` and comparing with the rendered `ne` (likewise `w`/`e`, `sw`/`se`), `mc03_male_clothes01`'s silhouette
     differs in (share of the pixels either has) `idle` 23 %, `phone` 26 %, `walk` 40 %, `run` 45 %, `attack` 61 %, and the colours in 68 to 90 %. The other three bodies are within
     3 points. It is not a pixel shift (shifting the flip by -2 to 2 px, 0 is the best). `0307-trial/sheets/mirror_<body>_x3.png` shows render, flipped and difference
     for four clips.
  2. **The Model and the poses are asymmetric**: the idle's weight shift, the hair, the dragon print on the tee, and above all the clips (a right-handed `attack` becomes
     left-handed; a mirrored `walk` starts on the other foot, best phase shift 4 of 8 frames; a thing held in the right hand, such as 0238's phone or stick, moves to the left).
  3. **The baked light flips.** The toon light is fixed in camera space (top left), so a mirrored frame is lit from the top right.
  4. **The normal map's x has to flip with the frame.** Measured, the flipped normal with x negated (R to 255 - R) is closer to the render than without (mean channel
     difference 29 to 48 against 48 to 54), though not equal (point 1). **Godot 4.7.2 does it itself**: a flat normal map leaning +x, lit by a directional light at 8 angles, is
     lit from the opposite side with `flip_h` on (`godot_check/light_flip.gd`), so the game needs no shader change.
  5. `flip_h` with `margin` is exact (section 2). The cell mirrors exactly only because the pivot is x = 39.0 in a 78 px cell; an odd cell width, or a pivot
     not at half the width (0238's 86 px stick cell, pivot 43), moves the pivot by a pixel.
  6. The export (`character.json`, `.tres`) would need the three directions to point at another direction's frames with `flip_h` set, the game's direction picker would
     set it, and the pivot-drift Check should compare a mirrored frame with its source.
- So C costs the look unless the three directions are rendered from a symmetric Model with symmetric clips. It is the lever the Owner should judge on the mirror sheets.

### 4. Duplicate frames (D)

Only `idle` has them: a `still` of 16 frames with one blink frame, so 128 cells hold 13 distinct frames (115 duplicates; 118 for `mc03_female`). Nothing else has any:
no holds, no loop ends, no transition ends equal to their clip's (0 shared between clips). Saving: **-3 % disk, -10 to -13 % VRAM**. A shorter `still` (say 2 frames,
the game holds one) saves the same with no atlas change.

### 5. The PNG itself (E)

- The palette is fixed: the finished colour atlas has 17 distinct colours (counting transparent) for `mc03_male`; the normal atlas 141 to 143 (its own levels). Both fit an 8-bit indexed PNG.
- Indexed: **-59 to -61 % on disk** (about 1.0 to 1.15 MB to 0.41 to 0.45 MB), **no change in VRAM**: Godot imports a lossless PNG as RGBA8 whatever it was on disk. VRAM shrinks
  only by trimming, mirroring, fewer frames, or a VRAM-compressed import (BPTC is a quarter, but lossy: not suited to a palette or a normal map, and not tried).
- The `sheet`/`export` Stages would have to write the indexed PNG, and the Godot import must stay lossless.

### Side-by-side GIFs (the Owner picks fps per clip from these)

All in `C:\Homespace\kiripix\backlog\m5\0307-trial\gifs\`, named `<body>_<clip>_x1.gif` and `<body>_<clip>_x3.gif` (1x and 3x), 56 files, 5.7 MB. One column per fps (the
current one first, then 8, 6 and 4 where lower; each labelled with its fps and frames), rows `s`, `e`, `n`, finished frames. Clips: `walk`, `run`, `attack`, `phone`, `phone_in`,
`phone_out`, and `idle` (one column: its frame count is `still`). Bodies: `mc03_male_clothes01`, `mc03_female_clothes01`, `mc03_male`, `mc03_female`.
Examples: `...\gifs\mc03_male_clothes01_walk_x3.gif`, `...\gifs\mc03_male_clothes01_attack_x3.gif`, `...\gifs\mc03_female_clothes01_run_x1.gif`.

Other sheets: `...\0307-trial\sheets\mirror_<body>_x3.png` (lever C: render | flipped | difference).

### What the numbers say (not a decision)

1. E (indexed PNG) and B (trim) change no pixel: -60 % disk and -77 % VRAM; both live in `sheet` and `export` (and a `margin` in `character.json`). Godot draws B exactly, flipped and lit.
2. A is the Owner's per-clip look decision; the 8 fps cap is -14 % disk, -10 % VRAM, and `idle`'s `still` can be shortened for nothing.
3. C changes the look and the clips; keep it for symmetric clips if at all.
4. Without C, B + D + E is about -61 to -63 % disk and -79 to -81 % VRAM (about 9 MB a body, from 43 MB); with A cap 8 on top, about -67 % disk and -82 % VRAM (about 8 MB); with A cap 6, -73 % and -86 % (6 MB). With C too, 150 to 235 KB and 3 to 5 MB.

Not done: no GPU render (the CPU render is the same pixels); the Godot checks ran on `mc03_male` only; no load-time measure of the larger `.tres`; the Owner's fps choice and
the build tickets, which wait on the Owner.

## The Owner's choice (2026-11-18)

- **fps:** 8 for every clip, except `run` at 12 ("better at 12fps"). These go into the Project's clip table (0239) in the art
  repo, the Owner's data; no code. `idle` (a `still`) has no fps column: a shorter `still` there also removes its duplicate
  frames (lever D), so D needs no build.
- **No mirroring** (lever C): it breaks the look (asymmetric Models, right-handed attacks, the baked light, held things).
- **Build:** trimmed cells (B) and indexed PNG for the colour atlas (E):
  [0308](0308-m5-trimmed-cells-in-the-sheet.md), [0309](0309-m5-export-trimmed-cells.md),
  [0310](0310-m5-indexed-colour-atlas.md).
