---
status: todo
milestone: M5
agent: core-engineer
type: ticket
---

# M5: a write to `kiripix.toml` keeps the Owner's comments and layout

Found at the M4 gate ([0142](../m4/0142-m4-gate.md), 2026-11-16). Milestone M5 is a placeholder: the Owner picks it.

## The gap

Kiripix writes `kiripix.toml` whole, with `tomli_w` from the settings document (`kiripix/core/settings.py`). Every write, a
migration's or `ramps-add`'s, drops the Owner's comments and reflows the file: the art Project's file lost 17 of its 23
comment lines on the first `ramps-add` (a migration from `schema_version` 1 to 6), and again on the second. Claude restored
it by hand both times. A Project file the Owner reads and edits shouldn't lose what they wrote in it.

## What to build

- Writes that change `kiripix.toml` edit it in place: a format-preserving TOML library (`tomlkit`, added to `uv.lock`), or
  targeted edits of the lines that change, so comments, key order and inline tables stay.
- A migration bumps `schema_version` and adds or renames only what it must.

## Acceptance criteria

- [ ] CLI seam: a commented `kiripix.toml` at an old `schema_version` keeps every comment after a migration and after
      `ramps-add`, and its settings are the same as before.
- [ ] `uv sync --locked` passes with the new dependency, if one is added.
