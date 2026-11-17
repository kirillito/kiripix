---
status: todo
milestone: M5
agent: ui-engineer
type: ticket
parent: 0255-m5-traversal-links.md
depends_on: [0265-m5-link-marker.md, 0266-m5-reach-through-links.md]
---

# M5: UI: draw a Link, and cross it in the walk test

Spec §11 (place, walk test). Part of [0255](0255-m5-traversal-links.md).

## What to build

- **On the place screen:** a Link tool. The first click sets `from` and the second `to`. It's drawn as a line with a dot at
  each end and an arrow when one-way. Edit `kind` and `two_way` in the Marker panel. `link.*` findings are shown at their end.
- **The walk test:** when the Body stands within a tile of a Link's end, a key moves it to the other end (respecting
  one-way), so the Owner can walk the room as the game will.
- The reach overlay shows ground reached through a Link in the reachable colour.

## Acceptance criteria

- [ ] Playwright: drawing a Link records one `link` Decision. In the walk test, the key at its `from` end puts the Body at
      `to`, and a one-way Link doesn't take it back.
- [ ] `npm run build` passes.
