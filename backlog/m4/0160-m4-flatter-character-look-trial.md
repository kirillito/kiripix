---
status: todo
milestone: M4
agent: character-pipeline
type: trial
parent: 0161-m4-characters-after-the-m3-gate.md
depends_on: [0148-m4-render-material-pass.md]
---

# M4: trial: a flatter, more 2D look for characters

Spec §1 (a Sea of Stars-like look) and §6.3 (render, palette, finish). Found at the M3 gate
([0117](../m3/0117-m3-gate.md)), 2026-11-11: "Lighting on character looks amazing, however the result looks too different
compared to scenes background: character is pixelated, but at the same time it looks too 3D-like." The Owner asked for more
optional shading styles, such as cel or toon, to give characters a unified 2D look.

## What may make it look 3D

Before building a shader, find which of these the eye reads as "3D", on mc02 beside a painted ch01_dungeon room in Godot:

- **The texture's own gradients.** mc02's albedo is textured, so `render` has 60 to 80 colours per frame before `palette`
  ([0105](../m3/0105-m3-toon-shading.md)). Painted sprites use a few flat colours per part.
- **Smooth light across a part.** Three bands of half-Lambert follow the surface's curve, which reads as volume.
- **The normal map in Godot.** A `PointLight2D` over the normal map lights the character per pixel, as a 3D surface. The
  rooms are never re-lit (the game's lighting option A).
- **No inner lines.** Hand-drawn sprites outline parts against each other (hair, face, sleeves); the silhouette alone
  ([0106](../m3/0106-m3-outline-method-trial.md)) leaves the inside soft.

## What to try

Each as an option on the existing Stages, rendered on mc02 in all 8 directions, idle and walk:

1. **Flat parts:** each material's albedo replaced by its mean (or its dominant colour), then the toon bands. Needs the
   material pass of [0148](0148-m4-render-material-pass.md).
2. **Two bands with a hard terminator** and no rim, as cel shading: `bands=2`, the shadow's edge moved toward the light.
3. **Part ramps:** each part mapped to its own 2- or 3-colour ramp ([0147](0147-m4-character-palette-ramps.md)), so a part
   never shows more than its ramp.
4. **Inner lines at part borders:** a line where the material changes (not where depth jumps), in a darker colour of the part
   or the outline colour.
5. **A weaker normal map:** the normal pass flattened toward the camera (a `normal_strength` on `finish`), so 2D lights tint
   the character more than they shape it.

## What to record, in this ticket

- Sheets of each option and combinations, on mc02 next to a ch01_dungeon room at 1x and 4x, and a Godot capture under a
  `PointLight2D`.
- The Owner's choice: which options become parameters, and their defaults. A follow-up ticket for each one to build.

## Acceptance criteria

- [ ] The sheets and captures above, their paths listed here.
- [ ] The Owner's choice recorded, and the build tickets filed.
