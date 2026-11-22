---
status: done
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0327-m6-match-scope.md]
---

# M6: `kiripix queue`: everything waiting on the Owner, across all Assets

Spec §5 (status), §10.2 and §14 (M6, rooms at chapter scale). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md).
The UI's flow over it is [0329](0329-m6-ui-review-queue.md).

## The gap

`status` lists every Asset's Stages, and `next` names one Asset's next step, but nothing lists what waits on the Owner across
the Project. After first passes on a district's rooms ([0331](0331-m6-first-passes-over-a-list-of-rooms.md)), the Owner would
open each room to find its stops.

## What to build

A read-only Command, `kiripix queue [--match <glob>] [--kind <kind>] [--json]`. It records nothing and takes no lock beyond
what `status` takes. Its `data`:

- **`stops`**, each one stop the Owner owns, in Asset ID order (so a district's rooms sit together), then Stage order:
  - `review`: a Stage in `needs-review`, with its reason (what changed: a replayed click, a new Source, a divergent merge).
  - `input`: a Stage in `needs-input` whose next step is an `owner_action` (as `next` gives it), with that action.
  - `finding`: a finding of a built Stage with an `owner_action`, errors before warnings, with its code, message and
    position. A Project check's finding (`clips.timing_differs`, `exit.not_paired`) is listed under each Asset it names.
  - Each item has `asset`, `kind`, `stage`, `type`, the Stage's input hash, the command that settles it when there is one
    (`kiripix accept <id> <stage>`), and the Stage's live hand-over notes ([0326](0326-m6-hand-over-note.md), once it lands).
- **`agent_fixable`**: the findings with a `fix`, counted per Asset with their commands. Not items (the Owner's Q3 in 0324):
  a session runs them before the Owner sits down.
- **`counts`**: items by type, and the Assets with none.

An Asset with nothing waiting adds nothing. A Stage below a `needs-review` Stage isn't built (§5), so it adds nothing either.

**Speed.** The queue runs every built Stage's Checks across the Project. Measure `check --all` on the art Project first and
record it here. The target is under 5 s for 30 rooms with nothing stale. If Checks are the cost, cache each Stage's findings
in `.kiripix/` keyed by its input hash and the Check's own version, as a cache that deleting loses nothing from; `check`
shares that cache.

Exit code 0 whatever the queue holds: a listing isn't a failure.

## Acceptance criteria

- [ ] CLI seam: a temporary Project with a `needs-review` Stage, an owner-only `needs-input`, an owner-action finding and a
      fixable finding gives one item of each of the first three types, in Asset and Stage order, and the fourth only in
      `agent_fixable`.
- [ ] CLI seam: `--match` and `--kind` narrow the items; a Project check's finding appears under each Asset it names.
- [ ] `queue` has a sample in `tests/cli/test_contract.py`.
- [ ] `check --all`'s time on the art Project before and after, and `queue`'s, recorded here.
- [ ] Spec §10.5 lists the Command.

## Result

Built: `kiripix queue [--match] [--kind]` (`kiripix/commands/review_queue.py`), over `kiripix/core/queue.py`, whose `build_queue(project,
assets, cache, every)` returns the queue for any set of Assets (`Queue.by_asset(id)` gives an Asset's items by type and its
agent-fixable count: what 0328 reads). `next` and `queue` share `stage_step` (the command or owner action of a Stage that isn't
done); `next` now calls it. `project_checks.run_project_checks` runs the registered Project checks.

- A Stage that reads a Stage that isn't done adds nothing (what it says may change once that is done: the rule `status` shows as
  "waits on"), so a new prop lists its first stop, not every later one. A Project check's finding is listed under the Asset in its
  `position.asset`; one that names no Asset is not listed (use `check --all`).
- Findings of built Stages come from `done` Stages only. Info findings are neither items nor counted.
- `failed` and runner-call `needs-input` (a command an agent runs) are not items.
- Test aids: the test Kind `gated` (an owner-only `needs-input`), `demo.owner_text` and the Project check `demo.mirrored` in
  `tests/fixtures/kiripix_test_recipes.py`. Tests: `tests/cli/test_queue.py`; samples in `test_contract.py` and `test_serve.py`.
- No Stage version bumped; no data file changed.

Speed, measured on the Owner's art Project (`../urban-mystery-club-art`, 52 Assets, 34 of them with nothing waiting, nothing stale): `check --all` 49 s and 54 s; `queue` 5.2 s cold and 1.3 s warm (once the hash cache is filled). `check --all` is slower because it also runs `next` for each Asset and the Exporter's checks; `queue` runs each done Stage's Checks once. The cost is not the Checks, so no findings cache was added; "before and after" is moot, since `check` was not changed. On a temporary Project with a handful of Assets it is instant.


**Review fixes (2026-11-20):** `items` is now `stops` (`QueueStop`, the glossary's word; "item" is banned) in the JSON, the code and the UI, and `stage_step` is `what_next`. A Stage is skipped when it reads *any* Stage that isn't done, not only the first open one (two open branches each list their own stop and nothing below either). `queue` exits 0 whatever it finds, as the ticket says: an Asset that can't be read is a finding, not exit 1 (a glob that matches nothing is still refused). Test: `test_a_broken_asset_is_a_finding_and_the_exit_is_still_zero`.
