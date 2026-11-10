---
status: done
milestone: M3
agent: core-engineer
type: ticket
parent: 0097-m3-characters.md
depends_on: [0103-m3-clips-stage.md]
---

# M3: a Probe that reads a character file's actions and bones

Spec §6.3 (rig, clips) and §11. Found in [0114](0114-m3-ui-model-rig-clips-screens.md). Before `clips` runs, nothing lists the
actions in a rigged file or a clip-source file, so the Owner types an action name and its frame range by hand. A wrong range
shows up only as `clips.range` after a run. The "Map a bone" form has the same problem: the only list of a rig's bones is the
first 12 in the `rig.bone_missing` message.

## What to build

- A Probe Command `inspect <asset> <file>` (pick the name that fits the existing Probes in `kiripix/commands/probes.py`).
  `<file>` is a Model Variant, the rigged file or a clip source, by the name `show` gives it. It returns the file's armature,
  its bone names, and its actions with their frame ranges and frame rate. Like every Probe, it records nothing.
- It calls Blender through `kiripix.recipes.blender_launcher` with `kiripix/blender/read_actions.py` (0103). Extend that script
  to return bone names too, rather than writing a second script. `clips` must keep working unchanged.
- The answer is cached by the file's content hash and the Blender version, so a second call doesn't start Blender. Each call
  starts Blender once, which takes several seconds, so it is a Job with progress like other slow Commands. It is cancellable,
  and it takes the GPU lock only if the script needs it (it shouldn't).
- Missing Blender gives the same `blender.not_found` / `blender.wrong_version` findings as the Stages.

## Acceptance criteria

- [x] CLI seam on the fake: a rigged file and a clip source each list their actions and bones. A second call doesn't call
      Blender (the fake counts calls). A Model Variant with no armature lists none.
- [x] Real Blender (`blender` mark): `rigged.fbx` lists the same actions and ranges that `clips.json` resolves for it.
- [x] A sample in `tests/cli/test_contract.py`.

Budget: 80–150k tokens.
