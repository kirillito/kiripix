---
status: todo
milestone: M5
agent: imaging-engineer
type: trial
parent: 0236-m5-the-games-next-needs.md
---

# M5: trial: can Kiripix suggest a room's foreground Layers?

Spec §6.1 (`layers`), §1 (goal 2). Prototype code stays in `backlog/m5/0286-trial/`, not in `kiripix/`. Runs without the
Owner until the last step.

## Why

On the laneway, `layers` was 9.2 of the Owner's 19.2 minutes in the UI. After Claude's first pass, the Owner added two Layers
for the poles, which the first pass couldn't know to lift. A foreground object is one an actor can walk behind: tall, standing
on walkable ground, with `solid` at its foot and not over its top. Masks and the painting may be enough to find most of them.

## What to do

1. On the built ch01 rooms in the art Project, read-only (the laneway, the dungeon rooms; not `harbor_front`), take the
   Owner's own foreground Layers as the answer key.
2. Prototype a suggester from what Kiripix already has:
   - from `solid`: the components whose painted object extends above them, using a colour region grown up from the foot (the
     flood Op) or SAM 2 with a box over the component;
   - from the painting: tall thin objects (poles, lamps) with SAM 2 automatic masks.
3. Score it against the key: how many of the Owner's Layers it finds (IoU over 0.7), and how many false ones it suggests per
   room.
4. If it finds most of them with few false ones, write up what a Probe (`probe layer-suggest`) would return: boxes and the
   `box` Decisions to record, which the Owner accepts or ignores in the UI.

## What to record, in this ticket

- The score per room and method, with overlays (suggested against the Owner's) at 1x, and their paths.
- The time per room and VRAM.
- A recommendation: a Probe ticket (with its agent), or "not worth it", with why. The Owner's view of the overlays is the
  only Owner step.

## Acceptance criteria

- [ ] The scores and overlays above, on at least three rooms.
- [ ] The recommendation and the Owner's choice recorded. If yes, the Probe ticket filed.
