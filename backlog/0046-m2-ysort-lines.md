---
status: done
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

- [x] A room with a Layer and no line fails `layer.no_ysort`, exit 2 from `check`; adding a line or the flag clears it.
- [x] A room with no Layers passes, and its existing `ysort` Markers give the warning only.
- [x] A `ysort` without `layer` from `decide` is refused with `decision.invalid`.
- [x] `show` gives the sort position of each Layer.

## Notes

- The sort position is in `work/place/markers.json` under `sort`, one entry per Layer: `{layer, above, marker, y, slope}`.
  `y` is the line's mean y rounded half up, `(y + y2 + 1) // 2`; `None` when the Layer is `above` or has neither line nor
  flag. `above` wins over a line on the same Layer. `show` gives the same list per Stage as `sort` (from the Decisions
  alone, so a Layer with no line or flag isn't listed there).
- New findings: `ysort.no_layer` (warning, a legacy line), `ysort.sloped` (warning, ends more than half a tile apart),
  `ysort.unknown_layer` (error). `place` now also depends on `project.tile` and on `layers`.
- Only the first line placed on a Layer sorts it; a later one on the same Layer is ignored without a finding (open question).
- After review (2026-11-05): `markers.json` carries `schema_version` 1, and its readers refuse an older file, naming the
  rebuild. A sort position is a typed `SortPosition`. A second line on one Layer gives the warning `ysort.extra_line`.
