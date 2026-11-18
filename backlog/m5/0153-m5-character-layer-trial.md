---
status: done
milestone: M5
agent: character-pipeline
type: trial
parent: 0152-m5-character-layers.md
---

# M5: trial: render a hair style and an outfit as layers over a body

Spec §6.3 and §16 (open decision 9). Part of [0152](0152-m5-character-layers.md). Prototype code stays in the scratchpad or the
trial's own folder under `.kiripix/`, not in `kiripix/`.

## What to do

1. From mc02 (`c:\Homespace\[assets]\mc03\build_mc03.py`), make a body and two layers as separate objects on one rig: the hair,
   and the jacket with its hood. Add one silhouette-changing piece for question 1 of 0152, such as a long coat.
2. Render the body alone, then each layer with the body as a holdout, at `top34_8` in 8 directions, for `idle`, `walk` and
   `attack`: same cell and pivot.
3. Stack them in a fixed order and compare with a full render of the same character: count the pixels that differ per frame,
   and show where.
4. Try the outline both ways (per layer; once on the stack) and lay them out as sheets for the Owner.
5. Measure the render time per layer against the full body.

## Since the generator trial (2026-11-14)

The generator trial ([0164](../m4/0164-m4-claude-built-base-models-trial.md)) didn't answer 0152's three questions: it
merged every part into one mesh and rendered the whole character. But it gives this trial an easier start than mc02: the
art repo's `chargen/` already builds hair, tops, coats, hats and skirts as parts on mc03's skeletons, so step 1 can build
the body and each layer as separate objects with `chargen/generate.py` instead of from `build_mc02.py`. A long coat and a
hood-like hat are in its library already (question 1). What it showed about bases went to
[0165](../m4/0165-m4-characters-share-a-base.md), which no longer waits for this trial.

## A weapon as a layer: moved to 0238 (the Owner, 2026-11-16)

Steps 6–8 below and the weapon criterion moved to the held-things trial [0238](0238-m5-held-things-trial.md), so (a) or (c)
is settled in M5's first wave, ahead of layers. The game needs a phone in the hand at its M03 and weapons at its M05–M06, two
to four game milestones before layers. Skip steps 6–8 here, and reuse 0238's holdout render if it chose (c).

Also read 0152's "What the game needs from layers": accessories (a backpack whose order flips between south and north), the
six fixed Parts, and layers for generator-built Models.

### As first written (from 0170, 2026-11-15)

M4's trial [0170](../m4/0170-m4-weapon-in-a-battle-clip-trial.md) put a weapon in mc02's `attack` clip as option (a), a mesh
parented to the right-hand bone, and the Owner deferred the choice to this trial. Its results in `backlog/m4/0170-trial/` are the
baseline: 1 m stick, 8 directions at 52 px, the cell 78 to 92 for every clip (+39 percent atlas), no measurable render cost,
outlined for free, attachment materials numbered after the Model's.

6. Render the same stick as a layer over mc02's `attack` (option (c)), with the body as a holdout, and compare with 0170 on:
   the cell and atlas size (does idle stay at 78?), the render cost, the outline where the stick crosses the body's silhouette,
   the palette (in 0170 the stick took one of the body's 16 colours), and depth by direction.
7. **Put the stick in the hand.** In 0170 the stick floated beside the fist: the grip offset and rotation were guesses. Whichever
   way wins, find how the grip is set so the weapon sits in the hand in every frame (an offset and rotation per clip, a grip bone,
   or a socket empty in the Model), and show it on the sheet.
8. Lay out the attack with (a) and (c) side by side, at 4x and as a GIF, like 0170's.

## What to record, in this ticket

- The differing-pixel counts, the sheets' paths and the Owner's view of each.
- The answers to the three open questions of 0152, with the Owner's choice.
- A list of work tickets to file (render, palette, sheet, export, UI), each with its agent, and any change to what the game asked
  for (DEC-052).

## Acceptance criteria

- [x] The sheets and numbers above (steps 1 to 5, on the generated mc03 male base instead of mc02: see Results).
- [x] The Owner's answers to 0152's questions are recorded here, and the work tickets are filed.
- [x] ~~The weapon compared as (a) and (c) against 0170, held in the hand, with the Owner's choice and its build ticket.~~ Moved to
      [0238](0238-m5-held-things-trial.md) (2026-11-16), and closed here by the Owner on 2026-11-18: 0238 runs it on the
      `wearable` render path ([0291](0291-m5-wearable-model-rig-render.md)).

## Results (2026-11-18, steps 1 to 5; the weapon, steps 6 to 8, is 0238's)

Everything is in `backlog/m5/0153-trial/` (scripts, JSON results, `sheets/`); frames are in the session scratchpad, not kept.
Nothing in `kiripix/` or the art repo changed (`generate.py` was run unchanged from a driver that moves its output folder).

### What was built

- **Models:** the art repo's `chargen/` at commit 7979476, `generate.py` unchanged, on the `adult_male` base (mc03's male
  underwear body on its Mixamo rig). `npcs/` in the trial folder holds four parameter files: `body` (bald, underwear), `hairp`
  (kit hair `parted`, blond), `jacket` (`jacket` + `tee` under + `hood` + `trousers` + `sneakers`, green), `coat` (long `coat`
  with `high_collar`, burgundy). Each builds in 1.2 to 4.0 s.
