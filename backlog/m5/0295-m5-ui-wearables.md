---
status: done
milestone: M5
agent: ui-engineer
type: ticket
parent: 0152-m5-character-layers.md
depends_on: [0293-m5-wearable-sheet-and-export.md, 0294-m5-wearable-stack-check.md]
---

# M5: UI: a character's Wearables, and a stack preview

Part of [0152](0152-m5-character-layers.md). From the trial [0153](0153-m5-character-layer-trial.md)'s Results and the Owner's answers (2026-11-18).

## What to build

- The status board shows a Wearable under its body.
- A stack preview on the body's `sheet` screen: the body with chosen Wearables at 4x, played by clip and direction, stacked by
  `order` or by depth (a toggle), with the `wearable.stack_differs` boxes.
- Each Wearable's cost beside it: render seconds and atlas size.

## Acceptance criteria

- [x] Playwright: a fixture body with two Wearables shows both in the preview, and the toggle changes the stacking.
- [x] `npm run build` passes.

## Result

- **Board** (`web/src/components.tsx`, `StatusBoard`): a Wearable is listed under its body's row (indented, `board-<id>` with `data-body`),
  with its cost beside it (`cost-<id>`: `render 0.1 s`, `atlas 234 x 234 px`). A Wearable whose body isn't on the board (filtered
  out, or unknown) stays in its own `wearable` section. The body of each Wearable is `show`'s `params.body`.
- **Stack preview** (`web/src/wearableScreens.tsx`, `StackPreview`, under the body's `sheet` screen in `App.tsx`): the body and the
  chosen Wearables (a checkbox each, with its `order` and cost) at 4x, `image-rendering: pixelated`, by Clip and Direction, with
  Play. A toggle, `By order` / `By depth`. Order: the body first, then the Wearables by `order` and ID. Depth: per pixel, the nearest
  depth wins, a tie to the later (the rule of `kiripix/ops/stack.py`), computed client-side from the depth atlases; a 16 bit gray PNG is
  decoded in the UI (a `<canvas>` would cut it to 8 bit). The `wearable.stack_differs` findings of the body (from `check`) are listed
  with a "Show the worst frame" button, and the worst frame's box (the finding's `position`) is drawn on it.
- **Read through:** `status`, `show`, `check`, and the file route only (`sheet.json`, `render.json`, atlases, depth frames). No Command
  is added or changed, and nothing is sent.
- **What the backend doesn't give (worked around, no backend ticket needed to ship this):**
  - The body's `sheet` has no depth atlas (only a Wearable's does). The body's depth is read from its `render` frames
    (`files.depth` in `render.json`) and put in the cell as `sheet` puts the colour frame (the frame's pivot, rounded, on the cell's
    pivot). If the body's `sheet` ever gets a `depth.png`, the preview should read that instead.
  - A body's Wearables aren't listed by any Command: the UI takes the Wearables from `status` and reads each one's `show`
    (`params.body`). Fine for a few Wearables; a `show` field `wearables` on a body would save the calls.
  - `wearable.stack_differs` gives the three worst frames' boxes only in its message text; its `position` is the worst frame's box, which
    is the one drawn. The other two boxes would need a structured field.
- **Test:** `web/e2e/wearables.spec.ts` (3 flows, on the fake Blender of tests/fixtures: the board with cost; a body with two Wearables
  in the preview, the toggle changing the stacking, a Wearable taken off; the stack Check's box on the worst frame). The test writes the
  Wearables' atlases and depth frames itself, since the fake renders flat frames of one colour. `npm run build` passes.
- Screenshots: `web/test-results/wearables-board.png`, `wearables-stack.png`, `wearables-stack-differs.png`.
