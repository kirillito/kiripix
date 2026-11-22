---
status: done
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

## Result

- `web/src/waitingRooms.tsx`, shown under the district grid through `DistrictView`'s `extra`: it calls `to-paint --match <glob>`
  (writing to `.kiripix/previews/to-paint`, the one state folder the file route serves) and shows a tile per room it lists.
  **Copy prompt** copies the brief's prompt file (`to-paint`'s own output); **Open canvas** opens the canvas PNG of a room mid-`extend`;
  the file name to save as is `return_name`. A room with no brief or no prompt shows `to-paint`'s reason and fix.
- **A drop on a tile** is `import` for a room with no Source and `extend add` (with the side `to-paint` names) for one mid-`extend`.
  A room that now has one unpicked Variant still waits (`to-paint`'s rule); the lone Variant is the Owner's to pick.
- **Check the inbox** runs `inbox` and shows its summary, each file's outcome (imported, unmatched, ambiguous, failed), and the rooms
  with a lone Variant to pick, each opening its room on the Source Stage.
- Tests: `web/e2e/waiting-rooms.spec.ts` (tile and Copy prompt, a drop imports one Variant, Check the inbox).
- **Backend gap, not built:** "Dropping anywhere else on the view runs `inbox` on the dropped files by their names" needs `inbox`
  to take uploaded files (it reads a folder on disk only), or a Command that stores a file into the inbox folder. The UI holds no
  file-name rules, so it doesn't match names itself; a hint tells the Owner to drop on a tile or fill the inbox folder. A backend ticket
  should add a multipart `files` input to `inbox`.


**Review fixes (2026-11-20):** A drop on a tile no longer chooses between `import` and `extend add` in the UI (ADR 0008), and no longer skips the canvas record: it runs `inbox --file` into that room with the sides `to-paint` gave it.
