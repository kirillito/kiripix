---
status: done
milestone: M3
agent: ui-engineer
type: ticket
---

# M3: finding your way around a room larger than the canvas

Spec §11. Found by the Owner in [0063](m2/0063-m2-multi-screen-source-trial.md), on 1024 x 320 and 640 x 528 rooms: zoomed in, they
found no way to move around the image. Dragging, arrow keys and scrollbars all did nothing.

## What's there today

All in `web/src/pixelCanvas.ts`.

- Holding `Space` and dragging, or dragging with the middle button, pans. No e2e test covers it.
- Only the mask and layer screens mention it, as "`Space` pans", which doesn't say to hold it and drag. The other screens say
  nothing.
- The wheel and `Z` zoom around the image's centre plus the pan, not around the pointer. So the detail under the pointer moves
  away as you zoom in, usually off the canvas.
- Zoom stops at 1x, so a room wider than the canvas never fits, and opens showing only its middle.
- Pan has no limit, so the image can be dragged out of sight, with no key to bring it back. Only changing Asset or toggling the
  game frame resets it.

## What to build

In `web/src/pixelCanvas.ts`, so every Stage's screen gets it:

- **Zoom about the pointer:** the wheel keeps the pixel under the pointer where it is. `Z` keeps the canvas's centre. Zoom stays
  integer.
- **Drag to pan:** a left drag that no tool takes, and that isn't on the split, pans. Tools keep the left button when they take
  the gesture, so the brush and clicks don't change. `Space` and the middle button still pan over a tool.
- **Arrow keys pan,** by a fixed distance in canvas pixels, faster with `Shift`. Not while typing in a field, and not during the
  walk test, which owns the arrow keys (`web/src/walkTest.ts`).
- **Scrollbars:** thin ones along the canvas's right and bottom edges, shown only when the image overflows on that axis, with a
  thumb that shows the visible part and can be dragged.
- **A limit on pan:** part of the image always stays on the canvas.
- **Reset:** `Home` returns to the fit view (zoom and pan).
- **The hint:** one line on every Stage's canvas screen, saying to hold `Space` and drag, plus the new keys. The mask and layer
  screens' lines change to match.

The game frame (`setGameFrame`) still draws at the image's top-left. Moving that frame around a wide room is not part of this
ticket, nor is a zoom below 1x, which would break the integer-zoom rule.

## Acceptance criteria

Playwright, on a room larger than the canvas:

- [x] A wheel step keeps the pixel under the pointer in place, to within one zoomed pixel.
- [x] A left drag on a screen with no tool under it moves the image; on the mask screen, the brush still paints and doesn't pan.
- [x] `Space` and drag, and a middle-button drag, move the image over a tool.
- [x] An arrow key moves the image; the same key in a text field or in the walk test doesn't.
- [x] Scrollbars appear only on an overflowing axis; dragging a thumb moves the image.
- [x] Panning far past an edge leaves part of the image on the canvas.
- [x] `Home` returns to the zoom and origin of the fit view.
- [x] Clicking a finding still centres its pixel, and clicks and brush strokes still land on the right pixel after zoom and pan.
