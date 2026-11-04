---
status: todo
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

- [ ] Playwright: drawing a line for a Layer records one Decision naming that Layer; the toggle records one.
- [ ] Playwright: in the walk test, the Body north of a line is drawn under the Layer, and south of it over the Layer; an
      "always above" Layer is over in both.
