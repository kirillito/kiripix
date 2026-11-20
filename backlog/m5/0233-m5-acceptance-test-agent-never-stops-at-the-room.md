---
status: done
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

- [x] The harness's choice above, with its tests (`uv run pytest tests/acceptance`) and the dry run passing.
- [x] `status` names the command for a `todo` Stage whose inputs are all there.
- [x] A real run passes, its tokens recorded.

## Result

- **Harness (first option, workable):** `StandInOwner.step` in `tests/acceptance/harness.py` now does all of its untagged
  room entries (masks brush, layer click, the Markers with the first, wrong `battle.test`) at the agent's first stop,
  whatever the Stage and whatever `only_this_stage` says, once. Entries tagged `when_stage` (the area's move onto the floor,
  the character's clips) still wait for their Stage. If the agent has already exported the room, the room is stale after
  "Done, carry on." and the agent must rebuild and re-export. Tests in `tests/acceptance/test_harness.py`: the first stop at the
  character's `clips` brings the room entries once; two older tests adjusted to the new rule. The dry run is unchanged
  (the scripted agent's first stop is at the room, as before).
- **`status`:** human output marks the first not-done Stage when it is `todo` as `copy       todo (ready: kiripix run demo.a)`
  (`StatusData.text` in `kiripix/commands/project.py`); JSON unchanged. Test: `tests/cli/test_status_ready.py`.
- **The real run** was left to the Owner at first, then run in the session below. Note that no dry run exercises the
  change-after-export path (the scripted agent stops at the room first), only the real agent does.
- **Real run, 2026-11-18 ([report](../../docs/acceptance/2026-11-18-m5.md)): FAIL, 54,766 fresh tokens, 43 commands**
  (M3's pass: 19,079; M4's fail: 36,110). The `todo` fix worked: after the clip Decisions the agent ran `status`, then
  `kiripix run character.hero` and exported. The room entries ran at its first stop (`reach`), and the crate Layer is in the
  Manifest. It failed on one check only: the agent had already placed `battle.test` at (64,64)–(191,127); the stand-in
  owner's wrong `battle.test` replaced it; on `area.no_walkable` the agent put its own box back without stopping, so the
  `when_stage: place` move to [32, 0, 95, 31] never ran. The agent told the owner and named `undo`.
- **Verification loosened (the Owner's choice):** any `battle.test` box of whole 32 px cells inside the room passes, the
  owner's or the agent's own (`area_box_problem` in `tests/acceptance/harness.py`; `AREA_BOX` is gone). Standing on it and
  reaching it are `check --all`'s part (`area.no_walkable`, `area.not_reached`). Tests in `test_harness.py`; the 11-18 run's
  scene passes it; `docs/acceptance/README.md` updated.
- **Real run 2, 2026-11-18 ([report](../../docs/acceptance/2026-11-18-m5-2.md)): FAIL, 38,418 fresh tokens, 29 commands.**
  A new place to get lost: after the owner's room entries, `status` showed `layers needs-input (Runner not run yet)` and
  `reach needs-input (no Spawn or Exit…)` (the old build's finding, though the owner had placed the spawn). The agent didn't
  run `kiripix run room.alley layers --rerun` ("may be slow or cost money") and asked the owner for a spawn and the clips.
  Run 1 had run that same command itself, so this is the agent's luck as much as the tool's.
- **`status`, second change (the Owner's choice):** human output only, JSON unchanged (`_stage_line` in
  `kiripix/commands/project.py`). A Stage whose only wait is its Runner calls names the command:
  `layers     needs-input (run: kiripix run room.alley layers --rerun)  (Runner not run yet)`. A not-done Stage that reads the
  first Stage not done says so, since its line may be about an older build: `reach      needs-input  (waits on masks; may
  change once masks is done: no Spawn or Exit …)`; a Stage that doesn't read it (`palette`) keeps its plain line. Tests:
  `tests/cli/test_status_waiting.py`. Full suite: 6 failures, none from this (PIL loaded at start through
  `kiripix/ops/__init__.py` importing `ops.sheet`, and five `character.json` and held-render tests of the uncommitted
  0308–0313 work).
- **Real run 3, 2026-11-19 ([report](../../docs/acceptance/2026-11-19-m5.md)): FAIL, 57,240 fresh tokens, 45 commands.**
  The room passes everything now: the agent ran `layers --rerun` itself, put the area on cells itself, rebuilt and re-exported
  after the owner's room review, and the Layer, the Area2D and `check --all` are clean. The hero was lost: the agent first
  stopped at `clips`, so the owner did the room and the three clips at once; after "Done, carry on." the agent ran `status`
  (which said `clips todo (ready: kiripix run character.hero)`), worked only on the room, and closed with "clips still needs
  the animation list" from memory. Its last command, `check --all`, exited 0 with no word of the unbuilt hero.
- **Both of the Owner's fixes for run 3:**
  - The stand-in owner's handback says what it did, never a Command: `handback` in `tests/acceptance/harness.py`
    ("Done: I recorded Decisions on room.alley (masks, place) and on character.hero (clips), and I accepted room.alley's
    layers. Carry on."). Tests in `test_harness.py`; README updated.
  - `check --all` lists each Asset `next` doesn't call done, with `next`'s data (`unfinished` in `CheckData`; human
    output `not finished: character.hero clips is todo; run: kiripix run character.hero`). Not a finding, so the exit code
    and the findings stay the Checks' own (an info finding broke ten tests that compare `check --all`'s findings, and
    mixed "not built" into "built wrong"). `_unfinished` in `kiripix/commands/checks.py`; spec §10's `check` line.
    `check <id>` leaves it to `next`. Test: `tests/cli/test_check_unfinished.py`.
- **Real run 4, 2026-11-19 ([report](../../docs/acceptance/2026-11-19-m5-2.md)): PASS, 65,825 fresh tokens, 49 commands,
  4 agent runs.** Against M3's pass of 19,079 that is 3.4 times as much, for a task that is much bigger since M3 (the room in
  two pieces with `extend`, the area, a review of the room after its export, the character beside it). The owner's room
  review, the Layer accept and the area's move onto the floor all ran; the agent checked `unfinished` before closing.
  Ticket done.
