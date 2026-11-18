---
status: done
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

- [x] Playwright: drawing a Link records one `link` Decision. In the walk test, the key at its `from` end puts the Body at
      `to`, and a one-way Link doesn't take it back.
- [x] `npm run build` passes.

## Result

- **Place screen:** `link` is a Type in the Marker panel (key `L`). A first click on the room sets `from` (shown as a dot, with a
  line to the pointer), the second sets `to` and records one `link` Decision (`id`, `from`, `to`, `kind`, `two_way`). Escape
  drops a first click. The Link is drawn as a line with a dot at each end and an arrow at `to` when one-way. Dragging an end
  records one `link` Decision of the same ID (a move); a click on an end selects it. `kind` and `two_way` are edited in the
  Marker panel and saved with "Save <id>". Links are listed under "Links". `link.*` findings with a position ring their end on
  the canvas, and show in the usual findings list. Code: `web/src/markerTool.ts` (`Link`, link drawing and gestures),
  `web/src/roomScreens.tsx` (panel), `web/src/App.tsx` (`decideLink`).
- **Walk test:** `C` moves the Body to the other end of the nearest Link with an end within reach; a one-way Link only works
  from its `from` end (`crossFrom` in `web/src/walkTest.ts`). On the reach screen a Link whose report entry says
  `reached: false` is drawn in the unreachable colour. The reach overlay's ground through a Link is the backend's Reachable Mask
  (0266); the UI draws nothing of its own.
- **Gap for a backend ticket:** no Command gives the UI `project.tile` (not in `show`, `status` or `describe`), so "within a tile"
  uses a constant, `LINK_REACH = 16` (the default tile) in `walkTest.ts`. A Project with another tile needs `show` to carry it.
- **Tests:** `web/e2e/links.spec.ts` (2 flows: draw a one-way Link and cross it, no way back; edit a Link in the panel, then
  cross a two-way Link both ways). `npm run build` passes. Screenshots: `web/test-results/place-link.png`,
  `web/test-results/reach-link-walk.png`.
