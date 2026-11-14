---
status: done
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0193-m4-loop-kit-and-import.md, 0192-m4-frame-ops.md]
---

# M4: the `loops` Stage builds kit frames and edit frames

Part of [0183](0183-m4-ambient-animation.md), route (c). Spec §6.1 (Looks: the edit pipeline). Part B follows 0193's Part B and
is cut with it.

## Part A: kit frames

- A `frames` Loop with `source = "kit"` takes the imported frames as they are (they are on the target grid already). Any pixel
  off the palette maps to the nearest palette colour and raises `loop.off_palette` with the count, as a warning here: the
  Owner's editor may have added a near-miss. It stays an error if more than 1 % of the frame's pixels are off (set by 0184).
- Pixels changed outside the region are cut away and reported by `loop.outside_region` (warning), with the box of each patch.
- On a Loop with `layer = <id>`, a kit frame's alpha is the Layer's alpha for that frame, so motion past the Layer's
  silhouette works: where the frame's alpha is 0 and the Layer's still alpha was 1, the Plate's fill shows.
- A palette change remaps kit frames with the `palette` Stage's mapping and puts them in `needs-review`.

## Part B: edit frames

- Each picked edit frame goes through the shared edit pipeline from 0189 (resize, register, fit, optional regrade, map the
  whole edit, cut to the region), as a Look does.
- Per frame: `loop.misaligned` (error) and `loop.drift` (warning), with `look.misaligned`'s and `look.drift`'s limits.
- On a Loop with `layer = <id>`, an edit frame has no alpha of its own, so it is cut by the Layer's still alpha.
  `loop.past_layer` (warning) counts the pixels of change that fall outside it.
- `loop.flicker` (warning, new): pixels that change between consecutive edit frames outside the part the Owner meant to move
  (outside the union of the frames' `difference` against frame 0, grown by 1 px). Above a share of the region (set by 0184),
  the edits disagree, and its `owner_action` suggests a kit instead.

## Acceptance criteria

- [x] CLI seam: kit frames with one off-palette pixel and a stray stroke outside the region raise the two findings and build;
      on a Layer Loop, a frame that moves past the silhouette shows the Plate's fill.
- [x] CLI seam: a palette change remaps kit frames into `needs-review`.
- [ ] CLI seam (Part B; left until trial 0184 has run, the Owner's decision, as for 0193's Part B): two edit frames, one shifted by 2 target px, raise `loop.misaligned` on that frame only; an edit
      that redraws the whole region raises `loop.flicker`.
- [x] `loop.seam`, `loop.still` and `loop.flash` from 0189 apply to imported frames unchanged.

Budget: 150–250k tokens (Part A alone: 80–140k).

## Result (Part A, 2026-11-13)

Part B (edit frames) is left until trial 0184 has run (the Owner's decision); its criterion stays unchecked.

- **Build** (`recipes/loops.py`, `_kit_frames`): a frame Loop takes its frames from its kit when its `frames` Decision has `source`
  `kit`, or when it has no `frames` Decision and a kit is imported. Frame 0 is the room; frames 1..N-1 are the stored frames, taken as
  painted. Inside the region: alpha >= 128 is opaque (a partial alpha is reported, `loop.partial_alpha` error); alpha 0 keeps the room's
  pixel on the Plate and leaves the pixel empty on a Layer (the Layer's strip carries the frame's own alpha, so the Plate's fill shows).
  A pixel off the palette takes the nearest colour in OKLab (`quantize`, ties to the lowest index) and is counted. A frame whose size
  differs from the built box fails the build ("write a new kit").
- **Findings:** `loop.off_palette` per frame, warning, error above `KIT_OFF_PALETTE_ERROR` = 1 % of the region (`# set by 0184`);
  `loop.outside_region` (warning) per 8-connected patch with its box; `loop.partial_alpha` (error). `loop.seam`, `loop.still`,
  `loop.flash`, `loop.frame0` apply unchanged.
- **`loops.json`:** the record gains `kit` (null unless a kit Loop): `{box, remapped, frames: [{frame, file, off_palette, remapped,
  first_off_palette, region_pixels, partial_alpha, outside: [[x,y,w,h]...], outside_pixels}]}`; `source` is `kit`, `op` and `params` null.
  No schema bump (a key was added). `frames`/`steps` are 1 + the imported count.
- **Palette change:** the build remaps with the new palette (no `off_palette` finding for those pixels; `remapped` counts them) and
  the Stage is `needs-review`. This needed a small generic hook: `StageSpec.review` / `review_reason` (`recipes/base.py`),
  `AssetGraph.moved_inputs` and its use in `state` and `accept` (`core/graph.py`, `core/editing.py`). `kits_moved` (`recipes/kit_record.py`)
  lists each kit Decision painted on another palette; `accept` re-records it with the current palette hash.
- Tests: `tests/cli/test_loop_kit_frames.py`; `test_loop_kit.py` updated (a palette change is now needs-review, not needs-input).

## Closing notes (2026-11-13)

- Closed 2026-11-13 with Part A; Part B (edit frames) waits for trial 0184, the Owner's decision.

## After trial 0184 (2026-11-14)

- `KIT_OFF_PALETTE_ERROR` 1 % kept: the trial painted no kit.
- Part B is kept, and moves to [0220](0220-m4-loops-build-edit-frames.md), with the trial's numbers. Its `loop.flicker`
  changes: the union of the frames' differences against frame 0 covers a whole TV screen that turns on, so it would never
  fire. 0220 measures flicker between edit frames instead, and adds a `hold`.
