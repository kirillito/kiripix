---
status: todo
milestone: M4
agent: character-pipeline
type: ticket
parent: 0161-m4-characters-after-the-m3-gate.md
---

# M4: `render` gets a cel band edge and smoothed shading

Spec §6.3 (render). Chosen by the Owner in the trial [0160](0160-m4-flatter-character-look-trial.md), 2026-11-13: variant
`24_cel_s_lines_d`. This is its "cel_s" half; the inner lines are [0214](0214-m4-inner-lines-op.md) and
[0215](0215-m4-finish-inner-lines.md).

Today the toon bands cut half-Lambert at equal steps, so with 2 bands the shadow starts where the surface turns from the light
(0.5), and its edge follows every fold. In the trial, a cut at 0.62 on normals smoothed by 1.5 px gave one large shadow shape
per part, which reads as drawn.

## What to build

- Two parameters on the character's `render`, beside `bands` and `shadow`:
  - `band_edge` (float, 0 to 1, default 0.5): where the light band ends, in half-Lambert. Half-Lambert is shifted by
    `0.5 - band_edge` and clipped to 0..1 before it is cut into bands. So with 2 bands the cut is at `band_edge`, and with
    more bands every cut moves by the same amount. 0.5 is the shading as it is now.
  - `band_smooth` (float, px, 0 or more, default 0): the sigma of a Gaussian that blurs the normals before they are lit. The
    blur is inside the silhouette only (a normalised convolution over the mask, so the background does not leak in), and the
    result is scaled back to unit length. 0 is the shading as it is now.
- Both go into `shade` in `kiripix/blender/render_frames.py`. The reference is `shade` and `smooth_normal` in
  `C:\Homespace\urban-mystery-club-art\.kiripix\trials\0160-flat\options.py` (the trial did it on the 8-bit passes; here it is
  on the EXR normals).
- **Only the colour pass uses the smoothed normals.** The normal, depth, mask and material passes do not change, byte for
  byte.
- The `toon` object of `render.json` records `band_edge` and `band_smooth`. Bump `RENDER_SCHEMA_VERSION`; an older render is
  stale on its own and rebuilds (as in [0148](0148-m4-render-material-pass.md)). No migration.
- With both at their defaults the colour pass is byte-equal to what `render` writes now. The Owner accepts that declaring the
  parameters makes every existing character stale once (2026-11-13).

## Out of scope

- Setting the look on the characters of the art Project. The Owner sets `band_edge=0.62 band_smooth=1.5` on the mc03 bodies
  and tunes from there.

## Acceptance criteria

- [ ] CLI seam, on the fake Blender: `kiripix set <character> render band_edge=0.62 band_smooth=1.5` reaches the `toon`
      object of `render.json`, and a value out of range is refused with a finding.
- [ ] Marked `blender` test, on the fixture: with the defaults the colour pass is byte-equal to before; with
      `band_edge=0.62` more opaque pixels are in the shadow band than at 0.5; with `band_smooth=1.5` the normal pass is
      byte-equal to the unsmoothed one.
- [ ] `uv run pytest`, `uv run lint-imports` and `uv run mypy` pass.
