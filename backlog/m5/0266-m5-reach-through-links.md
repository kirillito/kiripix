---
status: todo
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0255-m5-traversal-links.md
depends_on: [0265-m5-link-marker.md]
---

# M5: `reach` crosses Links

Part of [0255](0255-m5-traversal-links.md). Spec §6.1 (`reach`), §7 (reach Ops).

## What to build

- **The Op:** the footprint flood takes a list of links, each a pair of points and a direction. When the flood reaches one
  end of a Link (the end's footprint cell is in the flooded set), it seeds the other end, and for a two-way Link the reverse.
  It repeats until nothing new is reached. It stays pure, with the existing step size.
- **`reach`:** passes the room's Links. Ground reached only through a Link is reachable. The report names, for each island
  that a Link joins, the Link that does it (info). A Link whose `from` end is unreachable is listed with the unreachable
  Markers. A one-way Link's `to` end may be a dead end, and that's fine.
- The exported `NavigationPolygon` stays walkable ∩ reachable, now including ground reachable through Links. The game moves
  the actor across a Link by script, not by navigation.

## Acceptance criteria

- [ ] Golden or unit seam: two walkable areas split by `solid`, joined by a two-way Link, flood as one. With a one-way Link,
      only the forward side is reached from the back.
- [ ] CLI seam: a room whose second area was `reach.unreachable_island` has no such finding once a Link joins it, and the
      report names the Link.
- [ ] `reach` on the laneway-sized fixture stays within 10 % of its time without Links.
