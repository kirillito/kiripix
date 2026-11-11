---
status: done
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0098-m3-blender-renders-and-pinning.md, 0099-m3-core-for-characters.md, 0100-m3-character-test-fixtures.md]
---

# M3: run Blender headless, and the `model` Stage

Spec §6.3 (model), §10.4 (the GPU lock), §12 (3D) and §13. Stories 3 and 4 of [0097](0097-m3-characters.md). Follows the ADR
from [0098](0098-m3-blender-renders-and-pinning.md).

## What to build

- **The seam:** one place in `recipes` that runs `blender -b -P kiripix/blender/<script>.py -- <args.json> <result.json>`,
  finds Blender from `[character]` or `PATH`, refuses a version other than 5.2 with a finding, streams progress, and on cancel
  kills the process and leaves nothing written (the Stage's output folder is swapped in whole). A test can replace it with
  a fake through `KIRIPIX_TEST_RECIPES`, as it replaces a Runner; add that fake to `tests/fixtures/kiripix_test_recipes.py`.
- `kiripix/blender/` with its first script. An import-linter contract that nothing in Kiripix imports `kiripix.blender`.
- **The `model` Stage:** imports the picked `.glb`, `.fbx` or `.blend`, applies transforms, sets +Z up and the scale so the
  Model's height is a known size, and writes the normalised Model and a `model.json` (`schema_version`, height, bounds, the
  armature and its bone names, the actions found).
- No Blender, or the wrong version: `failed` with a finding whose `owner_action` says how to install or point to 5.2.

## Acceptance criteria

- [x] CLI seam, on the fake: `run` builds `model`, `next` names `rig`, a cancelled run leaves the Stage `todo`.
- [x] Without Blender, the finding names the setting and the version; exit 1.
- [x] Marked `blender` test: each fixture from [0100](0100-m3-character-test-fixtures.md) normalises to the same height and
      up axis, and `model.json` lists its bones and actions.
- [x] `uv run lint-imports` passes with the new contract.

