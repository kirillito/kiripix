---
status: done
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0188-m4-cycle-ops.md, 0189-m4-loops-stage.md]
---

# M4: a pulse's depth in lightness, not in ramp places

Found by trial [0184](0184-m4-ambient-animation-trial.md) (2026-11-14). Spec §6.1 (`loops`).

A `pulse` moves each pixel `depth` places lighter along its ramp (`cycle_pulse`, `kiripix/ops/cycle.py`). A place is
whatever the palette gives. On the Owner's 283-colour palette, depth 2 raised a TV screen's mean OKLab L from 0.324 to 0.460.
The Owner plans 512 to 1024 colours, which puts 2 to 4 times as many colours in a ramp, so the same Decision would make a
visibly weaker pulse, and every pulse Loop would need its depth raised after a palette change. Ramps are built per colour
from a hue window since 0184, so a denser palette no longer changes their hue, only their step.

## What to build

- **`cycle_pulse(..., lift)`:** in place of `depth`, `lift` is a lightness change in OKLab L (0.15 by default, about what
  depth 2 gave on the 283-colour palette). At the pulse's peak, each pixel takes the ramp colour whose L is closest to its
  own L plus `lift`, never darker than itself and never past the ramp's end. The frames in between follow the same
  triangle as now, at a share of `lift`, so a pixel reaches its peak colour in whole ramp places whatever the palette.
- **The `cycle` Decision:** `lift` replaces `depth` for a pulse. A Decision that still has `depth` is refused by the
  Stage. The finding names the replacement: `lift` = depth x 0.075. No production room has a pulse yet (the 0184 trial's
  were scratch). The UI's slider changes with it (one control in `loopScreen.tsx`).
- `loop.pulse_spills` and the flash measure are unchanged.

## Acceptance criteria

- [x] Golden: the same lit region pulsed with one `lift` on a palette and on the same palette with a colour added between
      each pair in every ramp reaches a peak lightness within 0.03 of each other.
- [x] Golden: no pixel ends darker than it started, or outside its ramp.
- [x] CLI seam: a `cycle` Decision with `depth` is refused, and the finding names `lift`.

Budget: 60–100k tokens.

## Result (2026-11-14)

- `cycle_pulse(image, region, palette, lift=PULSE_LIFT, steps)` (`PULSE_LIFT` = 0.15 replaces `PULSE_DEPTH`): in a frame whose
  share of the triangle is `a / steps`, each pixel takes the colour of its ramp, at or above its own place, whose OKLab L is
  nearest its own L + `lift` x `a / steps`; a tie takes the darker one. Frame 0 is the input, the pulse is the same triangle.
  The old whole-place rounding is gone, so a half-way frame may stay on the pixel's own colour when a place is wider than the
  half lift.
- **Refusal chosen: a held reason, per Loop.** `_held_cycle` in `recipes/loops.py` answers a `cycle` Decision with `depth`
  (rotate or pulse) with `loop.held`: the message says `lift` = depth x 0.075 = the converted value, and the `owner_action`
  says to decide the cycle again with that `lift`. The Stage is `done` and the other Loops build. `depth` stays in the
  Decision's schema, so the Decision is accepted and refused at build, not at `decide`. `loops.json` entries have `lift`
  (a number or null) in place of `depth` (no schema bump: nothing else reads it).
- UI: the pulse's `loopScreen.tsx` control is a number field `loop-lift` (it was `loop-depth`; it was a field, not a slider),
  a positive number, placeholder 0.15. `npm run build` passes; Playwright not run.
- Spec §6.1 `loops` row names `lift`. Tests: `tests/golden/test_cycle_ops.py` (dense palette within 0.03; no pixel darker or
  outside its ramp; `cycle_puddle_pulse.png` regenerated), `tests/cli/test_loops.py` (a `depth` is held and names the `lift`).
