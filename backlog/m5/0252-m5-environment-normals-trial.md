---
status: done
milestone: M5
agent: ml-engineer
type: trial
parent: 0236-m5-the-games-next-needs.md
---

# M5: trial: normal maps for a painted room from a depth Runner

Spec §8 (Runners: depth), §7 (normals from a depth map), §14 Later ("normal maps for painted backgrounds"). Part of
[0236](0236-m5-the-games-next-needs.md), item 8. The game's ISS-020 (`docs/DECISION_LOG.md`) and M10-02: a flashlight in an
unpowered tunnel, and supernatural glow on walls. Prototype code stays in `backlog/m5/0252-trial/`, not in `kiripix/`.

## Why

The game's lighting (its "Option A") never relights a painted Plate. This is a test the game decides at its M10, not a change
to that rule. A Plate with a normal map in a `CanvasTexture` would let a `PointLight2D` shade its walls.

## What to do

1. **The Runner:** pick a depth model that runs in 8 GB, with its licence confirmed for commercial use and its weights'
   source recorded (spec §8: Depth Anything V2 Small first; check the larger sizes' licences, and anything newer, since the
   choice stays open). Don't add it to the project yet.
2. **Depth to normals:** run it on the Source of a ch01 dungeon room (the stand-in for the game's tunnels), map the depth
   through the room's Grid transform, turn it into normals (Sobel on depth), and quantise them to a few levels. Do it per
   Plate and per foreground Layer, each cut by its alpha.
3. **In Godot 4.7:** the Plate as a `CanvasTexture` with that normal map, under a `PointLight2D` that follows the mouse, beside
   the same Plate without one. A short capture or GIF for the Owner.
4. **Measure** peak VRAM, time per room, and how the normals look at a Layer's edge and on flat painted floors (they should
   stay flat).

## What to record, in this ticket

