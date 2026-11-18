---
status: done
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
- Review fixes: the version reason is transitive. A stamp holds `upstream_versions` (every Stage above it), so a Stage
  below a bumped one says so even after the bumped one is rebuilt; an older stamp falls back to each upstream stamp's
  version. One `_hash_document` builds both hash forms (`older_form`); `_outside_inputs` takes the hash function for the
  base's built Stages. CLAUDE.md's line also says a changed declared default needs a `version` bump.
- `status` and `show` say why a Stage is stale when it's the version ("Kiripix's `finish` changed: version 2 → 3"), so the
  Owner can tell a code change from their own edit.
- Existing built Stages must not all turn stale on the first run after this lands: a hash recorded without a version reads
  as version 1. Bumping a version is then a deliberate change in a ticket, named in its "Result".
- CLAUDE.md's conventions get one line: a change to what a Stage writes bumps its `version`.

## Also: a new parameter at its default (added 2026-11-17)

A Stage's input hash holds every declared parameter with its default (`AssetGraph.params`), so adding a parameter makes the
Stage stale on every built Asset of the Kind. M5's first wave did this twice: 0237's `render.points` (every character
re-renders in Blender) and 0258's `brief.state` (every Prop rebuilds, with identical output). Leave a parameter out of the hash
while it holds its default, so adding one is never a rebuild, and a deliberate rebuild is a `version` bump. That changes every
hash once, so land it with the rule above that reads a hash recorded without a version as version 1, and check it against a
copy of the art Project (`status --all` the same before and after). Until this lands, don't rebuild the art Project's
characters for 0237 alone.

## Acceptance criteria

- [x] CLI seam: a built Asset stays `done` after this lands. Bumping a Stage's version (in a test Recipe, `demo`) makes it and
      the Stages after it stale, and `status` says it was the version.
- [x] ADR 0005 gets a short note that a Stage's version is one of its inputs. `uv run lint-imports` and `uv run mypy` pass.

## Result

- `StageSpec.version` (int, default 1) is in the input hash. A parameter that equals its declared default is left out of
  the hash (`AssetGraph._hashed_params`), so adding one is no rebuild. A bump makes the Stage and every Stage below it
  stale on every Asset of the Kind.
- Old records: core also works out the older form of the hash (`AssetGraph.legacy_input_hash`: every parameter, no
  version; it adds the version only when it isn't 1, so no old stamp matches a bumped Stage). A stamp or a failure
  recorded in either form counts as current (`current_hashes`). A stamp gets `version`; one without reads as 1. The hash
  form on disk changes the first time a Stage is rebuilt.
- `status` and `show` say "Kiripix's `finish` changed: version 2 → 3" for the Stage itself, or name the upstream Stage whose
  version changed (`AssetGraph.stale_reason`); any other staleness keeps "an input changed since the output was built".
- Render script: its hash does not make `render` stale. `render` hashes the Blender version and `RENDER_SCHEMA_VERSION`
  (both computed settings); the script hash is only in the render cache key (`render.py`, `_script_hash`). A change to the
  script must bump `RENDER_SCHEMA_VERSION` or `render`'s `version`.
- Art Project (a copy at `urban-mystery-club-art`, minus `.git`, in the scratchpad; the real one untouched): `status` with
  HEAD's code and with this change differs only in `finish`, `sheet` and `export` of 13 characters, stale because 0247's
  `FINISH_SCHEMA_VERSION` 2 → 3 (not this ticket). Every other of the 270 Stages has the same status. No Stage's version
  is bumped by this ticket.
- CLAUDE.md has the one line; ADR 0005 has the note.

Tests: `tests/cli/test_graph.py` (version bump with reason, a stamp without a version, a parameter set to its default); the
test Recipe's `concat` takes its version from `KIRIPIX_TEST_CONCAT_VERSION`. Not covered at the seam: a stamp holding the
older hash form (checked on the art copy above).
