---
status: done
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0257-m5-prop-states.md
depends_on: [0258-m5-prop-state-decision-and-import.md]
---

# M5: the Prop's Stages run per state

Part of [0257](0257-m5-prop-states.md); its table is the design.

## What to build

- **`cutout`, `fit`, `palette`, `finish`, `footprint`** run once per state. Each state's Decisions name it (a `state`
  field, absent meaning the default), and its outputs go under `states/<s>/` in the Stage's output folder. The default
  state's outputs stay where they are today, so an existing Prop rebuilds byte-equal.
- **One scale:** `fit` takes the default's scale for every state. In `grid` mode a state whose detected scale differs is
  `fit.scale_differs` (error). In `downscale` mode the state is fitted at the default's scale into its own size, cropped by
  its own offsets, and `fit.cropped` names the state.
- **Footprint:** each state has its own polygon and origin. `footprint.no_origin` names the state.
- **Status:** a change to one state's Decisions rebuilds that state only, where the Stage can tell. A palette change rebuilds
  all of them.
- Per-state loops check the cancel token between states.

## From 0258 (2026-11-17)

0258 made `src/states/**` and the `state_pick` Decisions inputs of `source`, so today a state's `import` or `pick` makes the
default state's `cutout` and every Stage after it stale (they rebuild to identical output). When the Stages run per state, a
state's files and picks should be inputs of that state's Stages only.

## Acceptance criteria

- [x] CLI seam: a Prop with a default and a `toppled` state of another size builds both through `footprint`, at one scale,
      each with its own origin and polygon.
- [x] A Prop with no states rebuilds byte-equal to today's outputs.
- [x] A state missing an origin raises `footprint.no_origin` naming it. A `grid` scale mismatch raises `fit.scale_differs`.
- [x] `uv run lint-imports` and `uv run mypy` pass.

## Result

- Every Stage after `source` runs for the default state (outputs where they always were), then for each other state under
  `states/<id>/` of its output folder. `source` writes `states/<id>/source.png` and `state.json` (the size); `cutout` passes
  `state.json` on; a Stage finds its states by the folders of its upstream's output (`prop_states.state_ids`, `state_view`,
  `each_state`, `check_each_state`), so each Stage's own function runs unchanged on a state. Matting makes one Runner call
  per state's Source. Cancel is checked between states.
- `fit`: the default first; each state is fitted at the default's scale into its own size. `grid`: a different detected
  scale fails with `fit.scale_differs` (owner action; exit 3). `downscale`: the default's scale, the shared offsets,
  `fit.cropped` naming the state. `run_fit` and `check_fit` (common.py) gained `size`, `scale`, `state` and `offsets`
  arguments; `check_fit` builds a state's wording itself ("the state asks for", "the state's"), not by patching text.
- **Own offsets:** a `state_offset` Decision on `fit` (`state`, `offset_x`, `offset_y`; the latest of a state counts). Without
  one a state takes the `fit` parameters' offsets, as the default does. A state's `fit.cropped` fix is the `decide` for it.
- `footprint`: the Decision takes an optional `state`; each state has its own polygon and origin, and a missing one holds the
  Stage back with `footprint.no_origin` naming the state. A footprint for an undeclared state is `prop.state_unknown`.
  Two codes: `prop.no_origin` is the default state's finding as it has always been (a stable code Owners' notes and agents
  may match), `footprint.no_origin` is new for a state, so the needs-input for a missing state origin can be told from the
  default's; a state's message names the state ("the state toppled: it has no origin ...").
  State findings say "the state <id>: ..." and carry the state's file path.
- Not done: `export` still exports the default only ([0260](0260-m5-export-prop-states.md)).
- Status granularity: a Stage's input hash is one per Stage, so a state's `import`, `pick` or footprint still makes that Stage
  and those below it stale (they rebuild all states; the default's output is identical). Per-state staleness needs the graph to
  hash a Stage per state; not done here. A Prop without states: no hash, stamp or output changes (no Stage `version` bumped,
  no new upstream), and it has no `states/` folder. Version rule (0278): a Prop without states writes the same output, so no
  `version` is bumped; a test pins the Stages' input hashes and the output files' hashes for one (the brief, source and
  cutout hashes are the ones taken before the change; `fit` gained an empty Decision list, which no hash holds).

Tests: `tests/cli/test_prop_state_stages.py` (also own offsets, pinned hashes); `tests/cli/test_prop*.py` and `test_export_prop.py` pass (52).

The Owner, 2026-11-17: per-state staleness is [0288](0288-m5-a-prop-state-rebuilds-alone.md).
