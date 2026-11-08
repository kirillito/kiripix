---
status: done
milestone: M3
agent: core-engineer
type: ticket
---

# M3: `check` says which results come from an out-of-date Stage

Spec §10.5. Found by [0076](m2/0076-m2-claude-layers-first-pass-trial.md). With `layers` in `needs-review` and five y-sort lines just recorded,
`kiripix check room.ch01_dungeon_r02` listed `place` as checked and returned no findings. That reads as a pass, but `check_asset`
(`kiripix/core/project_checks.py`) runs a Stage's Checks whenever it has an output, however old. So it was checking the `place` output
from before those lines, and the real result appeared only after `accept`.

## What to build

- **`CheckData` gains `out_of_date`:** the `<asset> <stage>` pairs among `stages` whose status isn't `done`, each with its status and
  reason. The Checks still run on them as now.
- **The text says so:** for example, `checked 8 built Stage(s), 3 out of date: place, reach, export`.
- **Exit codes don't change.** A clean result on out-of-date Stages stays 0, as this adds information and blocks nothing. An agent reads
  `out_of_date` to know what the 0 covers.

Whether a Layer has its line before `accept` is answered by the `layer-stats` Probe ([0084](0084-m3-layer-stats-probe.md)), and whether
Markers are reached by the `reach` Probe ([0078](0078-m3-reach-probe.md)). This ticket doesn't run `place`'s Checks on pending work.

## Acceptance criteria

- [x] CLI seam: on a fully built room, `out_of_date` is empty.
- [x] With `layers` in `needs-review`, `out_of_date` names the Stages after it, with their status and reason, and the exit code is 0 if the findings are clean.
- [x] `check --all` gives the same for every Asset.
- [x] The text form names the out-of-date Stages.
- [x] `tests/cli/test_contract.py` passes with the changed output, and the output schema describes the new field.

## Notes

Tests use a `brief` Stage made stale by `set` (the `layers` needs-review case goes through the same `graph.state` call). `check_asset` now returns a third value, the states of checked Stages that aren't `done`.
