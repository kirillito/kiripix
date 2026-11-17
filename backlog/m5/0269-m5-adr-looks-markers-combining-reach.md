---
status: todo
milestone: M5
agent: reviewer
type: ticket
parent: 0254-m5-looks-markers-combining-and-reach.md
---

# M5: ADR draft: a Look's Markers, two Looks at once, and `reach` per Look

Part of [0254](0254-m5-looks-markers-combining-and-reach.md). The spec ticket's four proposals become one ADR amending
[ADR 0009](../../docs/adr/0009-a-rooms-looks-are-a-stage-on-the-room.md), for the Owner to accept or change. The work
tickets are written from the accepted ADR, not before it.

## What to do

- Draft `docs/adr/0013-...` (the next number): the context (the laneway's yard behind its gate, the game's M10 R6), the four
  decisions as 0254 proposes them, and their consequences:
  - `place.json`'s, `reach.json`'s and `room.json`'s formats and `schema_version` bumps;
  - the Manifest's ID lists;
  - what the game has to do (swap collision and navigation, enable a Look's lights);
  - what stays open (soft edges).
- Fix spec §6.1 and §16 decision 8 where they say a Look can't take collision away (the code lets a Look's `solid` erase).
- Once the Owner has accepted the ADR, write the work tickets 0254's "Order" lists, each with its agent, acceptance criteria
  at the CLI seam, and `depends_on`. Writing them is this ticket's last step (the reviewer splits specs into tickets).

## Acceptance criteria

- [ ] The ADR drafted as `proposed`, with the spec's stale sentences fixed.
- [ ] The Owner's acceptance recorded in the ADR (the Owner's, not the agent's).
- [ ] The work tickets filed from the accepted ADR, and listed in 0254 and 0236.
