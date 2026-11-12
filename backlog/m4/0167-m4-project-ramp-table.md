---
status: todo
milestone: M4
agent: core-engineer
type: ticket
parent: 0166-m4-ramps-match-across-characters.md
depends_on: [0150-m4-palette-ramps-per-part.md]
---

# M4: a Project ramp table, the Command that fills it, and a Project check

Spec §6.3 (palette) and §16 (open decision 9). Part of [0166](0166-m4-ramps-match-across-characters.md). The Owner chose the
table over `ramps_from`, and shared colours for skin and hair only (2026-11-12): the art Project's table gives `rgb` to `skin` and
`hair`, and the code allows `rgb` on any part.

## What to build

- **`[[character.ramps]]` in `kiripix.toml`** (`CharacterSettings`): an ordered list of `{name, length, rgb?}`. `name` is a
  part name (lower-case snake_case); `length` at least 2; `rgb`, when given, is `length` colours dark to light, each a colour of
  the Project palette. Refused at load, each with a finding: a name twice, an `rgb` of the wrong length, a colour not in the
  palette, and a colour in two parts' `rgb`. Bump the Project's `schema_version` with a migration in `kiripix/core/settings.py`
  that adds an empty list. An empty table means 0150's behaviour.
- **`ramps-add <character> --parts skin,hair [--colours]`**, owner-only like `palette-add` (it makes every character's `palette`
  stale): appends each named part of the character's built `palette.json` to the table, with its length and, with `--colours`,
  its colours. A part already in the table is refused unless it matches; the finding says which field differs. Under the
  project lock, written atomically. `--dry-run` shows the table it would write.
- **A Project check, `palette.parts_differ`** (registered with `register_project_check`, run by `check --all`): for each
  character whose `palette` is built, each of its parts is in the table with the same length and row and, when the table has
  `rgb`, the same colours. One finding per character and part, naming the field. The `fix` is `kiripix run <character> palette`. The same holds for each exported `character.json`, read from the export folder, whose `fix` is its `export`.
- `describe` and `schema` show the table and the Command, with an example. A sample in `tests/cli/test_contract.py`.

## Acceptance criteria

- [ ] CLI seam: a Project of version N migrates to an empty table; each bad table above fails to load with its own finding code.
- [ ] CLI seam, on the fake character: `ramps-add` writes the table from `palette.json`; again with the same parts writes
      nothing; with a different length it's refused.
- [ ] CLI seam: two fake characters whose built `palette.json` disagree on a part's length or row raise `palette.parts_differ`
      in `check --all`, exit 2, with a `fix`.
- [ ] `uv run lint-imports` passes: core reads `palette.json` as a file, never through `kiripix.recipes`' Stage code.

Budget: 150–250k tokens.
