---
status: todo
milestone: M1
agent: ml-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0016-m1-masks.md, 0012-m1-override-accept-review.md, 0031-m1-cooperative-cancel.md]
---

# M1: pinned Runner calls, and SAM 2 click-to-segment in masks

Spec §5 (Pinned calls, Running), §8, and ADRs 0002 and 0004. docs/runner-licences.md (SAM 2: Apache-2.0, every
size). User stories 13–15 of [0010](0010-m1-room-end-to-end.md).

## What to build

- Pinning: a Runner call's key covers the input image or crop hash, the click Decisions, the parameters, and the
  Runner's ID with a hash of its weights (not the device). Results go in `pinned/` by key, committed. A Stage's
  pinned results are part of its input hash.
- `run` never calls a Runner. When a pinned result is missing or keyed on changed inputs, the Stage is `needs-input`
  with "Runner input changed" (or "Runner not run yet"), and `next` names `kiripix run <id> <stage> --rerun`.
  `run --rerun` (at any scope, including `--all`) runs it and lands the Stage in `needs-review`.
- `runners/`: lazy load, one at a time, unload after use; weights downloaded on first use into `.kiripix/weights/`,
  with their hash and licence recorded. ONNX Runtime with CUDA, a CPU fallback, and `--cpu`. The GPU lock is held
  while a Runner is loaded.
- SAM 2 (small or base) for `click` Decisions in `masks`: clicks map from target pixels to the Source through the
  Grid transform, the Runner works on the high-resolution Source (capped at about 1–1.5k px), and its mask maps back
  to a 1-bit Mask on the target grid. Positive and negative clicks. Turn `gpu=True` back on for the `masks` Stage
  (0016 left it off, since flood, brush and import need no GPU).
- Cancel ([0031](0031-m1-cooperative-cancel.md)): a Runner call takes the Command's cancel token. ONNX Runtime
  sessions run with a `RunOptions` whose `terminate` is set when the token fires, so a cancel stops a running
  inference rather than waiting for it. Weight downloads check the token between chunks. Add a test with the fake
  Runner: cancel during a long call, and `run.cancelled` comes back with nothing pinned.
- `kiripix runners list|pull|rm`.
- Every Runner call is appended to `history.jsonl` with `runner`, the parameters and the time.
- Tests never download weights: a fake Runner, registered through the test hook, returns a deterministic mask.

## Acceptance criteria

- [ ] With the fake Runner: a `click` and `run --rerun` give a pinned result and `needs-review`; `accept` gives
      `done`; a plain `run` after deleting `work/` rebuilds from the pinned result without calling the Runner.
- [ ] Changing the Source after that makes `masks` `needs-input` with "Runner input changed".
- [ ] A manual (not CI) check of the real SAM 2 on a real room, on the owner's 8 GB GPU and with `--cpu`.
