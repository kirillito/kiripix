---
status: done
milestone: M5
agent: core-engineer
type: ticket
parent: 0240-m5-portrait-kind.md
---

# M5: the portrait canvas defaults to 192 x 240

Found by closing [0241](0241-m5-portrait-trial.md) ("Answers after the redesign"). The game's portrait spec (its 0091 and
DEC-071; [0240](0240-m5-portrait-kind.md), "Input from the game") sets **192 x 240** for the whole cast, anchor bottom centre
(96, 239). Kiripix's `[portrait] canvas` defaults to 160 x 224, the trial's withdrawn answer
([0242](0242-m5-portrait-asset-and-emotions.md)).

## What to build

- `PortraitSettings.canvas` defaults to `(192, 240)` (`kiripix/core/settings.py`), and `kiripix new`'s `kiripix.toml`
  template says `canvas = [192, 240]` and `# anchor = [96, 239]` (`kiripix/core/project.py`). The spec's copy of the
  template (§ the `kiripix.toml` sample) and §6 portrait text say the same.
- **No migration change.** The 8 → 9 migration's 160 x 224 is what version 9 meant, and a migration stays pure and fixed. A
  Project that wrote `canvas = [160, 224]` keeps it; that's the Owner's setting. Say so in the Result, with the one line the
  Owner changes in their game Project's `kiripix.toml` (or do it for them at the gate, as the other owner steps are).
- Check that a changed default reaches `brief`'s input hash (it reads `portrait.canvas`), so a Project relying on the
  default sees its portraits stale. Name that in the Result.
- Update the tests that assume 160 x 224 from the default (`tests/cli/test_portrait.py`, `test_portrait_stages.py`,
  `test_export_portrait.py`): the ones about the default move to 192 x 240; the ones about something else can keep a
  Project canvas of their own.

## Acceptance criteria

- [x] CLI seam: a new Project's portrait `brief` is 192 x 240 with anchor (96, 239).
- [x] CLI seam: a Project with `canvas = [160, 224]` written keeps it.
- [x] `uv run lint-imports` and `uv run mypy` pass.

## Result

Done 2026-11-19 in the main session (the ticket names `core-engineer`; the Owner asked for it in the main session's batch).

- `PortraitSettings.canvas` defaults to `(192, 240)`; `kiripix new`'s template and the spec's copy say `canvas = [192, 240]`
  and `# anchor = [96, 239]`; spec §6.7 says "default 192 x 240, the game's".
- **No migration change.** The 8 → 9 migration writes no canvas (it never did), so a Project without `[portrait] canvas`
  reads today's default; its docstring now says so. A Project that wrote `canvas = [160, 224]` keeps it (new test
  `test_a_project_that_wrote_the_old_canvas_keeps_it`).
- **The Owner's art Project** (`urban-mystery-club-art`) is at `schema_version` 7 with no `[portrait]` section, so it takes
  192 x 240 with no line to change.
- **The input hash:** `brief` hashes `portrait.canvas` as resolved (`AssetGraph._setting_for_hash` reads the settings with
  their defaults), so a Project relying on the default sees its portraits' `brief` stale and rebuilds them.
- **Tests:** `test_portrait.py` (the brief's default is 192 x 240 at (96, 239); the version 8 file reads 192 x 240; the
  string replacements follow the template) and `test_export_portrait.py` (the exported record and image size) moved to
  192 x 240; `test_portrait_stages.py` moved with 0321. `lint-imports` and `mypy` pass.
