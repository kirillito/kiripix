---
status: todo
milestone: M3
agent: godot-export
type: ticket
parent: 0097-m3-characters.md
depends_on: [0112-m3-sheet-stage.md, 0096-m3-merge-exported-images.md]
---

# M3: the character's export: `SpriteFrames`, `CanvasTexture` and the scene

Spec §6.3 (export), §9 (Character) and ADR 0003. Story 14 of [0097](0097-m3-characters.md). Q5 of 0097 fixes the animation
names: `<clip>_<dir>`, such as `walk_sw`. After [0096](0096-m3-merge-exported-images.md), which changes the same export code.

## What to build

- The `export` Stage leaves engine-free outputs in `out/export/`: both atlases and `character.json` (`schema_version`,
  `asset`, cell size, pivot, the clips with directions, frames, frame rate and loop).
- Godot 4.7, under `export.godot.root`:
  - a `CanvasTexture` with the colour atlas as diffuse and the normal atlas as its normal map;
  - a `SpriteFrames` `.tres` with one animation per clip and direction, named as the Owner decided, each frame an
    `AtlasTexture` region of that `CanvasTexture`, with the clip's speed and loop flag;
  - a scene: an `AnimatedSprite2D` with its offset set so the feet are at the scene's origin.
  Confirm in Godot 4.7 that an `AtlasTexture` over a `CanvasTexture` keeps the normal map under a `PointLight2D`. If it
  doesn't, stop and report the alternatives (one `CanvasTexture` per frame, or a material) before choosing.
- The Manifest's exported IDs gain `clips` (each exported animation name), frozen like Layers. This bumps the Manifest's
  schema: migrate or refuse an old one, as spec §4 allows through M3, and keep the merge driver's union of IDs working.
- Add `character` to `_FILES_BY_KIND` and `EXPORTERS`. Output is byte-identical across runs.

## Acceptance criteria

- [ ] A character exports into a temporary Godot folder; the `.tres` and `.tscn` match golden text files, and a second export
      writes nothing.
- [ ] Removing or renaming an exported clip is refused by the freeze; adding one is fine.
- [ ] Editing the scene refuses; `--force` backs it up.
- [ ] `export --all` exports rooms, Props and characters, and `manifest merge` unions `clips`.
- [ ] The Godot check above is recorded here, with the Godot version used.