- **Layers as separate objects on one rig** (`assemble.py`): generate.py joins every part into one mesh, so the trial splits
  each built mesh by material into objects on the body's armature (no change to chargen): `body`, `hair`, `jacket` (top,
  sleeves, hood, tee), `legs` (trousers, shoes), `coat` (coat, collar) and a hand-modelled `pack` (a box behind the torso and
  two straps over the shoulders, on `Spine2`). Materials are renamed `<layer>.<name>`, so each layer's ramps are its own.
  chargen's clothes are the body's own faces pushed out, so **a layer is clean separate geometry with the body's weights**
  and splitting needed nothing from chargen. The body object keeps the faces under the clothes, so it is the holdout.
- **Render:** `kiripix/blender/render_frames.py` unchanged, run through `render_layers.py` (adds `show` and `holdout`
  args: a holdout object hides what is behind it, is not drawn, and is outside the object mask). `top34_8`, 8 directions,
  `idle` (1 frame: it is a 24-frame still), `walk` (8) and `attack` (19) from mc03_male_clothes01's clips: 28 frames x 8
  directions = 224 frames per scenario. Camera, depth scale and material numbers are set up with every object visible, so
  every scenario shares them. Toon settings are the asset's (2 bands, shadow 0.22).
- **Scenarios:** `body`; `full_jacket` and `full_coat` (body + legs + outfit + hair + pack, nothing held out: the reference);
  and one per layer (`hair`, `legs`, `jacket`, `coat`, `pack`) with the body as holdout.
- **Not done:** palette mapping (colours are the Model's; the outline colour is palette index 195 of the art repo's palette,
  (53, 38, 37)); the normal pass was rendered but not compared; the hood is small (a flattened ball behind the neck), so
  the hood-under-hair question is barely tested (no pixel conflict); the pack's straps lie inside the jacket's thickness.

### Cell and pivot

`fit_cell` (read-only import) on the union of body and every layer: **cell 78 for all, the same as mc03_male_clothes01's**
(bounds idle +-12.8, walk +-21.0, attack +-27.3 px). The pivot is (39, **66**) with the layers and (39, 67) for the body
alone: the hair makes the Model 1 px taller. A body fitted on its own would put the pivot 1 px off the layers', so the cell
has to be fitted once, over the body and every layer that exists, or fixed by the body with room left.

### Q1 numbers: the stack against the full render, per frame

A pixel differs when its alpha or its colour differs. 224 frames per stack; the visible pixels are those of the full render.
Order = body, then the listed layers, each pasted over the last where it has pixels.

| Stack (fixed order) | Visible px (all frames) | Differing px | Share | Frames with a difference | Largest frame | Idle / walk / attack differing px |
|---|---|---|---|---|---|---|
| jacket: legs, jacket, hair, pack | 147,543 | 2,229 | 1.5 % (10 px a frame) | 216 of 224 | 24 | 89 / 686 / 1,454 |
| coat: legs, coat, hair, pack | 162,938 | 3,657 | 2.2 % (16 px a frame) | 220 of 224 | 41 | 137 / 1,043 / 2,477 |

