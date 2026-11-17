---
status: done
milestone: M4
agent: character-pipeline
type: trial
parent: 0161-m4-characters-after-the-m3-gate.md
depends_on: [0148-m4-render-material-pass.md]
---

# M4: trial: a weapon in a battle clip

Spec §6.3 (clips, render) and §16 (open decision 9). The game's DEC-051: a class changes the battle clips, **with the weapon in
the frames**: Sanjay's leaf rake, an instrument for the musician, a melee weapon for the third class. Added 2026-11-12. **High
priority:** it blocks the game's M03-02 ("one attack clip per class").

## The gap

Kiripix renders the Model's meshes and nothing else. A battle clip from Mixamo moves an empty hand; there is no way to put a
weapon in it for some clips and not in idle, walk or run.

## Three ways

1. **(a) An `attach` field on a `clip` Decision:** a mesh (from a file imported with a new role, such as `--role attachment`, or
   an object of a `.blend`) parented to a named bone for that clip only, with an offset and rotation. Its material is a material
   of the material pass ([0148](0148-m4-render-material-pass.md)), so it can be a part with its own ramp (`rake`) or a fixed
   colour.
2. **(b) The Owner makes one rigged file per class** in Blender, with the weapon parented to the hand, and imports it as the
   clip source. Today a clip source gives only its action, not its meshes, so either `render` would take the meshes of the clip
   source too, or each class becomes its own character Asset (4 bodies x 3 classes = 12 Assets, rendering idle, walk and run
   12 times).
3. **(c) A weapon layer** over the body: needs M5's layers ([0152](../m5/0152-m5-character-layers.md)), so probably not for the
   game's M03.

## What to do

1. Prototype (a) on mc02's `attack` clip with a placeholder stick (a 1 m cylinder, its own material `weapon`) parented to the
   right hand, in the trial's own folder (a Blender script over the rigged file, not in `kiripix/`). Render all 8 directions
   at 52 px, through `palette` and `finish` as far as the prototype can.
2. Measure and record:
   - **Render cost:** ms a frame with and without the stick.
   - **The cell:** the cell is one size for the whole character (M3's Q12), grown until every pose fits. A long weapon swung
     wide may grow it for every clip, idle included, and so the atlas. Record the cell before and after, and the atlas size.
   - **The outline:** the stick must be in the object mask so the silhouette includes it. Check it in `finish`.
   - **The material pass:** numbering materials by name (0148) would shift every index when `weapon` is added. Record whether
     an attachment's materials must be numbered after the Model's.
   - **Depth:** the stick in front of and behind the body by direction, as Blender draws it (no extra work expected).
3. Weigh (b) and (c) on paper against (a): Asset count, renders, files the Owner keeps in Blender.
4. Lay out the 8 directions of the attack with and without the stick as a sheet at 4x, and a GIF; list their paths here.
5. Record the Owner's choice. If (a) wins, file the build ticket (Decision field, attachment import, `render` parenting, the
   material pass order, `describe`), after [0156](0156-m4-edit-a-clip.md) since both edit `kiripix/recipes/clips.py`.

## Acceptance criteria

- [x] The sheet, the GIF and the measures above, recorded here with their paths.
- [x] The Owner's choice recorded, and the build ticket filed if (a) is chosen. (Deferred to M5; no build ticket.)

Budget: 150–250k tokens.

## Results (2026-11-15, steps 1 to 4; the Owner's choice, step 5, is open)

**Subject.** `character.mc02` (rigged Mixamo file, clips idle 100 frames, walk 32, attack 25, all at 12 fps, 8 directions, 52 px).
mc02's art-Project folder has no built stages (only an old `out/export`), so a scratch copy of the Asset was built end to end with the
real Stages (`model`, `rig`, `clips`, `render`, `palette`, `finish`, `sheet`) in a scratch Project outside the repo, with `bands = 2`,
`shadow = 0.22` (the mc03 look). That is the baseline ("without"). The art Project was left alone.

**The prototype** (all in `backlog/m4/0170-trial/`, nothing in `kiripix/`):

