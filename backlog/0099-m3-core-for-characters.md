---
status: done
milestone: M3
agent: core-engineer
type: ticket
parent: 0097-m3-characters.md
---

# M3: core for characters: Model and animation imports, and character settings

Spec §4, §6.3, §10.5 (`import`) and §16 decision 1. Stories 3 and 6 of [0097](0097-m3-characters.md). Q7 and Q8 of 0097
shape the settings; both were answered on 2026-11-08 (below).

`import` takes only PNG and JPEG today (`kiripix/commands/sources.py`), and `kiripix.toml` has no character settings.

## What to build

- `import <id> <file>` on a character takes `.glb`, `.fbx` and `.blend` as Variants, stored by hash under `src/` as an image
  is, and `pick` picks one. An image is refused on a character, and a Model on a room or Prop, with a finding that names the
  right Kind.
- Animation sources for `clips`: a way to add an animation file (a Mixamo `.fbx`) to a character, stored by hash, and named
  by the `source` field of a `clip` Decision. Propose the Command surface (for example `import <id> <fbx> --clip-source`)
  in the ticket before building it.
- The rigged file that comes back from Mixamo: a way to add it, for the `rig` Stage to read. It can share the surface above.
- A `[character]` section in `kiripix.toml`: `height` in target px (default 52), the Blender path (optional; `PATH` otherwise),
  and the camera presets if the Owner wants them per Project (Q7). `ProjectSettings` gains it with a `schema_version` bump and
  a migration in `kiripix/core/settings.py`; unknown keys stay an error.
- `describe character` and `next` say what to import.

## Command surface

Approved by the Owner on 2026-11-08.

- `import <id> <file> --role variant|clip-source|rigged`, default `variant`.
  - `variant`: a room or Prop takes a PNG or JPEG (as before); a character takes a `.glb`, `.fbx` or `.blend`, stored as
    `src/<hash>.<ext>`. `pick` picks it.
  - `clip-source`: a character's animation file, stored as `src/clips/<stem>.<hash>.<ext>`. Its name is the file stem, which a
    `clip` Decision's `source` names. The same name with other content replaces the earlier file.
  - `rigged`: the file that comes back from Mixamo, `src/rigged/<hash>.<ext>`; a new one replaces the old.
- A wrong file is refused with exit 1: `import.image_needs_room_or_prop` and `import.model_needs_character` (each with a `fix`
  that creates an Asset of the right Kind), `import.role_needs_character`, `import.not_a_model`, `import.not_found`.
- `show` lists `variants`, `clip_sources` and `rigged`. `describe character` and `next` say what to import.
- `[character]` in `kiripix.toml` (schema_version 2, migrated in memory from 1): `height` (default 52), `blender` (optional;
  `PATH` otherwise), and `[character.camera.<name>]` presets with `elevation` and `directions`. M3 ships only `top34_8`, at 30
  degrees (Q7). The `render` Stage's `camera` parameter picks one by name.
- Q8: `height` in `[character]` is the Project default. The `render` Stage declares a `height` parameter (unset by default)
  that overrides it; the Stage that reads both (0104) lands later. `render` hashes `[character]`, so a change shows it out of date.
- The `rig` and `clips` Stages will hash `src/rigged/*` and `src/clips/*` when they are built (0101, 0102); the `model` Stage's
  `src/*` does not reach into those folders.

## Acceptance criteria

- [x] CLI seam: a `.glb` imports as a Variant and is picked; its file sits in `src/` by hash; the `model` Stage's input
      hash changes with the pick.
- [x] An image on a character, and a Model on a room, are refused with exit 1 and a finding with a `fix`.
- [x] An animation file and a rigged file are added and listed by `show`.
- [x] An old `kiripix.toml` migrates in memory; `[character]` defaults to `height = 52`.
- [x] Contract samples for every changed Command pass.
