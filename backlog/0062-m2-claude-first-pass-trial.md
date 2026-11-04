---
status: todo
milestone: M2
agent: none
type: trial
parent: 0037-m2-layers-and-props.md
depends_on: [0036-m2-flood-does-nothing-on-a-painted-plate.md, 0059-m2-slow-click-to-segment.md, 0060-m2-room-border.md, 0061-m2-ui-room-border.md]
---

# M2: trial: does a Claude first pass save the Owner time?

Spec §2 (principle 3) and §14 (M4). Story 21 of [0037](0037-m2-layers-and-props.md). The Owner wants Claude's help in preparing
rooms, and asked to plan it around the time-per-room measure. The risk is that correcting a poor first pass takes longer than
doing the work by hand, so test that on a real room before building for it.

This needs no MCP: the CLI already does everything a first pass needs. It runs in a main session with the Owner, with no
subagent and no new code. If it needs a Command that doesn't exist, record that as the result rather than build it here.

## What to do

1. Take a real room of about the harbour's complexity that the Owner hasn't prepared. Import and fit it.
2. Claude does the first pass with the CLI and looks at the room through `kiripix preview`: `solid` and `pit` Masks by clicks,
   floods and the border, then Spawns and Exits. It works to a set token budget, agreed at the start.
3. Claude never accepts: `accept` stays the Owner's. A `needs-review` Stage waits for them.
4. The Owner corrects the room in the UI to a finish they'd ship, and notes their own total time.

## What to record, in this ticket

- The Owner's time on this room, against their time on the gate's hand-made reference room ([0058](0058-m2-gate.md)).
- How much of the first pass survived: Decisions kept against undone or added, from the journals.
- The tokens and money it cost, and where Claude went wrong: which object types, and which Commands were missing or awkward.
- A recommendation for M4: build on this, narrow it (for example to Markers only, or to a first `solid`), or drop it.

## Acceptance criteria

- [ ] One real room done this way, with the numbers above recorded.
- [ ] The Owner's call is recorded in the gate, [0058](0058-m2-gate.md).
