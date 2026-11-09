---
status: todo
milestone: M4
agent: qa-engineer
type: ticket
parent: 0127-m4-rooms-for-grid-battles.md
depends_on: [0131-m4-area-marker.md, 0132-m4-export-area.md, 0134-m4-export-masks-and-room-json.md, 0130-m4-extend-commands.md]
---

# M4: the agent acceptance test takes a room with an area

Spec §14 (the agent acceptance test). It's run at the gate, not in CI.

## What to change

- The stand-in Owner's fixture adds an `area` Marker (`battle.test`, cell 32) to the room, so the agent has to place it from
  `describe`, `next` and `check` output alone, and clear `area.no_walkable` if the fixture puts it wrong first.
- The room is two pieces joined with `extend`, from fixture pieces, before `import`.
- The run checks that the export has the `Area2D`, `masks/solid.png` and `room.json`.

## Acceptance criteria

- [ ] The harness runs the new steps on the fake Runners.
- [ ] The token count is recorded at the gate, against M3's.

Budget: 100–200k tokens to prepare, plus the run at the gate.
