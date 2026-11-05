---
status: in-progress
milestone: M2
agent: core-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: make `run --rerun` in `serve` use the warm Runner

Spec §10.4, §10.6 and ADR 0002. Proposal 1 of [0059](0059-m2-slow-click-to-segment.md), agreed by the Owner. After 0059 a click
with rebuild on takes 2.68 s on the GPU and 4.31 s on the CPU, and the hover after it 1.20 s and 2.68 s, because
`make_runner_calls` unloads the warm Runner, loads its own, encodes, and unloads it.

## What to do

In `serve`, a `run --rerun` makes its calls through the warm Runner and its embedding cache. A hover and a click on one room use
the same image, so the click runs only the decoder. The result pins exactly as before: the device was never in the key.

- The CLI stays cold, and so does an explicit `--cpu`.
- If the GPU lock is busy, the remaining calls take the cold path, which waits with `--wait` and asks another process's warm
  Runner to unload.

## Acceptance criteria

- [x] A click through `serve` after a hover computes no embedding, and leaves the Runner warm.
- [x] The pin has the same key as one the CLI makes.
- [x] A failed call fails the run and pins nothing. A cancelled one pins nothing and leaves the session usable.
- [x] With the GPU lock held by another process, a rerun through `serve` is busy.
- [x] A rerun from the CLI still unloads the warm Runner of a running `serve`.
- [x] The numbers are measured again and recorded in [0066](0066-m2-trim-what-a-mask-edit-pays.md), together with that ticket's.

## Changed behaviour

Two tests changed, because they described the old behaviour. A rerun through `serve` now leaves the warm Runner's GPU lock held,
where it used to release it. For the same reason, a cancelled rerun through `serve` leaves that lock too, and
`test_cancel_stops_a_runner_call_and_pins_nothing` now checks only for Asset locks.
