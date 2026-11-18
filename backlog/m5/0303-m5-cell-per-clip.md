---
status: todo
milestone: M5
agent: character-pipeline
type: ticket
parent: 0236-m5-the-games-next-needs.md
depends_on: [0302-m5-render-attached-things.md]
---

# M5: a cell per clip: a clip that doesn't fit the body's cell grows its own

Part of the held-things build chosen in [0238](0238-m5-held-things-trial.md) (the Owner, 2026-11-18): option (a), the thing
attached in the character's render for the clips that hold it, at a `grip_r` socket bone, with a cell per clip and a ramp row for a
class weapon. The trial's prototype (`backlog/m5/0238-trial/`, `held_render.py`, `grip_config.json`) is the reference.

## What to build

- **The rule (the Owner, 2026-11-18):** every clip keeps the body's cell, as today; a clip whose extent (its held thing, a long attack)
  doesn't fit gets its own larger cell and pivot. Measured in 0238 over 12 clips: the stick's `attack` 86 against the body's 78 is
  +3.4 % atlas (one cell for all: +21.6 %); the rake's 138 is +34 % (one cell: +213 %).
- `render`: cell and pivot per clip (`fit_cell` already measures per clip, 0155); `render.json` per clip.
- `sheet`: the atlas laid out by clip, each clip's cells at its own size; `sheet.json` and `character.json` carry `cell` and `pivot` per
  clip. `character.json` `schema_version` bump with its migration in `kiripix/core/settings.py`; a character whose clips all share the
  body's cell keeps the clip's `cell` equal to the character's.
- `sheet`'s Checks (stationary pivot drift, `sheet.part_vanishes`) per clip. Stage `version` bumps.

## Acceptance criteria

- [ ] CLI seam: a fixture character with one wider clip: that clip's cells are larger, every other clip's are the body's, and
      `character.json` lists each clip's cell and pivot.
- [ ] An old `character.json` migrates; `uv run lint-imports` and `uv run mypy` pass.
