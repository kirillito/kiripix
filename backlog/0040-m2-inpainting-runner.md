---
status: todo
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

- [ ] With the fake inpainter registered under `INPAINTER`, a test swaps in a second fake with another ID: its pinned calls
      go to "Runner input changed", and `run --rerun` remakes them into `needs-review`.
- [ ] Cancel during a long fake call: `run.cancelled`, nothing pinned.
- [ ] A manual (not CI) check of the real Runner on a real room, on the Owner's 8 GB GPU and with `--cpu`: time, memory and
      quality, recorded in this ticket as in [0020](0020-m1-pinned-runner-calls-sam2.md).
