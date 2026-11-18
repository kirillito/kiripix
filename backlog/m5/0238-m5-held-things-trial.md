---
status: done
milestone: M5
agent: character-pipeline
type: trial
parent: 0236-m5-the-games-next-needs.md
---

# M5: trial: a thing held in the hand, (a) attached or (c) a layer, and the cell

Spec §6.3 (clips, render) and §16 (open decision 9). Part of [0236](0236-m5-the-games-next-needs.md), item 1. Prototype code
stays in `backlog/m5/0238-trial/`, not in `kiripix/`.

**Moved here from the layer trial** ([0153](0153-m5-character-layer-trial.md), its steps 6–8) by the Owner on 2026-11-16,
because the game needs it two to four game milestones before layers.

## What the game needs

- **M03 (now):** the phone in the MC's `phone` idle (the game's DEC-068).
- **M05:** Sanjay's leaf rake, and the Beast Master's attack with its prop.
- **M06:** the Jazz Musician's battle clips with the instrument in the frames, on both bodies and both outfits (M06-13).

The baseline is [0170](../m4/0170-m4-weapon-in-a-battle-clip-trial.md) (`backlog/m4/0170-trial/`): option (a), a 1 m stick
parented to the right hand in `attack`. Two things stopped it:

- the stick floated beside the fist, because its offset and rotation were guesses;
- the cell grew from 78 to 92 for every clip, idle included (+39 % atlas).

## What to do

On `mc03_male_clothes01`, with two things: the phone (in its `phone` clip, or `idle` until that exists) and the 0170 stick or a
rake (in `attack`).

1. **The grip.** Find how a held thing sits in the hand in every frame. Try an empty (a socket) parented to the hand bone in
   the Model, with the thing parented to it. Or a grip bone, or an offset and rotation per clip. For the generator-built
   Models, say whether `chargen` can add the socket. Show the phone and the stick in all 8 directions at 4x and as a GIF.
2. **(a) attached against (c) a layer.** (a): the thing is in the character's render for that clip only. (c): it's rendered
   alone with the body as a holdout, in the body's cell and pivot, and stacked in the game. Compare them on:
   - the cell and atlas size;
   - render cost;
   - the outline where the thing crosses the body's silhouette;
   - depth by direction (the phone behind the body facing north);
   - the Owner's files in Blender;
   - the Assets needed (both bodies, both outfits, three classes).
3. **The cell.** Measure what (a) costs with the cell as it is (one per character), and with a cell per clip (idle and walk
   keep 78). A cell per clip changes `character.json` (`cell` and `pivot` per clip) and the game's loader. Say what breaks
   and what it saves. Under (c) the body's cell doesn't change, but say how big the layer's cell is.
4. **Colours.** Try the held thing with its own ramp row in the Project ramp table, and with fixed colours outside every
   part. Either way, a skin or hair swap must never touch it. Record which the Owner wants, per thing (the phone is probably
   fixed, an outfit-coloured weapon a row).
5. **Points.** If [0237](0237-m5-render-records-named-points.md) has landed, check that its `hand_r` point and the grip
   agree to a pixel, so the game's fallback and the real thing line up.

## What to record, in this ticket

- The sheets and GIFs, with their paths, and the Owner's view of each.
- The measures for 2 and 3, against 0170's.
- **The Owner's choice of (a) or (c)**, the grip method and the cell rule. Then file the build tickets, each with its agent:
  - for (a): the `attach` field on a `clip` Decision, the import, the parenting, attachment materials numbered after the
    Model's (0170), the cell rule and `describe`;
  - for (c): the weapon part of [0152](0152-m5-character-layers.md) goes first.

## Acceptance criteria

