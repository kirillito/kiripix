---
status: done
milestone: M5
agent: character-pipeline
type: ticket
parent: 0236-m5-the-games-next-needs.md
depends_on: [0300-m5-clip-attach.md]
---

# M5: import a held thing: its mesh and its materials

Part of the held-things build chosen in [0238](0238-m5-held-things-trial.md) (the Owner, 2026-11-18): option (a), the thing
attached in the character's render for the clips that hold it, at a `grip_r` socket bone, with a cell per clip and a ramp row for a
class weapon. The trial's prototype (`backlog/m5/0238-trial/`, `held_render.py`, `grip_config.json`) is the reference.

## What to build

- **`import --role thing --thing <id>`:** a mesh file (`.glb`, or a `.blend` object) stored per Asset under `src/things/<id>/`, its
  materials listed. A thing's origin and axes are its grip: the trial set them per thing in `grip_config.json`; the import keeps the file's
  own, and the clip's `offset` and `turn` adjust them.
- The thing's materials are numbered after the Model's (the Model's 1 to N stay put; 0170, 0238: the phone, screen and stick were 13 to 15),
  in a stable order per thing, so a material pass keeps its meaning when a thing is added.
- `show` lists the Asset's things and their materials.

## Acceptance criteria

- [x] CLI seam: a thing is imported, listed with its materials, and re-imported under its ID as a new Variant; a thing a clip
      attaches can't be removed while attached.
- [x] `uv run lint-imports` and `uv run mypy` pass.

## Result

- **`import --role thing --thing <id>`** (`kiripix/commands/sources.py`, `kiripix/core/things.py`): a character only (`import.role_needs_character` for
  another Kind); the ID is `[a-z0-9_]+` (`thing.invalid_id`); `--role thing` and `--thing` go together (`import.thing_needs_role`); the file is a `.glb` or
  `.blend` (`import.not_a_thing_model`). The mesh is stored as `src/things/<id>/<hash>.glb|.blend` (files directly in the folder, so 0300's
  `THINGS_PATTERN` `src/things/*/*` is unchanged). The file's origin and axes are kept as the grip. The name it came with goes in `imported.jsonl`.
- **A Variant per import:** importing under the same ID adds a Variant (`thing_variants` in the result lists them); the newest import is the thing's
  **current** Variant (the last `imported.jsonl` line of a file in the folder; the same mesh again adds no file but becomes current). There is no Pick.
- **Materials:** the names the render numbers by (materials the meshes use, sorted). A `.glb`'s are read from its JSON in Python; a `.blend`'s by
  Blender (`kiripix/blender/list_materials.py`, through `launch_for`) at import, stored as `<hash>.materials.json` beside it (not a Variant). If Blender
  can't run, the import still succeeds and the materials are `null`/`materials_known: false` until the render reads them. The `list_materials` script
  has no test on a real Blender here.
- **Numbering:** after the Model's count N, the things in the order they were **first imported** (a folder laid by hand comes after, by ID), each thing's
  own materials sorted by name, so adding a thing never moves an earlier number. `show` gives each material `number` (1-based among the things') and `index`
  (N + number, null while `render` hasn't built: N is `len(work/render/render.json materials)`).
- **`show`** has `things`: `{thing, variants, current, materials: [{name, number, index}], materials_known, attached_by}`.
- **`thing-remove <asset> <thing>`** (new Command, `mcp` hidden): deletes the thing and its Variants; refused while a clip's current `attach` holds it
  (`thing.attached`, `owner_action`), and for a thing the Asset hasn't (`thing.unknown`). Sample in `tests/cli/test_contract.py`, REST body in `tests/cli/test_serve.py`;
  `kiripix/commands/index.py` regenerated.
- **`clips copy`** adds a warning `clips.copy_thing_missing` (with `owner_action`) for each thing a copied clip holds that the target lacks.
- No Stage `version` bump: nothing a Stage writes changed (`clips` already hashes `src/things/*/*`).
- Tests: `tests/cli/test_held_things.py`, the thing shapes in `tests/cli/test_contract.py`.

### What 0302 needs

- Files: `kiripix.core.things.current(asset, id)` is the Variant to render; the Stage reads it from its inputs: add `THINGS_PATTERN` to `render`'s files and take
  the current Variant as the newest `src/things/<id>/*.glb|.blend` line of `imported.jsonl` (a Stage can't import core: read the journal itself, or pass the
  current file through a computed input; fall back to the only file).
- Materials: `things.listed(asset)` (core) gives each thing's `materials` and `first`; the same list is `show`'s `things[].materials`. Number a thing's
  materials from `len(Model materials) + first`. If `render.json`'s `materials` will include the things', `things.model_material_count` must then subtract them.

