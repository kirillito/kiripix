---
status: todo
milestone: M2
agent: imaging-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: a shift-click takes the object under it away from the Mask

Spec §11 ("shift-click subtracts"), §6 (masks, layers). Reported by the Owner on 2026-11-05. The rule below was agreed
by the Owner on 2026-11-05.

## What's wrong

Today a negative `click` joins the click right before it on the same Mask (or Layer), as a negative point of that one SAM
call (`click_groups` in `kiripix/recipes/common.py`). It refines only the last object. A Mask is the union of all its
objects, floods and strokes, so a negative click can't take away what any earlier click, flood or brush put there.

On `room.harbor_front` the Owner shift-clicked 14 times on an area of `solid`. Each shift-click made a new SAM call, and
`run` put the Stage in `needs-review` ("a Runner's new result waits for the Owner"). SAM did exclude every negative point:
the last object's segment went from 9,355 to 2,637 pixels (checked with the `segment-preview` Probe). But two earlier
positive clicks, at (473, 287) and (471, 289), each covered all those points by themselves, so nothing left the Mask.

## The rule

A negative click is its own SAM call: the object under the click, segmented as a positive click would segment it. Its
result is **removed** from the Mask (or the Layer) at its place in the replay order. So it takes away whatever is there,
whichever Decision put it there, and a later positive click, flood or brush can add the area back.

- `click_groups` no longer joins negative clicks. A negative click's call is `points: [[x, y, true]]`, the same as a
  positive click there, so it reuses that click's pinned result and Probe embedding.
- `masks` and `layers` replay a negative click by clearing its segment from the current Mask or Layer. On `layers` the
  Plate's hole is still derived from the Layers.
- A negative click with no positive click before it on that Mask or Layer is allowed: it takes away from a flood or a
  stroke too. Remove the `needs-input` "has no positive click" path for `masks`, and for `layers` if a Layer can have any
  other source.
- Journals with old negative clicks replay under the new rule. Their pinned results no longer match a call, so the Stage is
  `needs-input` until `run --rerun`, then `needs-review`. Through M3 the Owner has no production rooms, so that's acceptable.

Only the new rule is kept (the Owner, 2026-11-05). Trimming an object's edge, which the old rule could do, is the brush's
(`erase`) job.

## Acceptance criteria

- [ ] With the fake segmenter: two overlapping positive clicks, then a negative click inside both: the overlap leaves the
      Mask. A later positive click there adds it back.
- [ ] A negative click on an area a flood or a brush stroke made takes it away.
- [ ] A negative click at the same pixel as an earlier positive click reuses its pinned result: no new Runner call.
- [ ] The same on `layers`, for a Layer: the area leaves the Layer and the Plate's hole.
- [ ] Spec §6, masks and layers rows: say what a negative click does.

## Notes

The UI's preview and hint for the new rule are [0071](0071-m2-ui-shift-click-preview.md).
