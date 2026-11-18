---
status: done
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

- [x] Golden or unit seam: two walkable areas split by `solid`, joined by a two-way Link, flood as one. With a one-way Link,
      only the forward side is reached from the back.
- [x] CLI seam: a room whose second area was `reach.unreachable_island` has no such finding once a Link joins it, and the
      report names the Link.
- [x] `reach` on the laneway-sized fixture stays within 10 % of its time without Links.

## Result

- **Op** (`kiripix/ops/reach.py`): `reachable(..., links=())` and `reachable_via(...)`, which also returns the indexes of the
  Links that took the flood somewhere new. A Link is `(from, to, two_way)`, both ends (x, y). When a drain of the queue ends,
  each Link direction whose source spot is flooded seeds its other end; this repeats until nothing new is seeded. It works
  with `step` (the filled-in spots count) and `dash`. Pure; `Link` and `reachable_via` are exported from `kiripix.ops`.
- **Stage** (`kiripix/recipes/room.py`): `reach` reads `links` from `markers.json` (and the Probe from the `link` Decisions).
  A one-way Link turns off the step-1 shortcut that reuses a flood for every Marker inside it. The report gains `links`
  (`id`, `kind`, `two_way`, `from`, `to`, `joins`, `reached`). New Checks: `reach.link_joins` (info, one per Link that joins
  ground the Body can't walk between) and `reach.unreachable_link` (error, the Link is outside the main group of Markers: no
  end flooded, or for a one-way Link not its `from` end). The Reachable Mask includes ground reached through Links, so
  export's navigation (walkable ∩ reachable) follows. The `reach` Stage is `version` 2 (ticket 0278), so a room
  built before, with Links, is stale and rebuilds. Spec §6.1 updated.
- **Tests:** `tests/golden/test_reach.py` (5 new, golden `reach_link_two_way.png`, 48 x 32, a 4 x 4 Footprint; a
  small mask, no review needed) and `tests/cli/test_reachability.py` (3 new, plus the describe test's list of Checks). The reach, probe and
  golden files pass; `uv run mypy` and `uv run lint-imports` pass.
- **Timing** (a 1120 x 624 room, 16 x 8 Footprint, 586,800 walkable spots, 9 runs, min / median seconds):

  | | step 1 | step 3 |
  |---|---|---|
  | before the change | 0.163 / 0.170 | 0.374 / 0.444 |
  | after, no Links | 0.164 / 0.171 | 0.385 / 0.440 |
  | after, Links that reach nothing new | 0.167 / 0.174 | 0.379 / 0.429 |
  | after, Links that open a second area (2.3 x the spots) | 0.378 / 0.390 | 0.873 / 0.996 |

  So the Op with no Links, or with Links to ground already reached, is within 2 % of its time before. A Link that opens
  more ground costs in proportion to the ground it floods (the flood has more to do), not in overhead. The fixture is
  synthetic (no laneway Mask is in the repo).
