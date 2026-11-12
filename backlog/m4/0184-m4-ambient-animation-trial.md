---
status: todo
milestone: M4
agent: none
type: trial
parent: 0183-m4-ambient-animation.md
---

# M4: trial: what makes a real room feel alive for the least work?

Part of [0183](0183-m4-ambient-animation.md). It runs in a main session with no subagent and no Kiripix code. Scratch numpy
scripts stand in for the Ops, and a preview stands in for the game's player. Its results decide which route is built first and
set the defaults for `timing`, `loop.seam` and `loop.flash`.

## The room

The kitchen, `room.annex.living_kitchen` in the art Project (`../urban-mystery-club-art`), exported into the game (the Owner,
2026-11-12: it will be exported by the time this ticket is worked).

Before starting, the Owner picks one example of each from what the room has:
- **(b) a colour cycle:** a fluorescent tube, a stove's flame, an appliance's display or a screen.
- **(c) a frame loop:** a hanging plant, a curtain, a clock or a fan.

## What to do

For each example, record the Owner's time with a stopwatch, from starting until accepting the result.

**(b) The cycle.** The main session writes a scratch script that does what the `loops` Stage would: the region by `flood` from
a clicked pixel, the cycling colours, and both modes, `rotate` and `pulse` (the second as an `emissive` pulse on the light
source's own pixels only). Use a flicker sequence for a tube, or an even step for a screen. The Owner's input is the click,
the colour choice and the timing.

**(c) The frames, made two ways:**
1. **By an Op, at no cost to the Owner:** the main session writes `sway`, `shimmer` or `scroll` as a scratch numpy function,
   whichever fits. Output pixels are copies of input pixels. If the object needs to be a foreground Layer and isn't one, note
   how long lifting it out with `layers` takes.
2. **Owner-made:** the Owner chooses either a kit (the region at target size, the palette as `.gpl` and a swatch PNG, painted
   in their pixel editor) or 2 or 3 image-model edits of the Source, made with "Edit this image. Keep everything exactly the
   same except: …" and then registered, fitted and mapped by hand or with `kiripix op`, as in trial 0128.

**Preview.** Composite each Loop into the room at 640×360. Advance it in whole 60 Hz ticks, and loop it for at least 10
seconds. Write it as an APNG or a short video, scaled ×3 with nearest filtering. Frame 0 must be the exported room,
pixel for pixel; check that with numpy, not by eye.

**Measure:**
- Owner time per example and per frame source, and what took the time.
- Every frame on the palette (count off-palette pixels before any cleanup).
- For edit frames: registration, drift outside the region, and frame-to-frame flicker (how many pixels change between two
  edits that should differ only in the moving part).
- The seam: the change from the last frame to frame 0 against the median change between frames, and whether `pingpong` hides
  it.
- Flashes: brightness changes a second and the region's share of the screen, against the WCAG 2.3.1 general flash threshold.
- Size: frames and bytes per Loop.

## The Owner's verdict

Put the room preview with all the Loops on in front of the Owner, then again with each Loop alone. Ask:
1. Which one makes the room feel most alive? Which is not worth its time?
2. Does the `pulse` on the light source's own pixels read as the object glowing, as the Owner's Option A decision (0183,
   decision 2) expects, or as the room being re-lit? If it looks re-lit, the decision is revisited before (b) is built.
3. For (c): is the Op's motion good enough, or does it need hand-made frames?
4. Would the game's particles at an emitter (the coffee's steam) have done more for the room than either? Only if the game has
   a steam kind by then; otherwise skip this question.

## Acceptance criteria

- [ ] One (b) and one (c) made in the kitchen. Owner time, the measures above and the preview
      paths are recorded in this ticket.
- [ ] The Owner's verdict recorded, with answers to the four questions.
- [ ] A recommendation written into 0183: the first route to build (expected: (b)), the frame sources worth building for (c),
      and whether 0193's and 0194's Part B (edit frames) stays or is cut.
- [ ] Every default marked "set by 0184" in 0188, 0189, 0192 and 0194 replaced with the trial's value, or confirmed.

Budget: 80–150k tokens.
