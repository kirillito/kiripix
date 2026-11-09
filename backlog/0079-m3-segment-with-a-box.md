---
status: done
milestone: M3
agent: ml-engineer
type: ticket
---

# M3: segment with a rough box, not only a click

Spec §6.1. Found by [0062](m2/0062-m2-claude-first-pass-trial.md). A single click returned fragments of a compound object: 99 px and
then 1,183 px of r03's ticket booth, against a box of about 4,900 px. An agent can give a rough box more reliably than it can
choose the right point, and the Runner would snap that box to the object's edges. That matters most for Layers, whose edges are
visible, so this is worth more if the Layers trial, [0076](m2/0076-m2-claude-layers-first-pass-trial.md), shows the same fragments.

**It did.** Single-click probes came back partial or leaking on 11 of 14 on r02, 12 of 14 on r01, and 9 of 9 on r03's booth, while r03's
benches, planters, railings and pylons came whole. On r01 a few pixels decide it: 135,459 leaks to 8,841 px where 142,460 is the clean
rail, and the Owner lost about 6 minutes on the same kind of leak on that room's top rails. So add r01's rails to the comparison below.
They're the hardest case, and a box may not help on an image that dark.

`kiripix/runners/sam2.py` already passes an empty `input_boxes`, so SAM 2 may take a box with no new weights. Confirm that first.

## What to do

1. **Try it first.** Call the Runner with a box on r03's booth, a bench and a pylon, and on r01's top and lower rails, and compare with
   the click results recorded in 0062 and 0076. If a box isn't clearly better, record that here and close the ticket without building
   anything.
2. If it is better:
   - `segment-preview` accepts `x0,y0,x1,y1` as a box in target pixels.
   - A `box` Decision on `masks` and `layers`, `on_image` like `click`, with a positive and a negative form. It's one Runner call
     with a pinned result, and it needs `run --rerun`, as a click does.
   - Coordinates map through the Grid transform as a click's do.

This ticket adds no UI. If it's worth having by hand, that's a separate ticket for `ui-engineer`.

## Acceptance criteria

- [x] The comparison on the booth, a bench, a pylon and r01's rails is recorded here, with pixels and the bounding box.
- [x] If built: a `box` probe and the same `box` Decision give the same Mask.
- [x] If built: a rebuild doesn't re-run the Runner, and a changed image sends the Stage to `needs-review`. (As for a click: the changed Source makes the Stage `needs-input` with "Runner input changed", and `run --rerun` then lands it in `needs-review`.)
- [x] If built: existing `click` Decisions and their pinned results are untouched.
- [x] If built: the Runner's cancel still works during a box call. (The box goes through the same pinned call and `ort.run` with the cancel token as a click; tested with the fake Runner held in its embed under `serve`. Not timed on the real weights.)

## Trial result (2026-11-08): a box is clearly better where a click fragments or leaks

SAM 2.1 small takes a box with no new weights: the decoder's `input_boxes` input is `[batch, boxes, 4]` in the 1024 px frame, and
it runs with an empty `input_points`. Run from a scratch script on the real weights (GPU, one embedding per image: 0.6 s for r03,
0.16 s for r01; 0.02 to 0.03 s per box), reading the owner's Project read-only: nothing recorded, no Stage run, nothing pinned.
Pixels and boxes are on the target grid, mapped through the Grid transform as a Decision's are, with no `grow`. A box is the
accepted Layer's bounding box (for the booth, bench, pylons and lower rails) or read off the image (the top rails), padded by 0,
3 and 8 target px to stand for a rough box. IoU is against the accepted Layer, which is the Owner's own result, including the
booth's six clicks.

