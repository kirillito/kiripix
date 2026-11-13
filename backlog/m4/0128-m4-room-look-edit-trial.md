---
status: done
milestone: M4
agent: none
type: trial
parent: 0127-m4-room-looks.md
---

# M4: trial: what does an image model's edit of a room really change?

Spec §6.1 (Looks). A main session helps with the numbers, with no subagent and no new code. Its results set `register`'s
limits, `look.drift`'s tolerance and whether `regrade` should default to `none`.

## What to do

Use a ch01 dungeon room, not `harbor_front`. The Owner makes three edits of its Source with the image model they use, each
with "Edit this image. Keep everything exactly the same except: …":
1. a door shut (or open);
2. a lamp or torch unlit;
3. an object removed or broken.

For each edit, measured with numpy in a scratch script, outside the part meant to change:
- **Size:** what came back, against the Source's size.
- **Registration:** the scale and shift that best map it onto the Source after the resize, in Source px and in target px.
- **Drift:** after resize, registration, `fit` and `palette` (by hand, or with `kiripix op`), how many target pixels change
  outside the intended region, and where. How much of it is compression noise, and how much is redraw?
- **Light:** does the whole room's light shift, and would a regrade fitted outside the region fix it or undo the Look?
- **Region:** does a difference with a tolerance pick out the change cleanly (a lamp's glass, a door leaf)?
- **Noise:** at what crop size the edit's noise starts to show after `palette`.

## Acceptance criteria

- [x] Three edits measured, the numbers recorded in this ticket.
- [x] A recommendation for `register`'s limits, the drift tolerance and `regrade`'s default, written into 0130.

## Result (2026-11-12)

**The room:** `room.ch01_dungeon_r03`, Source `src/b7b4d171fd6f5a1a.png` (1376x768, the decoded `ch01-dungeon-r03.jpeg`).
Fitted as its last export was: `downscale` to the brief's 640x368, scale 48/23 (2.087 Source px per target px), offset 0,0;
`palette` strict, no dither, `orphan_size` 0, the Project's 225-colour palette. The Owner's three edits, made with Nano
Banana 2, in
`urban-mystery-club-art/`: `_1_gate_closed`, `_2_lamp_swtiched_off`, `_3_broken_object`. The intended part, drawn by hand
as boxes in Source px: the gate 580-795 x 20-195; the top-left ceiling lamp 195-320 x 25-72 and the left wall lamp
22-62 x 160-278; the centre turnstile 610-775 x 350-535. A scratch script (numpy and PIL, the room's own `downscale` and
`quantize` Ops) measured everything outside a box, with registration estimated outside the box grown by 48 px.

**Size.** All three came back at 1376x768, the Source's size, as JPEG quality 100 with 4:2:0 chroma, as the Source was.
Nothing needed resizing.

**Registration.** Phase correlation on 96 px tiles outside the region, 329 to 362 textured tiles per edit, then a robust
least-squares scale and shift per axis. The same estimator recovers a synthetic 1 % scale and a 3 px and 2 px shift to
within 0.09 px.

| Edit | Scale x, y | Shift x, y (Source px) | Largest displacement over the frame | Per-tile residual, median and p90 |
|---|---|---|---|---|
| gate | 0.99999, 1.00002 | +0.001, -0.003 | 0.01 Source px = 0.01 target px | 0.06, 0.14 Source px |
| lamp | 0.99998, 1.00004 | +0.015, -0.014 | 0.02 Source px = 0.01 target px | 0.06, 0.12 Source px |
| broken | 0.99999, 1.00002 | +0.003, -0.002 | 0.02 Source px = 0.01 target px | 0.06, 0.12 Source px |

Nano Banana 2 didn't rescale or shift at all. In 0063, Nano Banana drew 1.17 % larger, but there it painted a new piece
from a strip on a grey canvas; here it edited a whole picture in place. Registering changed each edit's drift count by 18 target px at most.

**Drift on the mapped image.** After fit and palette, the target pixels outside the box that differ from the mapped room:

| Edit | Changed outside | Of all outside | JPEG re-save of the Source, for scale |
|---|---|---|---|
| gate | 76,960 | 34 % | 6,271 (2.7 %) |
| lamp | 93,340 | 40 % | 6,271 (2.7 %) |
| broken | 78,510 | 34 % | 6,271 (2.7 %) |

These counts are mostly not redraw. The model re-renders every pixel: before palette, the fitted edit differs from the
fitted Source by a median of 0.9 ΔE (OKLab x 100) outside the box, p90 2.6, p99 8.3. A re-save as JPEG q100 4:2:0 gives a
median of 0 and p99 0.7, so file compression is a small part. The palette is dense, with a median of 2.9 ΔE from each
colour to its nearest neighbour, so a 1 ΔE nudge moves a pixel across a palette boundary about a third of the time. The
changed pixels are one palette step apart (median 3.5 ΔE, p90 6.0). They lie along every light gradient's colour bands and
the tile grout, all over the room. Of the gate's 76,960, 59,255 had a pre-palette ΔE under 3.

**Real redraw** is where the 3x3 mean of the pre-palette ΔE is at least 8, in components of 16 target px or more:

| Edit | Redraw outside the box | Where |
|---|---|---|
| gate | 8 blobs, 231 px | the two ceiling lamp tubes (y 52-66 Source px), the booth's window and door, poster text |
| lamp | 11 blobs, 12,257 px | the light pool of the two lamps that went out, Source x 22-413 y 10-365, which belongs in the region; plus the same thin redraw as the others |
| broken | 5 blobs, 179 px | the ceiling lamp tubes, the right booth's door frame |

At ΔE 5 the redraw grows to about 1,450 px in 40 blobs per edit: every thin bright line (turnstile arms, railings, the
lamp tubes, the booth's glass, the posters) redrawn by a fraction of a pixel. It's harmless, because the Look is cut to its
region, but it's real.

**Light.** The gate and broken edits don't shift the room's light: the mean ΔL outside is -0.15 and -0.03, and no sixth of
the room moves by more than 0.7. The lamp edit darkens the top-left quarter by 3 to 8 L, which is the Look itself: the
light pool, not drift. A per-channel OKLab regrade fitted outside the box improves the gate's and broken's mean ΔE outside by
0.1 only (1.28 to 1.18, 1.31 to 1.21), since nothing is there to fix. On the lamp it fits L = 1.023 L + 0.005 and lightens
the region by 1 L of its 19.5 L darkening, so it undoes about 5 % of the Look. It would undo more if the region left more of
the pool outside.

**Region.** A difference of the fitted images before palette, on its 3x3 mean, inside the box grown by 8 target px,
specks under 16 px removed:

| Edit | Tolerance 4 | Tolerance 6 | Tolerance 8 |
|---|---|---|---|
| gate | one blob, 5,453 px, x 279-380 y 12-91: the whole shutter (box 277-381 x 9-94) | splits in two, lid and slats | the lid and a few slats only |
| lamp | the ceiling lamp and its pool, 2,909 px, and the wall lamp, 1,800 px | the same, slightly smaller | the same, smaller |
| broken | one blob, 2,041 px, x 296-367 y 172-253: the turnstile and its debris | 1,411 px, loses the scattered debris | the two broken halves only |

Tolerance 4 picks out a door leaf or a broken object cleanly, with 14 or fewer specks inside the box. A lamp's glass can't
be told from its light pool by difference, because the pool changes as much as the glass; the box is what limits it. The
same difference on the mapped images is swamped at tolerance 3 (the gate's blob runs to x 193-392 through the palette
flips) and full of holes at 6.

**Noise against crop size.** The share of outside target pixels whose palette colour changes hardly moves with the
target's scale: the gate 31 % at 6 Source px per target px, 32 % at 4, 33 % at 3, 34 % at 2.09, 35 % at 1.5 and at 1. The
lamp and broken edits follow the same curve. So it shows at every crop size: it comes from the palette's step, not the
pixels' noise. Inside a box, the pixels the edit didn't really change (3x3 pre-palette ΔE under 3) still map differently
in 33 % (broken) to 48 % (gate) of cases. When the Look toggles, they'd flicker by one palette step.

## Recommendation

Written into [0130](0130-m4-looks-stage.md): keep `register` on with limits of 0.985 to 1.015 on scale and 4 target px on
shift; measure drift and the `difference` region on the fitted image before palette, never on the mapped one; drift
tolerance 8 ΔE (3x3 mean, components of 16 px and more); `difference` default tolerance 4; `regrade` defaults to `none`.
One new question for the Owner, also in 0130: the region's unchanged pixels flicker by one palette step when the Look
toggles.
