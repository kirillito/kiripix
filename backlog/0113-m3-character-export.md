---
status: done
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

- [x] A character exports into a temporary Godot folder; the `.tres` and `.tscn` match golden text files, and a second export
      writes nothing.
- [x] Removing or renaming an exported clip is refused by the freeze; adding one is fine.
- [x] Editing the scene refuses; `--force` backs it up.
- [x] `export --all` exports rooms, Props and characters, and `manifest merge` unions `clips`.
- [x] The Godot check above is recorded here, with the Godot version used.

## Result

**Files.** `export` Stage, in `out/export/`: `color.png`, `normal.png` (copies of `sheet`'s atlases) and `character.json`
(`schema_version` 1, `asset`, `files`, `cell`, `pivot` (from the cell's top left), `atlas`, `directions`, `clips`: the
`sheet.json` clips, each with `name`, `fps`, `loop`, `stationary` and `directions` of `{index, rect}`). The Stage reads only
`sheet`'s `sheet.json` and atlases. `kiripix export` writes, under `<root>/character/<name>/`: `<name>.tscn`, `frames.tres`
(`SpriteFrames`), `texture.tres` (`CanvasTexture`), `color.png`, `normal.png`; and `<root>/manifest/character.<name>.json`.

**Scene.** A `Node2D` root named for the Asset (metadata `kiripix_id`) at the feet, and a child `Sprite`, an
`AnimatedSprite2D` with `centered = false` and `offset = Vector2(-pivot.x, -pivot.y)`; its `animation` is the first one. Same
shape as a Prop's scene; the game finds the sprite by the path `Sprite`. Each `SpriteFrames` animation is `<clip>_<dir>`, a
frame is an `AtlasTexture` over `texture.tres` with duration 1.0, and `speed` is the clip's fps.

**Manifest.** `schema_version` 2: `ids.clips` lists every `<clip>_<dir>`. A version 1 Manifest is migrated on read (clips
empty; the next export rewrites it as 2), not refused, since refusing would lose the freeze it holds. The merge driver
unions `clips`; a newer schema is still named and refused. The freeze takes a character's current clips from its `clip`
Decisions (so `check` fails before anything is rebuilt), as Markers are for rooms.

**Godot check (done).** Godot 4.7.2-stable (official), Windows, 2026-11-10: a scene with the exported `SpriteFrames`
(AtlasTexture over CanvasTexture), a dark `CanvasModulate` and a `PointLight2D` to the right of a flat grey sprite whose
normal map faces the light in frame 0 and away from it in frame 1. Frame 0 reads 0.39 and frame 1 0.09, in both the
Compatibility (OpenGL 3.3) and Forward+ (Vulkan) renderers, so the normal map survives the `AtlasTexture`. No alternative
is needed. The headless load (animations, frame counts, speeds, offset, `canvas.normal_texture`) is the `godot`-marked test
in `tests/cli/test_export_character.py` (`KIRIPIX_GODOT` or `godot` on PATH; skipped without it); lighting needs a window, so
only this manual probe covers it. The Owner still looks at the lit character in [0117](0117-m3-gate.md).
