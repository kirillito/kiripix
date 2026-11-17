---
status: todo
milestone: M5
agent: imaging-engineer
type: trial
---

# M5 trial: PixelLab sprites beside 3D characters: size and style

Found at the M4 gate ([0142](../m4/0142-m4-gate.md), 2026-11-16): in Godot, beside the four mc03 bodies, "some of the sprites
from PixelLab are too small, and we need to deal somehow with the difference in style". Milestone M5 is a placeholder.

## What the gate saw

- **Size:** `sprite.animal_control_worker` is 42 px tall (`fit.height`) against the bodies' 52; `sprite.raccoon` 34 px. Both
  came from PixelLab rotations at its 52 and 40 px canvases ([0175](../m4/0175-m4-sprite-pixellab-export-trial.md)). `fit`
  `grid` never rescales, and `downscale` can't make a figure taller.
- **Style:** the bodies are 3D renders with 2 cel bands (`band_edge` 0.62, smoothed), a dark inner line per part, the
  palette's ramps and normals from the Model. A PixelLab figure has its own shading, its own outline (kept by
  `placement=edge`, recoloured to 195), more colours per part and "pillow" normals from its silhouette.

## Options to try (on the worker and the raccoon, next to mc03 in a ch01 room and in the kitchen)

1. **Bigger source, then `downscale`:** ask PixelLab for a larger canvas (64, or 96–128 px), then `fit mode=downscale
   height=52` (the raccoon at its own height). Kiripix's downscale and palette then set the pixel scale, which may also pull
   the style toward the rooms'.
2. **Steer PixelLab with the 3D look:** its `init_image` from a body's `model` still (`still.png`, DEC-044), so the pose,
   camera and proportions match the 3D route.
3. **Flatten in Kiripix:** `palette colors` lower (fewer shades per sprite, nearer 2 bands), an inner line by colour
   regions where a sprite has no materials, and the `flat` normals choice against `height`.
4. **Move people to the 3D route:** the Project already builds NPCs from a base Model (`npc_*`, 0224/0227); the sprite route
   could be kept for creatures (the raccoon, the "Waiting Ones"), where a 3D Model is the expensive part.

## What to record

- Sheets at 1x and 4x, each option beside mc03_male_clothes01 and mc03_female_clothes01, and a Godot capture under a
  `PointLight2D`.
- Owner time per sprite for each option, and PixelLab cost (DEC-004: $0 budget).
- The Owner's choice, and a build ticket for each part chosen.

## Acceptance criteria

- [ ] The sheets and the capture, their paths listed here.
- [ ] The Owner's choice recorded, and the build tickets filed.
