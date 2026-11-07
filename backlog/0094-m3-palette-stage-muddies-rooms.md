---
status: todo
milestone: M3
agent: imaging-engineer
type: ticket
---

# M3: the `palette` Stage turns rooms muddy

Spec §7. Found by the Owner at the [M2 gate](m2/0058-m2-gate.md): after `palette` the rooms "look like poorly compressed JPEGs" rather than
pixel art, "full of random pixels and unnecessary outlines", even with no dither, strength 0 and `orphan_size` 0. In Godot, r02
looked like "two images stitched together at the wrong places" around x = 220.

## What was seen (2026-11-07)

`room.ch01_dungeon_r02`, palette `bayer8`, `orphan_size` 2, the Project's 64-colour `style/palette.gpl`. The Source, `fit` and the
`palette` Plate compared side by side around x 150-330, y 60-200:

- **`fit` is faithful:** the teal-grey wall and the floor's soft light pool look like the Source.
- **`palette` isn't:** the teal-greys map to bands of brown, green and blue, and the pool's gradient breaks into hard-edged blotches.
  The seam the Owner saw is one of these band edges. It's there with the Godot light off, and none of the inpainted pixels show outside
  the Layers, so it isn't LaMa or the light.
- **`fit` adds dark edges** around the lockers that the Source doesn't have, which may be the "unnecessary outlines".

The dark dungeon rooms use a narrow range of colours that the 64-colour palette barely covers. Whether that's all of it, or the
mapping and dither also add noise, isn't known yet.

**`palette-suggest` (2026-11-07),** mean OKLab error of the nearest-colour mapping, before and after the suggestion. The three
dungeon rooms' `fit` images side by side, `--scale 1`; the subway reference at the default scale:

| Image | Asked | Got | Error before | After |
|---|---|---|---|---|
| r01 + r02 + r03 `fit` | 16 | 9 | 0.0302 | 0.0204 |
| r01 + r02 + r03 `fit` | 32 | 18 | 0.0302 | 0.0179 |
| `subway-lower-bay.jpeg` | 32 | 15 | 0.0241 | 0.0176 |
| the same, on the palette plus the dungeon 18 | 32 | 16 | 0.0212 | 0.0168 |

With the dungeon 18, r02's teal-grey wall and floor stay teal-grey instead of breaking into brown, green and blue bands, and r01 and
r03 lose their brown cast. So the palette is most of the cause on these rooms. The suggestions spend 3 to 5 colours on near-blacks
(`#000000`, `#000005`, `#010000`, `#000405`) that are 0.03 or more apart in OKLab but look the same: the distance rule may want a
lightness weight near black.

## What to do

1. **Measure.** For the three `ch01_dungeon` rooms, the mapping error per pixel in OKLab, from `fit` to `palette`, with the current
   palette and with it grown by `palette-suggest` ([0077](m2/0077-m2-grow-the-palette-from-an-image.md)) by 16 and 32 colours. Each with
   no dither, and with `bayer8`. Record a table and side-by-side images here.
2. **If the palette is the cause:** a Check on `palette` that warns when the mapping error is high, with a `fix` that runs
   `palette-suggest`, so the Owner sees it before the room looks wrong in the game.
3. **If the mapping or dither is the cause:** fix it in the Op, with golden images of a dark gradient and a teal-grey wall.
4. **The dark edges from `fit`:** find which `downscale` step adds them, and remove them unless the Source has them. Coordinate with
   [0081](0081-m3-downscale-keeps-one-scale.md), which changes the same Op.

## Acceptance criteria

- [ ] The measurement table and images are recorded here, with the Owner's look at the grown palette's result.
- [ ] A golden image of a smooth dark gradient maps without hard bands, with the palette the measurement picks.
- [ ] `fit` adds no dark edge that the Source doesn't have, on a golden image.
- [ ] If step 2 applies, the Check warns on r02 as it stands, with a `fix`.
