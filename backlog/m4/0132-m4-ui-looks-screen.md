---
status: done
milestone: M4
agent: ui-engineer
type: ticket
parent: 0127-m4-room-looks.md
---

# M4: the looks screen

Spec §6.1 (Looks) and §11; ADR 0009. Needs [0130](0130-m4-looks-stage.md). Follows M3's usability work
([0092](../m3/0092-m3-ui-layer-screen-legible.md), [0093](../m3/0093-m3-ui-findings-a-person-can-read.md)), so build on what those set.

## What to build

- A list of the room's Looks, each with its ID and its Condition when it has one, and the drag-and-drop import of an edit.
- A toggle between the room and the Look, at integer zoom, so the Owner sees exactly what the game will switch.
- Region by polygon and brush, and `difference` with a box and a tolerance slider, previewed before it is recorded.
- `look.drift`'s boxes drawn on the canvas, and clicking the finding goes to them.
- The Look's `solid` painted as on the masks screen.

Every action is one Command, as everywhere else.

## Acceptance criteria

- [x] Playwright: import an edit, name the Look, draw a region, and see the toggle change only the region.
- [x] A drift finding's box shows on the canvas.

## Result

- **The screen** (`web/src/lookScreen.tsx`, `web/src/lookTool.ts`; wired in `App.tsx`): the room's `looks` Stage. A list of the Looks
  (ID, Condition, "no region", changed pixels, drift count; keys 1 to 9), a "New Look" ID field with import by file or by dropping a PNG
  on the canvas, a Condition field (one `look` Decision), the Room/Look toggle (`V`, integer zoom, nearest-neighbour: the Look's pieces
  are laid over the `palette` picture at their `box`), region tools (Brush `B`, Erase `E`, Polygon `G`, Erase polygon `X`, Difference
  `D`), the targets Region (`R`) and Solid (`S`), `look.drift`'s boxes drawn dashed on the canvas (the finding jumps to the largest),
  and the Look's `solid` painted like a Mask (a Look with none shows the room's). Each gesture is one `decide`; a rebuild runs after it
  while "Rebuild the Looks" is on (a Look calls no Runner).
- **Reuse:** the region tools are `MaskTool` with the Mask names `region` and `solid`; `LookTool` adds the toggle, the drift boxes and the
  difference box. Ticket 0191 can map its gestures to its own Decisions the same way.
- **Gaps for a backend ticket.**
  1. *No Probe previews a `difference`.* The yellow preview is a rough client-side comparison of the edit (scaled to the room's size)
     with the mapped room, on the 3x3 mean in OKLab; the Stage measures the fitted images before the palette and drops specks, so its
     region differs. A `look-difference` Probe (box, tolerance, specks -> runs) would make it exact, and removes the client maths.
  2. *No Command lists a Look's edit Variants,* so the screen can't offer picking an older edit; an import stores the edit and picks it,
     two Commands for one drop (`import --look`, then `pick --look`).
  3. The `solid` base for a Look without its own comes from the `masks` Stage's `solid.png` through the `/files` route.
