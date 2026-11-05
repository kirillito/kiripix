---
status: done
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

- [x] Golden test for `chroma_key` on a flat background, and for majority-vote alpha.
- [x] `new prop`, `import`, `pick`, `run` with chroma: `palette.png` has binary alpha and every opaque pixel on the palette,
      with no Runner call.
- [x] Matting with the fake: `needs-input` "Runner not run yet"; `run --rerun` pins it into `needs-review`; `accept` gives `done`.
- [x] Swapping the fake matter for one with another ID gives "Runner input changed".
- [x] Every room test passes unchanged, and an existing room's input hashes don't change from the move.
- [x] `next` gives a command or an owner action at every prop Stage.
- [ ] A manual (not CI) check of the real matting Runner ([0041](0041-m2-matting-runner.md)) on a real prop Source,
      through `cutout` with `run --rerun`, on the Owner's GPU and with `--cpu`, recorded here as 0020's was: time cold
      and warm, VRAM above idle and peak, the GPU-vs-CPU alpha difference, edge quality, and a cancel mid-call.

## Notes (2026-11-04)

- **Shared code** is `kiripix/recipes/common.py`: image read and write, the Source Stage, the Grid read, `run_fit` and
  `check_fit`, and the palette Stage's `run_palette` and `check_palette`. Rooms pass their own image in. `tests/cli/test_room_hashes.py`
  pins the input hashes of a room's brief, source, fit and palette as they were before the move.
- **Alpha by majority vote** is the new Op `alpha_by_vote` (resample): a cell is opaque when at least half its Source pixels are
  (alpha from 128), in `grid` mode as in `downscale`, and a cell the vote makes opaque but whose sampled pixel is clear takes
  the cell's most common colour. Rooms still sample the centre pixel's alpha, as before.
- **Matting** lays the pinned matte over the Source's own colours at the Source's size (nearest, when the call was capped), so
  `fit` sees a full-size cutout. Its alpha is the lower of the Source's and the matte's.
- **Chroma Checks** (`cutout.chroma_keyed_nothing` under 1 % cleared, `cutout.chroma_keyed_everything` over 99 %, and
  `cutout.chroma_fringe`, a warning for an opaque pixel within 0.06 OKLab of the key that touches a cleared one) all point to
  `kiripix set <id> cutout method=matting`. The thresholds are guesses until a real prop shows otherwise (D7).
- **Size:** `fit.size_mismatch` is "exactly the brief's size"; `brief.larger_than_resolution` is "no larger than
  `project.resolution`" (D8).
- `finish`, `footprint` and `export` stay unbuilt, so `next` ends at `finish` with an owner action until the tickets for them.
- `tests/cli/test_graph.py` and `test_export.py` use `character` as the unbuilt Kind now.

## Manual check, still to record

Not run by the agent (it needs the Owner's GPU and the real weights). On a real prop Source with a painted, non-flat
background, in a prop Asset `prop.<id>` at a real brief size:

```
kiripix runners pull birefnet
kiripix import prop.<id> <real source>.png ; kiripix pick prop.<id> <variant>
kiripix set prop.<id> cutout method=matting
kiripix run prop.<id> brief ; kiripix run prop.<id> source
kiripix run prop.<id> cutout --rerun --progress jsonl     # cold, on the GPU: note the time; watch nvidia-smi for VRAM
rm -r assets/prop/<id>/pinned                             # (Windows: Remove-Item -Recurse) then the same on the CPU:
kiripix run prop.<id> cutout --rerun --cpu --progress jsonl
kiripix run prop.<id> --rerun                             # fit and palette on the accepted-or-not result
```

For warm times, start `kiripix serve`, delete `pinned/` and call `/api/run` (`{"asset": "prop.<id>", "stage": "cutout",
"rerun": true}`) twice. Keep the GPU result's `pinned/*.png` aside before the CPU run to compare the two alphas.

Record here, as 0020's was: time cold and warm; VRAM above idle and at the peak (`nvidia-smi` while it runs); the GPU-vs-CPU
alpha difference (compare the two `pinned/*.png` alphas); the edge quality in `work/cutout/cutout.png` and
`work/palette/palette.png`; and a cancel mid-call (Ctrl-C, or `POST /api/jobs/<id>/cancel` through `serve`), which must pin nothing.
