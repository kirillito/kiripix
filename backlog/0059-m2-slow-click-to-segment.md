---
status: todo
milestone: M2
agent: core-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: time click-to-segment, and stop a rebuild unloading SAM 2

Spec §10.4, §10.6 and ADR 0002. Story 19 of [0037](0037-m2-layers-and-props.md). The Owner found SAM 2 clicks slow at the M1
gate, and named them as a main cost in their time per room. Nobody has timed them. Do this ticket first in M2.

## The likely cause

`masks` has `gpu=True` ([room.py:903](../kiripix/recipes/room.py#L903)), so `execute` holds the GPU lock through a run that
replays pinned results and loads no Runner ([graph.py:535](../kiripix/core/graph.py#L535)). Spec §10.4 says the lock is held
only while a Runner is loaded. `hold` then asks a warm Runner to let go
([locks.py:152-155](../kiripix/core/locks.py#L152-L155)). So with "Rebuild the Masks after each edit" on, each edit may unload
SAM 2 and lose its embedding, and the next hover loads it and encodes the image again. This comes from reading the code. The
timing below decides.

## What to do

1. Measure before changing anything, on `room.harbor_front` or a room of its size, on the Owner's GPU: a hover's first preview
   on a cold server; a repeat hover; a hover straight after a rebuild; a click until its Mask shows, rebuild on and off. Split
   each into load, encode, decode and rebuild, wherever the time is visible.
2. Set `gpu=False` on `masks`, if step 1 shows the unload. `make_runner_calls` takes the lock itself, so `run --rerun` keeps it
   while a Runner is loaded.
3. Measure again, and record both sets of numbers in this ticket.
4. If most of the time is somewhere else, say where and propose the next change. Don't build it here. A different Runner is a
   fair proposal, since Runner choices stay open.

## Acceptance criteria

- [ ] The before and after numbers are recorded in this ticket.
- [ ] A CLI test: a plain `run` of a Stage that makes no Runner call doesn't take the GPU lock, and `run --rerun` still does.
- [ ] A test with a fake warm Runner: a rebuild of `masks` doesn't ask it to unload.
- [ ] `tests/cli/test_runner_calls.py` still passes unchanged.
