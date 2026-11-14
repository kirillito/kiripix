---
status: todo
milestone: M4
agent: core-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0189-m4-loops-stage.md, 0190-m4-export-loops.md]
---

# M4: rename and remove a Loop

Found by [0191](0191-m4-ui-loops-screen.md) (2026-11-13), its gap 1. Spec §6.1 (`loops`) and §9 (frozen IDs: "Before the
first export, IDs can be renamed freely"). Today a Loop, once declared, can only be undone Decision by Decision, newest
first.

## What to build

- **Two `loops` Decisions:**
  - `remove` {loop}: the Loop and every Decision naming it stop applying.
  - `rename` {loop, to}: `to` follows the Marker ID rule and is free among the room's Looks and Loops. Decisions before it
    that name `loop` apply to `to`, and Decisions after it name `to`. A kit Loop keeps its imported frames
    (`src/loops/<loop>/`).
  - Both can be undone like any Decision.
- **The freeze.** `_current_ids` in `kiripix/export/checks.py` takes the Loops the Stage itself declares after replay (a
  function from `recipes/loops.py`), not the raw `loop` Decisions. A Loop removed or renamed after export then fails
  `export.id_frozen`.
- **Refuse it up front.** As with a Layer's `remove` (`frozen_layer_findings` in `commands/decisions.py`), a `remove` or
  `rename` of a Loop the Manifest lists is refused before it is recorded.
- Looks have the same gap; this ticket doesn't cover them.

## Acceptance criteria

- [ ] CLI seam: rename a cycle Loop and a kit Loop. `loops.json` has the new IDs with the same frames, and `undo` brings the
      old ones back.
- [ ] CLI seam: remove a Loop. It is gone from `loops.json`, and the others are unchanged.
- [ ] CLI seam: with a game configured and the room exported, `remove` and `rename` of that Loop exit 1 with
      `export.id_frozen`, and nothing is recorded.
- [ ] CLI seam: a `rename` to a Look's ID or another Loop's ID is refused.
- [ ] Contract samples for the two Decisions; `lint-imports` and `mypy` pass.

Budget: 60–120k tokens.
