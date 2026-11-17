---
status: todo
milestone: M5
agent: core-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: a change to a Stage's code makes it stale, by a version the Stage declares

Spec §5 (the stage graph), ADR 0005 (status is derived). Found twice in M4: in 0203's "Open" ("A Kiripix code change alone
doesn't make a Stage stale") and at the M4 gate (after the `part_lines` fix, `finish`, `sheet` and `export` stayed `done` on
the old ramps). [0250](0250-m5-m4-gate-small-findings.md)'s `run --force --from` is the manual way. This is the automatic one.

## The gap

Status hashes a Stage's inputs and parameters, not the code that ran. When a fix changes what a Stage writes, every built
Asset looks `done` until someone forces it, Stage by Stage.

## What to build

- Each Stage declares a `version` (an int, default 1) beside its parameters. Its input hash includes it, so a bump makes that
  Stage stale on every Asset of the Kind, and the Stages below it follow as they do for any input.
- The Blender render script's hash already counts for `render` (ADR 0010). Check that, and say here whether it does.
- `status` and `show` say why a Stage is stale when it's the version ("Kiripix's `finish` changed: version 2 → 3"), so the
  Owner can tell a code change from their own edit.
- Existing built Stages must not all turn stale on the first run after this lands: a hash recorded without a version reads
  as version 1. Bumping a version is then a deliberate change in a ticket, named in its "Result".
- CLAUDE.md's conventions get one line: a change to what a Stage writes bumps its `version`.

## Acceptance criteria

- [ ] CLI seam: a built Asset stays `done` after this lands. Bumping a Stage's version (in a test Recipe, `demo`) makes it and
      the Stages after it stale, and `status` says it was the version.
- [ ] ADR 0005 gets a short note that a Stage's version is one of its inputs. `uv run lint-imports` and `uv run mypy` pass.
