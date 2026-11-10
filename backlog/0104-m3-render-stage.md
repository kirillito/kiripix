---
status: done
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0103-m3-clips-stage.md]
---

# M3: the `render` Stage: camera presets, 8 directions and the passes

Spec §6.3 (render), §10.4 (the GPU lock) and ticket 0031 (cancellable work). Stories 7 to 9 of [0097](0097-m3-characters.md).
Follows the ADR from [0098](0098-m3-blender-renders-and-pinning.md). Q6 of 0097 is answered: render all 8 directions, none mirrored. Q7: ask the Owner first.

Shading here is plain and flat; [0105](0105-m3-toon-shading.md) adds the toon look, so this ticket stays one session.

## What to build

- **Camera presets** `top34_4`, `top34_8`, `side`, `battle`: orthographic, angles from the presets (in `kiripix.toml` if
  the Owner chose that in Q7), the ortho scale set so the Model's height is `[character] height` target px.
- **Directions:** 8 for `top34_8` and 4 for `top34_4`, by turning the Model about its up axis in fixed steps, so the light
  stays with the camera. Name them as Q5 decided: `s sw w nw n ne e se`, `s` facing the camera.
- **Passes, per frame:** colour, normal, depth, and an object mask, all at the target size, no anti-aliasing (filter size
  0, no texture filtering), with binary alpha from the mask.
- **Frames:** each clip sampled at its frame rate from `clips.json`.
- **The pivot:** the ground point under the root, projected to the frame, written per frame to `render.json`
  (`schema_version`, frame size, pivot, per clip and direction the frame files).
- Takes the GPU lock; renders on the CPU with `--cpu`. Checks the cancel token between frames; a cancel leaves nothing.
- Progress events per frame. Pinned or not, as the ADR says.

## Acceptance criteria

- [x] CLI seam, on the fake: `run` writes every clip × direction × frame file and `render.json`; changing `camera` makes
      `render` stale (or `needs-input`, per the ADR) and everything below it.
- [x] A cancelled render leaves the Stage as it was.
- [x] Marked `blender` test: the walk fixture at `top34_8` gives 8 directions × its frame count, each frame exactly the
      target size, alpha only 0 or 255, the normal pass the same size as the colour pass.
- [x] Timing for the fixture and for one real clip is recorded here (GPU and CPU).
- [x] The measurement from [0098](0098-m3-blender-renders-and-pinning.md): one clip of the walk fixture in one direction,
      rendered twice on the GPU and once on the CPU with this Stage's settings, compared pixel by pixel per pass (GPU
      against GPU, GPU against CPU). Record "equal" or the count of differing pixels per pass here, and add the result to
      [ADR 0010](../docs/adr/0010-blender-renders-rebuild-and-are-not-pinned.md). It decides nothing; the ADR stands.

## Results

- **Timing** (Blender 5.2.3, this machine: Intel Core Ultra 7 155H, Intel Arc through oneAPI, no NVIDIA), the walk fixture at
  52 px (78 px cell), a Blender process from start to exit, warm file cache: 8 directions x 8 frames (64 renders, all four passes)
  took 5.7 s and 7.1 s on the CPU, and 10.7 s and 29.4 s on the GPU (the oneAPI kernels load slowly and the time varies). One
  direction, 8 frames: 3.4 s CPU, 5.2 to 6.5 s GPU. The first Blender run after a restart took about 19 s. At this size a frame is
  about 0.05 s, and the start-up dominates, so **the CPU is as fast as the GPU here and `--cpu` is a fine default for 52 px**.
  No real (Quaternius) clip was available, so one real clip isn't timed: scale by the triangle count, not the frame count.
- **The measurement** is in [ADR 0010](../docs/adr/0010-blender-renders-rebuild-and-are-not-pinned.md): colour and mask equal on
  all three; normal 45 and depth 11 pixels differ between GPU and CPU, the two GPU runs equal.
- Cycles, not EEVEE: EEVEE needs a GPU, and the ticket asks for `--cpu`. Every pass is a primary-ray value.
- The fixture `rigged.glb` carries a stray `Icosphere` mesh (a bone shape) that makes the Model 2.7 times too tall in `model`;
  the render test uses `rigged.fbx`. A ticket 0100 fix is the Owner's call.
