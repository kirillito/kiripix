---
status: done
milestone: M4
agent: core-engineer
type: ticket
---

# M4: `show` gives the Decisions as the Stage reads them, and marks the base's clip sources

Spec §10 and §11; ADR 0007 (adapters hold no logic) and ADR 0012 (a character made from a base). Found in the review of
[0210](0210-m4-ui-loops-screen-follow-ups.md) and [0227](0227-m4-ui-a-character-made-from-a-base.md), 2026-11-15. The UI side
is [0229](0229-m4-ui-drop-client-side-replays.md).

## The gap

Two screens do work that belongs to a Command, because `show` doesn't hand them the answer:

- **Loops.** `show` lists the `loops` Stage's Decisions as recorded. The Stage reads them through its `decisions_view`
  (`apply_loop_edits` in `recipes/loops.py`): a `remove` drops the Loop's earlier Decisions, a `rename` moves them to the new
  ID. So the loops screen copies that replay in TypeScript (`withEdits` in `web/src/loopScreen.tsx`), and the two can drift.
- **Clips.** The clips screen replays `remove` Decisions itself to know which clips are left (the `latest` map in
  `web/src/characterScreens.tsx`).
- **Clip sources.** `show.clip_sources` lists the base's files beside the character's own, with no mark. The clips screen
  guesses which are the base's from the path: `!file.startsWith("assets/<kind>/<name>/")`. That breaks if the layout or the
  separator changes.

## What to build

- `show`'s Stage detail gains the Stage's current Decisions as the Stage reads them: `AssetGraph`'s view (replayed, then through
  `decisions_view`), beside the recorded list the undo and redo controls still need. Each keeps `from_base`.
- Whatever the clips Stage does with `remove` (and a same-name `clip` over the base's) is visible in that view too, so the clips
  screen can list the clips without replaying anything. If the clips Stage applies `remove` inside its run rather than through a
  `decisions_view`, move it to one, so there is one replay for the Stage and `show`.
- Each `clip_sources` entry gains `from_base: bool`.
- The output schema says what each field is. The contract test validates it.

## Acceptance criteria

- [x] CLI seam: a room with a renamed Loop and a removed one. `show` gives the Loops' Decisions under the new ID, and none for
      the removed Loop. The recorded list is unchanged.
- [x] CLI seam: a character made from a base, with one base clip removed and one changed here. The view lists the changed clip
      as the character's own, and leaves out the removed one.
- [x] CLI seam: `clip_sources` marks the base's files `from_base: true` and the character's own `false`.
- [x] `uv run pytest tests/cli/test_contract.py`, `uv run lint-imports` and `uv run mypy` pass.

Budget: 40–80k tokens.
