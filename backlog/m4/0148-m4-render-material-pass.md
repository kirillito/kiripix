---
status: todo
milestone: M4
agent: character-pipeline
type: ticket
parent: 0147-m4-character-palette-ramps.md
---

# M4: `render` writes a material pass

Spec §6.3 (render). Part of [0147](0147-m4-character-palette-ramps.md).

## What to build

- In `kiripix/blender/render_frames.py`, a material-index pass beside the Object Index one: a primary-ray value, like the other
  passes, so it doesn't depend on the device. Number the Model's materials from 1 in a stable order (by name), 0 for the
  background, and write `material/<clip>/<dir>/<NNN>.png` (gray, 8 bit).
- `render.json` lists the materials by index (`"materials": [{"index": 1, "name": "boots"}, ...]`) and records the toon `bands`,
  so `palette` can size the ramps. Bump its `schema_version` (`RENDER_SCHEMA_VERSION`). Since
  [0154](../m3/0154-m3-stationary-clip-pivot-follows-the-hips.md) the format is an input of `render` (`render.format`), so an older
  render is stale on its own and rebuilds with everything after it; no migration (CLAUDE.md: no production characters).
- More than 255 materials fail the Stage with a finding.
- The colour, normal, depth and mask passes don't change, byte for byte.

## Acceptance criteria

- [ ] CLI seam, on the fake Blender: `render.json` carries `materials` and `bands`, and a `material/` frame per colour frame.
- [ ] Marked `blender` test: on the fixture (two materials, `skin` and `cloth`), every opaque pixel's material index is one of
      the two and every transparent pixel's is 0; the colour pass is byte-equal to before.
- [ ] mc02 renders with its 9 materials listed.
