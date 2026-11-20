---
status: todo
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

- **`items`**, each one stop the Owner owns, in Asset ID order (so a district's rooms sit together), then Stage order:
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
