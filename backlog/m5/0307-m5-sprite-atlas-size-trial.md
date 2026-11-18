---
status: todo
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

- [ ] The measures and the side-by-side GIFs above, their paths listed here.
- [ ] The Owner's choice recorded, and the build tickets filed.
