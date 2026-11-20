---
status: todo
milestone: M6
agent: godot-export
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0341-m6-room-normals-stage.md]
---

# M6: export a room's normal maps as `CanvasTexture`s

Spec §9 (Room) and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Ticket 3 of 0252's outline;
the trial's Godot test project (`backlog/m5/0252-trial/`) is the reference.

## What to build

- For a room whose `normals` Stage has output: `normals/plate.png` and `normals/<layer>.png` beside the scene, and each
  `Sprite2D` (the Plate and every foreground Layer) gets a `CanvasTexture` `.tres` with `diffuse_texture` and
  `normal_texture`, in place of its plain texture. A Look's and a Loop's pieces take the room's normal cut to their box (the
  ADR 0339 rule), as sub-region textures, so a lit Look matches the room.
- `room.json` gains `normals`: `null`, or the files by Plate and Layer. That is a `schema_version` bump. Every file goes in the
  Manifest. A room with `mode=off` exports as before, byte for byte except for `room.json`'s version.
- The export Stage's `version` bumps (it writes a new field), named in the Result.
- Don't run alongside [0345](0345-m6-export-named-masks.md): both bump `room.json`. They take turns.
- A note to the game for its M10-02, in the Result: the light height and energy need tuning to a room, and a normal-mapped
  Plate reads darker under the same light (0252's finding 4).

## Acceptance criteria

- [ ] CLI seam: a test room with normals exports the `CanvasTexture`s, the files and `room.json`'s `normals`, all in the
      Manifest; a room without normals has `normals: null` and the scene unchanged.
- [ ] Headless Godot (as the other export tests): the scene loads, and the Plate's material has a normal texture.
- [ ] Spec §9 updated; `room.json`'s new version named.
