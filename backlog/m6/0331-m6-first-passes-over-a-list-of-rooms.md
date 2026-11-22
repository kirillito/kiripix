---
status: done
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

- [x] The batch mode is in the repo, and the README's line on installing the skill covers it.
- [x] ~~A run over at least three ch01 rooms with painted Sources (the Owner paints them first), from one command, with no
      Owner input until the queue. Recorded here: per room, the stop, the tokens, the Decisions; then the Owner's minutes
      in the queue sitting (`stats --match`), against M5's 2.95 minutes for one room.~~ Dropped by the Owner (below).
- [x] ~~Every finding the run raises is filed as a ticket or accepted in writing.~~ No run, so no findings.

## Result

Built (main session, 2026-11-20); the run over the ch01 rooms waits for the Owner, so `status` stays `todo`.

- **Batch mode in the same skill**, not a sibling: `skills/room-first-pass/SKILL.md` gains "Batch mode" and the hand-over
  note at every stop (`kiripix note`, from [0326](0326-m6-hand-over-note.md)). One skill reads more clearly, because the
  per-room session *is* the single-room skill with two rules added (never ask or wait; no brief found → a note on `brief`, end).
- **The driver**, `skills/room-first-pass/batch.py` (standard library only): `--match <glob>` (via `status --match`, 0327) or
  room IDs; one `claude -p --output-format json` per room, in sequence; tokens from each result's `usage`
  (input, cache creation, cache read, output) and its reported cost; Decisions per Stage in this pass from `stats` before and
  after; where it stopped from `next`; live notes from `show` (a note on a `todo` brief is no `queue` stop, so `queue` can't
  give it). `--timeout` (minutes, default 60), `--allowed-tools` (default: Kiripix, Read, Write, Edit, Glob, Grep),
  `--model`, `--report`, `--dry-run`. The report is rewritten after every room, so a stopped batch still leaves one.
- **Skips, never guesses:** a room with no Variant is skipped before any session; a room whose session leaves a note on
  `brief` and stops there is reported as "no brief" with the note.
- **The report**, `.kiripix/first-passes/<date>.md`: a table (room, stop, Decisions this pass, tokens, minutes), per room its
  notes, tokens and the session's last words, the skipped rooms, then `kiripix queue --match <glob>` and `stats --match`.
- Tried with a stub in place of `claude` on a scratch Project (a room with a Source, one leaving a note on `brief`, one with no
  Source) and in `--dry-run` on the art Project (four ch01 rooms, all would run). No Command was missing, so no ticket filed.
- README's line on installing the skill names `batch.py`.

### The Owner's decision, 2026-11-20

The run and its measure are dropped. The Owner won't do a manual run, and comparing the queue sitting with M5's 2.95 minutes
says nothing: each M6 room now goes through more Stages (masks, layers, normals, palette and on), so an earlier milestone's
minutes aren't a baseline for it. Kiripix is meant to be run by agents, with the Owner reviewing results and adjusting along
the way. The batch mode stays, for agents to use (the gate runs it).
