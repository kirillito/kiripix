---
status: todo
milestone: M3
agent: ml-engineer
type: ticket
---

# M3: segment with a rough box, not only a click

Spec §6.1. Found by [0062](0062-m2-claude-first-pass-trial.md). A single click returned fragments of a compound object: 99 px and
then 1,183 px of r03's ticket booth, against a box of about 4,900 px. An agent can give a rough box more reliably than it can
choose the right point, and the Runner would snap that box to the object's edges. That matters most for Layers, whose edges are
visible, so this is worth more if the Layers trial, [0076](0076-m2-claude-layers-first-pass-trial.md), shows the same fragments.

`kiripix/runners/sam2.py` already passes an empty `input_boxes`, so SAM 2 may take a box with no new weights. Confirm that first.

## What to do

1. **Try it first.** Call the Runner with a box on r03's booth, a bench and a pylon, and compare with the click results recorded
   in 0062. If a box isn't clearly better, record that here and close the ticket without building anything.
2. If it is better:
   - `segment-preview` accepts `x0,y0,x1,y1` as a box in target pixels.
   - A `box` Decision on `masks` and `layers`, `on_image` like `click`, with a positive and a negative form. It's one Runner call
     with a pinned result, and it needs `run --rerun`, as a click does.
   - Coordinates map through the Grid transform as a click's do.

This ticket adds no UI. If it's worth having by hand, that's a separate ticket for `ui-engineer`.

## Acceptance criteria

- [ ] The comparison on the booth, a bench and a pylon is recorded here, with pixels and the bounding box.
- [ ] If built: a `box` probe and the same `box` Decision give the same Mask.
- [ ] If built: a rebuild doesn't re-run the Runner, and a changed image sends the Stage to `needs-review`.
- [ ] If built: existing `click` Decisions and their pinned results are untouched.
- [ ] If built: the Runner's cancel still works during a box call.
