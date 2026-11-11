---
status: done
milestone: M3
agent: character-pipeline
type: trial
parent: 0097-m3-characters.md
depends_on: [0105-m3-toon-shading.md]
---

# M3: trial: which outline method for 3D renders?

Spec §16, open decision 3 ("inverted hull, Freestyle or a post-process edge pass (M3, by test)"), §6.3 (finish) and ADR 0004.
Story 11 of [0097](0097-m3-characters.md).

Moved to M5 on 2026-11-10 and back to M3 on 2026-11-11. Meanwhile [0109](0109-m3-outline-op.md) and
[0111](0111-m3-finish-stage.md) built the silhouette alone, placed outside it. This trial confirms that on the real Model and
decides inner lines; if they're wanted, it adds a follow-up ticket for them.

**The real Model (2026-11-11):** `character.mc02` in the art Project (`urban-mystery-club-art`), built by a scripted
Blender session from the Quaternius base (`c:\Homespace\[assets]\mc02\`) and rigged by Mixamo, with `idle`, `walk` and
`attack`. The Owner will still revise it; these choices are about the rendering, not its details, so a revised Model only
needs a look at its new frames.

ADR 0004 draws outlines in `finish`, after `palette`, in a palette colour, as a **line Mask**: a binary image of where the
outline goes, which `finish` paints in one palette colour.

**The Owner's choice (Q2 of 0097, 2026-11-07): a 1 px silhouette from the render's object mask.** The mask is exact and
binary, so the line has no isolated pixels, unlike the room outlines traced from colour edges. Blender's own lines are sized in
scene units and come out 0 to 2 px at 52 px. This trial confirms the choice on a real character rather than comparing three
methods. Freestyle isn't tried.

## What to do

1. On one real Model the Owner chooses, at `top34_8`, with idle, walk and attack, make the silhouette line Mask per frame
   from the object mask. Also make a second version with inner lines, from jumps in depth between neighbouring pixels, to
   show whether parts like an arm over the body need them.
2. Paint each in one palette colour over the palette-mapped frames, and lay them out as before/after sheets per clip and
   direction.
3. **Only if the Owner dislikes the result:** try the inverted hull (a back-face shell rendered as its own mask pass) on the
   same frames.
4. Prototype code lives in the trial's own folder under `.kiripix/` or the scratchpad, not in `kiripix/`. Production code is
   [0109](0109-m3-outline-op.md) and [0111](0111-m3-finish-stage.md), both built with the silhouette only.

## What to record, in this ticket

- The sheets' paths, and the Owner's view of each: legibility at 52 px, and flicker between frames (outline pixels that
  appear and vanish on a still part).
- A flicker number per method: outline pixels changed between consecutive frames of the idle, on the body away from moving
  limbs.
- Render time added per frame, and VRAM.
- Whether inner lines (an arm over the body) are wanted, or only the silhouette.

## Results (2026-11-11)

On `character.mc02` as the art Project built it (`top34_8`, height 52, 78 x 78 cell, 3 bands, idle 100 frames, walk 12,
attack 25, 8 directions: 1,096 frames). The trial reads mc02's built `palette` frames and `render` mask and depth passes and
writes nothing into the Asset. Code and output are in the art Project, under
`C:\Homespace\urban-mystery-club-art\.kiripix\trials\0106-outline\` (gitignored, so it stays put; rerun with
`.venv/Scripts/python.exe <that folder>\trial.py` from Kiripix, `--threshold` to change the inner-line jump):

- `overview_frame0.png`: frame 0 of every clip and direction, in rows: before (the palette frames), + silhouette, + silhouette
  and inner lines. 4x nearest, captioned.
- `sheets/<clip>_<dir>.png`: per clip and direction, the same three rows over the first 24 frames.
- `idle_before.gif`, `idle_silhouette.gif`, `idle_inner.gif`: the idle in all 8 directions at 12 fps, 4x. These are for
  judging flicker.

Method:
- **Silhouette**: `outline_mask(mask, "outside")` on the render's object mask, the op `finish` already uses
  ([0109](0109-m3-outline-op.md)). The object mask and the palette frame's alpha are identical in all 1,096 frames, so this is
  exactly what `finish` ships today.
- **Inner lines**: an opaque pixel gets a line when a 4-neighbour is nearer the camera by more than 0.1 scene units (about
  3 px at 30 px per unit). The line sits on the far side of the jump (on the body behind an arm), the way the silhouette sits
  outside the shape. Painted in palette index 0 (`ink-1`, #010103), `finish`'s default `outline_colour`.

Numbers (mean per frame step, over the 8 directions):

| clip | method | line px per frame | px changed per step | toggles per step | toggles on still parts |
|---|---|---|---|---|---|
| idle | silhouette | 152 | 3.3 | 0.09 | 0 |
| idle | + inner | 202 | 4.9 | 0.15 | 0.07 |
| walk | silhouette | 157 | 169 | 64 | 0 |
| walk | + inner | 208 | 212 | 80 | 7.9 |
| attack | silhouette | 166 | 131 | 49 | 0 |
| attack | + inner | 221 | 184 | 70 | 10.5 |

- A **toggle** is a line pixel that appears and is gone again one frame later, or the reverse: the flicker the eye catches.
  **Still parts** are pixels whose 5 x 5 neighbourhood of the object mask is the same over those three frames, so a line
  change there isn't explained by the outline moving. The silhouette is a function of the mask's 3 x 3 neighbourhood, so its
  count there is 0 by construction. On the idle, the flicker number the ticket asks for (on the body, away from moving limbs)
  is **0 for the silhouette and 0.07 px per step with inner lines**: about one pixel every 14 frames.
  On walk and attack, the inner lines' "still part" changes are mostly an arm moving inside the silhouette, which is motion,
  not flicker.
- **Render time added: none, and no VRAM.** Both methods read passes `render` already makes (the mask and the depth). The op
  runs in numpy at 0.4 ms per frame for the silhouette and 0.8 ms for the inner lines, as unoptimised trial code.
- Inner lines add about a third more line pixels. They mark the backpack's edge, an arm over the body, and the legs crossing in
  a stride. On the idle facing `s` they separate the arms from the torso, the chin from the neck, and one leg from the other.
  They are heavier on the side away from the camera, because the line sits on the far side of each jump.
- Seen while making the sheets (tickets filed for the gate): the attack's foot is cut at the cell's bottom on `s`
  ([0155](0155-m3-attack-overflows-the-cell.md)), so there is no line under it; and the idle shifts by 1 px in `sw`, `w`, `ne`
  and `e` ([0154](0154-m3-stationary-clip-pivot-follows-the-hips.md)). The shift moves the whole sprite and its line together,
  so it doesn't show in the numbers above, which are per frame in the render's own frame. In the game it reads as swimming.

Not done: the inverted hull (step 3), only for if the Owner dislikes the silhouette.

## Acceptance criteria

- [x] The silhouette, with and without inner lines, on one real character, with the numbers above.
- [x] The Owner's view is recorded here: the silhouette kept, inner lines in or out, or the inverted hull tried.

**Owner's view (2026-11-11):** the sheets look good. **The silhouette is kept, and inner lines are out**, so `finish` stays as
it is ([0109](0109-m3-outline-op.md), [0111](0111-m3-finish-stage.md)), with no follow-up ticket. The inverted hull isn't
tried. Recorded in spec §16 decision 3.
