---
status: done
milestone: M2
agent: ml-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0039-m2-chained-runner-calls.md]
---

# M2: the inpainting Runner (LaMa today)

Spec §6.1, §8, ADRs 0002 and 0004, docs/runner-licences.md. Today's choice, not a lasting one.

## What to build

- `kiripix/runners/lama.py`: an inpainting Runner, and a role constant `INPAINTER` beside `SEGMENTER`. Nothing outside that
  file knows its engine or input size. Prefer ONNX Runtime; if PyTorch is the only way, stop and ask the Owner, since it
  changes the install.
- Its contract, in the role's docstring: an RGBA image and a crop with a hole in `params`, returning an RGBA image of the
  crop with the hole filled. The Stage owns nothing engine-specific.
- Weights pinned at one commit by each file's hash. `runners list`, `pull` and `rm` work with no change.
- Cancel: an inference stops through `RunOptions.terminate`, as in `sam2.py`.
- A fake inpainter in `tests/fixtures/kiripix_test_recipes.py`: deterministic, and it logs its calls.
- docs/runner-licences.md: the weights' hash and the conversion you pin. The file already gives LaMa a caveat, and the
  Places2 attribution. The conversion's own licence statement needs checking, as it did for SAM 2.

## Acceptance criteria

- [x] With the fake inpainter registered under `INPAINTER`, a test swaps in a second fake with another ID: its pinned calls
      go to "Runner input changed", and `run --rerun` remakes them into `needs-review`.
- [x] Cancel during a long fake call: `run.cancelled`, nothing pinned.
- [x] A manual (not CI) check of the real Runner on a real room, on the Owner's 8 GB GPU and with `--cpu`: time, memory and
      quality, recorded in this ticket as in [0020](0020-m1-pinned-runner-calls-sam2.md).

## Done (ml-engineer, 2026-11-04)

Built `runners/lama.py` (`Lama`, id `lama`, `INPAINTER` in `runners/__init__.py`), the fake `FakeInpainter` and the test
Kind `inpaint`, `tests/cli/test_inpainter.py`, and the licence note. Weights: `Carve/LaMa-ONNX` at commit `c3c0c9e4...`,
`lama_fp32.onnx`, sha256 `1faef530...`, 208 MB; fixed 512 x 512 input, so a crop is fitted inside the square (aspect kept,
edge-padded), inpainted, scaled back, and only the hole's pixels are taken from the result.

Manual check, not CI, 2026-11-04, CPU only: this machine has no NVIDIA GPU, so the 8 GB GPU run is still the Owner's.
CPU: load 20 s (first, cold), one call on a 220 x 260 crop 2.9 s; the pixels outside the hole are bit-identical. Tested on
a synthetic brick/gradient image, no real room was available in the repo: **the quality check on a real room, and the
GPU time and VRAM, are still to do (so the third criterion stays open).**

## Manual check on the Owner's GPU (2026-11-05)

`room.harbor_front`, `lama` on the Owner's 8 GB GPU (`device: cuda` in `history.jsonl`), as the `layers` Stage's run:

| | Stage time | GPU memory |
|---|---:|---:|
| A small Layer | 1.27 s | 521 MB |
| A large Layer (the lake, 22 LaMa calls) | 2.33 s | 1021 MB |

One LaMa call takes 0.23-0.31 s warm and about 0.8 s for the first call of a run.

**CPU.** The `--cpu` run did reach the CPU, but only one of its LaMa calls was made: `history.jsonl` has a single
`"device": "cpu"` call, 2.63 s for the crop `[456, 896, 768, 1193]`, the same crop CUDA did in 0.30 s (about 9x). The
others were served from `pinned/`, since the device isn't part of a call's key. So the Stage times of that run (0.72 s and
1.44 s) are not CPU inference times. A full CPU time needs a Layer not lifted before. Earlier, without a GPU: 2.9 s for
one call on a 220 x 260 crop. The Owner is looking at the CPU logs separately; this ticket doesn't wait on it.

**Quality.**
- Plausible fill: good on small and narrow objects, poor on large Layers, as expected.
- Seams: visible, many on large objects. They also show on small or narrow objects whose colour is close to the
  surrounding colour.
- Large holes: blurrier, and LaMa invents objects that don't belong. Lifting the lake as a Layer put a bridge in the middle
  of the lake.
- After `palette`: the export of the room then failed with `TypeError ... godot.py:113` and the room stopped loading. That
  was an export bug, not the Runner's, fixed on 2026-11-05: a Layer with neither a y-sort line nor "always above", in a room
  exported before, crashed the status check of every `show`. See [0047](0047-m2-export-room-layers.md).

Large Layers are where LaMa is weakest. A larger Plate source (a `plate-import` from a hand-painted or generated Plate,
[0044](0044-m2-plate-from-difference.md)) is the route for those today; a better inpainter is the Owner's call.
