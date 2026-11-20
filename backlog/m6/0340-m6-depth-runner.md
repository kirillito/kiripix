---
status: todo
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
- **Input cap** 1036 px on the long side (multiples of 14), falling back to 518 px when VRAM is short. That was about
  2.4 GB and 0.3 GB above baseline in the trial. Loaded lazily and unloaded after use, one Runner at a time.
- **Pinned** per ADR 0002: the key is the input hash, the parameters and the weights hash; there are no clicks. Output: a
  float32 depth image at the Runner's resolution, stored with the pin. The Stage maps it through the Grid (0341).
- **Cancellable:** `RunOptions.terminate` on cancel, as the other ONNX Runners do.

## Acceptance criteria

- [ ] The comparison's verdict and its images recorded here.
- [ ] CLI seam, with a stub engine as the other Runner tests use: a pinned call replays without loading the engine, and a
      changed weights hash makes it stale (`needs-input`, "Runner input changed").
- [ ] A real-GPU test, skipped without CUDA and the weights, as SAM 2's is: depth on the trial's room within 2x the
      trial's time.
- [ ] The licence entry and weights hash in the repo; spec §8 names the pick.
