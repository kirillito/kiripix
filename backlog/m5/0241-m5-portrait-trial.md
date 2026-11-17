---
status: todo
milestone: M5
agent: imaging-engineer
type: trial
parent: 0240-m5-portrait-kind.md
---

# M5: trial: a portrait set, its emotions registered and mapped as one

Part of [0240](0240-m5-portrait-kind.md). Prototype code stays in `backlog/m5/0241-trial/`, not in `kiripix/`. It reads
Kiripix's Ops (`kiripix.ops`) and doesn't change them.

**This prototype is also the game's fallback** for its M04 (the "small script in the art repo"). Keep it runnable from a
folder of PNGs, with a short README, so the game can use it if the Kind isn't built in time.

## What to do

1. **Inputs:** Sanjay's neutral portrait and three emotions (happy, angry, surprised), made by the Owner in the free image
   model as edits of the neutral one (the game's M04-02 and M04-03). If they don't exist yet, any character's set does.
   Record the Owner's minutes per emotion.
2. **Cutout:** chroma key, or BiRefNet if the background isn't flat.
3. **Register** each emotion to the neutral, with the Looks' registration Op, over the whole figure and then outside a
   rough face box. Record the scale, shift and residual for each emotion, both ways.
4. **Fit:** one `downscale` for the set from the neutral, onto 160 x 224 at a bottom-centre anchor. Try one other size if the
   result reads badly.
5. **Colours:** the set gets its own colours, not the Project palette (the Owner, 2026-11-16: portraits have gradients that
   a strict sprite palette can't hold). Choose `n` colours over the four images together (k-means in OKLab), at `n` 16, 32
   and 64, with and without ordered dither, then each image alone, and compare. Find the smallest `n` whose gradients read
   smoothly.
6. **Outline:** 1 px in the characters' outline colour (195), kept among the set's colours.
7. **Measure the shimmer:** per emotion, the pixels outside the face box that differ from the neutral's, with and without
   step 3's registration, and with joint mapping against separate mapping. Then copy the neutral's pixels outside the face
   (`lock_outside_face`) and show the result.
8. **Lay out** the four at 1x and 3x, flipping in place as a GIF, beside mc03 at 52 px and a ch01 room, for the Owner.

## What to record, in this ticket

- The residuals, the shimmer counts and the Owner's minutes per emotion.
- The sheets and the GIF, with their paths, and the Owner's view.
- Answers to 0240's four questions, with the Owner's choice, and any change to 0242–0245 before they start.

## Acceptance criteria

- [ ] The numbers and images above.
- [ ] The Owner's answers to 0240's questions recorded, and 0242–0245 updated to match.
- [ ] The prototype runs on a folder of PNGs, with its README, for the game's fallback.
