---
status: done
milestone: M5
agent: core-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: a `clip` Decision's `attach`: the thing a clip holds, at a socket

Part of the held-things build chosen in [0238](0238-m5-held-things-trial.md) (the Owner, 2026-11-18): option (a), the thing
attached in the character's render for the clips that hold it, at a `grip_r` socket bone, with a cell per clip and a ramp row for a
class weapon. The trial's prototype (`backlog/m5/0238-trial/`, `held_render.py`, `grip_config.json`) is the reference.

## What to build

- **`attach` on a `clip` Decision:** a list of held things, each `thing` (a held thing's ID, 0301), `socket` (a bone of the Model,
  default `grip_r`) and an optional `offset` (x, y, z in the socket's frame, Model units) and `turn` (degrees about each axis). A clip
  without `attach` holds nothing; a `transition` holds what its `from` clip holds.
- Validation: the thing exists on the Asset, the socket is a bone of the rigged Model (`clips.unknown_socket`, with a `fix` naming the
  `rig` bones), no thing twice in one clip. `describe` and `schema` show the field.
- `clips` Stage `version` bump; the clip table (`[[character.clips]]`, 0239) doesn't carry `attach` (a class's weapon differs by body).

## Acceptance criteria

- [x] CLI seam on the test Kind or a fixture character: a clip with `attach` is recorded and listed by `show`; an unknown thing or
      socket is refused with its finding; a transition inherits its `from` clip's things.
- [x] Contract samples updated; `uv run lint-imports` and `uv run mypy` pass.

## Result

- `attach` on a `clip` Decision (`kiripix/recipes/clips.py`): a list of `{thing, socket (default grip_r), offset [x, y, z], turn [x, y, z]}`; `describe` shows it
  in the Decision's schema. A thing twice in one clip is refused by the Decision's problem hook (`decision.invalid`, "more than once").
- `clips.json` gives a clip with `attach` an `attach` list (socket filled in; `offset` and `turn` only when given); a clip without it has no key.
  A `transition` gets its `from` clip's `attach`. `schema_version` stays 3 (an optional key). The `clips` Stage `version` is **2** (was 1), so
  `clips` and everything after it is stale on every character. The clip table (`[[character.clips]]`) is unchanged.
- Refusals, with the same codes at two places: `decide` (`kiripix/core/held.py`, `attach_edit_findings`, in the `decide`/`redo` edit checks) and the Stage's
  run (`_check_attach`, exit 3), which catches a thing taken away or a rig changed later. `clips.unknown_thing` (`owner_action`: import it with
  `--role thing --thing <id>`); `clips.unknown_socket` (the message lists the rig's bones; `fix`: `describe character --stage clips` at `decide`, `undo` in the
  run). At `decide` the socket is only checked once `rig` is built (it reads `work/rig/rig.json`, `parents`); the Stage checks it always.
  `clips.thing_twice` is the Stage's code for the same fault.
- Tests: `tests/cli/test_clip_attach.py` (on the fake Blender; the fake rig has no `grip_r`, so most tests name a fake bone as `socket`).

### What 0301 must provide

- **Layout:** a held thing `<id>` is a folder `src/things/<id>/` of the Asset with at least one file in it (`<id>` is lower-case `[a-z0-9_]+`). That is
  all 0300 reads: `kiripix/core/held.py` `asset_things(asset)` (at `decide`) and `recipes.clips.thing_ids(run.files)` (in the Stage), which sees the files
  through the Stage input `THINGS_PATTERN` (`src/things/*/*`, files one level under the folder; so a nested file is not seen: store the thing's files directly
  in `src/things/<id>/`, or widen the pattern). The tests lay a thing out as `src/things/<id>/model.glb`.
- **Reuse:** `recipes.clips.THINGS_DIR` and `THINGS_PATTERN`, `held.asset_things`. The `clips` Stage hashes the thing's files (so adding, removing or changing
  a thing makes `clips` stale; 0302's `render` should take the thing's files as its own input). A thing of a base is not looked at: only the character's own.
- **Left to 0301:** the `import --role thing --thing <id>` Command itself (the role, the ID check, the stored name, `import.role_needs_character`), and a
  message on `kiripix clips copy`: it copies a `clip` Decision whole, so a copied `attach` fails `clips.unknown_thing` at the next run until the thing is imported
  on the target too.
- `grip_r` is the default socket and does not exist in the Models yet (the Owner's `chargen` change); until then a clip names another bone as `socket`.