- `weapon_render.py`: runs inside Blender. It executes `kiripix/blender/render_frames.py` unchanged and adds, as option (a) would,
  one cylinder (8 sides, 1.18 Blender units long = 1 m on a 1.7 m body, radius 0.04, so about 2 px wide) with its own material
  `weapon`, parented by bone-parenting to `mixamorig:RightHand`, gripped 0.25 from its lower end, lying along the hand bone's X
  axis, and drawn (`hide_render`) only in the `attack` clip. The offset and rotation are guesses, not tuned: the stick is in a loose
  fist, not following the swing's intent.
- `run_trial.py` builds `render_frames` args from the built Asset and fits the cell with Kiripix's own `fit_cell` and `clip_bounds`
  (read-only import). `experiment.py` measures and renders; `bench.py` times; `build_with_stick.py` makes the "with" Project (all
  three clips re-rendered at the new cell, attack with the stick) and then `kiripix run --force palette`, `finish` and `sheet` ran on
  it with the real Stages; `check_outline.py` and `depth_and_numbering.py` measure the rest; `make_sheet.py` makes the images.
  Raw numbers: `measures.json`, `bench.json`, `outline_check.json`, `depth_and_numbering.json`.
- Limit: the prototype stands in for `render` only. `palette`, `finish` and `sheet` are the real Stages, run on the prototype's frames.

### Measures

- **Render cost.** The attack clip, 200 frames (25 x 8), CPU, 4 alternating runs each, loop only: **55.8 ms a frame without the
  stick, 59.4 ms with it** (runs 52.6 to 59.1 and 55.1 to 63.0; the difference, about 6 percent, is inside the run to run spread, and
  the with-stick frames are bigger, 92 px against 78). The stick costs nothing worth planning for. It was measured on CPU so as not
  to take the GPU lock; at one sample and no bounces, the cost is per-frame overhead (EXR write, numpy), not the geometry.
  All three clips at the 92 cell: 1056 frames in 64 s (61 ms a frame).
- **The cell.** The default cell is 78 (1.5 x 52). The attack's extent grew from +-32.2 px wide, -53.6 px up to **+-44.9 px wide,
  -60.8 px up** with the stick, so the fitted cell becomes **92** (pivot (46, 82), from (39, 68)). Idle and walk have no stick, but the
  cell is one size for the character, so **every clip is re-rendered at 92 and the atlas grows**: cell area 6084 to 8464 px
  (+39 percent). **Atlas 2652 x 2574 to 3128 x 3036** (34 columns; +39 percent in area). Width, not height, drives it: a 1 m weapon
  at arm's length goes about 12 px past the body's own reach. A longer weapon (a spear) would grow it further. Every clip's PNG and
  every Godot frame gets that much transparent margin; the exported frames are 92 px cells for idle too.
