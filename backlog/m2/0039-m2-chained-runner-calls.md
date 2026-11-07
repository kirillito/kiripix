---
status: done
milestone: M2
agent: ml-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: pinned Runner calls that depend on earlier ones

Spec §5 (Pinned calls), §8 and ADR 0002. An inpaint call's hole comes from a segmentation call's pinned result, so the
inpaint call can't be listed until that result exists.

## The gap

`make_runner_calls` ([graph.py:425](../../kiripix/core/graph.py#L425)) reads `missing_calls` once, so one `run --rerun` would
make the segmentation and stop at "Runner not run yet". `was_made_before`
([pinning.py:33](../../kiripix/core/pinning.py#L33)) compares only the Stage and `decisions`.

## What to build

- `run --rerun` keeps making calls until the Stage lists none missing. Pin each as it finishes, one Runner loaded at a
  time, unloaded before the next, and the GPU lock held only while one is loaded. A Stage's `runner_calls` lists a chained
  call only once what it depends on is pinned.
- `needs_input` tells the Owner the truth: "Runner not run yet" for a chained call never made, even though the call before
  it has a record with the same clicks, and "Runner input changed" after the Source changes or a Runner is swapped. A call
  that wraps its `decisions` (for example `[{"fill": [...]}]`) is one way to keep the two apart.
- How the hole reaches the Runner: start with `RunnerCall.params`, as a crop and runs in the style of `ops.mask_runs`. The
  key and the pinned record then cover it with no new field, and `Runner.call` keeps its signature. If that makes pinned
  records too large on a real hole, say so and propose a second input file.

## Acceptance criteria

- [x] With fake Runners: one `run --rerun` on a Stage with a chained call makes both calls and lands in `needs-review`, and
      `accept` gives `done`.
- [x] A cancel between the two keeps the first pinned, and the next `--rerun` makes only the second.
- [x] Changing what the first call returns changes the second call's key, so it goes to "Runner input changed".
- [x] A plain `run` after deleting `work/` calls no Runner.
- [x] The existing `tests/cli/test_runner_calls.py` still passes unchanged.
