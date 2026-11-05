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

- [x] `tests/golden/test_resample.py` passes unchanged, and random Masks and grids match the old `mask_to_target` exactly (3,000
      uniform and ratio grids).
- [x] `tests/cli/test_runner_calls.py` passes: a new Source still changes the pin key within one `run`.
- [x] `status` and `show` still report `export_command` as before.
- [x] The numbers are measured again and recorded here.

## Results (2026-11-04), with 0064 and 0065 in

Measured as in [0059](0059-m2-slow-click-to-segment.md), on the same room copy. "Start" is after 0059 and before these three
tickets. Seconds, medians of 4, except repeat hover and the Rerun row, which is one run of 4 clicks. Hovers come first, so the image
is already encoded: a click before any hover also pays one encode.

| | CPU start | CPU now | GPU start | GPU now |
|---|---:|---:|---:|---:|
| Click with rebuild on, until its Mask shows | 4.31 | **0.96** | 2.68 | **0.95** |
| Hover, straight after that click | 2.68 | **0.07** | 1.20 | **0.08** |
| Brush with rebuild on, until refreshed | 1.36 | 0.88 | 1.45 | 0.90 |
| Click with rebuild off, until refreshed | 0.62 | 0.37 | 0.63 | 0.38 |
| Rerun button, 4 clicks made with rebuild off | 3.94 | 0.83 | 2.65 | 0.75 |
| Hover, straight after a rebuild | 0.08 | 0.09 | 0.08 | 0.06 |
| Hover, repeat | 0.08 | 0.09 | 0.07 | 0.06 |
| Refresh alone | 0.59-0.67 | 0.33-0.35 | 0.59-0.65 | 0.33-0.36 |
| `masks` rebuild alone | 0.41-0.45 | 0.35-0.36 | 0.42-0.52 | 0.34-0.36 |

The first hover on a cold server also fell, from 7.13 to 3.83 s on the CPU and from 6.22 to 2.40 s on the GPU, nearly all of it in
load. Nothing here changes how a Runner loads, so don't credit these tickets: it is one sample each, and the cause is unknown.

The encode now matters once per image: 2.05 s on the CPU, and 0.46 s on the GPU in the same cold run.
