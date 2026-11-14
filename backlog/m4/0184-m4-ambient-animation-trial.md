---
status: done
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

- [x] One (b) and one (c) made in the kitchen. Owner time, the measures above and the preview
      paths are recorded in this ticket.
- [x] The Owner's verdict recorded, with answers to the four questions.
- [x] A recommendation written into 0183: the first route to build (expected: (b)), the frame sources worth building for (c),
      and whether 0193's and 0194's Part B (edit frames) stays or is cut.
- [x] Every default marked "set by 0184" in 0188, 0189, 0192 and 0194 replaced with the trial's value, or confirmed.
- [x] Part B (edit frames): 0193 and 0194 closed with Part A only, and 0196 hides the Edits source, so no ticket carries Part
      B now. If the trial keeps it, write three tickets from those Part B sections, with the trial's numbers (including
      `loop.flicker`'s share of the region): core (`import --loop --frame`, `pick --loop --frame`), imaging (building edit
      frames), UI (the Edits source on the loops screen). If the trial cuts it, say so in 0183's Order.

Budget: 80–150k tokens.

## Result (2026-11-14)

**The room:** `room.annex_living_kitchen`, Source `src/3364f0e5c696babe.png` (1376x768); fit `grid`, scale 4, offset 32,0,
so 336x192; `palette` strict, no dither, the Project's 283-colour palette. The room is the export's `plate.png` with its four
Layers on top (`sofa`, `table`, `door_bedroom`, `bench`). By the time the trial ran, 0188 and 0192 had shipped the Ops, so
the scratch scripts called Kiripix's own (`flood_region`, `cycle_pulse`, `cycle_rotate`, `flicker_sequence`, `sway`,
`scroll`, `register`, `warp_nearest`, `sample_nearest`, `quantize`, `seam_ratio`, `flash_count`) and tested them too.
`sample_nearest` on the grid and `quantize` rebuild the exported room exactly (0 pixels differ), so the edits were mapped
exactly as the room was. The previews centre the room on a black 640x360 screen.

**What the Owner picked:** (b) the TV screen; (c) the potted plant on the coffee table, by `sway`, with image-model edits as
the Owner-made source. After the first review the Owner dropped the plant and made the edits of the TV instead: a news
broadcast, which is (c) on the same object.

**Previews** (APNG, x3 nearest, 10 s in whole 60 Hz ticks) and the scratch scripts are in the art Project's
`.kiripix/trials/0184/` (not in git):
- `previews/room_all_on.png`: the pulse and the sway together.
- `previews/tv_pulse_flicker.png`: the shipped pulse, with the hue defect below.
- `previews/tv_pulse_fixed_d2_flicker.png` and `previews/tv_pulse_fixed_d4_flicker.png`: the pulse after the fix.
- `previews/tv_rotate5_even.png`: rotate.
- `previews/plant_sway_a1_f4_t12.png` and `previews/plant_sway_a2_f8_t8.png`: the sway.
- `previews/tv_edits_news_only.png`: all six edits.
- `previews/tv_one_edit_scroll.png` and `previews/tv_held_picture_ticker_edits.png`: the two cheaper strategies below.
- `previews/tv_edit_sheet.png`: the edit frames at x8.

Frame 0 of every preview is the exported room, pixel for pixel (checked with numpy on the decoded APNG).

### (b) The TV screen, a cycle

- **Region:** `flood` from (120, 58). Tolerance 0.03 takes 624 px, inside the bezel; 0.04 takes 635 and leaks 11 px into the
  bezel's bottom row; 0.06 takes 713. The default is now 0.03.
- **The shipped `pulse` was wrong on this palette.** `ramps` grouped colours by hue and split groups at gaps wider than 40
  degrees. A 283-colour palette has no such gap, so one "ramp" held 187 colours of every hue, and the navy screen pulsed
  navy, brown, green, brown. Fixed in this session (Owner, 2026-11-14): a colour's ramp is now the coloured palette colours
  within 25 degrees of its own hue (`RAMP_HUE_WINDOW`), ordered by lightness; greys keep one ramp. A larger palette makes the
  old rule worse, not better. A chroma limit was tried as well. It changed nothing on this palette, but on the default
  16-colour palette it took away `night`'s only lighter colour (`sky`), so it was dropped.
- **After the fix:** depth 2 raises the screen's mean OKLab L from 0.324 to 0.358, then 0.460. Depth 4 reaches 0.460 in its
  first step and 0.472 at most, the end of the ramp. 95 % of pixels move less than 22 degrees in hue. 0 pixels off the
  palette, 0 changed outside the region.
- **Rotate** over the screen's 3 colours with at least 5 px: hardly visible (mean L 0.312 to 0.342); the seam in its colour
  list is 1.41.
- **Owner time:** none to make: the main session clicked, picked colours and timing. Reviewing the variants took the Owner
  a few minutes; not stopwatched.

### (c) Frames

**By an Op: the plant, `sway`.** 60 px of leaves (box 116-127 x 91-97) above the pot rim, anchored at the leaves' bottom
row. The plant is on the Plate, not a Layer, so the Stage would refuse it (`loop.no_fill`). Lifting it with `layers` would
take a box Decision and a LaMa rebuild; that wasn't done, because the Owner dropped the plant. The scratch fill took the
nearest stand pixel in the row (at most 6 px uncovered at 1 px).
- Amplitude 1, 4 frames: 3 distinct, 33 px change a step, 475 bytes.
- Amplitude 1, 6 frames: two steps change nothing (`loop.still`).
- Amplitude 2, 8 frames: 5 distinct, seam 1.14, 645 bytes.

Every frame is on the palette by construction. Owner time: 0. A side finding: `sway` scales the shift by the image's row
farthest from the anchor, so a caller must crop to the object first. The Stage does (`_op_frames`).

