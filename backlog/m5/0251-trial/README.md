# Tileset trial (ticket 0251)

Can the free image model paint a tile kit that tiles? The results are in `backlog/m5/0251-m5-tileset-trial.md`.

- `input/`: the image model's pictures, as saved by the Owner. `grid.jpg` (prompt 1), `grid1-3.jpg` (prompt 2, a 4 x 4 sheet
  with magenta lines), `grid4.jpg` and `grid7.jpg` (prompt 3a, a room), `grid5.jpg` and `grid6.jpg` (prompt 3b, a junction).
- `prepare.py`: resamples grid4 (cut as a 9-slice on its own wall lines), grid5 (whole) and grid2's floor row so each lands
  on whole 16 px tiles at exactly 3 source px per game px. Writes `work/src_*.png`.
- Then Kiripix as it is, in a scratch copy of the art Project (its `kiripix.toml` and `style/palette.gpl`; nothing written to
  the art Project): `new room t_<n> --view top`, `set brief` (320 x 320, 320 x 320, 64 x 16), `import`, `pick`,
  `set fit mode=downscale scale=3`, `set palette strength=0 orphan_size=0 dither=none`, `run` (it stops at `reach`, which
  doesn't matter here). The `palette` Stage's `work/palette/palette.png` is copied to `work/pal_<n>.png`.
- `corridor.py`: slices those into 16 px tiles, lays out a corridor with two turns from a hand-written layout (an autotile
  rule picks each tile's piece from its neighbours), counts the seams, and draws the comparison with `ch01_dungeon_r01` (a
  52 px character, the 32 px battle grid). Writes `out/`.

```
uv run python backlog/m5/0251-trial/prepare.py
# (the Kiripix steps above)
uv run python backlog/m5/0251-trial/corridor.py
```
