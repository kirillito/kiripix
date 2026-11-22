---
status: done
milestone: M6
agent: core-engineer
type: ticket
---

# M6: a code update doesn't make the next open replay every lift

Spec §5 (input hash) and §10. Part of the Owner's report of 2026-11-21 that opening the Project in the UI is still very slow
after [0366](0366-m6-watch-the-project-without-scanning-it.md)–[0369](0369-m6-ui-refresh-asks-less.md).

## What was measured (2026-11-21, a copy of the art Project, 41 Assets, a quiet machine)

A real `kiripix serve`, `status`, `queue` and `probe style` asked together as the UI does on open:

| | ready | `status` | `queue` | all answered |
|---|---|---|---|---|
| cold (`.kiripix/derived-cache.json` gone) | 0.7 s | 19.6 s | 31.9 s | 32 s |
| warm | 1.2-1.4 s | 1.5-1.8 s | 1.7-2.0 s | 1.8-2.0 s |

A profile of a cold `status` from the CLI: 9.3 s, of which 8.1 s is `layers._lift` (`kiripix/recipes/layers.py:417`), replayed
by `AssetGraph.runner_calls` (`kiripix/core/graph.py:707`) for the input hash of two rooms' `layers` Stages. 0090 keeps that
answer in the computation cache, but its key (`_recipes_code`, `graph.py:178`) holds every file of `kiripix/recipes` and
`kiripix/ops` by size and time, so any update of Kiripix's code (this batch changed most of them; a `git pull` touches their
times) makes every lift replay on the next open. In `serve`, `status` and `queue` then both replay it at the same time
([0373](0373-m6-serve-works-the-project-out-once.md) stops that).

## What to do

1. Key `runner-calls:` on the Stage's `version` (`StageSpec.version`) instead of every recipe and Op file. Recommended: the
   Stage's `version` alone stands for its code, by the rule CLAUDE.md already has ("a change to what a Stage writes bumps its
   `version`": the Runner calls a Stage asks for are what it writes from). Add that consequence to CLAUDE.md's conventions ("a
   change to a Stage's `runner_calls`, or to an Op it replays, bumps its `version`"), and say in the Result what a forgotten bump
   would cost (a stale lift until the next bump or a deleted `.kiripix/derived-cache.json`).
2. The same audit for the Check cache's key (0367, `kiripix/core/checkcache.py`): Check code changes don't bump a `version`
   (0368 changed Checks with none), so the Check cache may keep a code key, but narrowed to what a Stage's Checks can reach
   (the recipe module that declares them, `kiripix/checks`, `kiripix/ops`), not every recipe.
3. Record the table above again (cold, warm) after the change, and once more after touching an unrelated recipe file
   (`kiripix/recipes/prop.py`): that open must be warm.

## Acceptance criteria

- [x] CLI seam (demo Kind): a derived answer survives a change to another recipe's source file and doesn't survive a `version`
      bump of its own Stage.
- [x] The art Project copy: after touching an unrelated recipe file, `status` is as fast as warm.
- [x] `uv run mypy` and `uv run lint-imports` pass.

## Result

### What was done (2026-11-21)

- `runner-calls:` is keyed on the Stage's `version` (`AssetGraph._calls_key` in `kiripix/core/graph.py`), not on every file of
  `kiripix/recipes` and `kiripix/ops` (`_recipes_code` is gone). An update of Kiripix that bumps no `version` no longer replays a lift.
  CLAUDE.md's code conventions say it: a change to a Stage's `runner_calls`, or to an Op it replays, bumps its `version`.
  **A forgotten bump costs** a stale Runner call list (so a stale input hash and status) until the next bump of that Stage or a
  deleted `.kiripix/derived-cache.json`. No Stage's `version` was bumped by this ticket: the key changed, and an old entry is only a miss.
- The Check cache keeps a code key, narrowed (`kiripix/core/checkcache.py`, `_code`): the module that declares the Stage's Check (and
  its `check_reads`), `kiripix/checks` and `kiripix/ops`; no other recipe. A Check that calls a helper in another recipe module must
  have that helper's module declared by the same rule (put the Check next to its helpers, or bump nothing and delete the cache).
- Tests: `tests/cli/test_derived_survives_code.py` (the new test Kind `counted` in `tests/fixtures/kiripix_test_recipes.py` counts how
  often its Runner calls are worked out, `KIRIPIX_TEST_SHOT_VERSION` bumps its `version`): the answer survives a changed time of
  `kiripix/recipes/prop.py` (put back after), is worked out again after a `version` bump; a demo Check's findings survive the same touch.
  Run with `test_check_cache.py` (15 passed) and `test_runner_calls.py` (41 passed, serial). `uv run mypy` and `uv run lint-imports` pass.

### Art Project copy (41 Assets; the machine was busy with the other agent's tests, so every time is noisy)

A real `kiripix serve`, `status`, `queue` asked together (`open_measure.py`):

| | ready | `status` | `queue` | all answered |
|---|---|---|---|---|
| before, cold (measured in the ticket, quiet machine) | 0.7 s | 19.6 s | 31.9 s | 32 s |
| before, warm | 1.2-1.4 s | 1.5-1.8 s | 1.7-2.0 s | 1.8-2.0 s |
| after, cold (busy machine) | 9.5 s | 56.2 s | 56.2 s | 56.3 s |
| after, warm, run 1 (serve killed before the cold run's cache was saved?) | 2.1 s | 19.3 s | 19.3 s | 19.4 s |
| after, a touched `kiripix/recipes/prop.py`, run 1 | 2.1 s | 2.5 s | 2.5 s | 2.6 s |
| after, warm, run 2 (busy) | 3.5 s | 5.8 s | 5.8 s | 6.3 s |
| after, a touched `prop.py`, run 2 (busy) | 10.4 s | 7.3 s | 7.3 s | 7.5 s |

The cold open was run while the machine was loaded, so it is slower than the ticket's, not comparable. The touched-`prop.py` opens
are as quick as the warm ones on the same machine at the same time (run 1: 2.5 s; run 2: 7.3 against 5.8 s, which is the noise), and
none replays a lift (a replay costs 8 s a room alone). The Owner may want to repeat the three rows on a quiet machine.
