---
status: done
milestone: M5
type: spec
parent: 0236-m5-the-games-next-needs.md
---

# M5: traversal Links: a Marker with two ends, for a hop, a climb or a jump

Spec §6.1 (place, reach), §9 (Room). Part of [0236](0236-m5-the-games-next-needs.md), item 6. The game's DEC-019 (collision
stays flat) and `docs/MILESTONE_PLANS.md` M10-04 ("content: traversal Markers reachable").

## Problem Statement

The game's tunnels (its M10) have context actions at marked spots: a hop down from the platform edge to the track level, a
climb back up, and a gap jump. They're short scripted moves, and collision stays flat. Kiripix has no Marker with two ends.
`reach` reports the ground on the far side of a hop as an unreachable island, which it isn't.

## Solution (the direction)

- **A Link** (the glossary gets it with [0265](0265-m5-link-marker.md)). It's a Marker with two ends on one Room: `from`
  and `to` (points), a `kind` (`hop`, `climb`, `jump`, or free text, like an Area's ID, with no meaning in Kiripix), and
  `two_way` (default true). Not an Exit: an Exit leads to another Room.
- **`place` checks:** both ends inside the room and on walkable ground (the Body's footprint fits). A unique ID, as for every
  Marker.
- **`reach`:** a Link joins its two ends in the flood (one way or both). Ground reachable only through a Link is reachable,
  and the report names the Link. A Link whose end isn't reachable from any Spawn or Exit is reported as other Markers are.
- **Export:** a `Node2D` named by the Link's ID with two `Marker2D` children, `from` and `to`, and metadata `kiripix_id`,
  `kiripix_type = "link"`, `kind` and `two_way`. `room.json` gets `links` (bump its `schema_version`). The ID is frozen
  once exported.
- **The UI:** draw a Link on the place screen as two clicks, with an arrow for a one-way Link. The walk test jumps the Body
  across it on a key.

## Open

- Whether a Look can add a Link (a ladder put down). That waits for [0254](0254-m5-looks-markers-combining-and-reach.md) and
  for a room that needs it.

## Order

[0265](0265-m5-link-marker.md) the Marker on `place` (core), [0266](0266-m5-reach-through-links.md) `reach` through Links
(imaging), [0267](0267-m5-export-links.md) export, [0268](0268-m5-ui-draw-a-link.md) the UI and the walk test.

## Result (2026-11-18)

Closed: its work tickets [0265](0265-m5-link-marker.md), [0266](0266-m5-reach-through-links.md),
[0267](0267-m5-export-links.md) and [0268](0268-m5-ui-draw-a-link.md) are done. The open question (a Look adding a Link)
moves to [0254](0254-m5-looks-markers-combining-and-reach.md) and its ADR draft [0269](0269-m5-adr-looks-markers-combining-reach.md).
