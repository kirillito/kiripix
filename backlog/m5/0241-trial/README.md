# Portrait set prototype (ticket 0241)

Makes one character's dialogue portraits, one PNG per emotion, all on one 192 x 240 canvas with one anchor, from a folder of
images. It follows the game's portrait rules (its ticket 0091 and DEC-071; Kiripix 0240, "Input from the game"). It is also
the game's fallback for M04 if the `portrait` Kind isn't ready for it.

## Use

Put the images in a folder, named by emotion: `neutral.png` (or `.jpg`/`.jpeg`, required: the reference), `happy.png`,
`angry.png`, and so on. Each is the same character on a flat chroma-key background, cut at the waist by the image's bottom
edge. The pose may change between emotions. Then, from the Kiripix checkout:

```
uv run python backlog/m5/0241-trial/portrait_set.py <folder> <out>                 # 32 colours, no dither, edge outline
uv run python backlog/m5/0241-trial/portrait_set.py <folder> <out> --n 48 --dither 0
uv run python backlog/m5/0241-trial/portrait_set.py <folder> <out> --head-top 36 --outline outside
```

It writes `<out>/<emotion>.png` and `<out>/portrait.json` (canvas, anchor, head top, fallback, the Grid, and two reports per
emotion). It takes about 10 s for six 896 x 1200 images.

What it does, in order:

1. **Chroma key.** The key colour is read from the image's border, so JPEG noise and a key that isn't exactly `#00FF00` are
   fine. The green spill and most of the white sticker rim round the figure are removed too.
2. **One scale for the set, from the neutral.** The scale puts the neutral figure's top 40 px below the canvas top
   (`--head-top`) and the image's bottom edge on the canvas's bottom. The crop is centred on the neutral figure. Every
   emotion gets the same scale and crop, so the head stays the same size. There's no registration and no lock: the body is
   free to change.
3. **The set's own colours.** One set of `n` colours over every image (k-means in OKLab).
4. **The outline.** The characters' 1 px outline colour, `#352625`. `edge` (the default) repaints the figure's own
   border; `outside` adds a pixel round it, which doubles the image model's own dark outline.

It warns, and `portrait.json` records:

- **`near_edge`:** opaque pixels within 2 px of the top, left or right edge. The rule is every gesture inside the canvas with
  2 px to spare; the bottom edge is the waist cut.
- **`light_edge`:** pale grey pixels on the silhouette's edge, what is left of the white rim. On Sanjay's trial set it finds
  2-4 per emotion, and they differ between emotions. Clean them by hand, or cut the image again.

## Settings to change in `portrait_set.py`

- `CANVAS`: 192 x 240, anchor bottom centre (96, 239). `HEAD_TOP`: 40. `SPARE`: 2.
- `OUTLINE`: the outline colour (palette index 195 of the Urban Mystery Club palette).

## The rest of the trial

`experiments.py` (the numbers and comparison images, into `out/`), `register_check.py` (registration against a known shift),
`layout.py` (the sheets and the GIFs beside mc03 and a ch01 room). They use the trial's own helpers in `portrait_set.py`
(`fit_grid` at the trial's 160 x 224, `register_set`, `FACE_BOX`, `lock_outside_face`), which `build` no longer uses. `layout.py` lays out the trial's 160 x 224 output (`out/portraits/`) and expects that size.
`input/` holds Sanjay's six images under emotion IDs. The results are in `backlog/m5/0241-m5-portrait-trial.md`.

It reads `kiripix.ops` only. Run it with `uv run` so the locked numpy and Pillow are used.