| Object | Truth (px, bbox) | Single click | Box, pad 0 | Box, pad 3 | Box, pad 8 |
|---|---|---|---|---|---|
| r03 booth | 9,968, 498,34 to 602,135 | 351 to 4,305 px from six points; IoU 0.04 to 0.43 | 10,034 px, IoU 0.94 | 10,175 px, IoU 0.94 | 10,460 px, IoU 0.93 |
| r03 bench (west) | 708, 41,264 to 57,310 | 698 px, IoU 0.99 | 822 px, IoU 0.86 | 1,000 px, IoU 0.71 | 1,060 px, IoU 0.67 |
| r03 pylon 1 | 827, 126,169 to 138,238 | 820 px, IoU 0.99 | 825 px, IoU 0.99 | 859 px, IoU 0.96 | 948 px, IoU 0.87 |
| r03 pylon 6 | 839 | 817 px, IoU 0.97 | 826 px, IoU 0.97 | 893 px, IoU 0.91 | 993 px, IoU 0.85 |
| r01 lower rail, west | 329, 116,452 to 151,471 | 142,460: 314 px, IoU 0.95. 135,459: **8,841 px, leaks 8,515** | 226 px, IoU 0.64 | 301 px, IoU 0.69 | 789 px, IoU 0.42 |
| r01 lower rail, east | 334 | 265,462: 310 px, IoU 0.93 | 473 px, IoU 0.70 | 615 px, IoU 0.54 | 773 px, IoU 0.43 |
| r01 top rail, west | no reference | 142,102: **25,306 px**, 25,102 to 155,471 (leak). 134,101: 838 px, but 42,101 to 272,113: both rails at once | 872 px, 42,101 to 151,109 | 962 px | 1,202 px |
| r01 top rail, east | no reference | 271,102 and 268,103: 144 and 148 px, 249,101 to 274,108 | 206 px, 249,101 to 274,109 | 251 px | 101 px |

- **The booth:** one box returns the whole object, 94% of the Owner's Layer, where six clicks were needed and a single click gave
  4% to 43%. The box was off by 3 or 8 px and it barely mattered. This is the case the ticket was opened for.
- **The top rails:** the click at 142,102 leaks to 25,306 px, which is the leak the Owner lost 6 minutes to. A box on the left rail
  gave 872 px with no leak at any padding up to 8 px, and the right one stayed within 250 px. A click at 134,101 happens to give
  both rails as one piece; a box gives each rail alone, which is what a Layer per rail needs.
- **Not better:** where a click already works, a box is no better and a padded one is worse. A bench or pylon's click is
  IoU 0.97 to 0.99, and a loose box takes in the shadow or its neighbour (leak up to 350 px at pad 8). The lower rails, 18 px
  thin on a dark ground, are worse by box than by the right click (IoU 0.4 to 0.7 against 0.93 to 0.95), though no box leaked more
  than 460 px, against the click's 8,515.
- **Conclusion:** a box is clearly better on compound objects and on leak-prone, thin ones (the booth, the top rails), and the
  agent can give it more reliably than the right point. It is a second way in, not a replacement: a click stays the way for a
  plain object. A tight box does better than a loose one, so the description tells an agent to draw it close and to try
  `probe segment-preview x0,y0,x1,y1` first.

## What was built (2026-11-08)

- `kiripix probe segment-preview <asset> x0,y0,x1,y1`: one box in target pixels, both corner pixels included. Not with clicks, and no
  `neg` form for the probe (it makes one call).
- A `box` Decision on `masks` (with `mask`) and on `layers` (with `layer`), each with `positive`: `{x0, y0, x1, y1, mask|layer,
  positive}`, `on_image` like `click`. A positive box adds the object, a negative one takes it away at its place in the replay,
  as a click does, and a Layer of positive boxes and clicks can mix. One Runner call, pinned; `run --rerun` makes it.
- The Runner call is `{"box": [x0, y0, x1, y1] in Source pixels, "max_size"}`, with no `points`: the probe's call and the Decision's
  are the same one, so the same key. The Source box is the box's outer edges through the Grid transform. A click's call is
  untouched, so its key and pinned results don't change, and the fill's key for a click is what it was.
- A box outside the Plate or with its corners the wrong way round is `needs-input` for the Owner, with the undo. A box on `layers` with
  a `plate` Decision is refused the same way, since that path lifts by difference and calls no Runner.
- Not done, since the ticket doesn't ask for them: `click-preview` takes clicks only, so a lift with boxes has no multi-prompt
  preview (a single `segment-preview` of each box is the same call); no UI.
