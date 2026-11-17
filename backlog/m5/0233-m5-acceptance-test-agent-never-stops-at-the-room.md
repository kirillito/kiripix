---
status: todo
milestone: M5
agent: qa-engineer
type: ticket
---

# M5: the acceptance test when the agent never stops at the room, and `todo` read as "not decided"

Found at the M4 gate ([0142](../m4/0142-m4-gate.md)): the real run of 2026-11-16 failed, 36,110 fresh tokens, 26 commands
([report](../../docs/acceptance/2026-11-16-m4.md)). M3's passing run: 19,079. Milestone M5 is a placeholder: the Owner picks it.

## What happened

1. **The agent never stopped at the room.** It joined the piece, placed a spawn and `battle.test` itself (the task asks it
   to place the area), ran the room to export, and only stopped at the character's `clips`. In M3 it stopped at `reach`, and
   the stand-in owner did its room part there: the crate's Layer and moving the area. This time the owner's room entries
   never ran (`only_this_stage` when the agent asks), so verification failed on the missing crate Layer and the area's box.
   The room as exported is legitimate: no Kiripix Stage asks for a Layer, and an agent can't know the owner wants one.
2. **After the owner's three clip Decisions** and "Done, carry on.", the agent ran only `kiripix status`, saw `clips todo`,
   wrote "still has no decisions", and stopped. `status` showed `needs-input` before the Decisions and `todo` after;
   `next` would have named `kiripix run character.hero`. The agent (`claude-haiku-5-5`) didn't run it.

## What to decide and build

- **The room's owner step:** either the stand-in owner does its room entries at the agent's first stop whatever the Stage
  (an owner reviewing the room, after which the agent must rebuild and re-export), or the task says the owner reviews the room
  before export, or the crate Layer drops out of the verification. The first tests the most: a change after export.
- **`todo` that is ready to run:** `status` (human output) could say so, for example `clips todo (ready: kiripix run
  character.hero)`, so a `todo` reads as work, not as a question. A CLI test for the line; the JSON keeps `status`.
- Run the real test again with `--milestone m4` (or `m5`) and record it against 19,079.

## Acceptance criteria

- [ ] The harness's choice above, with its tests (`uv run pytest tests/acceptance`) and the dry run passing.
- [ ] `status` names the command for a `todo` Stage whose inputs are all there.
- [ ] A real run passes, its tokens recorded.
