---
status: done
milestone: M6
agent: godot-export
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0362-m6-sprite-effect-parameters.md]
---

# M6: export an effect's blend, light mode and anchor

Spec §9 and §6.4. From the trial [0347](0347-m6-vfx-trial.md), gap 5: an effect's exported scene is a bare `AnimatedSprite2D`,
and nothing tells the game its blend or whether the room's lights touch it.

## What to do

- A sprite parameter `blend` (`mix`, the default, or `add`) and `lit` (default true; false is unshaded). `character.json`
  carries them with the `anchor`; its `schema_version` bumps with a migration (a data file's format change needs one).
- The scene writes a shared `CanvasItemMaterial` with the `blend_mode` and `light_mode` (unshaded as the rooms' Loops are),
  and the `offset` from the anchor.
- The Manifest freezes the effect's clip IDs as for any sprite.
- Tell the game what to expect, in the Result: the files, the blend, `light_mode`, the pivot, that a cone is exported facing east
  (the game turns it by 90 degrees, or we export `s w n e`), and that a one-shot ends on its last frame and the game frees the
  node on `animation_finished` (0347's list, section 7).

## Acceptance criteria

- [x] An `add`, unshaded spark and a `mix`, lit puff export scenes whose materials match; a Godot test (`godot` mark) loads them.
- [x] A sprite without these parameters exports exactly as before.
- [x] A CLI-seam test checks `character.json` and the migration of an old file.

## Result

Done 2026-11-21. Spec §9 (Sprite row) and §6.4 ("Blend and light") say it. The Godot test is written and was skipped here (no Godot 4.7
on this machine); it loads both scenes headlessly and checks the spark's material and the puff's lack of one.

- **Where the parameters live:** the sprite's `export` Stage: `blend` (choice `mix`|`add`, default `mix`) and `lit` (bool, default true).
  At their defaults they are out of the hash, so no Stage is stale. **Stage version bumps: none** (the file and scene of a sprite at the
  defaults are byte for byte as before; a test sets them to the defaults and finds `export` still done and every file the same).
- **`character.json` schema 8:** `blend` and `lit` are written, and `schema_version` is 8, only when either is not its default; every
  other file stays version 7 byte for byte (as `points` did for version 5). The migration 7 -> 8 is `_add_blend_and_lit` in
  `kiripix/core/settings.py` (`CHARACTER_MIGRATIONS`): `blend` `mix`, `lit` true, which is how those files were drawn. The reader takes 4 to 8.
- **The scene:** a sprite with `blend=add` or `lit=false` gets a `CanvasItemMaterial` sub-resource `effect_material`
  (`blend_mode = 1` for add, `light_mode = 1` for unlit; only the properties that differ from Godot's defaults) and `material =
  SubResource("effect_material")` on `Sprite`. A `mix`, lit sprite has no material at all (Godot's own defaults, so the puff "matches"
  by having none). The offset is, as before, the pivot, which 0362 made the effect's anchor.
- **Manifest:** the clip IDs (`<clip>_<dir>`) are frozen as for any sprite; no ID is added.
- **Not done, left for the Owner's call:** `frames.tres` still gives every frame `"duration": 1.0`; the clip's `ticks` are in
  `character.json` only (not in this ticket's list).
- Tests: `tests/cli/test_export_effect_blend.py`.

### For the game (0347's list, section 7)

- **Files** (as a sprite today): `sprite/<name>/<name>.tscn`, `frames.tres`, `texture.tres`, `color.png`, `character.json`; no
  `normal.png` for an effect (`fit effect=true`).
- **Blend:** `add` for the spark, cone and glow, `mix` for the puff and telegraph; the scene's `effect_material` sets it, and
  `character.json`'s `blend` says it for another reader.
- **`light_mode`:** unshaded (`light_mode = 1`, as a room's Loops are) when `lit` is false, for glows; a lit puff has no material.
  A file with no `blend` or `lit` key is `mix` and lit.
- **Pivot:** `character.json`'s `pivot` (and each clip's) is the effect's anchor from the cell's top left, and the scene's offset puts
  that pixel on the root, so place the node where the effect happens (the centre for spark and telegraph, the caster end for a cone).
- **Direction:** a cone is exported facing east as drawn; the game turns it by 90 degrees (whole pixels), or the sprite is given
  `directions=4` as `s w n e`.
- **One-shot:** a clip with `loop` false ends on its last frame (which may be blank); the game frees the node on `animation_finished`.

Follow-up in the same batch: the test harness didn't find the Owner's Godot, which is on PATH under its release name
(`Godot_v4.7.2-stable_win64_console.exe`). `find_godot` in `tests/conftest.py` now also takes the newest `Godot_v4.7*` executable in
a folder on PATH (the console build first), so the `godot`-marked tests run here. `frames.tres` now uses a clip's `ticks`: ticket
[0370](0370-m6-export-clip-ticks.md).
