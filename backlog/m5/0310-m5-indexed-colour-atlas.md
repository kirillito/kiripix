---
status: todo
milestone: M5
agent: character-pipeline
type: ticket
parent: 0307-m5-sprite-atlas-size-trial.md
---

# M5: the colour atlas as an indexed PNG

From the trial [0307](0307-m5-sprite-atlas-size-trial.md) (the Owner, 2026-11-18: build lever E). An indexed PNG is the disk
lever: -59 to -61 % alone on the four mc03 bodies. VRAM doesn't change (Godot imports a lossless PNG as RGBA8).

## What to build

- `sheet` writes `color.png` as an 8-bit indexed PNG with transparency (index 0 transparent) when the frames hold at most 256
  colours, which a palette-mapped character always does; otherwise RGBA, with an info finding naming the count.
- The normal and depth atlases stay as they are (not palette images).
- A Wearable's colour atlas the same. Stage `version` bump.

## Acceptance criteria

- [ ] CLI seam: a fixture's `color.png` is mode `P`, decodes to exactly the RGBA it replaces, and is smaller on disk.
- [ ] Real-Godot test (skipped without Godot): the exported scene imports and draws the indexed atlas unchanged.
- [ ] `uv run lint-imports` and `uv run mypy` pass.