Where (the full render's layer, then the layer the stack shows; `diff_where.json`):
- jacket stack: `jacket -> pack` 2,109 px, `hair -> pack` 120. The pack was pasted over the jacket and hair.
- coat stack: `coat -> pack` 3,045, `legs -> coat` 492, `hair -> pack` 120. The coat's skirt and sleeves hide the pack's
  edges, and a leg swung forward in `walk` and `attack` is in front of the coat's hem while `legs` sits below the coat.

Every order, per direction and per frame (all 24 orders of the four layers on every frame; `diff_counts.json`):

| | jacket stack | coat stack |
|---|---|---|
| Natural fixed order | 2,229 | 3,657 |
| Best single fixed order | 2,109 (pack under hair) | 3,537 |
| Best order per direction | 2,109 | 3,537 |
| Best order per frame | 2,109 | 3,388 |
| Pack under the outfit, facing south (the `s` frames) | 839, against 332 for the natural order | 841, against 565 |
| **Stack by depth** (each layer's depth pass, nearest wins) | **1** | **7** |

So a per-direction or per-frame order fixes almost nothing: **the pack and the outfit interleave in one frame.** The straps
are in front of the body but inside the jacket's thickness, and the box is behind the body but sticks out at the sides, so
no order of two whole layers is right (the pack under the jacket facing south is worse, 839 px, because the straps show in
the jacket's open front). **The body as holdout does solve the body against a layer**, including the pack behind the body
facing south: the pack's own render has already lost what the body hides, so the pack never has to go below the body. What
it can't know is another layer that is thicker than the body and in front of it. The depth pass of every layer, rendered
already, settles it to 1 and 7 px in 147k and 163k (the rest is a depth tie at 16 bits).

### Q2 numbers: the outline, both ways (colour 195, 1 px, outside; `outline_atlas.json`, `outline_variant.json`)

Against the outline of the full render (the single figure's):

| | jacket stack | coat stack |
|---|---|---|
| Once on the stack | 2,229 px differ (only the stacking errors above) | 3,657 |
| Per layer, each sprite outlined, then stacked | **19,330 px differ (13 % of the figure)**, 17,101 of them lines inside the figure (76 a frame) | 21,840, 18,183 inside |
| Per layer, skipping the pixels the body covers (a third way) | 3,119 differ, 890 inside (4 a frame) | 5,223, 1,566 |

Per layer draws a line along every layer's edge over the body, round the cut the holdout leaves (the face under the hair,
the whole torso under the jacket), as the red in `sheets/outline_jacket_walk2_x4.png` shows. The third way removes the lines
at the holdout's edge and keeps the lines between two layers.

### Cost (CPU, one Blender process, 224 frames each; the machine was shared with another agent's tests, so times vary by a few seconds)

| Scenario | Loop seconds | ms a frame |
|---|---|---|
| body only | 15.9 | 71 |
| full, jacket stack (5 objects) | 22.1 | 99 |
| full, coat stack | 24.8 | 111 |
| layer hair (+ body as holdout) | 18.7 | 84 |
| layer legs | 17.0 | 76 |
| layer jacket | 17.9 | 80 |
| layer coat | 22.3 | 99 |
| layer pack | 23.7 | 106 |

A layer render costs about the same as the full render (76 to 106 ms a frame against 99 to 111), because the holdout body is
in the scene and the time is the per-frame Cycles set-up, not the geometry. So the cost is **one full render per layer**:
at mc02's 70 ms a frame, a layer for a 15-clip set is about the 10 minutes the full body costs, plus `palette` and `finish`.
The saving is only that no combination is rendered.

### Atlas per layer (one sheet, a column per frame, a row per direction; 28 frames x 8 directions = 224 cells of 78 x 78)

| | Sheet px | PNG bytes | Opaque px | Share of the cells | Union bounding box of the pixels (x0, y0, x1, y1) |
|---|---|---|---|---|---|
| body (all of it) | 2184 x 624 | 175,576 | 114,412 | 8.4 % | 14, 7, 63, 75 |
| hair | same | 31,117 | 15,533 | 1.1 % | 12, 10, 65, 43 |
| legs (trousers, shoes) | same | 81,418 | 59,516 | 4.4 % | 17, 36, 60, 75 |
| jacket (with hood and tee) | same | 56,368 | 48,166 | 3.5 % | 17, 13, 60, 51 |
| coat | same | 87,134 | 94,504 | 6.9 % | 17, 13, 60, 60 |
| pack | same | 31,754 | 28,084 | 2.1 % | 22, 19, 55, 46 |
| full, jacket stack | same | 198,907 | 147,543 | 10.8 % | 12, 7, 65, 75 |
| full, coat stack | same | 201,919 | 162,938 | 12.0 % | 12, 7, 65, 75 |

Every layer has the body's cell and sheet size by the rule (pixel for pixel). A layer's PNG is 31 to 87 KB against 176 KB for
the body; in Godot an atlas is VRAM at its full size, so a layer costs the whole 2184 x 624 (about 5.4 MB at 4 bytes a pixel
for these 28 frames; the real idle has 24 frames, which export may or may not drop). A trimmed cell per layer would shrink it
(the hair's pixels fit 54 x 34 of 78 x 78) but breaks "stack pixel for pixel" unless each layer carries an offset. Not tried.

**The body under the outfit:** 88 % of the body's pixels (100,631 of 114,412 in the jacket stack; 101,430 in the coat stack)
are covered by a layer in the stack. The holdout needs the body there, and a body without the covered pixels would be wrong
for the next outfit, so there is no saving in the render; the game just draws the whole body under the layers.

### Sheets for the Owner (4x, `backlog/m5/0153-trial/sheets/`; rows are the 8 directions s, sw, w, nw, n, ne, e, se)

Columns of `layers_*`: body, each layer, the stack, the full render, the differing pixels in red, the stack by depth.
- `layers_jacket_walk2_x4.png`, `layers_jacket_attack9_x4.png`, `layers_jacket_idle0_x4.png`
- `layers_coat_walk2_x4.png`, `layers_coat_attack9_x4.png`
- `layers_jacket_walk2_packfirst_x4.png` (the pack under everything: worse facing north, 3,523 px)
- `outline_jacket_walk2_x4.png`, `outline_jacket_attack9_x4.png`, `outline_coat_walk2_x4.png`: full without outline, full
  outlined (the reference), outline once on the stack, per layer, per layer against the reference in red.

Owner's view of each (2026-11-18): a good start.

### Answers (proposed by the trial; accepted by the Owner, 2026-11-18)

1. **Order.** A fixed order is almost right (1.5 and 2.2 % of pixels, at most 24 and 41 px in a frame) and a per-direction or
   per-frame order doesn't help, because the pack interleaves with the outfit. Proposal: **export each layer with its depth
   pass (and its normal), plus a stacking order as the default**, so the game can stack by order (cheap, 1.5 to 2 % wrong at
   the edges of a thick outfit and a pack) or by depth in its compositor shader (exact to a few px). Kiripix keeps the body as
   the one holdout, never a body plus outfit. The order is a field of the layer's export (the pack above the outfit, the hair
   above the pack). If the Owner wants no errors without a depth shader, the only way is a layer rendered with the outfit as a
   second holdout, which is a combination (out of scope in 0152).
2. **Outline and normal map.** Proposal: **no outline in a layer; the game draws it once on the stack** (a 1 px outline of the
   stacked alpha, in the outline colour that `character.json` names). Per layer draws 76 px of lines a frame inside the figure
   (13 % of it). If the game won't draw it, the fallback is the third way (per layer, not over the body's pixels): a few lines
   between layers remain. The normal pass is per layer, quantised to the same levels, never palette-mapped. The normal
   comparison was not run; say if the Owner wants it before the tickets are filed.
3. **How Kiripix holds a layer.** Proposal: **its own Asset of Kind `layer` that names its body** (`body = "<asset>"`). A
   Variant doesn't fit: Variants are alternatives of one Asset, and a layer coexists with the body and other layers. The
   layer's `model` imports only its own meshes (`rig` checks them against the body's skeleton by bone names), `clips` are the
   body's (referenced, not copied), and `render` takes the body's `model`, `rig`, `clips` and cell as inputs, so the layer is
   stale whenever any of them changes and its render stays in step by the Stage input hash, with no new mechanism. Own
   `palette` ramps (disjoint from the body's), `finish` without an outline, `sheet`, and `export` writing the same animation
   names, cell and pivot plus a layer record (body, order, depth). The cell must be fitted once over the body and every layer
   (the pivot moved 1 px with the hair): either the body's cell is fixed with room, or a layer outside it is a finding. On
   the chargen side a part is already separate geometry with the body's weights, so chargen can write a layer's Model as its
   own file without joining; here a split by material did it.

### Work tickets (filed 2026-11-18 as 0290-0295, with the Kind named `wearable`; #8 is the art repo's)

| # | Ticket | Agent |
|---|---|---|
| 1 | `layer` Kind and `body` field: asset.toml, `describe`, the Stage graph (stale when the body's model, rig, clips or cell change), the one-cell rule and its finding | core-engineer |
| 2 | `model` and `rig` for a layer: import the layer's meshes, validate against the body's skeleton, material names kept per layer | character-pipeline |
| 3 | `render` with the body as holdout (`holdout` objects in `render_frames.py`, the object mask outside the holdout), the cell fitted over body and layers, depth and normal per layer | character-pipeline |
| 4 | `palette` for a layer (ramps of its parts disjoint from the body's) and `finish` for a layer without an outline | imaging-engineer |
| 5 | `sheet` and `export` of a layer: same animation names, cell and pivot as the body, a layer record with `body`, `order` and the depth pass | godot-export |
| 6 | A Check `layers.stack_differs`: stack in order and by depth, report differing px per frame (this trial's measure; informational) | imaging-engineer |
| 7 | UI: a layer as a child of its body, a stack preview at 4x with the order and a depth toggle, per-layer cost (render seconds, atlas px) | ui-engineer |
| 8 | chargen: write each part as a separate Model file on the base's skeleton; art repo, not Kiripix | the Owner (art repo) |

Changes to what the game asked for (DEC-052): none needed, except that a layer's atlas is the body's full cell (about 5 MB of
VRAM a layer for 28 frames x 8 directions) and the stack isn't exact (1.5 to 2 %) unless the game stacks by depth.
