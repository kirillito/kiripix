---
status: todo
milestone: M6
agent: none
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0325-m6-review-queue-command.md, 0326-m6-hand-over-note.md, 0327-m6-match-scope.md]
---

# M6: first passes over a list of rooms, without the Owner

Spec §1 (goal 2, "faster") and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Builds on M5's
[0249](../m5/0249-m5-room-first-pass-workflow.md) and its skill,
[skills/room-first-pass/SKILL.md](../../skills/room-first-pass/SKILL.md). Done in the main session (doc work and a run; no
agent).

## The gap

The skill takes one room through its first pass in one session, with the Owner starting it. A chapter is about 30 rooms. One
session over many rooms would grow its context with every room, and each room's tokens would be lost in the total. M5's run
couldn't record its tokens at all: the session can't read its own count.

## What to build

- **The skill's batch mode**, in the same skill or a sibling `room-first-pass-batch`, whichever reads more clearly: given a
  glob ([0327](0327-m6-match-scope.md)) or a list of room IDs, it runs **one fresh session per room, in sequence** (Runners
  share the 8 GB GPU, so rooms don't run side by side). A small driver script in the skill's folder runs
  `claude -p` per room with the single-room skill and `--output-format json`, so each room's tokens come from the result's
  usage, not from the session.
- **At each stop**, the single-room skill now writes a hand-over note on the Stage ([0326](0326-m6-hand-over-note.md)):
  why it stopped, and what's left for the UI. It records every Decision it can while it waits (Masks, `place`), as 0249
  found, and moves on.
- **A room the session can't start** (no Source, no brief) is skipped with a line in the report, never guessed.
- **The report**, written to `.kiripix/first-passes/<date>.md` in the art Project: per room, where it stopped, its notes,
  its Decisions per Stage and its tokens; then `kiripix queue --match <glob>` ([0325](0325-m6-review-queue-command.md)) as
  the Owner's starting point.
- Where the batch needs a Command Kiripix lacks, file a ticket instead of scripting around it.

## Acceptance criteria

- [ ] The batch mode is in the repo, and the README's line on installing the skill covers it.
- [ ] A run over at least three ch01 rooms with painted Sources (the Owner paints them first), from one command, with no
      Owner input until the queue. Recorded here: per room, the stop, the tokens, the Decisions; then the Owner's minutes
      in the queue sitting (`stats --match`), against M5's 2.95 minutes for one room.
- [ ] Every finding the run raises is filed as a ticket or accepted in writing.
