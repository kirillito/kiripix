---
status: done
milestone: M2
agent: core-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: time click-to-segment, and stop a rebuild unloading SAM 2

Spec §10.4, §10.6 and ADR 0002. Story 19 of [0037](0037-m2-layers-and-props.md). The Owner found SAM 2 clicks slow at the M1
gate, and named them as a main cost in their time per room. Nobody has timed them. Do this ticket first in M2.

## The likely cause

`masks` has `gpu=True` ([room.py:903](../kiripix/recipes/room.py#L903)), so `execute` holds the GPU lock through a run that
replays pinned results and loads no Runner ([graph.py:535](../kiripix/core/graph.py#L535)). Spec §10.4 says the lock is held
only while a Runner is loaded. `hold` then asks a warm Runner to let go
([locks.py:152-155](../kiripix/core/locks.py#L152-L155)). So with "Rebuild the Masks after each edit" on, each edit may unload
SAM 2 and lose its embedding, and the next hover loads it and encodes the image again. This comes from reading the code. The
timing below decides.

## What to do

1. Measure before changing anything, on `room.harbor_front` or a room of its size, on the Owner's GPU: a hover's first preview
   on a cold server; a repeat hover; a hover straight after a rebuild; a click until its Mask shows, rebuild on and off. Split
   each into load, encode, decode and rebuild, wherever the time is visible.
2. Set `gpu=False` on `masks`, if step 1 shows the unload. `make_runner_calls` takes the lock itself, so `run --rerun` keeps it
   while a Runner is loaded.
3. Measure again, and record both sets of numbers in this ticket.
4. If most of the time is somewhere else, say where and propose the next change. Don't build it here. A different Runner is a
   fair proposal, since Runner choices stay open.

## Acceptance criteria

- [x] The before and after numbers are recorded in this ticket.
- [x] A CLI test: a plain `run` of a Stage that makes no Runner call doesn't take the GPU lock, and `run --rerun` still does.
- [x] A test with a fake warm Runner: a rebuild of `masks` doesn't ask it to unload.
- [x] `tests/cli/test_runner_calls.py` still passes unchanged.

## Results (2026-11-04)

**The Owner's clicks were never on the GPU.** All 26 Runner calls in `room.harbor_front`'s history say `device: cpu`. The
project's `.venv` has `onnxruntime-gpu` but no CUDA libraries, so ONNX Runtime can't load `cublasLt64_13.dll` and SAM 2 falls
back to the CPU. Nothing tells the Owner except an error in the server's stderr. `uv sync` causes it: a dry run shows it
uninstalling the 7 `nvidia-*` packages that the README's `uv pip install "onnxruntime-gpu[cuda,cudnn]"` adds.

**The unload was real, and is fixed.** `masks` no longer sets `gpu=True`. `describe` still reports `gpu: true` for it, now
derived from its Runner calls.

### Method

A copy of `room.harbor_front` (640x368, Source 1376x768, 75 Decisions) on an RTX 2070 Super (8 GB), in a real `kiripix serve`
with SAM 2's methods timed, driven over REST with the Commands the UI sends. "Refresh" is the UI's `status`, `show`, `next` and
`check`. The CPU column is the project's `.venv`. The GPU column is a throwaway venv with the README's extras. Times are
seconds, medians of 4 except repeat hover (6) and the cold server (1), so small differences are noise. They leave out the UI's
60 ms hover delay and drawing in the browser.

| | CPU before | CPU after | GPU before | GPU after |
|---|---:|---:|---:|---:|
| Hover, first on a cold server | 9.13 | 7.13 | 7.89 | 6.22 |
| Hover, repeat | 0.09 | 0.08 | 0.06 | 0.07 |
| **Hover, straight after a rebuild** | **3.45** | **0.08** | **1.30** | **0.08** |
| Brush with rebuild on, until refreshed | 1.87 | 1.36 | 1.50 | 1.45 |
| Click with rebuild on, until its Mask shows | 4.91 | 4.31 | 2.66 | 2.68 |
| Hover, straight after that click | 3.00 | 2.68 | 1.28 | 1.20 |
| Click with rebuild off, until refreshed | 0.65 | 0.62 | 0.64 | 0.63 |
| Hover, straight after that click | 0.08 | 0.08 | 0.07 | 0.07 |

Where the time goes, in the "after" runs:

| | CPU | GPU |
|---|---:|---:|
| Cold hover: load (first import of ONNX Runtime included) | 4.88 | 5.29 |
| Cold hover: encode | 1.82 | 0.46 |
| Any load after that | 0.72 | 0.88 |
| Encode | 1.85 | 0.20-0.28 |
| Decode | 0.04-0.06 | 0.02 |
| Unload, and the wait for the GPU lock | 0.41 | 0.28 |
| `masks` rebuild | 0.41-0.45 | 0.42-0.52 |
| Refresh | 0.59-0.67 | 0.59-0.65 |

### Where the rest of the time is: proposals, none built here

A click and the hover after it still take 7.0 s on the CPU and 3.9 s on the GPU.

1. **Make `run --rerun` use the warm Runner in `serve`.** `make_runner_calls` still goes through `warm.one_runner_loaded`, so
   each click unloads SAM 2, loads it, encodes, and unloads it, and the next hover loads and encodes again. Calling it through
   the warm Runner and its embedding cache removes both loads, both encodes and the unload. By subtraction that leaves about
   1.2 s for a click and 0.08 s for the hover on either device, once the image is encoded. The biggest gain, and it helps
   whichever device runs.
2. **Keep the CUDA libraries, and say when they're missing.** Make them survive `uv sync`, for example as an optional
   extra that the Owner syncs with, and add a finding, or a field in `runners list`, when a GPU machine falls back to the CPU.
   This takes an encode from about 1.85 s to about 0.25 s.
3. **Trim what every Mask edit pays.** Refresh (about 0.6 s) and the rebuild (about 0.45 s) now dominate a brush stroke, and
   would dominate a click after proposal 1.

A different Runner isn't called for yet. A warm decode takes 0.02-0.06 s, and the encode is what a different Runner would
change, which proposals 1 and 2 already mostly remove.
