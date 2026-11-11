---
status: done
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0101-m3-blender-launcher-and-model-stage.md]
---

# M3: `model` measures meshes that aren't part of the character

Spec §6.3 (model). Found in [0104](0104-m3-render-stage.md): the fixture `rigged.glb` carries a stray `Icosphere` mesh, a
bone's custom shape that the glTF exporter wrote out as a mesh. The `model` Stage counts it, so the Model comes out 2.7 times
too tall. The render tests use `rigged.fbx` to get round it. An artist's `.glb` can carry the same kind of mesh, so the fix
belongs in the Stage, not only in the fixture.

## What to build

- In a rigged Model, `normalise_model.py` measures height and bounds only from meshes skinned to the armature (an Armature
  modifier or a parent of type armature). A mesh that isn't skinned is left out of the measurement and reported in
  `model.json` (`ignored`: its name and its vertex count).
- When a mesh is left out, the Stage gives the warning `model.unskinned_mesh`. It names the mesh, and its `owner_action` says
  to remove the mesh from the file or to re-import it skinned.
- A Model with no armature is measured from all its meshes, as now.
- Regenerate `rigged.glb` in `tests/fixtures/characters/` without the stray mesh, with the generator 0100 left. Keep a
  copy that still has the stray mesh as its own fixture, for the warning's test.

- **The Blender version, not its path, in the hash** (Owner's decision, 2026-11-09; settles 0101's open question). `model`,
  `rig` and `clips` call Blender too, so like `render` (0104, ADR 0010) they hash the virtual setting `blender.version`.
  None of the four hashes the `[character] blender` path: moving the same Blender must not make anything stale. `launch`
  still needs the path, so give it to `launch` some way other than the Stage's hashed inputs. Record this in ADR 0010.

## Acceptance criteria

- [x] Real Blender: the regenerated `rigged.glb` and `rigged.fbx` normalise to the same height within 1%.
- [x] Real Blender: the fixture with the stray mesh normalises to the same height, and gives `model.unskinned_mesh`.
- [x] The render tests from 0104 that use `rigged.fbx` also pass on `rigged.glb`.
- [x] CLI seam on the fake: changing `[character] blender` to another path with the same version leaves `model`, `rig`,
      `clips` and `render` done. A different version makes all four stale.

## Follow-up (Owner's decision, 2026-11-09)

- An unskinned mesh in a rigged Model is **deleted from the scene** before `model.blend` is saved, not only left out of the
  measurement, so `render` never draws it. It stays in `model.json` `ignored`, and the `model.unskinned_mesh` warning
  stays, saying the mesh was dropped.
- `validate_rig.py` counts vertices (and measures size) with the same rule: skinned meshes only, and never a pose bone's
  `custom_shape`. A rigged file with a stray mesh then still matches its Model.

- [x] Real Blender: `rigged_stray.glb`'s `model.blend` has no stray mesh, and its render matches `rigged.glb`'s.
- [x] Real Blender: a rigged file with a stray mesh validates against the clean Model without `rig.model_mismatch`.

Budget: 80–150k tokens.
