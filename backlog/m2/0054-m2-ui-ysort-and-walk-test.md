---
status: done
milestone: M2
agent: ui-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0045-m2-palette-with-layers.md, 0046-m2-ysort-lines.md]
---

# M2: y-sort lines per Layer, and Layers in the walk test

Spec §6.1 (Walk test), §11 (Place). Story 10 of [0037](0037-m2-layers-and-props.md). Follows D3 in [0037](0037-m2-layers-and-props.md).

## What to build

- The place screen: a `ysort` line chooses its Layer, an "always above" toggle per Layer, and the Layer shown while its line
  is drawn. `layer.no_ysort` findings jump to it.
- The walk test: the mapped Layers drawn over or under the Body, from the sort position in Command outputs, never worked out
  in the UI. Don't change the dash rule in `walkTest.ts`.

## Acceptance criteria

- [x] Playwright: drawing a line for a Layer records one Decision naming that Layer; the toggle records one.
- [x] Playwright: in the walk test, the Body north of a line is drawn under the Layer, and south of it over the Layer; an
      "always above" Layer is over in both.

## Notes

- Place screen (`web/src/roomScreens.tsx`): a `ysort` type shows a Layer dropdown, and the line is one `marker` Decision carrying
  `layer`. A "Layers" list shows each Layer with an "always above" checkbox (one `above` Decision per toggle) and its sort
  position as `show`'s `place.sort` gives it. The chosen Layer is washed over the image (`LayerHighlight`, `web/src/sortView.ts`)
  while a line is drawn. A `layer.no_ysort` finding (its position names `layer.<id>.png`) jumps to the place screen with that
  Layer chosen and the type on `ysort`.
- The Layer list is the Layer files of `palette` (else `layers`): read from the Stages' `outputs`, not `layers.json`, so the
  place screen lists Layers before `palette` is built.
- Walk test (`web/src/walkTest.ts`, `ReachPanel`): the Layer images come from `palette`'s `layer.<id>.png`, the sort from
  `place.sort`. A Layer is drawn over the Body when `above` or when the Body's y is smaller than the line's `y`; on the line the
  Body is in front. The Body's y is its footprint's middle, the same point the game's actor origin must be (see the Notes of
  [0047](0047-m2-export-room-layers.md)). The
  dash rule is untouched, and a changed sort doesn't send the Body back to the Spawn. The canvas carries `data-layers-over`.
- `data-layer-shown` on the canvas names the Layer washed on the place screen.
- E2E: `web/e2e/ysort.spec.ts` (3 flows) and `layeredRoom` in `harness.ts` (two Layers from a Plate image, no Runner call).
  `place.spec.ts` "a y-sort line is drawn with a drag" now chooses a Layer.
- A `ysort` with no `layer` can't be made from the UI; a legacy one shows without "for <layer>" and `ysort.no_layer` reports it.
