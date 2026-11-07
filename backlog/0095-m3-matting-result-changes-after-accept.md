---
status: todo
milestone: M3
agent: ml-engineer
type: ticket
---

# M3: an accepted matting result asks for review again

Spec §8 (pinning) and ADR 0002. Found during the [M2 gate](m2/0058-m2-gate.md) in the art Project, 2026-11-07.

`prop.street_lamp`'s `cutout` is `needs-review` although its journal holds an `accept` for the pinned call `cf21fd12…`. The accept
lists the result's hash as `71985f5d…`; the pinned PNG on disk is `d39cf4d7…` by sha256. `history.jsonl` shows BiRefNet running
again on CUDA for the same key after the Owner had accepted it. `graph.unreviewed_pins` (`kiripix/core/graph.py:256`) reviews a
result again when it changed, which is right. The question is why it changed.

Guesses, untested: BiRefNet on CUDA isn't deterministic from run to run, so a rerun with the same inputs gives other bytes, or the
result's hash is computed from something other than the pinned file. If it's the first, every rerun of a matting Stage would ask the
Owner to review an unchanged-looking result again.

## What to do

1. Run BiRefNet twice on the same Source, on CUDA and on the CPU, and compare the outputs byte for byte, and as alpha.
2. Check which bytes the accept's hash covers, against the pinned file.
3. Fix by the finding: make the Runner's output stable (deterministic settings, or rounding the alpha before it's stored), or keep the
   pinned result when a rerun's differs by less than a stated tolerance, with the tolerance recorded in the history entry.

The same may hold for SAM 2 and LaMa. Check them the same way, and note it here.

## Acceptance criteria

- [ ] The two comparisons are recorded here, per Runner.
- [ ] Accept, `run --rerun` with nothing changed, and the Stage stays `done` for BiRefNet, at a seam the CI can run without a GPU
      (a fake Runner with the same nondeterminism) and once by hand on the GPU.