- The Runner's licence, weights' source, VRAM and time.
- The capture, with its path, and the Owner's view.
- A recommendation for the game's M10: if it's yes, the tickets to file (a depth Runner, a `normals` step for rooms, the
  export's `CanvasTexture` for the Plate and Layers). If it's no, one line in spec §14.

## Acceptance criteria

- [x] The licence confirmed before anything is downloaded into a Project. Any unclear licence goes to the Owner.
- [x] The capture and measures above, and the Owner's verdict recorded.

## Results

Run by the ml-engineer agent, 2026-11-18, on `ch01_dungeon_r01` of the art Project (read-only; nothing written there). Prototype
code, outputs and the Godot test project are in `backlog/m5/0252-trial/`; the weights are in
`~/.cache/kiripix-trial-0252/model.onnx`, outside every Project and outside the repo.

### Step 1: the Runner and its licence (checked before any download)

Licence tags read from the Hugging Face model cards (API) on 2026-11-18:

| Model | Licence | Commercial use |
|---|---|---|
| Depth Anything V2 **Small** (`depth-anything/Depth-Anything-V2-Small`, 25M) | Apache-2.0 | yes |
| Depth Anything V2 Base, Large (and Giant) | CC-BY-NC-4.0 | **no** |
| Depth Anything 3 **Small** (`depth-anything/DA3-SMALL`, Nov 2025) | Apache-2.0 | yes |
| Depth Anything 3 **Base** (`depth-anything/DA3-BASE`) | Apache-2.0 | yes |
| Depth Anything 3 Large (and larger) | CC-BY-NC-4.0 | **no** |

- **Picked for the trial: Depth Anything V2 Small**, as spec §8 says. Weights: the ONNX conversion
  `onnx-community/depth-anything-v2-small` (`onnx/model.onnx`, fp32, 99,060,839 bytes, sha256
  `afb6a5c28f3b6bf1618c6e43f02073ef9dfdc70e937502d51603e57b0a1df10c`), card licence Apache-2.0, base model the Apache-2.0
  Small above. Runs on ONNX Runtime (no PyTorch needed).
- Open for the Owner: DA3-Small and DA3-Base are Apache-2.0 too and newer (DA3 gives metric-ish depth and is said to be sharper at
  edges); not tried, and DA3 has no ONNX conversion I checked. V2 Base, V2 Large and DA3 Large/Giant are non-commercial:
  **never add them.** The card tags are not the licence text itself; before the Runner goes into the project, read the
  `LICENSE` file in the Small repo and record it in the Runner's entry. No licence was unclear, so no question blocks the trial.

### Steps 2-4: the numbers

Source 864x1216, Grid `scale 54/25 x 76/35`, offset 0, fit 400x560. Model input 742x1036 (long side about 1k, multiples
of 14). RTX 2070 Super, ONNX Runtime 1.31.1 CUDA provider (needs `onnxruntime.preload_dlls()`, as `kiripix/runners/ort.py` does).

| | GPU, input 742x1036 | GPU, input 364x518 | CPU, input 742x1036 |
|---|---|---|---|
| session load | 0.8-1.0 s | 0.8 s | 0.6 s |
| first run | 0.9 s | 0.6 s | 3.8 s |
| later run | **0.23 s** | 0.03 s | 4.8 s |
| peak VRAM above baseline (nvidia-smi poll, 50 ms) | **about 2.4 GB** (2416, 2417 MiB in two runs) | **about 0.3 GB** (324 MiB) | none |

The GPU was shared with another trial; the baseline was read just before each run (1.4 GB). The 2.4 GB at 1036 is mostly ONNX
Runtime's arena and the attention buffers, so it stays under the 8 GB cap with room for Blender, but a 518 px input
(about 0.3 GB) is the safer setting if a deep Runner is loaded at once; its depth is blurrier (`depth_518.png`). Depth to
normals, quantised, for the Plate and four Layers, naive and masked: **1.9 s on the CPU, numpy only** (including start-up).
So a room costs about 3 s on the GPU and about 8 s on the CPU, with no Owner time.

### What the normals look like

Pipeline (`normals.py`): depth (relative, nearer = bigger) resampled through the room's Grid (box filter), scaled to 60 px
of height across the room, Sobel, then each tilt component quantised: a dead zone of 0.10 is flat, then 3 levels per side up
to 0.75. For a Layer, "masked" means the depth outside its alpha is first refilled from inside it, so the cut's edge makes no step.

- **Flat floors stay flat.** On the Plate's walkable area 88.6 % of the pixels are exactly flat (0.5, 0.5, 1). The walkway's
  stairs give horizontal banding, which reads as stair edges under the light. Large smooth ramps (the room's outer walls) get
  gentle tilt in 1-2 levels, which is what a wall should do.
- **The Plate** is not holed in the export (alpha is 100 % over the inpainted room), so the Plate's depth is the whole room's
  depth, including the Layers' shapes; the Layers' depth bumps stay in the Plate's normals under them. Harmless while the Layer
  covers them.
- **At a Layer's edge**, naive normals (cut after Sobel) have 31 % of the 2-px rim tilted strongly on `layer1`, and 80 % on the
  small `layer3`; masked cuts that to 23 % and 74 %. The step in depth is real (a ledge in front of a pit), so the light shows
  it as a dark band above the ledge and a bright lip, a shadow-like edge (see `zoom_layer_edge.png`). The small Layers (the
  pipes, 330 px, `layer3` 1,000 px) get almost no flat area: they're 1-3 px wide, so every pixel is an edge.
- Layer alpha is speckled (dither-like holes on `layer1`'s pit side), so its normals speckle too. Where the alpha holes the Plate's normal shows
  through, so there it matches.
- Depth Anything gives a smooth, relative depth: no hard cliffs, but it also puts the pit's far floor near-flat, so the
  dark pits don't light up oddly. It cannot find fine relief (cracks, brick) from a smooth depth map, only the room's big forms.
- In Godot a normal-mapped Plate is **darker overall than the plain one at the same light**, because a flat surface at a
  grazing light height has N.L below 1 while a plain texture counts as fully facing. A usable look needs a light `height` of about 70
  px (the trial's default) and a higher energy; the game would tune this per room.

### Godot 4.7.2 test scene

`backlog/m5/0252-trial/godot/`: `main.tscn`, `main.gd`, `project.godot` (Compatible with 4.7; run with the
`C:\Workspace\[godot]\Godot_v4.7.2-stable_win64.exe`). Left half: the Plate and the four Layers each as a `CanvasTexture`
with its own normal map, under a `PointLight2D` (radial gradient, height 70, energy 3.5, `CanvasModulate` 0.12). Right half:
the same Plate and Layers with no normal map, with an identical light at the same relative place. **To open it:** start Godot,
Import, pick `backlog/m5/0252-trial/godot/project.godot`, press F5, move the mouse over either half (the light follows it
on both); mouse wheel changes the light's height; `L` switches the left half's normal maps off and on.
`--auto` runs a scripted light path.

Captured headless-style (a real window, scripted light, 90 frames of the viewport saved by the scene):

- GIF, 45 frames, 4 MB: `backlog/m5/0252-trial/out/r01/capture.gif`
- Stills: `.../out/r01/shot_10.png`, `shot_40.png`, `shot_70.png`; zoom at a Layer's edge: `zoom_layer_edge.png`
- Normal maps: `.../out/r01/normals/{plate,layer.layer1,layer.layer3,layer.pipe_e,layer.pipe_w}.{naive,masked}.png`;
  overview `montage_r01.png`; depth `depth.png`, `depth_target.png`; numbers `stats.json`, `depth_cuda.json`, `depth_cpu.json`.
- The raw 90 frames in `.../out/r01/shots/` (26 MB, git LFS not set for them) can be deleted: only the GIF and stills matter.

### Recommendation for the game's M10 (the agent's view; the Owner decides)

**Yes, as a cheap option, on one condition: the Owner's eye on the capture.** The Runner is commercial-safe, small, fast, and
the result lights big forms (walls, ledges, stairs, the ceiling) plausibly while floors stay flat; the cost per room is a few
seconds. What it will not do is fine relief, and the Layer edges give a shadow-like rim which may or may not be wanted.
If the Owner says yes, outlines of the tickets to file (not filed):

1. **A `depth` Runner:** Depth Anything V2 Small (or DA3-Small/Base after a trial), ONNX, licence entry, weights hash, pinned
   per ADR 0002 (the input hash, the parameters, the weights hash; no clicks), input cap 1036 px with a 518 px fallback,
   CPU fallback (about 5 s).
2. **A `normals` Stage for rooms** after `layers` and `palette`: depth through the Grid, masked fill per Layer, Sobel, quantise
   (`strength`, `deadzone`, `levels` parameters), output `normal.png` per Plate and per Layer, a check for "flat where the Mask is
   walkable" and a `normals.stale` finding when the Layers change; the Owner can paint a normal-map fix over it (a Decision).
3. **The export's `CanvasTexture`** for the Plate and each Layer (`.tres` with `diffuse_texture` and `normal_texture`, in
   the Manifest, a `normals` flag in `room.json`), and a test scene like this trial's.
4. A short note in the game's M10-02: the light height and energy need tuning to a room; normal-mapped Plates read darker at the same light.

If the Owner says no: one line for spec §14 Later: "Normal maps for painted rooms from a depth Runner: tried in 0252 and not
taken (the relief is too coarse for the game's lights)."

### Waits on the Owner

- Open the GIF or the scene, and give a verdict (the second criterion below).
- Decide whether DA3-Small/Base (Apache-2.0) should also be tried.

### The Owner's verdict (2026-11-18)

**Yes:** "0252 results look good." The four tickets above are the build for the game's M10, filed in M6 on 2026-11-19 as
[0339](../m6/0339-m6-adr-room-normals-stage.md) to [0343](../m6/0343-m6-ui-room-normals.md) (an ADR first: per ADR 0004 the
Stage sits before `palette`). Open: whether
DA3-Small/Base is tried first (ticket 1 says "or after a trial").
