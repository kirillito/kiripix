---
status: done
milestone: M3
agent: qa-engineer
type: ticket
parent: 0097-m3-characters.md
depends_on: [0113-m3-character-export.md]
---

# M3: the agent acceptance test with a character

Spec §14 (the agent acceptance test). Story 16 of [0097](0097-m3-characters.md). As [0057](../m2/0057-m2-agent-acceptance-test.md)
was for M2.

## What to build

- The task gains a character: from `import` of a Model to `export`, beside the room, using only `--help`, `describe`, `next`
  and `check`.
- Fixtures: a pre-rigged fixture Model from [0100](0100-m3-character-test-fixtures.md), so `rig` passes without Mixamo, and
  its animation source. The stand-in Owner's `clip` Decisions (idle, walk, attack) in `tests/acceptance/fixtures/owner.json`.
- The renderer is the fake, set by the harness only, as the Runners are (0037's D16). `describe` must not show the test Kinds.
- A pass also needs: the character's clips in its Manifest, and `check --all` clean.
- Keep the task prompt's existing lines, so runs compare.

## Acceptance criteria

- [x] The dry run passes in `uv run pytest tests/acceptance`.
- [x] One real run on the cheap model, recorded under `docs/acceptance/` with `--milestone m3`, compared in its Notes with
      M2's 16,941 fresh tokens. Note how much of the rise is the character. A failure is filed as a ticket in `backlog/`.

## Notes

- Harness built and the dry run passes (`uv run pytest tests/acceptance`, 29 passed). The character runs on the fake Blender
  end to end: `sheet.empty_frame`, `sheet.pivot_drift` and `check --all` come out clean on its opaque frames.
- The task prompt keeps every line it had; it gains one paragraph naming `character.hero` and its Model file, and its last
  sentence now says "the room and the character".
- The real run is not done yet (it spends money on the external API). The Owner runs it with:

  ```
  uv run python -m tests.acceptance.run --milestone m3
  ```

  then ticks the second box once the report is in `docs/acceptance/`, compares its fresh tokens with M2's 16,941 and notes
  how much of the rise is the character (the commands from `import character.hero` on, in the report's command table).

## The real runs (2026-11-11)

- **First run: FAIL,** [2026-11-11-m3.md](../../docs/acceptance/2026-11-11-m3.md), 27,647 fresh tokens, 28 commands. Two causes,
  both fixed in the main session the same day instead of as tickets (the Owner's call):
  - The harness counted an agent's stop as a question to the owner only if its closing message said "owner"; Haiku asked
    "you", at `clips`, so the stand-in owner never answered. Now any stop before the end is a report, and the owner answers
    only what `owner.json` has for the Stage `next` is at.
  - `next` had the two owner choices the wrong way round for an agent: `clips` offered a `decide` command with a placeholder
    source, and `reach`'s owner_action held a runnable `decide … place` command, which the agent ran with a position it chose.
    So the room never waited on the owner, the crate was never lifted, and it exported without the Layer. Both are now owner
    steps with no command (`kiripix/recipes/clips.py`, `kiripix/recipes/room.py`).
- **Second run: PASS,** [2026-11-11-m3-2.md](../../docs/acceptance/2026-11-11-m3-2.md), **19,079 fresh tokens** in 4 agent runs
  and 25 commands, 202 s. Against M2's 16,941: +2,138 (about 13 %).
- **How much is the character:** 7 of the 25 commands (`import --help`, `import`, `pick`, `run`, then `status`, `run`, `export`
  after the owner's clips), and one more owner turn, at `clips`. The room took 18 commands against M2's 17. The report doesn't
  split tokens by command; by commands and turns, the character is most of the rise, at roughly 2,000 fresh tokens.
