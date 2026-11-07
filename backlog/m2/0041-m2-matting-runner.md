---
status: done
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

## Settled (Owner, 2026-11-04)

- The conversion's MIT tag is accepted as its licence, as SAM 2's conversion was (docs/runner-licences.md).
- The full fp32 `model.onnx` (972 MB). `BiRefNet_lite` is the fallback if it's too heavy, and needs the Owner's approval.
- The test Kind `matte` showing in `describe` when test recipes are on is fine (D16).

## Acceptance criteria

- [x] `runners list` shows it with its licence, hash and size. A test with the fake makes one pinned RGBA result.
- [x] Cancel during a long fake call: `run.cancelled`, nothing pinned.
- Moved to [0050](0050-m2-prop-stages-to-palette.md) (Owner, 2026-11-04): a manual check of the real Runner on a real
  prop Source, through the prop's `cutout` Stage. It ran end to end here on the CPU (2026-11-04, synthetic 400 x 300:
  load 12 s, calls 14-28 s, a cancel stopped it 0.31 s in and the session stayed usable).
