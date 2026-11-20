---
status: todo
milestone: M6
agent: ui-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0330-m6-ui-district-view.md, 0349-m6-to-paint-pack.md, 0350-m6-source-inbox.md]
---

# M6: UI: a district's rooms waiting for a Source

Spec §11 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Adds to the district view
([0330](0330-m6-ui-district-view.md)); no logic of its own.

## What to build

- In the district view, the rooms waiting on a Source are shown as an empty tile, each with **Copy prompt** (the brief's
  prompt, to the clipboard), **Open canvas** (for a room mid-`extend`), and the file name to save the result as.
- **Drop an image on a tile** to import it to that room (the `import` or `extend add` that `inbox` would run). Dropping
  anywhere else on the view runs `inbox` on the dropped files by their names.
- A **"Check the inbox"** button runs `inbox` and shows its result: imported, unmatched, and rooms with a lone Variant to pick.

## Acceptance criteria

- [ ] Playwright against a real `kiripix serve`: a district with a room without a Source shows its tile; Copy prompt copies
      the brief's prompt; dropping a PNG on the tile imports one Variant.
- [ ] `npm run build` passes.
