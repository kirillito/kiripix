---
status: done
milestone: M3
agent: core-engineer
type: ticket
---

# M3: ask `reach` about the current Masks, before anyone accepts

Spec §10.1. Found by [0062](../m2/0062-m2-claude-first-pass-trial.md). One `click` puts `masks` in `needs-review`, which stops `place`
and `reach` until the Owner accepts. So an agent has to do clicks last and hand over Markers that `reach` hasn't confirmed. The
trial avoided this by recording no clicks. It matters as soon as clicks are worth using, so it waits until there is evidence
of how much: the Layers trial, [0076](../m2/0076-m2-claude-layers-first-pass-trial.md), is the first. If no first pass ends up using
clicks, close this ticket.

## What to build

- A `reach` Probe: `kiripix probe reach <asset>`. From the Masks as built, including a pending click's result, and the `place`
  journal's current Markers, it answers with what the `reach` Stage reports: Markers reached, islands and narrowest gaps.
- It records nothing and changes no status. It never stands in for an accept, and `reach` itself stays stopped.
- A hook on the Stage, the way `SegmentHooks` serves `segment-preview`, so that `commands` holds no logic and the Probe and the
  Stage share one computation.
- The result says when it is based on a Mask awaiting review, so nobody mistakes it for a confirmed result.

## Acceptance criteria

- [x] CLI seam: on a `done` room, the Probe's `report` equals `report.json` from the `reach` Stage.
- [x] With a pending click that opens a way, the Probe shows the Marker reached while status stays `needs-review`.
- [x] Nothing is written to the journals or to the Stage outputs, and no Asset lock is taken.
- [x] With no Marker placed, the finding says so.
- [x] The Probe's sample in `tests/cli/test_contract.py` passes. (That file has one sample per Command, `probe echo`, not per Probe; the Probe is covered in `tests/cli/test_reach_probe.py`, as 0084 and 0085 were.)
