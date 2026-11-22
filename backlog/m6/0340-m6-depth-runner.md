---
status: done
milestone: M6
agent: ml-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0339-m6-adr-room-normals-stage.md]
---

# M6: a `depth` Runner: Depth Anything, ONNX, pinned

Spec §8 (the depth row), ADR 0002 (pinning). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Ticket 1 of
0252's outline ([0252](../m5/0252-m5-environment-normals-trial.md), "Recommendation"); the trial's prototype and numbers are
in `backlog/m5/0252-trial/`.

## What to build

- **First, a short comparison (half a day at most):** Depth Anything V2 Small, which the trial used, against DA3-Small and
  DA3-Base (both Apache-2.0 on their cards). Use the trial's room `ch01_dungeon_r01` and its capture, and convert DA3 to ONNX
  only if that is quick. Keep V2 Small unless a DA3 is clearly sharper at wall and Layer edges in 8 GB. Record the pick here.
  V2 Base or Large, and DA3 Large or Giant, are non-commercial: **never add them.**
- **The Runner** in `kiripix/runners/depth.py`, on ONNX Runtime as `ort.py` does (CUDA with `preload_dlls()`, CPU fallback,
  about 5 s). Its licence entry comes from the repo's `LICENSE` file itself, not the card tag. Its weights hash goes in
  `weights.py`, with the weights downloaded on first use into `.kiripix/weights/`.
- **Input cap** 1036 px on the long side (multiples of 14), or 518 px when VRAM is short. That was about 2.4 GB and 0.3 GB
  above baseline in the trial. The size is a recorded parameter in the call's key, set by the Stage, never lowered silently
  from the machine's free VRAM (ADR 0014). Loaded lazily and unloaded after use, one Runner at a time.
- **Pinned** per ADR 0002: the key is the input hash, the parameters and the weights hash; there are no clicks. Output: a
  float32 depth image at the Runner's resolution, stored with the pin. The Stage maps it through the Grid (0341).
- **Cancellable:** `RunOptions.terminate` on cancel, as the other ONNX Runners do.

## Acceptance criteria

- [x] The comparison's verdict and its images recorded here.
- [x] CLI seam, with a stub engine as the other Runner tests use: a pinned call replays without loading the engine, and a
      changed weights hash makes it stale (`needs-input`, "Runner input changed").
- [ ] A real-GPU test, skipped without CUDA and the weights, as SAM 2's is: depth on the trial's room within 2x the
      trial's time.
- [x] The licence entry and weights hash in the repo; spec §8 names the pick.

## Result

Done 2026-11-20 by the ml-engineer agent.

- **The Runner:** `kiripix/runners/depth.py`, ID `depth-anything-v2-small` (role constant `runners.DEPTH`), Apache-2.0,
  ONNX Runtime (CUDA with `preload_dlls()`, CPU fallback), loaded lazily and unloaded after use, not kept warm. Weights: the
  `onnx-community/depth-anything-v2-small` fp32 `onnx/model.onnx`, pinned at commit `4472b736...`, 99,060,839 bytes, sha256
  `afb6a5c2...` (the trial's file). Licence entry and sources in `docs/runner-licences.md`; spec §8 names the pick.
- **Contract (for 0341):** the call's image is a whole RGBA image; `params` is `{"size": 1036 | 518}` and `decisions` is `[]`.
  It returns a float32 `(H, W)` depth in 0 to 1 (nearer is bigger, the image's own min and max), at the model's input size:
  the long side at `size`, both sides a multiple of 14 (864 x 1216 at 1036 gives 742 x 1036). The Stage maps it through the
  Grid. Cancel goes through `ort.run` (`RunOptions.terminate`).
- **The pinned result** is a 16-bit greyscale PNG (`pinning.store` takes a float32 result; `runners.depth.encode` and
  `decode` convert). 8 bits would stair-step the gradients under Sobel. The Stage reads it with PIL (mode `I;16`) and
  `decode`. Pillow's `convert("RGBA")` clips 16-bit to white, so a thumbnail made through `load_rgba` shows a depth pin as
  white: the review UI should show it as a browser does (a 16-bit PNG is fine in `<img>`), or the Stage's own 8-bit image
  does. Not done here (0341 or the UI).
- **The input size is a recorded parameter, never lowered from free VRAM** (ADR 0014). I chose to **fail**, not to record a
  fallback: a call at a `size` the GPU has no room for raises a `RunnerError` that names the parameter ("set the call's
  `size` to 518, or run with --cpu"). The CPU at the same `size` gives the same key, so `--cpu` is the other way out. The
  Stage (0341) owns the parameter and turns that message into its finding with a `fix`. A `size` that isn't 1036 or 518 is
  refused. Detecting "no room" is by the engine's error text, untested on a real out-of-memory (no GPU on this machine today).
- **Comparison, V2 Small against DA3-Small and DA3-Base:** the ONNX conversions exist
  (`onnx-community/depth-anything-v3-small` and `-base`, Apache-2.0 cards), so I ran all three on the trial room at 1036 px:
  `0340-depth-comparison.png` (source, V2 Small, DA3-Small, DA3-Base, nearer is lighter; DA3 gives depth, so inverted).
  V2 Small has the cleanest edges at the pit walls and ledges. Both DA3s are blotchier, with halos along the outer walls and
  banding on the stairs, and none is clearly sharper. They are also bigger (DA3-Base's weights are 412 MB) and take a 5-D
  input and four outputs. **Verdict: keep V2 Small.** ADR 0014's "still open" item on DA3 is settled. The Owner can look at the
  image to disagree. I added no DA3 weights to the repo.
- **Numbers:** this machine's CUDA was not usable today (`cudaSetDevice` failed with 801, no `nvidia-smi`), so **no GPU time or
  VRAM was measured**. The trial's remain the reference: about 2.4 GB above baseline at 1036 and 0.3 GB at 518, about 3 s a
  room with the load. On the CPU today: load 0.5 s, 1036 px 2.8 s, 518 px 0.7 s on the trial room. The real-GPU test is
  written and skips without CUDA; it hasn't passed on a GPU yet.
- **Tests:** `tests/cli/test_depth.py` (the test Kind `depth` and `FakeDepth` are in `tests/fixtures/kiripix_test_recipes.py`):
  a pinned call replays without the Runner, other weights make it `needs-input` with "Runner input changed", the record,
  failure, cancel, the listing, and two real-weights tests (GPU within 2x the trial's 3 s; CPU, and a refused size).
- **No Stage `version` bumps**: no Stage uses the Runner yet. `pinning.store` gains a float32 branch only.
- **The Owner accepted** the `onnx-community` conversion of V2 Small on 2026-11-20, as for SAM 2, BiRefNet and LaMa (its card
  states no licence text of its own); recorded in `docs/runner-licences.md`.
