---
status: todo
milestone: M2
agent: imaging-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0041-m2-matting-runner.md]
---

# M2: the prop Recipe, from brief to palette

Spec §6.2, §7 (cleanup, resample) and ADR 0004. Stories 11 and 12 of [0037](0037-m2-layers-and-props.md). Follows D7, D8 and D10 in [0037](0037-m2-layers-and-props.md).

## What to build

- Move what rooms and props share out of `room.py` into a recipes module: read and write helpers, `source`, the grid and
  palette code. Rooms must behave and hash exactly as before.
- Run functions and `image` for `brief`, `source`, `cutout`, `fit` and `palette`. Fix the upstreams `chain()` can't give:
  `fit` needs `cutout`, `brief`.
- `cutout`: method `chroma` through a new `chroma_key` Op on the full-size Source; method `matting` through one pinned call
  to `MATTER` only, on the Source, capped. Choosing `chroma` calls no Runner and needs no pinned result.
- `fit`: colours as for rooms; alpha to the target grid by majority vote, so it's binary. `image.partial_alpha` is implemented.
- `palette`: the room's mapping and orphan cleanup, keeping transparent pixels. `palette.off_palette` is implemented.
- A finding when chroma keys nothing or nearly everything, per D7, and the size Check per D8.
- `tests/cli/test_graph.py` and `test_export.py` use `prop` as the example of an unbuilt Kind. Move those to `character`.

## Acceptance criteria

- [ ] Golden test for `chroma_key` on a flat background, and for majority-vote alpha.
- [ ] `new prop`, `import`, `pick`, `run` with chroma: `palette.png` has binary alpha and every opaque pixel on the palette,
      with no Runner call.
- [ ] Matting with the fake: `needs-input` "Runner not run yet"; `run --rerun` pins it into `needs-review`; `accept` gives `done`.
- [ ] Swapping the fake matter for one with another ID gives "Runner input changed".
- [ ] Every room test passes unchanged, and an existing room's input hashes don't change from the move.
- [ ] `next` gives a command or an owner action at every prop Stage.
- [ ] A manual (not CI) check of the real matting Runner ([0041](0041-m2-matting-runner.md)) on a real prop Source,
      through `cutout` with `run --rerun`, on the Owner's GPU and with `--cpu`, recorded here as 0020's was: time cold
      and warm, VRAM above idle and peak, the GPU-vs-CPU alpha difference, edge quality, and a cancel mid-call.
