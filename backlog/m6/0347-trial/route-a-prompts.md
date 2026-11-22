# Route (a) prompts: for the Owner to try in the image model's own UI

Route (a) needs the Owner (the UI is not scriptable here). One prompt per effect, each asking for a strip of frames on a
flat background. Paste the prompt, save the PNG, import it with
`kiripix import sprite.<name> <file> --role sheet` and a `sheet` Decision (layout `rows`, directions `["s"]`, the frame
count), `fit` `chroma=#FF00FF`. Record the minutes it took (start the clock at the paste, stop at the imported sheet), and
the number of tries.

Common block (put it first every time):

> Pixel art game effect sprite sheet, a single horizontal strip of N equal square cells, no gaps, no labels, no borders,
> each cell W x H pixels at 1:1 pixel scale (do not smooth, no anti-aliasing, hard pixel edges, no soft glow or blur, no
> gradients: glow is done with dithering and flat colour steps). Flat solid magenta (#FF00FF) background in every cell. The
> effect is centred in the cell on the point named below. Limited palette, only these colours: paper #FAFEEB, amber
> #FEDA43, amber #E1A441, orange #E28135, red #B3181F, teal #38FCFB, pale teal #9BCBD5, blue #6AA6C1, blue #4B7DA0,
> violet #82448B, stone #B9B1A6, stone #6A5E59. Style: top-down three-quarter RPG, as in Chrono Trigger battle effects.
> The frames play left to right as an animation.

| Effect | N x W x H | Prompt after the common block |
|---|---|---|
| hit spark | 5 x 24 x 24 | "A hit spark: frame 1 an 8-point white-yellow star burst, frame 2 a smaller bright core with four short orange rays, frame 3 a ring of orange with yellow flecks, frame 4 a thin broken orange ring, frame 5 a few orange specks. Centre of the burst at the centre of each cell." |
| sound wave (a cone of cells) | 8 x 96 x 64 | "A sound wave from a horn pointing right: curved arcs (concentric circle segments) in teal and pale teal with a white leading edge, spreading to the right inside a 68 degree cone whose point is at the left edge, middle row of each cell. Frames 1 to 5 the arcs move outward, frames 6 to 8 they fade to blue. The cone fills 3 cells of 32 px at the right." |
| summon puff | 8 x 48 x 48 | "A summoning puff of smoke on the ground: frame 1 a small bright cream flash, frames 2 to 5 a round puff of stone-grey and cream smoke growing, with a few amber and violet sparks, frames 6 to 8 the smoke thins and breaks up. Smoke sits on the ground point 34 px from the top at the horizontal centre." |
| buff glow on a unit | 8 x 48 x 64 | "A buff aura on a character's feet: a flat ellipse ring of amber light on the ground (ellipse 40 x 14 px, 34 px from the bottom edge) that pulses between two ambers, with 3 to 5 small white-gold sparks rising from it. The first frame and the last frame must match so it loops. Nothing is drawn above the ring except the rising sparks." |
| target telegraph | 4 x 32 x 32 | "A danger marker for one 32 x 32 px floor tile: red and orange corner brackets on the tile border, a dithered orange fill that gets denser in frame 2 and 3 (checkerboard dither, not a soft fill), and back to frame 2 in frame 4 so it loops. Exactly square, aligned to the cell edges." |

What to look for: whether the model keeps every cell on the same pixel grid, keeps to the palette, keeps the centre, and
whether frames of an effect read as one effect. `fit mode=downscale` is the likely path (an image model does not draw at
1:1), so also record whether the figure height rule (`height`) means anything for an effect (it does not: see the
trial's gaps).
