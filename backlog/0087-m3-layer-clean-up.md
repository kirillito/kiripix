---
status: done
milestone: M3
agent: imaging-engineer
type: ticket
---

# M3: clean up a Layer: drop its specks, and add pixels by brush

Spec §6.1. Found by [0076](m2/0076-m2-claude-layers-first-pass-trial.md). Two things `trim` can't do well:

- **Specks take a round of their own.** Segmenting leaves stray pieces of 1 to 5 px. On r02 and r03 each needed their coordinates read
  out and a trim recorded, with another rerun, for 9 and 7 pixels in all.
- **`trim` only removes.** r03's joints between arm and pylon, about 2 to 3 px each, stay in the Plate. A click there returns the whole
  pylon, so no Decision can add just those pixels.

Trim with a thick stroke already covers rectangles, so this ticket adds no rectangle trim.

## What to build

- **A `min_piece` parameter on `layers`** (int, default 0, set with `kiripix set`): after the replay, a connected piece of a Layer under
  this many target pixels goes back to the Plate, before the hole is filled. 0 changes nothing. Real pieces can be small, with r03's
  thinnest arm at about 80 px, so the default stays off, and the Owner or an agent chooses.
- **An `add` Decision on `layers`,** the opposite of `trim`: a brush stroke in target pixels, with `layer`, `radius` and `points`. Those
  pixels join the Layer, taken from the fit image, with full alpha, and leave the Plate. It replays in order with `click` and `trim`.

`add` changes the hole, so the Plate's fill can need a new Runner call. Say so in its description. As with a click, an unpinned fill
needs `run --rerun` and lands in `needs-review`.

This ticket adds no UI. A brush that adds on the layer screen is a separate ticket for `ui-engineer`.

## Acceptance criteria

- [x] CLI seam: with `min_piece` 8, a Layer's pieces under 8 px are gone and their pixels are back in the Plate; larger pieces are untouched.
- [x] `min_piece` 0, and a room that never set it, build the same output as before, with no new review.
- [x] `add` puts its stroke's pixels in the Layer, and a `trim` recorded after it takes them away again.
- [x] After `add` and `min_piece`, `layers.recompose_mismatch` and `layers.plate_hole` report nothing.
- [x] An `add` that needs a new fill stops with `needs-review` on a plain `run`'s rules, and a rebuild with the fill pinned makes no Runner call.
- [x] Golden seam: the piece-size Op, on a Mask with pieces either side of the limit.
- [x] Existing `click` and `trim` Decisions and their pinned results are untouched.
- [x] `describe room --stage layers` lists the parameter and the Decision, and the contract test passes.
