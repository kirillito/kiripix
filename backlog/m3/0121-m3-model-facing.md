---
status: done
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0104-m3-render-stage.md]
---

# M3: which way the Model faces

Spec §6.3 (model, render). Found in [0104](0104-m3-render-stage.md). The `render` Stage assumes the Model faces -Y in
Blender, which the fixtures and Mixamo exports do. A Model that faces +Y, or +X, renders its `s` direction (Q5: `s` faces the
camera) as its back or its side, and every direction after it is shifted. Nothing warns the Owner.

## What to build

- A `facing` parameter on the `model` Stage: `-y` (the default), `+y`, `-x` or `+x`. `normalise_model.py` rotates
  `model_root` so that the Model always faces -Y afterwards. `model.json` records the facing it applied.
- `rig`, `clips` and `render` read the normalised Model, so they need no change. Check that a rigged file from the Mixamo round
  trip (0102) gets the same rotation as the Model it came from.
- The parameter is part of `model`'s inputs, so changing it makes `model` and everything below it stale.
- No automatic detection: guessing a front from a mesh is unreliable. The screen from
  [0122](0122-m3-model-still.md) is how the Owner sees the facing.

## Acceptance criteria

- [x] Real Blender: a copy of the fixture rotated 180°, with `facing = "+y"`, renders the same `s` frames as the original
      with the default (pixel-equal colour pass, or within the GPU/CPU difference ADR 0010 records).
- [x] CLI seam on the fake: changing `facing` makes `model` stale, and `describe character --stage model` lists the parameter.

Budget: 60–120k tokens.
