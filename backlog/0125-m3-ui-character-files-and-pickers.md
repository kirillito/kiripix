---
status: todo
milestone: M3
agent: ui-engineer
type: ticket
parent: 0097-m3-characters.md
depends_on: [0122-m3-model-still.md, 0123-m3-read-a-character-file-probe.md, 0124-m3-show-names-and-sizes-character-files.md, 0114-m3-ui-model-rig-clips-screens.md]
---

# M3: the character screens use the still, the file Probe and the original names

Spec §11. Follows [0114](0114-m3-ui-model-rig-clips-screens.md), whose screens work round five gaps. Three tickets close
them; this one uses what they add. Don't run it alongside 0115: both edit `web/src/characterScreens.tsx`.

## What to build

- **Model screen:** each Variant row shows `imported_as` from `show` instead of the hash (the hash stays as a hint). Size
  comes from `show`, and the Range request to the file route is removed. The picked Model shows `work/model/still.png`
  ([0122](0122-m3-model-still.md)).
- **Clips screen:** the source box lists the actions of the rigged file and of each clip source from the Probe in
  [0123](0123-m3-read-a-character-file-probe.md), not only the Model's own actions. Choosing an action fills its range and frame rate.
  The Probe is slow the first time, so the box shows that it is reading the file, and it can be cancelled.
- **Rig screen:** the "Map a bone" form offers the rig's bone names from the same Probe instead of a typed name.

## Acceptance criteria

- [ ] e2e on the fake Blender: a Model imported as `hero_v2.fbx` is listed by that name. Choosing a clip source's action
      fills its range. A bone is picked from a list.
- [ ] `npm run build` passes.

Budget: 60–120k tokens.
