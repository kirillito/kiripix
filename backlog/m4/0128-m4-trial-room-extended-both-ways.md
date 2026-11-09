---
status: todo
milestone: M4
agent: none
type: trial
parent: 0127-m4-rooms-for-grid-battles.md
---

# M4: trial: a room extended in both directions, taken to export

Spec §16, open decision 7. Trial [0063](../m2/0063-m2-multi-screen-source-trial.md) extended one direction per room: the subway east
(1024 x 320, exported) and the harbour south (640 x 528, stopped at `place`). Grid battles make rooms larger than one screen in
both directions (the game's DEC-048), so a corner piece has to join two neighbours at once. 0063 also left the real collision
piece count and `export` time of a large room unknown, because no large room had complete Masks.

A main session helps with the Kiripix side and the numbers, with no subagent and no new code. Use a ch01 room, not
`harbor_front`.

## What to do

1. **Extend** a ch01 painting east, then south, then fill the corner, to about 2 x 2 screens (about 1280 x 736 target px).
   Use 0063's 1376 x 768 canvas, and join with 0063's scratch script (register, tone, seam). The corner registers against two
   edges.
2. **Run it to `export`**, with complete `solid` and `pit` Masks. Let Claude make the first pass through the CLI, on a room with
   many objects, and then fix it in the UI. Add a few Layers, Spawns, Exits, and a box where a battle would be. Draw the box by
   hand: the `area` Marker doesn't exist yet.
3. **SAM 2 at this size:** the Source is about 2750 x 1580 px, squeezed about 2.7x across by the encoder. Click the same small
   objects on the whole image and on a crop of about one screen, cropped by hand. Compare pixels and boxes, as 0076 did.

## What to record, in this ticket

- **The corner join:** the residual after registering against two edges, and whether any seam shows after `fit` and `palette`.
- **SAM 2:** whole image against crop, per object, in pixels and boxes. If the crop is clearly better, file the ticket below.
- **Collision:** pieces per Mask, `export` time, scene size and `reach` time. A lighter collision export
  (one `ConcavePolygonShape2D` per Mask) gets a ticket only if the count is high, roughly more than 600 pieces per screen,
  or if the game's M01-12 measurement finds a cost.
- **The UI at this size:** canvas navigation, and whether the walk test follows the body.
- **The Owner's time,** for the extending and for the rest.

## Acceptance criteria

- [ ] The results above are recorded here.
- [ ] Each Kiripix limit found is filed as a ticket.
- [ ] Spec §16, open decision 7, has the result for rooms extended in both directions.
- [ ] The SAM 2 result is recorded, and if the crop is clearly better, the ticket below is filed in M4 for `ml-engineer`. If it
      isn't, the result is recorded and no ticket is filed.

## If clicks are worse: a SAM 2 crop on large rooms (the ticket to file)

The encoder stretches the whole Source to 1024 x 1024 ([sam2.py](../../kiripix/runners/sam2.py)). On a Source of about 2750 x 1580
px, one encoder pixel covers about 2.7 Source px across and 1.5 down, and the decoder's 256 x 256 Mask is just as coarse.
Encoding a window of about one screen gives back a one-screen room's resolution.

- **An optional `crop`** in target px on the click Decision and on `segment-preview` (`--crop x0,y0,x1,y1`), so the Owner in the
  UI (a dragged rectangle, a separate `ui-engineer` ticket) and an agent through the CLI choose where SAM 2 runs. With 0079's box,
  if it was built, the box plus a margin can be the crop.
- **Optionally, an automatic window** when no `crop` is given and the Source is larger than about 1,400 px on either side. The
  windows sit on a fixed grid (for example 1024 px every 512 px), so nearby clicks share one encoding, and the Runner caches a few
  embeddings, not only the last one. Include this only if the trial shows the Owner or Claude would otherwise crop on most clicks.
- **Pinning:** the crop is part of the call's parameters, so a replay is exact. Existing click Decisions keep their whole-image
  call and their pinned results.
- **`segment.cut_by_window`** (warning): the Mask touches an edge of the crop that isn't the image's edge. Its `fix` is the same
  click with a wider `crop`.
- **Acceptance:** this trial's comparison, repeated through the Runner; a probe and the same Decision give the same Mask; an old
  click Decision rebuilds without a Runner call; the cancel token still works during an encode.
- Budget: 200–300k tokens, plus about 100–150k tokens for the UI ticket.
