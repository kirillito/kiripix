---
status: done
milestone: M2
agent: core-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: `preview` shows a region, a pixel grid, and where the Body fits

Spec §10. Found by [0062](0062-m2-claude-first-pass-trial.md). An agent sees a room only through `preview`, and it judged every
coordinate by eye from a whole room at 2x. It also couldn't see where the Body fits, only `solid` and `pit`, so reach findings
were its only view of that. The Owner said testing the walk took most of their time, so an overlay an agent can check first
may reduce what reaches them. That is untested.

## What to build

`kiripix/core/previews.py` and `PreviewInput` in `kiripix/commands/checks.py`. Today `overlay` takes only `masks`.

- `--region x,y,width,height`, in target pixels: crop before the zoom, so a detail can be seen closely in a small image. A
  region outside the image is refused with a finding. The result gives the region, so that a pixel in the image can be mapped
  back.
- `--grid N`: a line every N target pixels, drawn after the zoom, measured from the room's origin and not the crop's, with
  every fifth line stronger. It's a small pure Op. No text labels, which would need a font.
- `--overlay walkable` and `--overlay reachable`: tint the Stage outputs that already exist, `walkable.png` from `place` and
  `reachable.png` from `reach`. If that Stage has no output, the finding names the `run` to make it.
- The preview's file name includes the region, the grid and the overlay, so that one preview doesn't overwrite another.

These read outputs only. `preview` still changes nothing in the Project but its own previews.

## Acceptance criteria

- [x] CLI seam: a region's PNG has the right size, and its pixels match the same area of the full preview.
- [x] A grid at N lines up with the target pixels at any zoom, including in a region that doesn't start on a multiple of N.
- [x] The `walkable` overlay shows nothing on `solid` or a Pit, and the `reachable` overlay leaves out an unreachable island.
- [x] With `reach` not built, `--overlay reachable` is refused and the finding's `fix` runs it.
- [x] The contract sample in `tests/cli/test_contract.py` covers the new flags.
