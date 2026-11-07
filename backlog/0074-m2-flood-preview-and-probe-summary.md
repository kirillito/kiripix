---
status: todo
milestone: M2
agent: core-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: try a flood without recording it, and ask a Probe for a summary

Spec §10.1. Found by [0062](0062-m2-claude-first-pass-trial.md). Claude tried floods only at tolerance 0.04, because each try
means a Decision, a `run`, a preview and an undo. The Owner asked whether other tolerances were tried, and the honest answer was
no. `segment-preview` meanwhile returns every run of the Mask, which an agent has to filter out of its output each time.

## What to build

In `kiripix/commands/probes.py`, with the work in core:

- A `flood-preview` Probe: `kiripix probe flood-preview <asset> x,y,tolerance [x,y,tolerance ...]`. It calls the same
  `flood_region` Op that the `flood` Decision replays, on the built Plate, so a Probe and a Decision always agree. Several
  arguments give several answers, so one call can sweep tolerances. It needs no Runner and takes no GPU lock.
- Every result holds `pixels` and a bounding box, on both this Probe and `segment-preview`.
- `--summary` on `probe` leaves out `runs`. The default stays as it is, since the UI's hover reads the runs.
- A Plate that isn't built is refused, and the finding names the `run` to make it.

## Acceptance criteria

- [ ] CLI seam: `flood-preview` gives the same `pixels` as `floods.json` after recording that flood and running `masks`.
- [ ] Three tolerances in one call give three answers. Nothing is recorded, and status doesn't change.
- [ ] `--summary` gives `pixels` and the box with no `runs`, on both Probes. The default result still has `runs`.
- [ ] The bounding box matches the runs.
- [ ] The Probe's sample in `tests/cli/test_contract.py` passes.
