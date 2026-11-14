---
status: done
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0184-m4-ambient-animation-trial.md, 0189-m4-loops-stage.md]
---

# M4: frame Ops (`sway`, `shimmer`, `scroll`) and frames from an Op

Part of [0183](0183-m4-ambient-animation.md), route (c). Spec §7 (Ops). The cheapest frames: no image from the Owner. Every
output pixel is a copy of an input pixel, so frames are on the palette by construction.
**Defaults marked "set by 0184" come from the trial**, which tries these Ops as scratch functions first; port its versions.

## What to build

- **Ops** in `ops/`, pure and golden-tested:
  - `sway(rgba, anchor_row, amplitude, frames) -> rgba frames`: row r shifts by
    `round(amplitude * sin(2πk/frames) * d(r))` whole pixels, where `d` grows from 0 at the anchor to 1 at the far end. The
    alpha moves with the pixels. Defaults: `amplitude` 1, `frames` 4 (set by 0184).
  - `shimmer(rgb, region, amplitude, wavelength, frames) -> frames`: each row inside the region shifts by
    `round(amplitude * sin(2π(row / wavelength + k / frames)))`, taking pixels from inside the region only. Defaults:
    `amplitude` 1, `wavelength` 6, `frames` 6 (set by 0184).
  - `scroll(rgb, region, dx, dy, frames) -> frames`: the region's pixels move by (dx, dy) per frame and wrap within the
    region's box, masked to the region. Default `frames` is the period of the wrap.
  Frame 0 of each is the input.
- **In the Stage:** a `frames` Decision with `source = "op"`, the Op's name and parameters. For `sway`, the Loop must have
  `layer = <id>`: the Op moves the Layer's RGBA, and where it uncovers pixels the Plate's fill shows. On `layer = plate` the
  Stage refuses with `loop.no_fill` (error), whose `fix` is none and whose `owner_action` names the `layers` Decision that lifts
  the object onto its own Layer.
- Op frames rebuild on any upstream change and stay `done`.

## Acceptance criteria

- [x] Golden tests: each Op on a small fixture (a plant Layer over a Plate, a puddle, a window), pixel-exact; every output
      pixel exists in the input; frame 0 equals the input.
- [x] CLI seam: a `sway` Loop on a Layer builds a strip whose frames carry their own alpha; on `plate` it raises
      `loop.no_fill`.
- [x] `loop.seam` is quiet on `sway` and `shimmer` at their defaults (they are periodic).

Budget: 150–250k tokens.

## Result (2026-11-13)

Trial 0184 hadn't run: defaults are placeholders with `# set by 0184` in `kiripix/ops/frames.py` (sway 1 px / 4 frames,
shimmer 1 px / 6 rows / 6 frames).

- Ops `sway`, `shimmer`, `scroll`, `scroll_period` in `kiripix/ops/frames.py`; goldens `sway_plant.png`, `shimmer_puddle.png`,
  `scroll_window.png`, test `tests/golden/test_frame_ops.py`. Shimmer's wave is taken relative to frame 0's so that frame 0 is
  the input (shifts up to twice the amplitude); a rounding is half away from zero.
- Stage: `frames` Decision `{loop, source: op|kit, op: sway|shimmer|scroll, params: {anchor_row, amplitude, wavelength, dx, dy,
  frames}}`. `source = kit` is held (needs-input, names 0194). `sway` on `plate` gives `loop.no_fill` (error, owner_action only)
  from `check`; a `sway` Loop with no region drawn moves the whole Layer; its box widens by the amplitude. `difference` is
  refused for Op frames. Tests: `tests/cli/test_loop_frame_ops.py`.

## Closing notes (2026-11-13)

- The Owner approved the golden images (`sway_plant`, `shimmer_puddle`, `scroll_window`) on 2026-11-13.
