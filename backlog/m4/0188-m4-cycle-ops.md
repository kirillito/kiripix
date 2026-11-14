---
status: done
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0184-m4-ambient-animation-trial.md]
---

# M4: colour cycle Ops and the flicker sequence

Part of [0183](0183-m4-ambient-animation.md), route (b). Spec §7 (Ops). Pure functions in `ops/`, no I/O, golden-tested.
**Defaults marked "set by 0184" come from the trial;** until it reports, use the placeholder and leave a `# set by 0184` comment.

## What to build

- `cycle_index(image, region, colours) -> index`: an 8-bit image, 0 outside the region or where the pixel's colour isn't in
  `colours`, else 1 + its position in the list.
- `cycle_rotate(image, index, colours, steps) -> frames`: frame k replaces each indexed pixel's colour with
  `colours[(i + k) % len]`. `steps` defaults to `len(colours)`; frame 0 equals the input inside the region, always.
- `ramps(palette) -> ramp per colour`: groups the palette by hue in OKLab and orders each group by lightness, so a colour has a
  darker and a lighter neighbour, or none at an end. Stable for a given palette.
- `cycle_pulse(image, region, palette, depth, steps) -> frames`: each region pixel moves up to `depth` places along its own
  ramp (towards lighter), and back, over `steps` frames; frame 0 is the input. A pixel at its ramp's end stays. Defaults:
  `depth` 2, `steps` 4 (set by 0184).
- `flicker_sequence(seed, frames, mean_ticks, spread, length_ticks) -> [(frame, ticks), …]`: a fixed, seeded sequence over the
  given distinct frames (e.g. on, dim, off), summing to `length_ticks`, starting on frame 0. Same seed, same list, on every
  platform (a local PCG or `numpy.random.Generator(PCG64)`, never global state). Defaults: `mean_ticks` 6, `spread` 0.6,
  `length_ticks` 600 (set by 0184).
- `even_sequence(frames, ticks, pingpong) -> sequence`: the plain timing: each frame for `ticks`, and with `pingpong`,
  0 1 … n−1 … 1. Default `ticks` 8 (set by 0184).
- `flash_count(frames, sequence, region_area, screen_area) -> flashes per second`: the WCAG 2.3.1 general flash measure, with
  relative luminance from sRGB. A flash is a pair of opposing changes of at least 10 % of the maximum, where the darker
  state is below 0.80, counted only when the region is at least 25 % of a 341 × 256 area at 1024 × 768, scaled to the
  Project's resolution. The thresholds are named constants (set by 0184).
- `seam_ratio(frames, sequence) -> float`: the change from the last shown frame to frame 0, over the median change between
  consecutive shown frames (pixel count). For a cycle, the largest OKLab step in `colours` at the wrap, over the median step.

## Acceptance criteria

- [x] Golden tests: `cycle_rotate` and `cycle_pulse` frames on a small fixture (a "neon tube" and a "puddle"), compared
      pixel-exactly; every output pixel is a palette colour; frame 0 equals the input.
- [x] Unit checks: `flicker_sequence` is identical across two runs and sums to `length_ticks`; `flash_count` trips on a
      fixture flashing 5 times a second over a quarter of the screen and not on 2 a second; `seam_ratio` is 1.0 on a
      `pingpong` sequence of smooth frames.
- [x] `lint-imports` passes (`ops` imports nothing else from Kiripix).

Budget: 120–200k tokens.

## Result (2026-11-13)

`kiripix/ops/cycle.py`, exported from `kiripix.ops`; tests in `tests/golden/test_cycle_ops.py`, goldens
`cycle_neon_rotate.png` and `cycle_puddle_pulse.png`. Trial 0184 hadn't run: every default is a placeholder with a
`# set by 0184` comment (pulse depth 2 and steps 4, flicker 6 / 0.6 / 600, even ticks 8, ramp hue gap 40 degrees, grey
chroma 0.03, WCAG thresholds). Added beyond the ticket: `cycle_seam_ratio(colours, pingpong)` for the cycle case of the
seam measure. Frame ids in `flicker_sequence` and `even_sequence` are given as a list of ints.

## Closing notes (2026-11-13)

- The Owner approved the golden images (`cycle_neon_rotate`, `cycle_puddle_pulse`) on 2026-11-13.

## After trial 0184 (2026-11-14)

- `ramps` changed: the hue gap of 40 degrees made one ramp of 187 colours on the Owner's 283-colour palette, and a navy
  screen pulsed through brown and green. A colour's ramp is now every coloured palette colour within 25 degrees of its own
  hue (`RAMP_HUE_WINDOW`), not a partition. Grey chroma 0.03 confirmed. The puddle golden changed in 10 pixels.
- Confirmed: pulse `depth` 2 and `steps` 4; flicker 6 / 0.6 / 600; even `ticks` 8; the flash thresholds.
