---
status: todo
milestone: M1
agent: qa-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0022-m1-export-ownership-and-id-freeze.md]
---

# M1: the agent acceptance test harness

Spec §14 (the agent acceptance test). User story 33 of [0010](0010-m1-room-end-to-end.md).

## What to build

- A harness, outside CI, that starts an agent on a cheap model with a fixed token budget, in a fresh Project with an
  imported room image and an empty temporary Godot project, with the task "take this room from `import` to `export`".
  The agent sees only the tool (`--help`, `describe`, `next`, `check` and the rest of the CLI), never the source, the
  spec or CLAUDE.md.
- The stand-in owner: a fixture file of the owner's Decisions (the Pick, the Mask strokes, the Markers), fed in through
  `decide` and `accept` with `KIRIPIX_TEST_OWNER=1`, set by the harness only, whenever the agent reports an owner
  action.
- The result: pass or fail (the room is exported and `check --all` is clean), the tokens used, and every Command the
  agent ran. Recorded in a dated file under `docs/`, so each milestone's token count can be compared.
- Every failure is treated as a tool bug: the harness's report names the step where the agent got lost.

## Acceptance criteria

- [ ] A dry run with a scripted "agent" that follows `next` exactly passes, so the harness itself is known to work.
- [ ] One real run on the cheap model, with its tokens recorded, and any failures filed as tickets in `backlog/`.
