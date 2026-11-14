---
status: done
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

- [x] Playwright against `kiripix serve`: flood a region, pick two colours, choose `rotate`, set ticks; the preview plays and
      `loops.json` has the Loop.
- [x] Playwright: a flicker fast enough to trip `loop.flash` shows the error, and accept is disabled until the timing changes.
- [ ] The Owner makes the kitchen's colour cycle in the time 0184 measured or less, timed and recorded here.

Budget: 150–250k tokens.

## Result (2026-11-13)

- **Screen:** `web/src/loopScreen.tsx` (`LoopsPanel`), `web/src/loopTool.ts` (`LoopTool`: the preview and the eyedropper's click), wired in
  `App.tsx` (`isLoops`, a per-screen rebuild flag, Accept disabled while a Check is an error). The Loops list (ID, form, layer, size,
  findings; keys 1 to 9), New Loop, layer / light / phase (`loop` Decision), region tools Flood `F` (tolerance slider), Polygon `G`, Brush
  `B`, Erase `E`, Erase polygon `X` (`MaskTool`, one Mask "region" filled from the built strips' alpha), Eyedropper `I` with a reorderable
  colour strip and the Project palette's swatches (a chip lights its pixels in the region), rotate or pulse with steps, depth and
  emissive, timing (ticks, or one per frame; ping-pong; flicker with seed, Reroll, mean, spread, length), and a preview (`P` play or pause,
  `N` step a tick, `O` solo) that steps whole 60 Hz ticks from `requestAnimationFrame` by `loops.json`'s `sequence` and `phase`.
  Pause returns to tick 0, frame 0, which is the room. Findings of the selected Loop show inline; `loop.seam` and `loop.flash` carry a
  button that sends the finding's `fix` Decision as the same Command; `loop.pulse_spills` shows by the emissive box.
- **Tests:** `web/e2e/loops.spec.ts`, three flows (flood, two colours, rotate, ticks, the preview; flicker trips `loop.flash` and Accept
  stays disabled; an agent's cycle and the seam fix). The Owner's timed kitchen run stays unchecked.
- **Backend gaps:** (1) rename and delete of a Loop have no Command: left out. (2) A Loop with no `cycle` (or a rotate under two colours)
  holds the whole Stage (needs-input), so a region flooded first is not drawn until the cycle is valid; a Command or Probe that builds or
  previews a region alone would fix that. (3) A `loop` Decision replaces the one before, so each edit sends every field.