**Owner-made: six image-model edits of the TV.** tv05 turns the TV on with a news picture; tv02, 03, 04, 06 and 07 change
the ticker. They took about 15 minutes of the Owner's time for all six (about 2.5 a frame).

| Edit | Scale x, y | Shift (Source px) | Residual (target px) | Outside the screen: median ΔE | mapped px changed | `drift_boxes` px |
|---|---|---|---|---|---|---|
| tv05 | 0.9998, 1.0003 | 0.16, -0.14 | 0.041 | 1.65 | 65 % | 1 725 |
| tv02 | 0.9998, 1.0002 | 0.15, -0.09 | 0.037 | 2.61 | 79 % | 2 330 |
| tv03 | 0.9997, 1.0001 | 0.20, -0.06 | 0.036 | 3.65 | 84 % | 4 919 |
| tv04 | 0.9996, 1.0000 | 0.23, 0.00 | 0.036 | 4.67 | 86 % | 14 241 |
| tv06 | 0.9997, 1.0001 | 0.16, -0.06 | 0.037 | 3.53 | 84 % | 4 488 |
| tv07 | 0.9997, 1.0001 | 0.20, -0.07 | 0.036 | 3.61 | 84 % | 4 680 |

- **Registration** is fine everywhere (well under a target pixel). Every edit was 1377 px wide, one more than the Source.
- **Chained edits degrade.** As the Owner saw, the median ΔE outside the screen climbs with each edit (1.65, 2.61, 3.65,
  4.67), because each edit was made from the one before. Outside the region it is cut away and costs nothing in the game,
  but the same drift happens inside the region. Edit the Source each time, never an edit (the Owner's note).
- **Palette:** before mapping, every pixel of every edit is off the palette (703 of 703 in the screen), as with Looks. The
  mapped frames are all on it.
- **Flicker:** between two edits that should differ only in the ticker, 340-448 of the screen's 703 px change. Of the still
  picture's 481 px, 177-261 change: 37-54 % of the picture, or 25-37 % of the region. The picture boils.
- **Two cheaper strategies, both with 0 px of picture flicker:** hold one edit (tv02) and move its 3-row ticker band with
  `scroll` (dx -1: 37 frames, 3 535 bytes); or hold tv02's picture and take only the ticker band from each edit (5 frames,
  3 560 bytes). The Owner doesn't mind that the ticker can't be read: at 37x19 px nothing on a TV can be.
- **Seam:** 1.2 for the news frames alone, 1.6 when the loop starts on the dark screen; `pingpong` isn't needed.
- **Flash:** 0. The screen is 0.27 % of 640x360, under the WCAG area of 2.78 %, so no Loop in this room can trip
  `loop.flash`.
- **Frame 0 is the dark TV.** A Loop's frame 0 is the room, and the room's TV is off. The `ticks` minimum is 1, so a TV that
  is always on still shows frame 0 for at least one tick a loop. Follow-up: [0222](0222-m4-loop-rest-frame.md).

### The Owner's verdict (2026-11-14)

1. **Most alive:** the TV with the news broadcast. **Not worth the time:** the plant's sway here. A plant that small,
   swaying that much, makes the room look windy. The Owner would use a sway outdoors, slower and at most 1 px.
2. **The pulse** reads as the object glowing, not as the room re-lit. The Owner would use it on dungeon lamps, not on a TV,
   which wants a picture. Option A (0183, decision 2) stands.
3. **The Op's motion** works and is too strong as tried. The plant needs no hand-made frames; the TV needs edit frames.
4. Skipped: the game has no steam kind yet (`game/world/fx/` has only `dust_motes.gd`).

### Defaults

The code comments now say "confirmed by 0184", or give the trial's value:
- Pulse `depth` 2 and `steps` 4: confirmed.
- Flicker 6 / 0.6 / 600, and even `ticks` 8 for cycles: confirmed.
- Ramps: the 40-degree hue gap is replaced by a 25-degree hue window; grey chroma 0.03 confirmed.
- Flash thresholds: confirmed.
- `sway` 1 px and 4 frames: confirmed. The Owner wants it slower than 12 ticks a frame.
- `shimmer`: not tried; kept.
- `SEAM_LIMIT` 3.0: confirmed.
- `PULSE_REACH` and `KIT_OFF_PALETTE_ERROR`: not measured; kept.
- Flood tolerance: 0.04 changed to 0.03, in the Stage and the loops screen.

### Part B stays

The Owner's favourite Loop came from edits, so Part B stays, with three lessons from the trial:
- edits are made from the Source only, never from an edit;
- a `hold` takes the still part of the region from one frame;
- `loop.flicker` warns at 30 % of the region.

Tickets: [0219](0219-m4-import-and-pick-edit-frames.md) (core), [0220](0220-m4-loops-build-edit-frames.md) (imaging) and
[0221](0221-m4-ui-loop-edits-source.md) (UI).

### Changed in Kiripix in this session

- `kiripix/ops/cycle.py`: `ramps` works per colour, by a hue window (`RAMP_HUE_WINDOW`), instead of partitioning the
  palette by hue gaps; comments on the defaults.
- `tests/golden/test_cycle_ops.py`: new test, a dense 36-hue palette never ramps across hues; the test palette's expected
  ramps updated.
- `tests/golden/expected/cycle_puddle_pulse.png`: rewritten. In frame 2, ten blue pixels now stop at light blue instead of
  pale blue, which is 27 degrees from the blue. Enlarged before and after: `previews/golden_puddle_pulse_before_after.png`.
- `kiripix/recipes/regions.py`, `web/src/loopScreen.tsx`: flood tolerance 0.03.
- `kiripix/ops/frames.py`, `kiripix/recipes/loops.py`: comments on the defaults.
