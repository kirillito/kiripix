---
status: todo
milestone: M5
agent: godot-export
type: ticket
parent: 0255-m5-traversal-links.md
depends_on: [0265-m5-link-marker.md]
---

# M5: export Links

Spec §9 (Room). Part of [0255](0255-m5-traversal-links.md).

## What to build

- In the room's scene, a `Links` node with one `Node2D` per Link, named by its ID, holding two `Marker2D` children, `from` and
  `to`, at the ends. The Link's node has metadata `kiripix_id`, `kiripix_type = "link"`, `kind` and `two_way`.
- `room.json` (bump `schema_version`) gets `links`: ID, kind, `from`, `to`, `two_way`.
- The Manifest lists the Link IDs in their own list, frozen once exported.

## Acceptance criteria

- [ ] CLI seam: a room with a one-way and a two-way Link exports both nodes, with their metadata and ends, and `room.json`
      lists both.
- [ ] A rename of an exported Link is refused.
- [ ] Spec §9's Room row describes Links.
