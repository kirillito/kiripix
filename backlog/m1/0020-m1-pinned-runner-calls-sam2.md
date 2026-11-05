---
status: done
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

- [x] With the fake Runner: a `click` and `run --rerun` give a pinned result and `needs-review`; `accept` gives
      `done`; a plain `run` after deleting `work/` rebuilds from the pinned result without calling the Runner.
- [x] Changing the Source after that makes `masks` `needs-input` with "Runner input changed".
- [x] A manual (not CI) check of the real SAM 2 on a real room, on the owner's 8 GB GPU and with `--cpu`. See below.

## Manual check (2026-11-03)

On the owner's RTX 2070 Super (8 GB) and a real room, `subway-lower-bay` (1376 x 768 Source, 640 x 360 target), with
`onnxruntime-gpu[cuda,cudnn]` installed:

- **Time, one call:** 0.64 s on the GPU, 2.14 s with `--cpu`. Further clicks on the same image in one run: about 0.08 s.
- **Memory:** about 2.35 GB above idle (3.4 GB peak, with 1.07 GB idle), well inside 8 GB.
- **Same result:** the GPU and `--cpu` Masks for that click were byte-identical on this room. ADR 0002 doesn't rely on it.
- **Quality:** clicks on a pillar, a fire extinguisher, a train door's window and a puddle each gave a clean Mask of that
  object, and a click on the floor gave one tile. A click takes what is under it, so a floor needs a flood or several clicks.
- **Cancel, real inference:** `RunOptions.terminate` stopped the encoder 0.27 s into a 2 s call on the CPU and 0.17 s into
  a 0.5 s call on the GPU, and the session stayed usable.

## Notes

- **A positive click is one Runner call**, with the negative clicks right after it on the same Mask refining it. Its
  result is added to the Mask. So clicking a second object keeps the first one's pinned result, and undo and redo find
  theirs again. A negative click with no such positive before it, or a click off the Plate, is `needs-input`.
- **Status stays derived.** A result is unreviewed until an `accept` entry in the Stage's journal lists it: the existing
  `{accept: [...]}` entry now lists pinned results as well as divergent entries, so the journal's format is unchanged,
  and a fresh clone sees `done`. It lists `<key>:<hash of the result>`, so a call on other inputs, or a result that
  changed, is reviewed again, even if the new result has the same pixels as an earlier one. A remade call with the same
  key and the same bytes needs no second review; `run` says so with `skipped` and a message.
- **"Changed" or "not run yet":** the record beside a result (`pinned/<key>.json`) holds the click Decisions. A missing
  call whose Decisions have a record was made on other inputs, so it is "Runner input changed". The Source's change shows
  once `run` has rebuilt `source`; until then `masks` is `stale`.
- **The key** uses the weights' hash declared in `runners/`, never read from the files, so a fresh clone with no weights
  finds its pinned results. The pinned Mask stays at the capped Source size (1536 px on the longer side), and maps to the
  target grid on replay, so it survives a change to `snap_cell`.
- **The GPU lock** is held while a Runner is loaded and through the `masks` run function (`gpu=True`, as asked), even for
  a run that calls no Runner. `--cpu` takes no GPU lock, but one process still loads one Runner at a time, since a
  server's Commands share the registered Runners. `runners rm` takes the GPU lock.
- **The model stays replaceable** (the Owner's decision, 2026-11-03; spec §8). A swap sends every pinned call to
  "Runner input changed", and only `runners/sam2.py` knows about ONNX Runtime.
- **The dependency** is `onnxruntime-gpu`. It finds CUDA at load time and falls back to the CPU; the CUDA libraries are a
  separate install of about 2 GB, so they aren't a dependency of Kiripix or CI.
