---
status: todo
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

## Acceptance criteria

- [ ] The silhouette, with and without inner lines, on one real character, with the numbers above.
- [ ] The Owner's view is recorded here: the silhouette kept, inner lines in or out, or the inverted hull tried.
