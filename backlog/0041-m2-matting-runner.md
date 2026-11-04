---
status: todo
milestone: M2
agent: ml-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: the matting Runner (BiRefNet today)

Spec §6.2, §8, ADR 0002, docs/runner-licences.md. Today's choice, not a lasting one.

## What to build

- `kiripix/runners/birefnet.py`: a matting Runner, and a role constant `MATTER`. Nothing outside the file knows its engine.
  Prefer ONNX Runtime; if PyTorch is the only way, stop and ask the Owner.
- Its contract: an RGBA image and `max_size` in `params`, returning an RGBA image with the matte as its alpha, capped at
  `max_size` on the longer side, so partial alpha survives until `fit`.
- Weights pinned at one commit by each file's hash. Cancel through `RunOptions.terminate`.
- A fake matter in `tests/fixtures/kiripix_test_recipes.py`.
- docs/runner-licences.md: the weights' hash and the conversion's licence.

## Acceptance criteria

- [ ] `runners list` shows it with its licence, hash and size. A test with the fake makes one pinned RGBA result.
- [ ] Cancel during a long fake call: `run.cancelled`, nothing pinned.
- [ ] A manual (not CI) check of the real Runner on a real prop Source, on the Owner's GPU and with `--cpu`, recorded here.