- [x] The phone and the stick sit in the hand in every frame and direction, on the sheet (the grip is rigid; the Owner's eye on the offsets is pending).
- [x] (a) and (c) compared on the points above, with numbers.
- [x] The Owner's choice recorded, the build tickets filed, and spec §6.3 and §16 decision 9 updated to say which.

## Results (2026-11-18, steps 1 to 5; the Owner's choice is open)

Everything is in `backlog/m5/0238-trial/` (scripts, JSON results, `sheets/`). Frames and the scratch Project are in the session scratchpad,
not kept; `make_project.py`, `render_scenarios.py` and `inject.py` rebuild them. Nothing in `kiripix/`, `tests/`, `web/` or the art repo
changed. Subject: `mc03_male_clothes01`'s Model (`work/model/model.blend`), its clips `idle`, `walk`, `attack` (the 0170 1 m stick), `phone_in`,
`phone`, `phone_out`, a 1.5 m rake, a phone (85 x 160 x 11 mm, a dark body and a lighter screen). Renders are CPU (no GPU lock), 8 directions,
52 px, cell 78. Option (a) is `render_frames.py` unchanged plus a wrapper that shows the things per clip and numbers their materials after
the Model's. Option (c) is the real `wearable` argument of `render_frames.py` (0291), the body a holdout. `palette`, `finish` and `sheet` are
the real Stages, run in a scratch Project made of the art repo's `kiripix.toml` and style. Raw numbers: `measures_cells.json`, `timings.json`,
`compare.json`, `colours.json`, `points_check.json`.

### 1. The grip

- **Method that works: a socket at the palm, fixed on the hand bone.** The hand is rigid: the clips don't key the fingers, so the fist's
  hollow moves 0.0 to 0.6 px inside a clip and 0.3 to 1.2 px between clips. One socket per Model, no offset per clip, is enough. The
  socket's frame comes from the rest bones, nothing guessed by eye: X across the hand (index to little finger knuckle), Y along the fingers,
  Z out of the back of the hand, origin 0.11 Model units along Y from the wrist (3.3 px, at the knuckles) and 0.02 toward the palm.
  Each thing has its own offset in that frame (`grip_config.json`): the phone lies on the palm, the stick and the rake pass through the
  fist across the palm (X). The stick sits in the fist in all 8 directions of `attack`, no floating (the 0170 fault).
- **Empty or bone?** An Empty parented to the hand bone follows the hand in Blender, but **does not survive the glb round trip**: exported by the
  glTF exporter and imported by `model` (`normalise_model.py`), it comes back parented to `RightHand` but 5.96 Model units away (the bone's
  length, 601 cm: the importer puts a bone child at the tail). A **socket bone `grip_r` under `RightHand`** survives exactly: after the same round
  trip it is 0.0005 units from where it was put (under 0.02 px), its axes agree, and `render points=grip_r@grip_r` reads it (a bone gives its head).
  `rig` allows more bones than the base. So: a bone, not an Empty.
- **Can `chargen` add it? Yes.** `generate.py` is a Blender script that already poses the hand bones (hand scale) and exports with
  `bpy.ops.export_scene.gltf`; it can add the bone just before the export from the final rest bones, so it scales with the hand and the
  body. `roundtrip_make_bone.py` does it on the built `.glb` of this character. The art repo is the Owner's; not changed.
- Thing positions in the hand's frame are set by hand in `grip_config.json` and are a first pass: at 52 px the hand is about 4 px, the
  phone 3 x 5 px. The Owner's eye is needed on every thing's offset.

### 2. (a) against (c), with numbers (0170's values in brackets)

| | (a) attached | (c) a layer (the landed Wearable, 0290-0295) |
|---|---|---|
| Render ms a frame (CPU, 1 sample) | base 60.8; with things 58.9 (stick alone in attack 57.6 vs 55.8 for the phone clips; 0170: 55.8 vs 59.4). Nothing worth planning for | the same per frame (stick layer 55.6, phone layer 48.2, rake 66.6), but **one more full render per layer**: 608 extra frames for stick plus phone over the body's 800 (+76 % of the render time; `palette` and `finish` run again too: 24 s and 20 s for the body's 800 frames) |
| Pixels | the thing adds 5,753 px to the 87,759 px of the body in `attack`; the phone 154 px of 118,038 | the stack of body plus layer equals (a) to **1 px in 93,512** (attack) and 0, 1 and 0 px in `phone_in`, `phone`, `phone_out`: a body as the one holdout is exact. The layer holds 7,454 px (stick), of which 1,701 are in front of the body; 463 px for the phone, of which 309 are in front |
| Outline where the thing crosses the body | one `finish` pass: the silhouette plus inner lines at the borders between materials (the Asset's `inner_lines = outline`) | no outline in a layer; the game draws it once on the stack: the silhouette is the same, but **the lines at the thing's border over the body are lost**: 2,465 px in `attack` (16 a frame) and 994 in `phone` (4.6 a frame) are inner-line pixels within 1 px of the thing. Unless the game draws them from the layers' depth |
| Depth by direction | as Blender draws it. The phone is hidden by the body in many frames (see below) | the same (the holdout is the body); the layer carries the body's depth |
| Owner's files in Blender | one Model with a socket bone and the thing meshes (or one file per thing, imported with a new role) | one Wearable Model per thing: skinned to the hand at weight 1 (the grip is baked in the mesh), the body deleted. As built the Wearable keeps no per-clip list |
| Assets (2 bodies, 2 outfits, 3 classes) | no Asset added; things are a field of a clip Decision. The cell is per character | 1 Asset per thing, per body (the body's skeleton): 6 weapons x 2 bodies = 12 Assets, the phone 2 more; **an outfit change needs nothing** (the layer is on the body, not the outfit) |
| Cell (one cell per character) | see 3 | **As landed, a Wearable has the body's cell and pivot (§6.3: `wearable.outside_cell`; its fix is the body's `cell_margin`).** So (c) does *not* leave the body's cell alone: the stick needs the body at 86, the rake at 138, exactly as (a). It also renders **every** clip of the body (no clip list), so a weapon layer is mostly empty frames |

The phone vanishes behind the body in many frames (`sheet.part_vanishes`, from the real Check): in `phone`, `e` 13 of 27 frames, `s` 8 of
27 (the screen 11), `se` 6, `ne` 5, `sw` 2. It is the true depth with this pose (the hands are at the belly); the game's fallback phone should
follow the point's `hidden` flag, and the Owner should look at whether that is the pose he wants. The pivot-drift Check passes for every
stationary clip with things (the pivot is the cell's pivot, as `render` sets it). Material numbers: the phone, screen, stick are 13 to 15 after
the Model's 1 to 12, as 0170 said; the body's numbers don't move.

### 3. The cell (frames of the real 12 clips: 119 per direction, 952 cells; atlas = cells x side squared, RGBA bytes for the colour atlas)

Per-clip extents are the measure pass's own (`measures_cells.json`): the body's cell is 78 for every clip (0170: 78). `attack` with the
stick needs **86** (pivot (43, 75); 0170: 92); with the rake **138** (pivot (69, 113)); the phone stays in 78 (the phone alone ends 27 px above
the feet).

| Rule | Stick | Rake |
|---|---|---|
| One cell for the character (today): every clip re-rendered at the new size | 86: +21.6 % area, 28.2 MB colour atlas against 23.2 MB (real sheet of the 6 clips: 2262 x 2184 to 2494 x 2408) (0170: +39 %) | 138: **+213 %**, 72.5 MB; the normal atlas doubles it |
| A cell per clip (idle and walk keep 78) | +3.4 %, 24.0 MB | +34.0 %, 31.0 MB |
| (c) with the Wearable as built | as one cell (the body's cell grows by `cell_margin`) | as one cell |
| (c) with the layer's own cell | the layer 86 (pivot (43, 75)), the body unchanged at 78: the saving of a cell per clip, but the layer's pivot is 4 and 8 px from the body's | 138 for the layer only |

What a cell per clip changes: `character.json` has one `cell` and one `pivot` (§9), `sheet` one atlas grid, the `.tres` the animation
regions and the scene's one offset ("offset so the pivot pixel is the origin", so the offset would be per animation) and the game's loader.
`kiripix sheet` and the stationary-pivot rule keep working; `fit_cell` already measures per clip (0155), so the numbers cost nothing.
It saves 18 percentage points for the stick and 179 for the rake. A cheaper cousin, not tried: keep one logical cell but trim each frame in
the atlas and let `AtlasTexture.margin` restore it, which shrinks both the atlas and VRAM and leaves the loader's cell alone.

### 4. Colours (real `palette` and `finish`)

- **Fixed colours outside every part (the thing in no part):** the phone took 6 colours and the stick 7 (shades and the outline's) from the
  16-colour fixed subset, which the body shares: the subset is re-chosen, and one body pixel of the 46,411 in `walk` changed (0 in `idle`).
  Harmless here, but every new thing re-chooses the body's fixed colours.
- **Its own row in the ramp table (`phone=phone+phone_screen`, `stick`, `rake=rake+rake_head`, length 2 each):** the fixed subset is
  **identical to the body's** (0 differing body pixels in idle and walk), the phone is 3 colours (with the outline's) and the stick 4, and the rows
  are colours nothing else uses, so a skin or hair swap can't touch them. Cost: a row in every character's `ramps.png` (a part a character
  lacks is a transparent row), and a 2-colour ramp makes the phone's dark body and light screen two flat colours.
- The phone has no use for a swap. A skin or hair swap never reaches either option's colours.

### 5. Points (0237)

`hand_r` is the hand bone's head, the wrist; the grip is 3.3 px along the hand. Measured over `idle`, `walk`, `attack`, `phone` (560 frame-directions): the
distance is 0.2 to 3.3 px (mean 2.6 to 2.9), the same pixel in 5 of 560 and within a pixel on each axis in 52. **They don't agree.** Fix:
record the point on the socket, `render points=hand_r@grip_r` (a bone, so it survives the round trip); then the game's fallback and the
real thing are the same point (0 px by construction, `run_points.py` reads `grip_r` through `points` in the round-tripped Model).

### Sheets and GIFs (the Owner's view of each: pending)

All in `C:\Workspace\kiripix\backlog\m5\0238-trial\sheets\`, finished frames (own ramp rows), rows s sw w nw n ne e se:
- `phone_8dir_without_left_with_right_x4.png` (the `phone` clip, frames 0, 6, 12, 18, 24; both in the 86 cell)
- `stick_attack_8dir_without_left_with_right_x4.png` (frames 0, 4, 8, 12, 15, 18)
- `rake_attack_8dir_with_x4.png` (the rake, cell 138)
- `phone_phone_8dir_x3.gif`, `stick_attack_8dir_x3.gif`, `rake_attack_8dir_x2.gif` (the 8 directions, two rows of four, at the clip's fps)

Not done: the phone's offset is a first pass and at 3 x 5 px I haven't judged it beyond the zooms (4x pixel density, scratch only); the
`phone_in` and `phone_out` clips show the phone for all their frames (the phone should come from the pocket there; a per-frame toggle isn't
tried); no GPU render; no Mixamo-rigged Model; the rake's hand pose and grip are untuned; the layer's own `palette`/`finish` (the
stack is compared in colour, before the palette).

### Proposal for the Owner (not a decision)

1. **(a) attached.** It costs nothing at render time, needs no new Asset per weapon and body, keeps the inner lines at the thing's border,
   and (c) as built has no cell advantage (the Wearable shares the body's cell) and no clip list. Take (c) only for what really is a layer
   in the game (a held thing that changes by outfit is not).
2. **Grip:** a socket bone `grip_r` under the right hand bone, added by `chargen` before its glb export (an Empty doesn't survive the glb),
   each thing with its own offset and rotation in the socket's frame; the Model keeps one socket, no offset per clip. `render points=hand_r@grip_r`.
3. **Cell rule:** a cell per clip, with the one-cell rule as the fallback: a clip whose extent doesn't fit grows its own cell, so the stick
   costs +3.4 % and the rake +34 % instead of +21.6 % and +213 %. If the Owner won't change the loader, keep one cell and cap a held
   thing's length (a 1 m stick is 86; the rake, 138, is too long for one cell).
4. **Colours:** the phone fixed, its own row not worth a row (the phone needs no swap); a class weapon (stick, rake) a row of length 2 in the
   ramp table, so it never moves the body's fixed colours and an outfit-coloured weapon can follow the outfit.

### Draft build tickets (not filed; they wait on the Owner)

For (a), in the order they edit `clips.py` and `render_frames.py` (not at the same time as 0237/0281):
1. `attach` on a `clip` Decision (`thing`, `bone`/`socket`, optional offset and turn), `describe`, validation, `clips` Stage version bump
   (core-engineer).
2. Import of a thing: a role `attachment` for a mesh file, or objects of the Model, stored per Asset; its materials (character-pipeline).
3. `render`: the wrapper's logic in `render_frames.py`: parenting to the socket bone, per-clip visibility, materials numbered after the
   Model's, the thing in the measure pass, `render.json` records `attach` per clip; `render` Stage version bump (character-pipeline).
4. Cell per clip: `render.json` `cell`/`pivot` per clip, `sheet` layout, `character.json` (`cell`, `pivot` per clip, schema bump and migration),
   the Godot export (`frames.tres` regions, per-animation offset) and the game's loader (imaging-engineer, godot-export; the game's side
   is the Owner's).
5. `palette`: a thing's material in a part or fixed; Checks tolerate a material absent from a clip (imaging-engineer).
6. chargen: add the socket bone `grip_r` to each Model and a `points` default (art repo, the Owner).
7. UI: show the thing and its socket on the frames (ui-engineer, after 0284).
For (c) instead: a clip list and its own cell and pivot for the Wearable (0290-0295 change), then the weapon Wearables per body (the
weapon part of 0152).

(Criteria below: the first and second are met; the third waits on the Owner.)

### The Owner's view (2026-11-18)

The sheets and GIFs: "Results from 0238 look amazing. Very very good, I'm pleased!" The choice of (a) or (c), the grip, the
cell rule and the colours (the proposal above) is still to record, then the build tickets.

### Comparison sheets (follow-up, 2026-11-18; made by `0238-trial/make_compare.py` from the renders above, nothing re-rendered)

All in `C:\Workspace\kiripix\backlog\m5\0238-trial\sheets\`.
- `compare_a_vs_c_stick_attack_x4.png`: rows are direction and frame of `attack` (s 4, w 8, n 8, e 4, e 12, se 10); columns (a) attached, (c) the body's own
  finished frame with the layer pasted over and the outline drawn once on the stack, the differences in red over a dimmed (a), and the layer alone. Look at the red
  lines along the stick where it crosses the jacket and legs: 1 to 20 px a frame, and the column 4, where the layer is only the visible part of the stick.
- `compare_a_vs_c_phone_phone_x4.png`: the same for `phone` (s 12, n 12, e 3, e 12, se 12, ne 12). Look at rows n and ne: the layer is empty, because the body hides the phone
  (the depth by direction), so (a) and (c) agree; the few red pixels are in s and e.
- `compare_a_vs_c_stick_attack_sw_x3.gif`, `compare_a_vs_c_phone_phone_s_x3.gif`: all frames of one direction, (a), (c) and the differences side by side.
- `cells_stick_one_cell_above_per_clip_below_x1.png` and `cells_rake_one_cell_above_per_clip_below_x1.png`: the whole atlas of the 12 clips at 1x, each cell with its grid, one
  block per clip (8 direction rows by frames), real frames where this trial rendered the clip (empty cells for run and the transitions). Above: one cell for every clip (the
  title gives the cells, pixels and MB: +21.6 % for the stick, +213 % for the rake). Below: a cell per clip, only `attack` larger (orange; +3.4 % and +34 %); every other clip,
  the phone's three included, stays 78 (the phone is the same in both).
- `cells_c_layer_own_cell_vs_body_cell_x3.png`: (c)'s layer cell for the stick (86) and the rake (138): the widest frame of `attack`, the body's 78 cell in green, the layer's own cell
  in orange, the pivot as a red cross. Look at how far the rake leaves the body's cell, and that the layer's pivot is (4, 8) and (30, 46) px from the body's.
- `compare_colours_fixed_vs_row_x10.png`: the hand at 10x, the thing in fixed colours (left) against a row of its own (right), for the stick and the phone; under them the 16 fixed
  colours of the palette (body only, things fixed, things in rows; a white frame is a colour the body-only palette lacks) and the one body pixel that changes under the fixed option,
  marked in red: `walk` `nw` frame 4, pixel (48, 72), (200, 198, 204) to (209, 208, 215), a light grey sole or shoe pixel.

What I saw that the numbers hid: the (a)-(c) differences are a handful of pixels along the thing's edge over the body, not whole areas; and under the fixed option the palette
re-chooses 9 of the 16 fixed colours (seven are tans and blues for the things), the body keeping its look only because those colours were unused in idle and walk.

### The Owner's choice (2026-11-18)

- **(a) attached**, "for clarity": the difference from (c) is barely visible on the comparison sheets (1-20 px a frame along the thing's
  edge).
- **The cell:** the body's cell, and a clip that needs more (a held thing, a long attack) grows its own: the cell-per-clip rule of
  proposal 3 (+3.4 % for the stick, +34 % for the rake, against +21.6 % and +213 % with one cell).
- **Colours:** a class weapon gets a ramp row; the phone keeps fixed colours.
- **Grip:** the `grip_r` socket bone. It isn't a look to compare: an Empty under the hand lands a bone's length off after the glb export,
  and the bone survives it. The Owner's eye is on each thing's offset in the hand (the sheets).
- **New need, from the Owner:** the atlases are too large for a big set of animations, and the clips are smoother than they need to be:
  trial [0307](0307-m5-sprite-atlas-size-trial.md).

Build tickets filed: [0300](0300-m5-clip-attach.md) `attach` on a clip (core-engineer), [0301](0301-m5-held-thing-import.md) import a thing
(character-pipeline), [0302](0302-m5-render-attached-things.md) `render` draws it at its socket (character-pipeline),
[0303](0303-m5-cell-per-clip.md) a cell per clip (character-pipeline), [0304](0304-m5-export-cell-per-clip.md) its export (godot-export),
[0305](0305-m5-held-thing-colours.md) its colours (imaging-engineer), [0306](0306-m5-ui-held-things.md) the UI (ui-engineer). Left to the
Owner: `grip_r` in the art repo's `chargen/generate.py` (before its glb export, from the final rest bones; `roundtrip_make_bone.py` shows how).
