---
status: done
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0219-m4-import-and-pick-edit-frames.md, 0194-m4-loops-build-imported-frames.md]
---

# M4: build a Loop's edit frames, with a held part

Part of [0183](0183-m4-ambient-animation.md), route (c): 0194's Part B, kept by trial
[0184](0184-m4-ambient-animation-trial.md), with what the trial measured. Spec §6.1 (Looks: the edit pipeline).

## What the trial found

Six edits of a TV (37x19 target px, 703 px of screen): registration was well under a target pixel each time, and every
pixel was off the palette before mapping, as for Looks. Between two edits that should differ only in the news ticker,
340-448 of the 703 px changed, and 177-261 of the still picture's 481 px did (25-37 % of the region). The picture boils.
Holding the picture from one edit and taking only the ticker band from the others (or moving it with `scroll`) left 0 px of
flicker in the picture. The previews are in the art Project's `.kiripix/trials/0184/previews/`.

## What to build

- **Build:** each picked edit frame goes through the shared edit pipeline from 0189 (resize, register, fit, optional
  regrade, map the whole edit, cut to the region), as a Look does. Frame 0 is the room.
- **Per frame:** `loop.misaligned` (error) and `loop.drift` (warning), with `look.misaligned`'s and `look.drift`'s limits.
- **On a Layer:** an edit frame has no alpha of its own, so on a Loop with `layer = <id>` it is cut by the Layer's still
  alpha. `loop.past_layer` (warning) counts the pixels of change that fall outside it.
- **`hold` (new region Decision):** `polygon` or `brush` points, inside the Loop's region, and a `frame` (1 or more). In
  every frame from 1 on, the held part takes that frame's pixels, so only the rest of the region moves (the ticker under a
  still news picture). Frame 0 stays the room. A `hold` outside the region is cut to it, with an info finding.
- **`loop.flicker` (warning, new):** for consecutive edit frames (1 to N-1, and back to 1), the share of the region outside
  every `hold` whose pixels change. Over `FLICKER_SHARE` = 0.30 of the region it warns, naming the frame pair. Its
  owner_action suggests a `hold` over the part that should stay still, or a kit. The trial's boiling TV measured 0.48 to 0.64
  with no `hold`, and 0 with one. A Loop whose region changes this much on purpose (a whole screen cutting between shots)
  takes the warning; that is why it isn't an error.
- `describe` for `loops` names `hold`, and says frames are edits of the Source, not of each other.

## Acceptance criteria

- [x] CLI seam: two edit frames, one shifted past the limit (10 target px; 2 px is registered, as for a Look), raise
      `loop.misaligned` on that frame only.
- [x] CLI seam: two edit frames that redraw the whole region raise `loop.flicker`; a `hold` over all but a band clears it,
      and the built frames are equal outside the band.
- [x] CLI seam: an edit frame on a Layer Loop is cut to the Layer's alpha, and change past it raises `loop.past_layer`.
- [x] `loop.seam`, `loop.still` and `loop.flash` apply to edit frames unchanged (same code path as other frame Loops;
      only `loop.still` has an edit-frame test).

Budget: 150–250k tokens.

## Result (2026-11-14)

- **Build.** `_edit_frames` in `kiripix/recipes/loops.py`. Each picked frame goes through `fitted_edit_file`, split out of
  `fitted_look` in `recipes/looks.py` (a Look and a Loop share it, and so does the `look-difference` Probe), run with the
  `looks` Stage's own parameters (`register`, `regrade`, `drift_tolerance`, from `run.upstream_params["looks"]`): the `loops`
  Stage gets no parameters of its own. The whole edit is mapped once (`map_to_palette` with the `palette` Stage's parameters)
  and the region cut from it. Registration leaves out `drawn`, the region before a Layer's alpha cuts it. A transparent pixel in
  an edit keeps the room's pixel. Frame 0 is the room, and the held reason's last "built in a later ticket" is gone. A Loop
  with Picks and no `frames` Decision is an edits Loop and no longer "has no frames". A `difference` is still held for an edits
  Loop (not measured across several edits).
- **`hold`** (region Decision of `loops`): `loop`, `frame` (1 or more), `points`, `radius` (brush, else a polygon), `erase`.
  Replayed in order into a map of which frame each pixel takes, cut to the region. In every frame 1 on, a held pixel takes
  the pixels of its frame. A hold on a Loop whose frames aren't edits, or naming a frame over the last picked one, holds the
  Loop (`_held_hold`). `loop.hold_outside_region` (info) counts what the cut removed.
- **Checks.** `loop.misaligned` (error), `loop.drift` (warning; the Look's `DRIFT_MIN_PIECE` and `drift_tolerance`),
  `loop.flicker` (warning, `FLICKER_SHARE` 0.30), `loop.past_layer` (warning), `loop.hold_outside_region` (info). Flicker is the
  share of the whole region, outside every hold, that changes between consecutive edit frames 1..N-1 and back to 1.
  `loop.seam`, `loop.still`, `loop.flash` and `loop.frame0` read the frames as for any frame Loop.
- **Deviation, settled.** The ticket's acceptance test says a 2 px shift raises `loop.misaligned`. With a Look's limits (4 px)
  registration corrects 2 px, as `test_an_edit_shifted_within_the_limits_is_registered...` shows for Looks, so the test shifts 10 px.
- `loops.json` per edits Loop: `source` `"edits"`, `edits` (per frame: `frame`, `file`, `registration`, `drift`), `flicker` (per
  pair: `from`, `to`, `share`), `holds` (`pixels`, `outside`, `file`: `<loop>/hold.png`, the held pixels at room size; or null with no hold), `past_layer` (px).
- **Positions.** Per-frame findings (`loop.misaligned`, `loop.drift`) carry `field` `loop.<id>.frame.<n>`; `loop.flicker` carries
  the pair's later frame (`to`; the wrap pair names frame 1) with the Loop's box; `loop.past_layer`, `loop.hold_outside_region`
  carry the Loop's box. `loop.held` is unchanged (`field` `loop.<id>`).
- Spec (`loops` row) and ADR 0011 (Edit frames) updated. Tests: `tests/cli/test_loop_edit_build.py` (8); the 0219 tests now expect
  a built Loop where they expected the hold; `hold` in the contract sample (`LOOP_EDITS`).
- Not measured: the Look-over-Loop `loop.overlaps_look` is unchanged; a real trial TV wasn't available, so the 0.30 limit
  rests on the ticket's numbers (0.48 to 0.64 boiling, 0 held).
