---
status: todo
milestone: M5
agent: core-engineer
type: ticket
parent: 0255-m5-traversal-links.md
---

# M5: the Link Marker on `place`

Part of [0255](0255-m5-traversal-links.md). `reach` through a Link is [0266](0266-m5-reach-through-links.md).

## What to build

- **A `link` Decision on `place`:** an ID (unique among the room's Markers), `from` and `to` (points in target pixels),
  `kind` (free text, snake_case; `hop`, `climb` and `jump` named in `describe` as examples), and `two_way` (default true).
  `remove` and `rename` like other Markers. The ID is frozen once exported.
- **Checks:** `link.outside` (an end outside the room, error), `link.not_walkable` (an end where the Body's footprint doesn't
  fit, error, naming the end), and `link.same_place` (the ends closer than one tile, warning).
- `show` lists Links with the other Markers. `place.json` carries them, and its `schema_version` is bumped.
- The glossary gets **Link**: _a Marker with two ends on one Room, where an actor crosses by a scripted move (a hop, a
  climb, a jump)_. _Avoid_: portal, traversal, jump point (and Exit, which leads to another Room).

## Acceptance criteria

- [ ] CLI seam: a Link between two walkable spots is recorded and shown. An end on `solid` raises `link.not_walkable`, and an
      end past the room's edge raises `link.outside`.
- [ ] Contract sample for the Decision. Spec §6.1 (`place`) lists Links.
