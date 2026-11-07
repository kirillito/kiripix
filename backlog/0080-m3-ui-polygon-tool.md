---
status: todo
milestone: M3
agent: ui-engineer
type: ticket
depends_on: [m2/0072-m2-polygon-decision.md]
---

# M3: a polygon tool on the mask screen

Spec §6.1 and §11. The Owner's idea, from [0062](m2/0062-m2-claude-first-pass-trial.md): six clicks build a six-point polygon on the
Mask. It sits in M3 because the trial's corrections took about a minute and because a new hand tool in M2 would change the
comparison the gate is measuring, the time for the hand-made reference room ([0058](m2/0058-m2-gate.md)). Reconsider it if the
gate's hand-made room shows a lot of tracing.

## What to build

In `web/src/maskTool.ts` and the mask screen, beside `brush`, `erase`, `flood` and `click`:

- Each click adds a point, and a live outline shows the polygon with the pointer as its next point.
- Clicking the first point, or Enter, closes it and sends one `polygon` Decision. Esc drops it, and Backspace removes the last
  point. Nothing is recorded before it closes.
- It uses the current Mask and has an erase form, as the brush does.

## Acceptance criteria

- [ ] Playwright: six clicks and Enter give one `polygon` Decision with those six points, and the Mask shows it.
- [ ] Esc records nothing. Backspace removes the last point.
- [ ] Undo removes the polygon in one press.
- [ ] Erase form clears the area.
- [ ] Keyboard flow matches the other tools on the screen.
