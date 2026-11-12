---
status: todo
milestone: M4
agent: ui-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0185-m4-emitter-shape-direction-colours.md, 0139-m4-ui-draw-an-area.md]
---

# M4: draw an emitter's shape and direction, and pick its colours

Part of [0183](0183-m4-ambient-animation.md), route (a). Spec §11 (the place screen). Doesn't depend on the trial (0184).

## What to build

On the place screen, with an emitter Marker selected:
- **Shape:** a choice of point, line, box or polygon, drawn on the canvas with the area tool's box (0139) and the polygon
  tool's clicks (0080). Drag to move the shape with its Marker; drag a corner or point to change it.
- **Direction:** drag an arrow from the Marker; its end is the `direction` point. Shown as an arrow with its length in px.
- **Colours:** an eyedropper on the room (each click adds the pixel's colour) and a palette swatch grid; a strip of the
  chosen colours, reorderable, with remove. Off-palette is impossible from either tool.
- **Preview:** the shape filled at low opacity in a colour of the list, and a few still dots along the arrow in the chosen
  colours, so the Owner sees where particles start and go. No motion: the particles are the game's.
- Every change is one `marker` Decision through the Command, so `undo` works as for other Markers.

## Acceptance criteria

- [ ] Playwright against `kiripix serve`: draw a box emitter, a direction and two colours; `room.json` after `place` has them.
- [ ] `undo` restores the previous shape; moving the Marker moves its shape and arrow.
- [ ] The Owner sets the kitchen cup's emitter (shape, upward arrow, steam colours) in under 2 minutes, timed and recorded here.

Budget: 100–180k tokens.
