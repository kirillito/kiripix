---
status: done
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

- [x] CLI seam: a commented `kiripix.toml` at an old `schema_version` keeps every comment after a migration and after
      `ramps-add`, and its settings are the same as before.
- [x] `uv sync --locked` passes with the new dependency, if one is added.

## Result

`save_settings` (kiripix/core/settings.py) no longer dumps the settings whole. `render_settings` parses the file it replaces with
`tomlkit`, applies the migration to it as edits (`_merge`: only the keys the migration added, renamed or removed), then applies
only what differs between the file's own settings and the new settings (`_apply_changes`). A default the file never wrote is not
added, and every comment, key, order, spacing and inline table stays. A new `[[array.of.tables]]` row is added in place with a
blank line after it. If the edit doesn't read back as the new settings, the file is dumped whole as before. `asset.toml` goes
through the same path.

For 0239: a migration stays a pure dict-to-dict function. Add it to `PROJECT_MIGRATIONS`, bump `PROJECT_SCHEMA_VERSION`, and the
next write merges the migrated document into the old file: only what the migration changed is touched. A new
`[[character.clips]]` needs nothing extra; `_merge` adds the first row and appends later ones. `ramps-add` now calls
`save_settings` (its own text appender is gone). `tomlkit` is in pyproject.toml and uv.lock.

Tests: tests/cli/test_settings_comments.py (comments kept after `ramps-add` on a file annotated line by line, after a write that
migrates a version 2 file, and after a second `ramps-add`).

### After review (2026-11-17)

- `save_settings` returns False when an existing file couldn't be edited in place and was written whole. `ramps-add` and
  `clips-add` then warn `settings.layout_lost` (owner_action: restore the comments from the last commit). `set`, which writes
  `asset.toml`, doesn't report it yet.
