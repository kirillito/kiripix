---
status: done
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0104-m3-render-stage.md]
---

# M3: toon shading in the render

Spec §6.3 (render: "toon shading") and §1 (a Sea of Stars-like look). Story 8 of [0097](0097-m3-characters.md).

Moved to M5 on 2026-11-10 and back to M3 on 2026-11-11, once a real Model existed.

**The real Model (2026-11-11):** `character.mc02` in the art Project (`urban-mystery-club-art`), built by a scripted
Blender session from the Quaternius base (`c:\Homespace\[assets]\mc02\`) and rigged by Mixamo, with `idle`, `walk` and
`attack`. The Owner will still revise it; these choices are about the rendering, not its details, so a revised Model only
needs a look at its new frames.

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
- [x] Sample sheets of a real Model at 2, 3 and 4 bands, their paths listed here for the Owner.

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

## mc02 at 2, 3 and 4 bands (2026-11-11)

The sheets for the third criterion. 3 bands is the art Project's own build of `character.mc02`. 2 and 4 bands were built in
scratch copies of the Project, with only `render bands` changed, through `sheet`, so the art Project is untouched. Everything
else is as built: `top34_8`, light -45 / tilt 35, `shadow` 0.5, `palette colors=16`, the outline at index 0. Real Blender 5.2,
GPU. In `C:\Homespace\urban-mystery-club-art\.kiripix\trials\0105-bands\` (gitignored; `compare.py` remakes them, given the
scratch copies):

- `bands_finish.png`: what ships, after `palette` and the outline. Rows are clip × bands (idle frame 0, walk frame 3, attack
  frame 10), columns the 8 directions, 4x.
- `bands_render.png`: the toon render alone, before `palette`, in the same layout.
- `bands_s_se_8x.png`: `s` and `se`, idle and walk, render and finish side by side at 8x, for the light's tilt.
- `colours.json`: distinct colours per frame, by clip and band count.

| bands | render: colours per frame | after palette: colours per frame |
|---|---|---|
| 2 | 59 to 62 | 14 to 15 |
| 3 | 69 to 72 | 16 |
| 4 | 81 to 82 | 14 to 15 |

What I see, for the Owner to judge:
- **`palette` decides more of the look than `bands` does.** mc02 is textured, so the render has 60 to 80 colours per frame
  whatever the band count. `palette colors=16` then picks 16 colours for the whole character, and most of the bands' steps
  merge. After `palette`, 2 and 4 bands look close. 3 bands is the odd one out: `palette` spends its colours differently and
  maps the front of the shirt, facing `s`, to a dark teal where 2 and 4 keep it brown-grey. To see bands do more, raise
  `palette colors` with them.
- **Light tilt:** at all three counts the front of the figure facing `s` sits in the middle tone, not the lit one. The lit band
  is on the head, the shoulders and the side toward the light (screen upper left). A larger `light_tilt` (toward the camera)
  would light the front more. That needs a render, which I haven't made.
- `render` took 119 s at 4 bands for the 3 clips × 8 directions (137 frames per direction), on the GPU, and 155 s at 2 bands
  while another job shared the machine. The art Project's 3-band build took 76 s. The scratch copies are in a temporary
  session folder, so `compare.py` will need them rebuilt.

**Owner's view of mc02's sheets (2026-11-11):** they look good. The default stays **3 bands**, and `light_tilt` stays **35**
(a per-Project setting in `[character.camera.top34_8]`, so it can be raised later without code). The dark teal shirt front
at 3 bands is a `palette colors=16` effect; M4's palette ramps per part ([0147](../m4/0147-m4-character-palette-ramps.md))
change how a character's colours are picked. Seen at the same time: mc02's 1 px eyes were lost to `palette`'s orphan
cleanup, not the shading; mc02 now builds with `orphan_size=0`, and [0149](../m4/0149-m4-part-ramp-ops.md) keeps such details.
