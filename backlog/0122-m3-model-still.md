---
status: done
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0104-m3-render-stage.md]
---

# M3: a still of the Model

Spec §6.3 (model) and §11. Found in [0114](0114-m3-ui-model-rig-clips-screens.md): the Model screen has no preview, because
nothing makes an image of the Model. The Owner can't see which Variant is which, which way it faces
([0121](0121-m3-model-facing.md)), or whether it came in at the right size, without running everything down to `render`.

## What to build

- The `model` Stage also writes `work/model/still.png`: the normalised Model in its rest pose, from the `s` direction with the
  default camera preset, at a fixed 256 px, flat albedo, no outline. Use the same camera code as `render`. If it can't be shared
  (each Blender script stands alone), copy it and say so in the script.
- The still is a preview, not an input to anything below `model`. It is in `model`'s outputs, so the UI finds it through
  `detail.outputs`.
- The UI shows it in [0125](0125-m3-ui-character-files-and-pickers.md).

## Acceptance criteria

- [x] Real Blender: each of the four fixtures writes a 256 px still with the figure's feet at the same row.
- [x] CLI seam on the fake: `still.png` is listed in `model`'s outputs (the fake writes a placeholder).

## Follow-up (Owner's decisions, 2026-11-09)

- **The still's camera stays fixed** (orthographic, `s`, 30° elevation, hard-coded in `normalise_model.py`). It doesn't read
  the default preset, so no camera setting is a `model` input.
- **The fixtures get a visible front.** The generator in `tests/fixtures/make_character_fixtures.py` adds a nose block, in a
  colour of its own, on the face's -Y side, skinned to the head bone. Regenerate all four fixtures and `rigged_stray.glb` with
  Blender 5.2.3. Then front and back differ in the still and in `render`'s `s` and `n` frames.

- [x] Real Blender: the still of each fixture shows the nose (its colour is present at `-y`, and absent at `+y`, where the
      Model is turned away).
- [x] The `facing` render test (0121) asserts that the `s` frame shows the nose colour and the `n` frame doesn't.
- [x] `tests/cli/test_character_*.py`, marked and unmarked, pass on the regenerated fixtures.

Budget: 40–80k tokens.
