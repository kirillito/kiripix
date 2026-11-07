---
status: todo
milestone: M3
agent: ui-engineer
type: ticket
depends_on: [0091-m3-remove-a-layer.md, 0083-m3-ui-show-that-work-is-happening.md]
---

# M3: the layer screen says what a click will do, and can remove a Layer

Spec §11. Found by the Owner at the [M2 gate](m2/0058-m2-gate.md), on `room.ch01_dungeon_r03`: "It's hard to understand how a lifted object
is extracted into a layer. Clicking an object and renaming a layer, or adding a new layer, doesn't seem to do anything", until "almost
a minute later the list of layers suddenly gets updated with layers that I was aimlessly lifting to see if it's working at all".

[0083](0083-m3-ui-show-that-work-is-happening.md) shows that work is running, and [0089](0089-m3-time-a-lift-honestly.md) looks at why a
lift is slow. This ticket is about the screen's model: which Layer a click goes to, and what happened to it.

## What to build

- **The Layer a click goes to is always visible:** named on the canvas cursor or beside it, not only selected in a list.
- **Adding or renaming a Layer shows at once** in the list, marked as having no pixels until its first lift lands, so the Owner
  doesn't add it again.
- **Each Layer in the list shows its state:** lifting, lifted (with its pixel count), or empty.
- **A click's result is shown against the click:** when the lift lands, the new pixels flash in the Layer's colour.
- **Remove a Layer** from the list, with [0091](0091-m3-remove-a-layer.md)'s Decision; undo brings it back.

## Acceptance criteria

Playwright, against a real `kiripix serve`:

- [ ] A new Layer shows in the list before its first lift lands, and a click is drawn as going to it.
- [ ] After a lift, the list shows the Layer's pixel count, and the new pixels are marked on the canvas.
- [ ] Removing a Layer takes it out of the list and the canvas, and undo brings it back.
