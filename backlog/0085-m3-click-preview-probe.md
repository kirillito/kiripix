---
status: done
milestone: M3
agent: core-engineer
type: ticket
---

# M3: a Probe that answers as a lift would, for many clicks at once

Spec §10.1. Found by [0076](m2/0076-m2-claude-layers-first-pass-trial.md), which has two costs from one cause:

- **A probe doesn't predict the lift.** `segment-preview` with several clicks sends them as one prompt, while a lift makes one Runner
  call per click and takes the union (`click_groups`, ticket 0070). On r02's lockers the same 6 clicks gave 13,471 px as a probe and
  11,980 px as a Layer, with two door tops missing, and that cost a correction round.
- **Each probe starts cold.** In the CLI each one loads the Runner and computes the embedding again, about 4 s. The trial's 90 probes
  took about 6 minutes, though a decode takes about 0.07 s.

`segment-preview` stays as it is, because the UI's hover uses it (`web/src/layerScreen.tsx`, `web/src/maskScreen.tsx`). Its `--help`
gains a line saying that several clicks are one prompt, unlike a lift.

## What to build

`kiripix probe click-preview <asset> x,y [x,y,neg ...]`, with the same click syntax as `segment-preview`. It answers with:

- `clicks`: for each click in order, its Mask's `pixels` and `box`, as a single click would give.
- `union`: the result of replaying them in order, where a positive click adds and a negative one takes away, with `pixels`, `box` and
  `pieces`.
- `embedding` and `device`, as now. `--summary` leaves out `runs`, as now.

One Runner load and one embedding per call in the CLI, and then one decode per click. In `serve` it uses the warm Runner. Each click
makes the same call as `click_call`, so the answer can't drift from the lift. It records and pins nothing.

## Acceptance criteria

- [x] CLI seam: for the same clicks, `union` equals a Layer lifted from them with `grow` 0, and equals the Mask a `masks` lift makes.
- [x] A negative click in the list takes its segment away at its place in the order.
- [x] Each entry in `clicks` equals `segment-preview` with that click alone.
- [x] 20 clicks in one call compute one embedding and load the Runner once.
- [x] `segment-preview`'s answers and the UI's hover are unchanged.
- [x] Nothing is written to the journals, the Stage outputs or the pinned results.
- [x] Busy behaves as `segment-preview` does: exit 4, with `--cpu` as the fix.
- [x] The Probe's sample: `test_contract.py` has one sample per Command (`probe echo`), which passes; the new Probe is covered by `tests/cli/test_click_preview.py` instead.
