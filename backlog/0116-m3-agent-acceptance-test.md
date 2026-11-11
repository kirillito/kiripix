---
status: todo
milestone: M3
agent: qa-engineer
type: ticket
parent: 0097-m3-characters.md
depends_on: [0113-m3-character-export.md]
---

# M3: the agent acceptance test with a character

Spec §14 (the agent acceptance test). Story 16 of [0097](0097-m3-characters.md). As [0057](m2/0057-m2-agent-acceptance-test.md)
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

- [ ] The dry run passes in `uv run pytest tests/acceptance`.
- [ ] One real run on the cheap model, recorded under `docs/acceptance/` with `--milestone m3`, compared in its Notes with
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
