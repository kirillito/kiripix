---
status: todo
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0104-m3-render-stage.md]
---

# M3: toon shading in the render

Spec §6.3 (render: "toon shading") and §1 (a Sea of Stars-like look). Story 8 of [0097](0097-m3-characters.md).

## What to build

- A toon material applied at render time over the Model's own colours: its base colour kept, light quantised to a few bands,
  with a key light fixed to the camera preset, so every character in the Project is lit the same.
- Parameters on `render`, shown by `describe`: `bands` (2–4), `shadow` strength, and the light's angle if the Owner wants it
  per Project rather than per preset.
- Textured Models keep their texture with nearest sampling.
- The colour pass changes; the normal, depth and mask passes don't.

## Acceptance criteria

- [x] CLI seam, on the fake: changing `bands` makes `render` stale and leaves the normal pass's hash alone, if the ADR lets
      a render rebuild.
- [x] Marked `blender` test: the fixture's colour pass has no more distinct colours per part than `bands`.
- [ ] Sample sheets of a real Model at 2, 3 and 4 bands, their paths listed here for the Owner.

## How it was built

- Toon method: the script steps the light itself. `shade()` in `kiripix/blender/render_frames.py` takes the Diffuse Color pass and
  the camera-space normal, computes half-Lambert `n . l * 0.5 + 0.5` against a key light fixed in camera space, cuts it into
  `bands` steps, and darkens each step down by an equal share of `shadow`; the brightest band is the Model's own colour. Why not a
  material: Shader to RGB is EEVEE-only, and `render` is Cycles so that `--cpu` works. A ramp in the material would need Cycles
  shading and a light vector that follows the camera orbit, while numpy on primary-ray values gives the same bytes on CPU and GPU,
  with no noise and no new Blender state. Textures keep their Closest sampling (the albedo already contains them); the normal,
  depth and mask passes are untouched.
- Light: fixed to the camera, so it sits at the same place on screen for every direction, frame and character. It is per camera
  preset (the conservative reading: the ticket says fixed to the preset): `[character.camera.<name>]` `light_angle` (degrees round
  the view axis from the screen top, default -45 = upper left) and `light_tilt` (toward the camera, default 35). Params on `render`:
  `bands` (2-4, default 3), `shadow` (0-1, default 0.5). All are inputs, so a change makes `render` stale. ADR 0010 lets render
  rebuild, so the normal pass has no hash of its own; the real-Blender test checks it is byte-equal across settings instead.
- Samples (4x nearest; rows: flat 0104 colour, then 2, 3 and 4 bands; real Blender 5.2.3, CPU, height 52, the fixture walk):
  `C:\Users\KIRILL~1.BRE\AppData\Local\Temp\claude\2a77692328d6afa9\3e81c363-7270-468b-8ddf-d2b52ef0293a\scratchpad\toon\compare_4x_all_dirs_frame0.png`
  and `...\scratchpad\toon\compare_4x_s_sw_e_n_frames0-1.png`.

Left open: the third criterion (sample sheets at 2, 3 and 4 bands) needs the Owner's eye; the sheets above are the fixture only,
not a real textured Model.

Owner's view of the fixture sheets (2026-11-09): all three are fine, 4 bands maybe the best; hard to judge on the blocky
fixture. The default stays 3 until the real character (the one prepared for 0106) is rendered at 2, 3 and 4 bands; that
render closes the third criterion and settles the default, with `light_tilt` checked at the same time (on the fixture the
front of the figure sat in the middle tone). The scratchpad paths above are temporary.