- **The outline.** `pass_index = 1` is set on every mesh by `render_frames.py`, so the stick is in the object mask with no extra
  work: of 9853 stick pixels in the 200 attack frames, 9853 are in the mask. After `palette` and `finish`, all 5289 background pixels
  beside a stick pixel are outlined (colour (1, 1, 3), the outline colour, the same as the body's). The stick has a palette colour
  (a tan); the palette stays 16 colours, so the stick took one slot from the body's colours. The stick never vanished (no
  `sheet.part_vanishes` for `weapon`; the existing warnings for backpack, straps and eyes are the body's, as in the baseline).
  The stick was 0 pixels in idle and walk, as wanted.
- **The material pass.** Numbering by name, as 0148 does, **does shift indices**, depending on the name: `weapon` sorts after
  `straps`, so for mc02 it is 10 and nothing moves, but `rake` is 8 (skin 9, straps 10) and `aardvark` is 1 (everything moves up).
  So **an attachment's materials must be numbered after the Model's** (Model's by name from 1, attachments after them): the indices of
  the body's parts stay the same in every clip and in every character that shares the base, which matters for the shared ramp
  table of [0166](0166-m4-ramps-match-across-characters.md) and [0167](0167-m4-project-ramp-table.md). (Verified by renaming; the
  "numbered last" variant gave backpack 1 to straps 9, weapon 10, whatever the weapon's name.) Also: `render.json`'s `materials`
  lists `weapon` for the whole character, with no pixels in idle and walk; `palette` and the Checks must tolerate a material
  absent from a clip.
- **Depth.** The stick is drawn by the depth test as Blender draws it. Share of the stick hidden by the body, by direction (all 25
  frames, the stick alone rendered against the full render): s 27.8, sw 43.7, w 51.2, nw 45.4, n 20.2, ne 11.0, e 9.9, se 9.7
  percent. So it is mostly in front of the body in the east and south-east views (right hand toward the camera) and about half behind it in the west views. No extra work, as expected. Where the stick crosses the
  body, the outline is only at the silhouette (`inner_lines` was off).

### Sheet and GIF

- Sheet at 4x (one row per direction s, sw, w, nw, n, ne, e, se; frames 0, 4, 8, 12, 16, 20 of the 25 of attack; left block without
  the stick, right block with it; both in the same 92 px cell, finished frames):
  `C:\Workspace\kiripix\backlog\m4\0170-trial\attack_8dir_without_left_with_right_x4.png`
- GIF at 2x, all 25 frames at 12 fps, the 8 directions side by side, without (top row) and with (bottom row):
  `C:\Workspace\kiripix\backlog\m4\0170-trial\attack_8dir_without_top_with_bottom_x2.gif`

### (b) and (c) against (a), on paper

| | (a) `attach` on a `clip` Decision | (b) a rigged file per class | (c) a weapon layer (M5) |
|---|---|---|---|
| Assets | none added: one body, one `attack` clip per class (a class is a `clip` with its attachment, e.g. `attack_rake`) | 4 bodies x 3 classes = 12 character Assets, or `render` takes the meshes of a clip source (new, and then the weapon is in every clip of that file) | none added, a Layer per weapon |
| Renders | idle, walk and run once per body; each weapon clip once. But the cell grows for all clips (+39 percent atlas here) | idle, walk and run 12 times (or the same render stage reading meshes from clip files) | the body once; the weapon is rendered separately, so the body's cell isn't grown, but the weapon needs its own render pass or Layer |
| Owner's files in Blender | one stick or weapon mesh per class (an object of a `.blend` or a glb) and an offset and rotation to tune, nothing per body | one rigged `.blend` per class, kept in step with the body's rig and Model | a weapon mesh, plus Layers of M5 (not available for the game's M03) |
| Cell | grows for every clip | grows for the clips with the weapon, but its own Asset takes the whole cell | stays (the weapon layer is composited, with its own size) |
| Fits the game's M03 | yes, a build of 4 parts (Decision field, import, parenting, material order, `describe`) | yes, today, by hand, with a lot of Owner work | no (M5) |

(b) is the only one that works today but multiplies the render cost and the Owner's Blender files by the number of classes.
(c) is the cleanest on the cell and is the later answer, but isn't for M03. (a) costs 3 to 4 tickets of build and no new Assets.

### Recommendation for the Owner (not a decision)

**Take (a)**, because the stick cost nothing in render time, is in the mask and the outline for free, and needs no new Assets.
Build it with: attachment materials numbered after the Model's; the attachment's bone named per clip (not per Asset), with offset
and rotation as a Decision field; and decide the cell's growth first. At 52 px a 1 m weapon makes the cell 92 for every clip, +39
percent atlas, so either the Owner accepts it, or a later change gives a clip its own cell (it is one size now by M3's Q12, which
the exporter and the game's sprite frames assume), or (c) is used for long weapons. Not tried here: a weapon with a real mesh and
texture (only a flat-coloured cylinder), tuning the grip per clip, the GPU render, and a weapon that needs two bones (a bow).
No build ticket was filed and the status is unchanged.

## The Owner's choice (2026-11-15)

**Deferred to M5.** (a) looks right in the sheet, but the stick isn't in the hand: it floats beside it, lifted in the air. The
grip offset and rotation were guesses (see the prototype above), and getting a weapon to sit in the fist for every frame is the
part (a) still has to prove. With M5 close, the Owner keeps these results as the baseline and compares (a) with (c), the weapon as
a layer, in M5's layer trial, [0153](../m5/0153-m5-character-layer-trial.md) ("A weapon as a layer"). No build ticket is filed.

Kept for that comparison: the scripts, the four `.json` measures, the sheet and the GIF in `backlog/m4/0170-trial/`. The scratch
Projects were in the session's scratchpad and are gone; `build_with_stick.py` and `run_trial.py` rebuild them.

The game's M03-02 ("one attack clip per class") goes without a weapon in the frames until M5 settles this.
