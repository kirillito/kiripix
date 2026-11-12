---
status: todo
milestone: M4
agent: character-pipeline
type: trial
parent: 0174-m4-sprite-kind.md
---

# M4: trial: a real PixelLab export, taken through by hand

Part of [0174](0174-m4-sprite-kind.md). No Kiripix code: this trial answers what the `sprite` Recipe's import and `fit` must
handle, on a real file, before [0178](0178-m4-import-a-sheet.md) and [0179](0179-m4-sprite-recipe.md) are built.

## Input

The PixelLab export the game makes for Sanjay in its M02
(`../urban-mystery-club/docs/backlog/m2/0041-m02-sanjay-sleeping-mc.md`): a PixFlux figure on a 56×56 canvas, idle in 4 or
more directions, steered to the 30° view. The Owner provides both the ZIP and the PNG sheet export, if PixelLab offers both.
If 0041 isn't done yet, any PixelLab figure in 4 directions will do.

## What to find out

- **The ZIP's layout:** folder and file names for rotations and for an animation, the direction words, frame numbering, any
  metadata file. Write it down as the naming rule 0178 and 0179 implement.
- **The PNG sheet's layout:** directions per row or per column, their order, the cell size, gutters.
- **Directions:** that PixelLab's `east` faces screen right, as Kiripix's `e` does (the M3 Q5 rule: from the screen's view).
- **The figure:** its height in px on the 56 canvas (against `[character] height` 52 and the game's 46–58 range); whether its
  edge is a 1 px dark line (which decides `placement = edge` as the default); whether it casts a shadow onto the lowest rows
  (which would put the measured feet in the wrong place); how much it shifts on the canvas between directions.
- **Normals:** the game's `tools/normal_map.py` output and a flat map, side by side in Godot under a `PointLight2D` beside
  `character.mc02`. Which reads better beside the 3D character?
- **Palette:** map one frame with `kiripix op quantize` (or the room's `palette` Op) to the Project palette with 16 colours,
  and note what is lost.

## Output

- A short report in this ticket: the naming rule, the answers above, and an image of the frames before and after the hand fit,
  enlarged, captioned with their sizes.
- A synthetic fixture **description** for 0179: a ZIP in the same layout, with tiny made-up frames (never PixelLab's own
  pixels, so no licence question arises in the repo).
- Any change to 0174's decisions, proposed to the Owner. Don't edit them yourself.

Budget: 30–60k tokens.
