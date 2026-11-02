---
status: review
milestone: M0
agent: core-engineer
type: ticket
parent: 0001-m0-skeleton.md
depends_on: [0004-m0-data-files.md]
---

# M0: init, new and describe; the Recipes declared

Spec §4, §6 and §10.2. User stories 1–4, 8–12, 32 and 33 of [0001](0001-m0-skeleton.md).

## What to build

- `kiripix init [dir]`: the project layout, `kiripix.toml` with defaults, `style/palette.gpl`, `.gitattributes` (LFS
  for binaries; `merge=union` and `eol=lf` for `history.jsonl` and `decisions/*.jsonl`) and `.gitignore` (`work/`,
  `.kiripix/`). Refuses an existing project (`project.exists`).
- `recipes`: room, prop and character declared with their Stages (in the ADR 0004 order), parameters (type, default,
  range), Decision schemas and Checks. Their Stages report `needs-input`, "not implemented until M1" (or later).
- `kiripix new <kind> <name> [--view top|side]`: creates `assets/<kind>/<name>/` with `asset.toml`, an empty
  `history.jsonl` and `decisions/`. Refuses a bad ID (`asset.invalid_id`), a duplicate (`asset.duplicate_id`), an
  unknown Kind (`kind.unknown`, listing the Kinds), a missing `view` for a room, and a `view` for a Kind without one.
- `kiripix describe project` and `kiripix describe <kind>`.
