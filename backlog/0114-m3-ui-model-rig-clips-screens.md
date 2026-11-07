---
status: todo
milestone: M3
agent: ui-engineer
type: ticket
parent: 0097-m3-characters.md
depends_on: [0103-m3-clips-stage.md, 0083-m3-ui-show-that-work-is-happening.md, 0093-m3-ui-findings-a-person-can-read.md]
---

# M3: the character's model, rig and clips screens

Spec §11. Stories 3, 5 and 6 of [0097](0097-m3-characters.md). After [0083](0083-m3-ui-show-that-work-is-happening.md) and
[0093](0093-m3-ui-findings-a-person-can-read.md), so these screens show work and findings the new way from the start.

## What to build

- **Model:** the Variants as a list with each file's name, size and the bounds from `model.json`, drag-and-drop import of
  `.glb`, `.fbx` and `.blend`, and number keys to pick. No 3D viewer: a still from the fake or real render is enough, if a
  Command offers one.
- **Rig:** the Stage's state; when it needs the Mixamo round trip, its `owner_action` as numbered steps, the upload file's
  path, and a drop target for the rigged file.
- **Clips:** the current clips as a table (name, source, range, frame rate, loop), a form that records one `clip` Decision,
  drop targets for animation files, and `undo`.
- Panels for parameter-only Stages (`render`, `palette`, `finish`) come from `describe`, as for rooms.
- If a screen needs something no Command offers, stop and report it: that's a backend ticket.

## Acceptance criteria

- [ ] Playwright, on the fake renderer: import and pick a Model; add a rigged file; record two clips and undo one.
- [ ] Every action is one Command, and the screens refresh when an agent changes the Asset.
