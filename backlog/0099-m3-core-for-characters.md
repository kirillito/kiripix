---
status: todo
milestone: M3
agent: core-engineer
type: ticket
parent: 0097-m3-characters.md
---

# M3: core for characters: Model and animation imports, and character settings

Spec §4, §6.3, §10.5 (`import`) and §16 decision 1. Stories 3 and 6 of [0097](0097-m3-characters.md). Q7 and Q8 of 0097
shape the settings: ask the Owner before building them.

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

## Acceptance criteria

- [ ] CLI seam: a `.glb` imports as a Variant and is picked; its file sits in `src/` by hash; the `model` Stage's input
      hash changes with the pick.
- [ ] An image on a character, and a Model on a room, are refused with exit 1 and a finding with a `fix`.
- [ ] An animation file and a rigged file are added and listed by `show`.
- [ ] An old `kiripix.toml` migrates in memory; `[character]` defaults to `height = 52`.
- [ ] Contract samples for every changed Command pass.
