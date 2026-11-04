---
status: todo
milestone: M2
agent: imaging-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0043-m2-layers-stage.md]
---

# M2: y-sort lines bound to Layers, and "always above"

Spec §6.1 (place), §9. Story 9 of [0037](0037-m2-layers-and-props.md). Follows D3 in [0037](0037-m2-layers-and-props.md).

## The gap

The `ysort` Marker ([room.py:511](../kiripix/recipes/room.py#L511)) has `x2` and `y2` but doesn't say which Layer it sorts.
"Always above" exists nowhere.

## What to build

- `ysort` gains a required `layer`. A `ysort` already in a journal, without one, still replays: `place` keeps it, and a
  warning finding says it sorts no Layer, with an `owner_action`.
- An `above` Decision on `place`: `{layer, above}`.
- `place` gains `layers` as an upstream, after `palette` (the first upstream with an image stays `palette`).
- `layer.no_ysort`, in `_check_place`: every foreground Layer has a line or the flag; `owner_action` names the Layer. A line
  or flag naming an unknown Layer is its own finding.
- The sort position per D3, written into `markers.json` or a sibling file, so the walk test and the Exporter read one number
  and never work it out twice.

## Acceptance criteria

- [ ] A room with a Layer and no line fails `layer.no_ysort`, exit 2 from `check`; adding a line or the flag clears it.
- [ ] A room with no Layers passes, and its existing `ysort` Markers give the warning only.
- [ ] A `ysort` without `layer` from `decide` is refused with `decision.invalid`.
- [ ] `show` gives the sort position of each Layer.
