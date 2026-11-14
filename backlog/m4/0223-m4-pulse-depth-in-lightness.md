---
status: todo
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

- [ ] Golden: the same lit region pulsed with one `lift` on a palette and on the same palette with a colour added between
      each pair in every ramp reaches a peak lightness within 0.03 of each other.
- [ ] Golden: no pixel ends darker than it started, or outside its ramp.
- [ ] CLI seam: a `cycle` Decision with `depth` is refused, and the finding names `lift`.

Budget: 60–100k tokens.
