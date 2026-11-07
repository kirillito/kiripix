---
status: todo
milestone: M3
agent: core-engineer
type: ticket
---

# M3: a `layer-stats` Probe: a Layer's numbers, and its y-sort line

Spec §10.1. Found by [0076](m2/0076-m2-claude-layers-first-pass-trial.md). After a lift, the only way to judge a Layer is by looking at
it. Claude wrote a scratch script for these numbers, and it found most problems without a picture: stray specks with their
coordinates, door tops missing from a Layer, and a Layer that had leaked. The Owner's `layer1` on r01 is 26,630 px in 90 pieces, which
one line of this answer would have shown.

The same trial typed all 23 y-sort lines by hand from those numbers, and one was 1 px off.

## What to build

`kiripix probe layer-stats <asset>`. It reads the `layers` output as built, including one awaiting review, and the `place` journal's
current Decisions. For each Layer it answers with:

- `pixels` and `box`.
- `pieces`: how many connected pieces (8-connected), the sizes of the largest few, and the pixels of any piece under about 50 px, so
  that a speck can be trimmed from the answer alone.
- `holes`: pixels enclosed by the Layer and not in it.
- `partial`: pixels with alpha between 0 and 255.
- `sort`: the current y-sort line, `above`, or `none`. This confirms before `accept` what `layer.no_ysort` will say after it.
- `ysort`: the suggested line, ready to use as the `data` of a `marker` Decision: ID `ysort.<layer>`, `y` the Layer's lowest row, and
  `x` and `x2` its extent. A suggestion only, since the Layer's foot isn't always where it sorts.

The answer says when the `layers` output is awaiting review.

The Probe records nothing and changes no status. A hook on the Stage, the way `SegmentHooks` serves `segment-preview`, keeps
`commands` free of logic. Counting pieces and holes is pure, so it belongs in an Op.

`describe`'s text for `layers` names the Probe, so that an agent finds it.

## Acceptance criteria

- [ ] CLI seam: on a room with Layers, `pixels`, `box`, `pieces` and `holes` match a Layer's PNG, for a Layer in several pieces and with a hole.
- [ ] It answers while `layers` is in `needs-review`, and says so.
- [ ] `sort` shows a line, `above` and `none`, each from the current journal, and follows an undo.
- [ ] A `ysort` entry passed to `decide` is accepted as it stands, and `layer.no_ysort` doesn't fire once that Layer's line is built.
- [ ] With no Layers, the answer is an empty list, not an error.
- [ ] Nothing is written to the journals or the Stage outputs, and no Asset lock is taken.
- [ ] The Probe's sample in `tests/cli/test_contract.py` passes.
