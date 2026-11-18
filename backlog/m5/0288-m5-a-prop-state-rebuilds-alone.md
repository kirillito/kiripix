---
status: done
milestone: M5
agent: core-engineer
type: ticket
parent: 0257-m5-prop-states.md
---

# M5: a change to one Prop state rebuilds that state only

Found in review of [0259](0259-m5-prop-stages-per-state.md) (2026-11-17), whose "Status" item it leaves open: "a change to one
state's Decisions rebuilds that state only, where the Stage can tell".

## The gap

A Stage has one input hash, so a state's `import`, `pick`, `state_offset` or `footprint` Decision makes that Stage and every
Stage below it stale for the whole Prop. The rebuild runs every state again; the other states' outputs come out identical, so
nothing is wrong, but each rebuild costs a Runner call per state in `cutout` and the Owner's wait.

## What to build

- The stage graph hashes a per-state Stage once per state: the state's own files and Decisions (those naming it, or none for
  the default) and the Stage's shared inputs (parameters, the palette). `status` and `show` stay one line per Stage, `stale`
  if any state is, and say which states.
- A run rebuilds only the stale states, copying the current ones from the Stage's last output (`StageRun`'s previous output
  folder), inside the one output folder core swaps into place, so the write stays atomic.
- 0258's note: a state's files and picks are inputs of that state's Stages only, not of `source` for every state.
- A Prop with no states keeps its hashes (`test_a_prop_without_states_has_the_input_hashes_and_outputs_it_had`), and stamps
  written before this read as current (as 0278 does for its hash form).

## Acceptance criteria

- [x] CLI seam: a Prop with a default and a `toppled` state, built; a `footprint` Decision on `toppled` rebuilds `toppled` only
      (the default's files keep their modification time, and the run's progress names one state).
- [x] A palette change still rebuilds every state.
- [x] A Prop with no states, and stamps from before, stay `done`. `uv run lint-imports` and `uv run mypy` pass.

## Result

- **Design:** the Stage's one input hash is unchanged (so `status` is one line per Stage, a Prop without states keeps every
  hash, and every stamp written before reads as current: `test_a_prop_without_states_has_the_input_hashes_and_outputs_it_had`
  still pins them). What is new is a hash per part in the stamp (`parts`: the default state's and each state's), and a run
  that builds only the parts whose hash changed. `StageSpec.parts` (`PartHooks`, recipes/base.py) names a Stage's parts:
  `inputs` gives each part's own inputs as content hashes, `copy` copies one part from the previous output. Core adds what the
  parts share (parameters, settings, version, `asset_params`) in `AssetGraph.part_hashes`.
- **Run:** `_Runner._reuse_parts` compares the parts with the last stamp's, copies the unchanged ones from `StageRun.previous`
  into the new folder (`copy2`, so modification times stay), and hands the Stage `StageRun.build_parts`, the parts to build.
  Core swaps the one folder in whole, so the write stays atomic. A forced run, a first build and a stamp without `parts` (one
  from before) build every part. The default part's image, when copied, isn't painted with Overrides again.
- **Prop:** `source`, `cutout`, `fit`, `palette`, `finish` and `footprint` have parts (`export` is whole). A part is the state's
  Decisions (those naming it; for the default, those naming none), its Variants (`source`), its part of the upstream output
  (the default's is the top level, a state's is `states/<id>/`), and the other upstreams (the brief). So a state's files and
  picks are inputs of that state's Stages only (0258's note). `fit`'s states also hold the default's cutout (one scale), so a
  change to the default rebuilds them (`default_feeds_all`). `cutout` with matting adds each Source's pinned matte. A palette
  or any shared parameter changes every part's hash.
- **Progress and status:** each built part is a `stage_progress` event naming it ("the state toppled", "the default state"),
  then one "built ..." event; `cancel` is checked between parts, and while copying. `status`/`show` keep one line per Stage
  and its stale reason adds "(changed: toppled)" for a Prop with states, by comparing the parts' hashes now with the stamp's
  (a stale Stage above counts too). A Prop with one part gets no such text. The reason is advice; the Stage's one hash is what
  makes it stale.
- No Stage `version` is bumped: no output changes (a Prop's outputs are byte-equal).
- Not covered: a stamp from before has no `parts`, so its first rebuild builds every state (it can't tell which changed).

Tests: `tests/cli/test_prop_state_stages.py` (a footprint Decision on `toppled` rebuilds it only, with the default's files
keeping their modification times and the progress naming one state; a new picked Variant of a state rebuilds none of the
default's Stages; a palette change rebuilds both; an older stamp stays done and builds everything; a Prop without states has
one part and its old reason). Ran `test_prop*.py`, `test_export_prop*.py`, `test_graph.py`.
