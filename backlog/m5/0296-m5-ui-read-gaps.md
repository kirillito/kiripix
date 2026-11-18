---
status: todo
milestone: M5
agent: core-engineer
type: ticket
---

# M5: what the UI had to work around: the tile, a body's Wearables, the body's depth atlas, a finding's boxes

Found by the UI tickets of the 2026-11-18 batch, each worked around in `web/`. Each is a read the UI should get from a
Command, not compute.

## What to build

- **The Project's tile** in `show` (or `describe project`): the walk test's "within a tile" of a Link's end uses a constant 16
  (`LINK_REACH` in `web/src/walkTest.ts`, [0268](0268-m5-ui-draw-a-link.md)).
- **A body's Wearables** in its `show` (`wearables`: IDs with their `order`): the UI reads every Asset's `show` to find them
  (`useWearables` in `web/src/wearableScreens.tsx`, [0295](0295-m5-ui-wearables.md)).
- **`depth.png` on a character's `sheet`**, in the sheet's layout, as a Wearable's `sheet` has
  ([0293](0293-m5-wearable-sheet-and-export.md)): the UI places the body's `render` depth frames into cells by the pivot itself.
  A change to `sheet`'s outputs: bump its `version`.
- **`wearable.stack_differs`'s worst frames** as data (frame and box each), not only in the message: the preview draws only
  `position`, the worst one ([0294](0294-m5-wearable-stack-check.md)).

Then the UI drops each workaround (a `ui-engineer` ticket, or this one's follow-up).

## Acceptance criteria

- [ ] CLI seam: `show` carries the tile, and a body's `show` its Wearables; a character's `sheet` writes `depth.png`; the
      finding's data lists the worst frames with their boxes. Contract samples updated.
- [ ] `uv run lint-imports` and `uv run mypy` pass.
