---
status: done
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

- [x] CLI seam: `show` carries the tile, and a body's `show` its Wearables; a character's `sheet` writes `depth.png`; the
      finding's data lists the worst frames with their boxes. Contract samples updated.
- [x] `uv run lint-imports` and `uv run mypy` pass.

## Result

- **Tile:** `show`'s `data.tile` (int, px, `project.tile`). Replaces `LINK_REACH` in `web/src/walkTest.ts`.
- **Wearables:** `show`'s `data.wearables`, a list of `{asset, order}` sorted by (`order`, ID); `order` is the Wearable's `sheet`
  parameter. Empty for an Asset with none. Replaces `useWearables`' scan of every Asset's `show` (`web/src/wearableScreens.tsx`).
- **`depth.png`:** a character's `sheet` writes `work/sheet/depth.png` (16 bit gray, 65535 where a cell has no frame pixel) in the
  layout of `color.png`, and `sheet.json` has `files.depth`; no `order` (a body is 0). Same encoding as a Wearable's. The UI can read
  the body's depth from the atlas at each `rect` instead of placing `render`'s depth frames by the pivot. **`sheet` `version` 1 to 2**
  (and `render` is now one of its upstream Stages, so it is stale on every character once).
- **`wearable.stack_differs`:** `Finding` gets an optional `data` object (left out of the JSON when empty; the contract schema
  has it). For this code: `{clip, differing, shown, worst: [{direction, frame, differing, box: {x, y, width, height}}]}`, the worst
  three frames, worst first; `position` is still the first one's box. No Stage version change.
- Code: `kiripix/commands/show.py`, `kiripix/checks/finding.py`, `kiripix/checks/stack.py`, `kiripix/recipes/wearable_sheet.py`
  (`run_body_sheet`, `add_depth_atlas`), `kiripix/recipes/character.py`. Tests: `tests/cli/test_read_gaps.py` (4), contract sample in
  `test_a_wearable_validates`.

### Review fixes (2026-11-18, main session)

- The walk test reads the Link reach from `show.tile` (`Crossings.reach`). `useWearables` still reads each Wearable: left for
  [0299](0299-m5-ui-portrait-and-wearable-follow-ups.md).
- No `sheet.json` `schema_version` bump for `files.depth` (the Owner, 2026-11-18): the `sheet` Stage's `version` bump already
  rebuilds every old one, and the Wearable's `sheet.json` carries the key at 1.
