---
status: done
milestone: M4
agent: character-pipeline
type: ticket
parent: 0161-m4-characters-after-the-m3-gate.md
---

# M4: `render`'s rest-pose measure counts meshes that don't render

Spec §6.3 (render). Found in [0155](../m3/0155-m3-attack-overflows-the-cell.md), 2026-11-11.

## The gap

`measure()` in `kiripix/blender/render_frames.py` takes the bounds of **every** mesh in the file's rest pose. Two things use
it:

- `normalise()` scales a rigged file to the Model's height and puts its feet at z = 0. It does this for a rigged file brought
  back from the round trip that has no `model_root`, such as a `.glb`.
- `set_up_scene()` takes the radius, which sets `depth_range`.

The glTF importer puts objects it doesn't want, such as a bone shape's `Icosphere`, in an excluded collection
(`glTF_not_exported`). That object never renders, but `measure()` counts it. On the `rigged.glb` fixture it is 2.0 units tall
where the body is 1.7, so the body would be scaled about 15 % too small and its feet put at the wrong height. The 0155 measure
pass skips it (`rendered_collections()`); this one doesn't. The `rigged.glb` render test passes only because its checks are
loose (the pivot within 2 px). Mixamo's `.fbx` files have no such object, so mc02 isn't affected.

0120 made the `model` Stage leave out meshes that aren't skinned; check whether this file reaches `render` through a path
0120 doesn't cover (the rigged file isn't the Model's `model.blend`).

## What to build

- `measure()` counts only meshes that render, with the same rule as the measure pass (`rendered_collections()`, not
  `hide_render`), and both share it.
- The `rigged.glb` render test checks the character's height in px against `height`, within 1 px, so a wrong scale fails.

## Acceptance criteria

- [x] Marked `blender` test: the `rigged.glb` fixture renders at the target height (within 1 px) and with its feet on the pivot
      row.
- [x] The `.fbx` fixtures render byte for byte as before.
