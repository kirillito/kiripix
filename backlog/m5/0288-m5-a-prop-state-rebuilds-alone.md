---
status: todo
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

- [ ] CLI seam: a Prop with a default and a `toppled` state, built; a `footprint` Decision on `toppled` rebuilds `toppled` only
      (the default's files keep their modification time, and the run's progress names one state).
- [ ] A palette change still rebuilds every state.
- [ ] A Prop with no states, and stamps from before, stay `done`. `uv run lint-imports` and `uv run mypy` pass.
