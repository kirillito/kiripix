---
status: todo
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

- [ ] The sheet, the GIF and the measures above, recorded here with their paths.
- [ ] The Owner's choice recorded, and the build ticket filed if (a) is chosen.

Budget: 150–250k tokens.
