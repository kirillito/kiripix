---
status: done
milestone: M5
agent: ui-engineer
type: ticket
parent: 0254-m5-looks-markers-combining-and-reach.md
depends_on: [0314-m5-look-markers-on-place.md, 0315-m5-reach-per-look.md, 0316-m5-export-look-markers-collision-navigation.md]
---

# M5: the UI for a Look's Markers, and `reach` and the walk test per Look

[ADR 0013](../../docs/adr/0013-a-look-has-its-own-markers-collision-and-reach.md), Consequences ("The UI"). Part of
[0254](0254-m5-looks-markers-combining-and-reach.md).

## What to build

- **`place`:** a light, emitter or interactable can be given a Look (or none), and a Marker in a Look is drawn only while
  that Look is chosen. The Command's refusals (`marker.look_type`, `marker.unknown_look`) show as findings.
- **`reach` view:** a Look picker (none, or each Look with its own `solid`) that draws that Look's reachable, its islands
  and its findings from `report.json`.
- **Walk test:** walks the room with a chosen Look's collision (the room's `solid` with the Look's change) and shows its
  Markers.
- No logic in the UI: it reads the Command results and the built files.

## Acceptance criteria

- [x] Playwright against a real `kiripix serve`: give a light a Look on `place`; it shows with that Look chosen and hides
      without it.
- [x] The `reach` view, with a fixture Look chosen that erases a wall, shows the yard reachable; without it, an island.
- [x] The walk test with that Look chosen walks through the cleared opening; without it, the wall stops it.
- [x] `npm run build` passes.

## Result

- **`place`.** A Look picker (`marker-look`) on the Marker form for a light, emitter or interactable, from `show.looks`; a new
  Marker or a saved one (Save) goes out in one `marker` Decision with `look`, left out for none. A "Show Look" picker
  (`place-look-view`) chooses which Look's Markers are drawn and listed with the room's own; choosing a Marker's Look shows it.
  A refusal (`marker.look_type`, `marker.unknown_look`) comes back from `decide` and shows as the usual finding. Files:
  `web/src/roomScreens.tsx`.
- **`reach`.** A Look picker (`reach-look`: none, or each Look in `report.json`'s `looks`) reads `report.json` and draws the room's
  or the Look's `reachable.png` tinted, its islands boxed, and lists the islands (with `added` for a Look) and the unreachable
  Markers from the entry. New `web/src/reachOverlay.ts`. The Look's own Markers are drawn only while it is chosen.
- **Walk test.** With a Look chosen it reads `place`'s `looks/<look>/walkable.png` and `clear.png`, the same source it reads for the
  room (`place`'s files, not `export`'s masks), and swaps them under the Body, which stays where it is. The paths are built beside
  the room's files because `show`'s `outputs` lists only top-level files; the file route serves them.
- **No backend change.** Nothing was missing from the Commands.
- **Tests.** `web/e2e/look-markers.spec.ts` (four, one per criterion and the refusal). Screenshots in `web/test-results/`:
  `look-markers-place-shown.png`, `look-markers-place-hidden.png`, `look-markers-reach-room.png`, `look-markers-reach-look.png`,
  `look-markers-walk-look.png`.
