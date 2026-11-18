---
status: done
milestone: M5
agent: core-engineer
type: ticket
parent: 0240-m5-portrait-kind.md
depends_on: [0241-m5-portrait-trial.md]
---

# M5: the `portrait` Kind, its emotions, and `import --emotion`

Part of [0240](0240-m5-portrait-kind.md): the Kind, `brief` and `source` with its emotions. The Stages after `source` are
[0243](0243-m5-portrait-recipe.md).

## What to build

- **The Kind:** `kiripix new portrait <name>` and `describe portrait`. The recipe's Stages are declared, and those after
  `source` are stubs until 0243. `new --help` lists the Kind (the M4 gate found `sprite` missing there, 0250).
- **`[portrait]` in `kiripix.toml`:** `canvas` (w, h) and the default `anchor`. Bump `schema_version`, with its migration.
- **`brief`:** the canvas and anchor (the Project's unless set), the `fallback` emotion (default `neutral`).
- **`source`:** the neutral Source is a Pick, as a Prop's is. An `emotion` Decision declares an emotion ID. `import <id> <png>
  --emotion <e>` stores a Variant under `src/emotions/<e>/`, and `pick <id> <v> --emotion <e>` picks it, recording the
  neutral Source's hash. A new neutral Source puts every emotion's pick in needs-input, with "the edit was made on another
  Source", as Looks do. `remove` and `rename` an emotion before export; after export the ID is frozen (ADR 0003).
- **Owner input:** picking an emotion's Variant among several is the Owner's, as a Pick is. An agent may pick a lone Variant.
- Findings: `portrait.emotion_unknown`, `portrait.emotion_unpicked` (needs-input, naming the emotion),
  `portrait.emotion_duplicate`.

## Acceptance criteria

- [x] CLI seam: a portrait with a neutral Source and two emotions, each imported and picked, shows them in `show`. A new
      neutral Source makes both needs-input.
- [x] `import --emotion` on an undeclared emotion fails with a fix that declares it.
- [x] Contract samples for the new Decision and the import flag. The glossary gets **Portrait** and **Emotion**, and spec §3
      moves `portrait` out of "later".

## Result

- **The Kind:** `kiripix/recipes/portrait.py`, registered in `recipes/__init__.py`. `new --help` and `describe portrait` list it
  (both read the registry). Stages: `brief`, `source` (built), then `cutout`, `register`, `fit`, `palette`, `finish`, `export`
  declared without a run function, so they are needs-input until 0243 and 0244 fill them. Their `version` is 1 and they have no
  parameters yet, so 0243 declares them without a rebuild or a bump.
- **`[portrait]` in `kiripix.toml`:** `canvas` (default 160 x 224, at least 16) and `anchor` (optional; unset is the bottom centre,
  `(width // 2, height - 1)`; it must lie on the canvas). **`PROJECT_SCHEMA_VERSION` is 9**, with the pure migration
  `_add_portrait_section` (8 to 9) in `kiripix/core/settings.py`; the init template has the section. The tests that assert the
  version string were moved to 9 (`test_character_import`, `test_character_generator`, `test_clip_table`, `test_ramp_table`,
  `test_icon`, `test_settings_comments`).
- **`brief`:** `width`, `height` (0 takes the Project's canvas), `anchor_x`, `anchor_y` (-1 takes the Project's anchor, else the
  bottom centre) and `fallback` (default `neutral`); `brief.json` is `width`, `height`, `anchor`, `fallback`. Checks:
  `brief.larger_than_resolution`, `brief.anchor_outside`, `brief.fallback_invalid`, each with a `fix`.
- **`source`:** the neutral Source is the Pick, ID `neutral`. Decisions `emotion` (`id`), `emotion_remove`, `emotion_rename` and
  `emotion_pick` (`emotion`, `variant`, `source`), replayed by `apply_edits` as a Prop's state edits are (a rename keeps the
  Variants' folder). `import <id> <png> --emotion <e>` stores `src/emotions/<folder>/<hash>.png` (core: `kiripix/core/emotions.py`);
  `pick <id> <v> --emotion <e>` records the neutral Source's hash. A new neutral Source puts every emotion's Pick in needs-input
  with "the edit was made on another Source", naming the emotions. A lone Variant gives a `fix` (an agent may pick it); several
  give an `owner_action`. `source` builds `source.png`, `emotions/<id>.png` and `emotions.json` (`schema_version` 1).
- **Findings:** `portrait.emotion_unknown` (a `fix` that declares the emotion, for an import or a pick), `portrait.emotion_unpicked`
  (needs-input, naming the emotion), `portrait.emotion_duplicate` (a repeated ID, or `neutral`), and `portrait.fallback_unknown`
  (the brief's fallback names no emotion; added here, a source Check). Refusals of the options: `import.emotion_needs_portrait`,
  `import.emotion_takes_one_image`, `import.emotion_takes_images`, `pick.emotion_alone`, `pick.emotion_needs_source`.
- **`decide` and `redo`** refuse a duplicate, an unknown emotion or a rename onto `neutral` before recording
  (`core.emotions.emotion_edit_findings`, called from `commands/decisions.py`).
- **`show`** gains `emotions`: each with its Variants, `picked`, `made_on` and `current`.
- **Glossary:** Portrait and Emotion. **Spec:** §3 moves `portrait` out of "later", a new §6.7, `[portrait]` in the example.
- **Not done, for 0244:** the ID freeze after export. It needs the Manifest (`ExportedIds`, `EXPORTERS` in `kiripix/export/`, owned
  by the export work), and a portrait has no exporter yet, so `emotion_remove` and `emotion_rename` are refused only for the
  reasons above. 0244 adds `emotions` to the Manifest's IDs and calls it from `emotion_edit_findings`' place, as
  `state_edit_findings` does for states.
- Tests: `tests/cli/test_portrait.py` (15), a sample in `tests/cli/test_contract.py`.
