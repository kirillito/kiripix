---
status: done
milestone: M3
agent: ml-engineer
type: ticket
---

# M3: an accepted matting result asks for review again

Spec §8 (pinning) and ADR 0002. Found during the [M2 gate](../m2/0058-m2-gate.md) in the art Project, 2026-11-07.

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

- [x] The two comparisons are recorded here, per Runner.
- [x] Accept, `run --rerun` with nothing changed, and the Stage stays `done` for BiRefNet, at a seam the CI can run without a GPU
      (a fake Runner with the same nondeterminism) and once by hand on the GPU.

## Findings (2026-11-07, ml-engineer)

Measured on the RTX 2070 Super, onnxruntime CUDA and CPU, on the lamp's `work/source/source.png` (1376 x 768, `max_size` 1536).

**Cause: the device, not run-to-run noise.** The accept (journal 00:30:31) lists `71985f5d…`, which is the CPU run of 00:29:11 (the
history shows CUDA, CUDA, CUDA, CPU, then the accept, then a CUDA run at 00:32:52 after the pin was removed). The accept's hash is the
same `sha256` of the PNG as `unreviewed_pins` computes, so there is no hash mismatch. The CUDA result is `d39cf4d7…`. I reproduced both
hashes on a copy: CPU gave `71985f5d…`, CUDA gave `d39cf4d7…`.

| Runner | CUDA vs CUDA (3 runs) | CPU vs CPU (2 runs) | CUDA vs CPU |
|---|---|---|---|
| BiRefNet (RGBA, 1376 x 768) | identical | identical | alpha differs by 1 level in 14 of 1,056,768 pixels; RGB equal |
| LaMa (512 x 512 crop, 5 rows of hole) | identical | identical | 1 value of 1,048,576 differs by 1 |
| SAM 2.1 small (one click, Mask) | identical | identical | identical (the Mask I used may be trivial; not checked further) |

So each device is deterministic; the two devices differ by rounding in a handful of pixels. `device` isn't in the key (ADR 0002), so the
same key can hold two different PNGs. The Runner output can't be made bitwise equal across devices (the boundary flips are in the
float matte before rounding), so no tolerance on the stored alpha would hold either.

**Fix.** `pinning.store` now also records `result_hash` (sha256 of the PNG it wrote) in the pin's record, after the PNG.
`graph.unreviewed_pins` treats a key the Owner accepted as still accepted when it is pinned again with other bytes, as long as the PNG
still matches its record's `result_hash` (`pinning.is_as_made`), i.e. the Runner made it for that key. A pin edited by hand, or a
record without `result_hash` (every pin made before this), keeps the strict rule: another hash is reviewed again. No tolerance
is needed, so none is recorded. A rerun on the other device still changes the pinned bytes, so the Stages downstream of it go
stale and rebuild, as they must.

**Tests.** `tests/cli/test_matter.py`: accepted on the CPU, pin removed, rerun on the other device with a fake matter that differs by
one alpha level on the CPU (`matter-cpu-differs` in the test recipes): Stage stays `done`; and an edited pin of an accepted key is
`stale`, then `needs-review`. By hand on a copy of the art Asset (CPU rerun 42.9 s incl. a cold start, accept entry, pin removed, CUDA
rerun 17 s incl. load): `cutout` stayed accepted, the next Stage is `fit`. The `accept` was written as a journal entry on the copy,
because `accept` is Owner-only.
