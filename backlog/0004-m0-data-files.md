---
status: review
milestone: M0
agent: core-engineer
type: ticket
parent: 0001-m0-skeleton.md
depends_on: [0003-m0-registry-and-contract.md]
---

# M0: data files, schema versions and migrations

Spec §4. User stories 5–7 and 13 of [0001](0001-m0-skeleton.md).

## What to build

- Pydantic classes for `kiripix.toml` (project, body, masks, export, providers) and `asset.toml` (Kind and
  parameters, never status: ADR 0005).
- Both carry `schema_version`. Migrations are pure functions from N to N+1, run in memory on read, and written back
  only when a writing Command saves the file.
- Unknown keys are an error. Validation errors become findings (`config.invalid`, `config.unknown_key`) with the file,
  the field path, the problem and a fix.
- Atomic writes (temporary file, then rename) as a core helper used for every write.

## Acceptance criteria

- [ ] A malformed or invalid `kiripix.toml` fails any project Command with the field and a fix, exit 1.
- [ ] A file at an older `schema_version` reads correctly and is not rewritten by a read-only Command.
