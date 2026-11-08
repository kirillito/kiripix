---
status: done
milestone: M3
agent: ml-engineer
type: ticket
---

# M3: LaMa takes 20 s to load, on every lift

Found by [0089](0089-m3-time-a-lift-honestly.md). Of a cold lift's 32 s on r02, **20.5 s is `onnxruntime.InferenceSession(...)` for LaMa**
(`kiripix/runners/lama.py`, `load`). It is the 23 s the 0076 trial couldn't explain: it sits between the last SAM 2 call and the first LaMa
call because that's where the Runner loads, and `_call` never timed a load.

- **It is CPU time, not the GPU.** The same model on the CPU provider takes 22 to 32 s; the process uses one core for all of it. `onnxruntime`
  1.31.1, `lama_fp32.onnx` (208 MB, the Carve export).
- **None of the cheap options helped.** Each was tried on the real model: graph optimisation levels (basic 28 s, none 37 s, default 21 s),
  saving the optimised graph and loading that (26 s), an ORT-format file (19 s), no pre-packing (24 s), no memory arena (23 s), no constant
  folding (21 s), one thread (32 s). So it isn't the optimiser or a copy to the GPU; something in session creation for this graph is slow.
- **Why it hurts:** `serve` keeps only an `EmbeddingRunner` (SAM 2) warm. LaMa is loaded and unloaded in every lift, so every lift in the UI
  waits 20 s, however warm SAM 2 is. A trim or an accept doesn't call it, so those are fast.

## What to do

1. Find out where the 20 s goes (ORT's verbose log with timestamps, or its profiler, or a build with symbols) and whether another export of
   big-lama (another opset, with the FFT written out, fp16) loads faster. Runner choices stay open: a swap needs the usual pinning rules.
2. Or keep LaMa warm in `serve`, as SAM 2 is, so only the first lift pays. That means the warm module takes any Runner, not an
   `EmbeddingRunner`, and the two Runners must fit in 8 GB together, or take turns (and then a lift that uses both still reloads one).
   LaMa's session on the GPU was not measured for VRAM here.
3. Cancel can't stop a load once ORT is inside `InferenceSession(...)`; a Ctrl+C is seen when it returns. A load this long makes that
   worth fixing (load on a thread, as `ort.run` does for an inference) whichever option is taken.

## Acceptance criteria

- [x] The cause of the 20 s is named here (below).
- [x] A lift in `serve` after the first doesn't pay it, or it is a few seconds. (LaMa is warm; second lift 0.2 s.)
- [x] Within 8 GB of VRAM. A cancel works during a load.

## Findings (ml-engineer)

**The cause: the graph has 17,480 nodes.** The Carve export has the FFT written out as ops: 7,054 `Constant`, 1,360 `Concat`, 1,348
`Reshape`, 1,322 `Slice`, 1,188 `Shape`, plus `Range`/`Cos`/`Sin`/`Einsum` (144 to 216 each) computing the DFT matrices from shape chains, all
at runtime opset 17. Only 222 are `Conv`. ONNX Runtime's session creation cost goes with node count, whichever the provider, so none of the
settings tried before could help. The same file run through onnxsim (`simplify`, fixed batch 1; transient `uv run --with onnx --with onnxsim`,
no dependency added) has **3,028 nodes** and (RTX 2070 Super, CUDA provider, then CPU provider):

| file | nodes | `InferenceSession` CUDA | CPU | first run | later run |
|---|---|---|---|---|---|
| `lama_fp32.onnx` (shipped) | 17,480 | 24.8 s | 25 s | 1.46 s | 0.24 s |
| the same, simplified (205 MB) | 3,028 | **1.4 s** | **1.1 s** | 0.93 s | 0.23 s |

On a random image with a hole the two outputs differ by at most 0.0014 (of a 0 to 255 scale) before rounding, and 7 of 786,432 values
differ by one level after it. That is the same size as the CPU-versus-GPU difference every Runner already has.

**What was done (no change to the weights).** `serve` now keeps LaMa warm beside SAM 2, and a cancel works during a load:
- `Runner.can_stay_warm` (default False; True for `EmbeddingRunner` and `Lama`). `kiripix/core/warm.py` holds up to `MAX_WARM = 2` Runners
  (least recently used goes first), under one shared GPU lock, each with its own idle timeout and unload-on-request. BiRefNet (about 2 GB)
  stays a load-and-unload Runner. A Runner with no embedding is called through `warm_call` as `runner.call`.
- `warm.load_runner` runs `runner.load` on a thread and polls the cancel token, as `ort.run` does. ORT can't be stopped inside
  `InferenceSession(...)`, so a cancel raises at once; the thread finishes alone and unloads what it loaded, and the next load of that
  Runner waits for it (and honours its own cancel). Used by the cold path in `graph.py`, the warm path and `segmenting._cold_call`.
- VRAM (nvidia-smi, base 0.74 GB with the desktop): SAM 2 +1.5 GB, LaMa +0.5 GB, BiRefNet +2.0 GB when loaded; SAM 2 and LaMa both warm
  and used: 3.4 GB above base (4.1 GB in all of 8 GB), including ORT's arenas after calls.
- Lift in `serve` (a SAM 2 call then a LaMa call on a 512 px image, run in-process through `warm_call` on the real weights): first lift
  SAM 2 load 2.0 s + LaMa load 26.7 s (measured while the test suite ran; 20 s alone), then **0.03 s and 0.2 s** for the second and third.
  Before: every lift loaded LaMa (about 20 s) and SAM 2 again (0.9 s). The CLI is unchanged: a cold lift still pays 20 s.

**The real fix for the first load (needs the Owner).** Ship the simplified export as the Runner's weights: load drops from 20 s to 1.4 s,
on the CLI and for the first lift in `serve`. It has to be hosted at a pinned URL (the Carve repo has none) and it is a different file, so
its sha256 is different, so `Runner.weights_hash` changes. By ADR 0002 every pinned LaMa call then has another key: each is "Runner input
changed", stays on disk, and a `--rerun` makes the call again for review (results differ by at most one level). Nothing is lost, but the
Owner reviews each Asset's patches again. The alternative that keeps pins valid is to make the simplified file on the machine from the
shipped one, which needs `onnx` and `onnxsim` as dependencies (heavy; not added). Not done: the Owner decides.

## The Owner's decision on the simplified export (2026-11-07)

Neither option for now: the shipped `lama_fp32.onnx` stays. A 20 s load in one Stage is acceptable. Switch to the simplified
export (3,028 nodes, about 1.4 s) only if the load turns out to slow the work on one room by more than 20 s in all, for example
by being paid again and again. Rebuilding rooms isn't a cost to weigh: none is ready for the game, and all are re-run anyway.

Where the load is paid today, for that judgement: LaMa is used only by the `layers` lift's fills. In `serve` it stays warm, so
a room's lifts pay it once, and again only after 5 minutes idle (`--warm-idle`), after a BiRefNet `cutout` (it loads alone and
unloads the warm Runners), or when another process asks for the GPU. From the CLI, as an agent works, every `run` that fills
pays it.
