---
status: todo
milestone: M4
agent: ui-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0189-m4-loops-stage.md, 0132-m4-ui-looks-screen.md]
---

# M4: the loops screen, with colour cycles and a live preview

Part of [0183](0183-m4-ambient-animation.md), route (b). Spec §11. It shares the region tools with the looks screen (0132).

## What to build

- **The list:** the room's Loops with ID, form, layer and findings; add, rename (until exported) and delete.
- **Region:** the looks screen's polygon, brush and difference tools, and `flood` (click a pixel; a tolerance slider).
- **Cycle:** an eyedropper that adds a clicked pixel's colour to the cycle list (with all its pixels in the region
  highlighted), a reorderable colour strip, `rotate` or `pulse` with `depth` and `steps`, and the `emissive` checkbox for a
  pulse.
- **Timing:** ticks per frame, `pingpong`, or flicker (seed, with a "reroll" that writes a new seed, mean, spread).
- **Preview:** the whole room at game resolution with every Loop playing, stepped in whole 60 Hz ticks from
  `requestAnimationFrame` by the same `sequence` the export writes (not CSS animation), with play, pause, step one tick, and
  "solo" to play one Loop. Pause shows frame 0, which is the room.
- **Findings** inline: `loop.seam` with its `pingpong` fix as a button, `loop.flash` as an error that blocks accept, and
  `loop.pulse_spills` next to the emissive checkbox.
- Every change is a Decision through the Commands, so `undo` works.

## Acceptance criteria

- [ ] Playwright against `kiripix serve`: flood a region, pick two colours, choose `rotate`, set ticks; the preview plays and
      `loops.json` has the Loop.
- [ ] Playwright: a flicker fast enough to trip `loop.flash` shows the error, and accept is disabled until the timing changes.
- [ ] The Owner makes the kitchen's colour cycle in the time 0184 measured or less, timed and recorded here.

Budget: 150–250k tokens.
