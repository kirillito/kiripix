---
status: todo
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

- [ ] CLI seam: two edit frames, one shifted by 2 target px, raise `loop.misaligned` on that frame only.
- [ ] CLI seam: two edit frames that redraw the whole region raise `loop.flicker`; a `hold` over all but a band clears it,
      and the built frames are equal outside the band.
- [ ] CLI seam: an edit frame on a Layer Loop is cut to the Layer's alpha, and change past it raises `loop.past_layer`.
- [ ] `loop.seam`, `loop.still` and `loop.flash` apply to edit frames unchanged.

Budget: 150–250k tokens.
