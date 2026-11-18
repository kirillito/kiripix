# Portrait set prototype (ticket 0241)

Makes one character's dialogue portraits, one PNG per emotion, all on one 160 x 224 canvas with one anchor, from a folder of
images. It is also the game's fallback for M04 if the `portrait` Kind isn't built in time.

## Use

Put the images in a folder, named by emotion: `neutral.png` (or `.jpg`/`.jpeg`, required: the reference), `happy.png`,
`angry.png`, and so on. Each is the same character on a flat chroma-key background, an edit of the neutral one. Then, from
the Kiripix checkout:

```
uv run python backlog/m5/0241-trial/portrait_set.py <folder> <out>            # 32 colours, no dither (the trial's pick)
uv run python backlog/m5/0241-trial/portrait_set.py <folder> <out> --lock     # copy the neutral's pixels outside the face
uv run python backlog/m5/0241-trial/portrait_set.py <folder> <out> --n 48 --dither 0
```

It writes `<out>/<emotion>.png` and `<out>/portrait.json` (canvas, anchor, fallback, the Grid, each emotion's registration).
It runs in about a minute for six 896 x 1200 images.

What it does, in order: chroma key (the key colour is read from the image's border, so JPEG noise and a key that isn't exactly
`#00FF00` are fine; a white sticker rim round the figure is removed too), registration of each emotion to the neutral, one
`downscale` for the set (largest scale that fills 224 rows, bottom edge anchored, crop centred on the neutral's figure), one set
of `n` colours over every image (k-means in OKLab), the characters' 1 px outline colour `#352625`, `--lock` if asked.

## Settings to change in `portrait_set.py`

- `CANVAS`: 160 x 224.
- `OUTLINE`: the outline colour (palette index 195 of the Urban Mystery Club palette).
- `FACE_BOX`: the head's box in the neutral's source pixels, drawn by eye for Sanjay at 896 x 1200. It is used for the
  registration (outside it) and for `--lock` (outside it the neutral wins). Change it for another character or image size.

## The rest of the trial

`experiments.py` (the numbers and comparison images, into `out/`), `register_check.py` (registration against a known shift),
`layout.py` (the sheets and the GIFs beside mc03 and a ch01 room). `input/` holds Sanjay's six images under emotion IDs.
The results are in `backlog/m5/0241-m5-portrait-trial.md`.

It reads `kiripix.ops` only. Run it with `uv run` so the locked numpy and Pillow are used.
