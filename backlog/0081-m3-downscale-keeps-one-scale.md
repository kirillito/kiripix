---
status: todo
milestone: M3
agent: imaging-engineer
type: ticket
---

# M3: `downscale` keeps one scale on both axes

Spec §6.1 (fit) and §6.2. Found by [0063](0063-m2-multi-screen-source-trial.md).

## The gap

`downscale` splits the Source into exactly the brief's width x height cells (`Grid.to_size`,
[resample.py](../kiripix/ops/resample.py)), so each axis gets its own scale. When the Source's aspect isn't the brief's, the
room is stretched, and nothing says so. A room's scale is locked to 52 px characters, so a stretch breaks it.

- The 0063 subway Source, 2185 x 768 into R4's 1024 x 320: 2.13 across, 2.40 down, an 11 % squash.
- `room.harbor_front`, 1376 x 768 into 640 x 368: 2.15 across, 2.09 down, 3 %.

The workaround in 0063 was to crop each Source to the brief's aspect before `import`.

## What to build

- `downscale` uses one scale on both axes: the largest that still fills the brief, `min(source_w / w, source_h / h)`, kept as
  a `Fraction`. The Source left over on the other axis is cropped. `grid.json` records equal `scale_x` and `scale_y`.
- `offset_x` and `offset_y` place the crop, in Source pixels, from the top left, as they do in grid mode. An offset that leaves
  less than the brief's size is a `StageFailure` that names the largest offset allowed.
- An info finding, `fit.cropped`, when the crop drops more than a few Source pixels: it says how many, on which axis, and its
  `fix` is the `set` command that centres the crop. Info, since the Owner may want the crop off-centre.
- Props share `run_fit`, so they follow the same rule.
- Update the `fit` row in spec §6.1, the `describe` text, and the parameter descriptions of `offset_x` and `offset_y`.

## Notes

- Everything downstream already reads the Grid's offsets: `mask_to_source`, `point_to_target` and the clicks sent to a Runner.
  Check that a click on a cropped room reaches the same Source point as before.
- **This changes `harbor_front`'s fit,** by 3 %, so its Mask clicks and floods go to `needs-review` and its export changes.
  Do it after the M2 gate has checked that an M1 room rebuilds with nothing to review. Through M3 the Owner has no production
  rooms, so no migration.

## Acceptance criteria

- [ ] CLI test: a 2185 x 768 Source into 1024 x 320 gives `scale_x` equal to `scale_y` (2185/1024), a 1024 x 320 `fit.png`, and
      a `fit.cropped` info whose `fix` centres it. Running that `fix` moves the crop.
- [ ] A Source with the brief's aspect fits byte-identically to today, with no finding.
- [ ] An offset too large to leave the brief's size fails and names the largest allowed.
- [ ] With a fake segmenter: a `masks` click on a cropped room is sent to the Runner at the right Source point.
- [ ] A prop with a matte, cropped, still gets binary alpha by vote.
