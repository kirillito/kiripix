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

- [ ] CLI seam, on the fake: changing `bands` makes `render` stale and leaves the normal pass's hash alone, if the ADR lets
      a render rebuild.
- [ ] Marked `blender` test: the fixture's colour pass has no more distinct colours per part than `bands`.
- [ ] Sample sheets of a real Model at 2, 3 and 4 bands, their paths listed here for the Owner.
