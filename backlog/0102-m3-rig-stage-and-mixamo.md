---
status: todo
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0101-m3-blender-launcher-and-model-stage.md]
---

# M3: the `rig` Stage and the Mixamo round trip

Spec §6.3 (rig). Story 5 of [0097](0097-m3-characters.md). Q11 of 0097 (Rigify) decides whether non-humanoids are in this
ticket; until the Owner answers, they get a finding and nothing else.

## What to build

- **Validate:** a humanoid armature with the bones the `clips` and `render` Stages need (hips, spine, head, both arms and
  legs, by Mixamo's names or a mapping). The Stage is `done` when they are there, and writes `rig.json` with the mapping.
- **No rig:** `needs-input`, with an `owner_action` listing the Mixamo steps: the file Kiripix has written for upload (an
  `.fbx` of the normalised Model, under `.kiripix/` or `work/`, its path in the finding), the settings to choose on Mixamo,
  and the exact command that adds the downloaded rigged file ([0099](0099-m3-core-for-characters.md)'s surface).
- **The rigged file comes back:** the Stage validates it, and checks that its mesh matches the Model it was made from (vertex
  count and bounds), so a rig made from another Model is caught.
- Checks with stable codes, such as `rig.missing`, `rig.bone_missing`, `rig.model_mismatch`.

## Acceptance criteria

- [ ] CLI seam, on the fake: a rigged fixture goes `done`; an unrigged one is `needs-input` with exit 3 and the steps in its
      `owner_action`; adding the rigged file makes it `done`.
- [ ] A rigged file made from another Model fails `rig.model_mismatch`.
- [ ] Marked `blender` test on [0100](0100-m3-character-test-fixtures.md)'s two fixtures.
