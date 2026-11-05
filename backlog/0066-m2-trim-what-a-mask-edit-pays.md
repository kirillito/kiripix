---
status: in-progress
milestone: M2
agent: core-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: trim what every Mask edit pays

Proposal 3 of [0059](0059-m2-slow-click-to-segment.md), agreed by the Owner. Each Mask edit pays a refresh of about 0.6 s and a
rebuild of about 0.45 s, on `room.harbor_front` with 24 click groups.

## Where the time goes

Profiled on a copy of that room:

- `status` and `show` work out every Stage's state, then `export_command` makes a new graph and does it all again.
- One pass over the states calls `pin_key` 130 times, and each stats and resolves the same `source.png`.
- `mask_to_target` takes 0.23 s of a 0.52 s rebuild, building two arrays of about 1M elements for each click group.

## What to do

- `export_command` takes the states its caller already has.
- `AssetGraph` remembers an image's hash for `pin_key`, and forgets it whenever a Stage rebuilds, since that can replace the image.
- `mask_to_target` works from the set pixels and the grid's edges. Its result doesn't change, pixel for pixel.

## Acceptance criteria

- [ ] `tests/golden/test_resample.py` passes unchanged, and random Masks and grids match the old `mask_to_target` exactly.
- [ ] `tests/cli/test_runner_calls.py` passes: a new Source still changes the pin key within one `run`.
- [ ] `status` and `show` still report `export_command` as before.
- [ ] The numbers are measured again and recorded here.
