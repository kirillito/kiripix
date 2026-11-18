---
status: done
milestone: M5
agent: core-engineer
type: ticket
parent: 0152-m5-character-layers.md
---

# M5: the `wearable` Kind: an Asset that names its body

Part of [0152](0152-m5-character-layers.md). From the trial [0153](0153-m5-character-layer-trial.md)'s Results and the Owner's answers (2026-11-18).

## What to build

- **The Kind:** `kiripix new wearable <name> --body <character or sprite asset>`; `body` in its `asset.toml`. `describe wearable`
  lists its Recipe: `model -> rig -> render -> palette -> finish -> sheet -> export` (no `clips`: the body's are used,
  referenced, not copied). Stages after `model` are stubs until 0291-0293.
- **In step with the body:** `render`'s input hash includes the body's `model`, `rig`, `clips` and cell, so any change to them
  makes every Wearable of that body stale, through the existing Stage graph and no new mechanism. `status` names the body as the
  reason.
- **One cell for the stack:** the body's cell and pivot are the Wearable's. A Wearable whose frames don't fit the body's cell is a
  finding, `wearable.outside_cell` (error, naming the frames), whose fix is the body's cell margin (built as `cell_margin`, a `render` parameter, since `render` fixes the cell; in the
  trial the hair moved the pivot 1 px). Agreed by the Owner, 2026-11-18.
- `body` pointing at a missing Asset, or at another Wearable, is `wearable.body_unknown`. Removing or renaming a body with Wearables is
  refused, naming them.
- `new --help` lists the Kind. **The word is Wearable** (the Owner, 2026-11-18): the glossary's Layer is a room's image
  plane, with a `layers` Stage and `layers.*` findings. The glossary has the entry; the game's docs say "layer".

## Acceptance criteria

- [x] CLI seam (the fake Blender): a Wearable on a character; a change to the character's clips makes the Wearable's `render` stale,
      naming the body.
- [x] `wearable.body_unknown` with a test; a contract sample for `new wearable`.
- [x] ~~The refused removal of a body with Wearables~~: dropped (2026-11-18). The ticket assumed a remove or rename Command; none exists for any Asset. `wearables_of` is ready for whichever ticket adds one.
- [x] `uv run lint-imports` and `uv run mypy` pass.

## Result

- **The Kind** `wearable` (`kiripix/recipes/wearable.py`, registered): `kiripix new wearable <name> --body <character|sprite id>`
  (`NewInput.body`; `body` is a required Kind parameter, so a missing one is `asset.param_required`). Recipe `model, rig, render,
  palette, finish, sheet, export`, no `clips`. `model` is the character's Stage (a Wearable takes a Model: `takes_models` now
  holds for a Kind with a body; `--role clip-source` is refused, `import.wearable_uses_body_clips`). The rest are stubs
  (needs-input, "not implemented until M5") for 0291 to 0293. No Stage `version` changed.
- **In step with the body:** `StageInputs.body` (`BodyInputs.built`, by the body's Kind) on `render`: a character body counts the
  input hashes of its `model`, `rig`, `clips` and `render` (whose hash fixes the cell and pivot); a sprite body its `frames` and
  `fit`. Core folds them into the hash (`AssetGraph.body_hashes`, `_outside_inputs`; nothing for a Stage without it, so no other
  hash moved). The stamp records them (`body`), so `status` says `its body character.zed (clips) changed since the output was
  built`. A change to the body's `palette`, `finish` or `sheet` leaves the Wearable alone. 0291 should add a wait for the body's
  built Stages if its `render` reads the body's files.
- **Findings:** `wearable.body_unknown` (missing, not an Asset ID, another Wearable, or not a character or sprite), at `new` and
  when a Wearable whose body was deleted or renamed by hand is loaded (owner_action). `wearable.outside_cell` is declared on
  `render` (CheckSpec) and documented; it fires when 0291 builds the render.
- **Removal and rename:** there is no Command that removes or renames an Asset yet, so nothing to refuse today.
  `kiripix.core.assets.wearables_of(project, body_id)` lists a body's Wearables for whatever adds one to refuse by.
- `asset.toml` is unchanged in format (`body` is an Asset parameter), so no `schema_version` bump or migration.
- Spec §3 and §6.3 (a note); the glossary already had the entry.
- **Tests:** `tests/cli/test_wearable.py` (on the test Kind `demo_wearable` in `tests/fixtures/kiripix_test_recipes.py`, which has
  the real `body` and `render` input with a `render` that runs, because the real one is a stub), and a sample in `test_contract.py`.
