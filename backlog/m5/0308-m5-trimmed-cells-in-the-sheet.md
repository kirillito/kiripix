---
status: todo
milestone: M5
agent: character-pipeline
type: ticket
parent: 0307-m5-sprite-atlas-size-trial.md
---

# M5: trimmed cells: the sheet packs each frame's opaque box, not its whole cell

From the trial [0307](0307-m5-sprite-atlas-size-trial.md) (the Owner, 2026-11-18: build lever B). Trimming is the VRAM lever:
-77 % alone on the four mc03 bodies, -5 to -10 % on disk. The trial's prototype is in `backlog/m5/0307-trial/` (`measure.py`,
`prep_godot.py`).

## What to build

- `sheet`: each frame cropped to its opaque box (colour, normal, depth and mask alike: one box per frame over every layer),
  packed into the atlas. Each frame records its packed `rect` and its `offset` inside its clip's logical cell (0303's per-clip
  `cell` and `pivot` stay the logical size), so the cell can be restored exactly.
- `sheet.json` and `character.json` carry the per-frame `offset` (a `schema_version` bump with its migration in
  `kiripix/core/settings.py`; an old file's frames have offset 0 and a rect the size of the cell).
- An empty frame (fully transparent) keeps a 1 x 1 rect, so every frame has a region.
- The `sheet` Checks read the logical cell, not the packed rect. Stage `version` bump.
- A Wearable's sheet (it shares the sheet code) trims the same way; a body and its Wearables still line up frame by frame.

## Acceptance criteria

- [ ] CLI seam: a fixture character's atlas area falls, and every frame restored from `rect` + `offset` into its cell is
      byte-identical to the untrimmed frame.
- [ ] An old `character.json` migrates; `uv run lint-imports` and `uv run mypy` pass.
