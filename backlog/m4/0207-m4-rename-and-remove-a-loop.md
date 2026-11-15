---
status: done
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

- [x] CLI seam: rename a cycle Loop and a kit Loop. `loops.json` has the new IDs with the same frames, and `undo` brings the
      old ones back.
- [x] CLI seam: remove a Loop. It is gone from `loops.json`, and the others are unchanged.
- [x] CLI seam: with a game configured and the room exported, `remove` and `rename` of that Loop exit 1 with
      `export.id_frozen`, and nothing is recorded.
- [x] CLI seam: a `rename` to a Look's ID or another Loop's ID is refused.
- [x] Contract samples for the two Decisions; `lint-imports` and `mypy` pass.

Budget: 60–120k tokens.

## Result (2026-11-14)

- **Two `loops` Decisions**, `remove` {loop} and `rename` {loop, to} (`kiripix/recipes/loops.py`). They are replayed by one
  pure function, `apply_edits`, that core hands to the Stage as `StageRun.decisions` through a new `StageSpec.decisions_view`
  (`recipes/base.py`, `core/graph.py`; the `loops` StageSpec in `recipes/room.py` sets it). A `remove` drops the Loop's earlier
  Decisions; a `rename` gives them the new ID; neither is left in the view. So `LoopInputs`, the held reasons, the Look/Loop
  ID clash, `loops.json` and the freeze all see the renamed IDs, and `held_loops` needed no change. The input hash and
  `show` still read the journal as recorded. Decisions recorded after a `remove` declare a new Loop; after a `rename`, a
  Decision naming the old ID declares another Loop of that name. Undo and redo are the journal's own.
- **A kit keeps its frames.** `rename` marks each earlier `kit` Decision with `was` (the ID the frames were stored under, set
  once, so a Loop renamed twice still points at `src/loops/<first ID>/`). The kit's frame lookup (`kit_record.py`, `loops.py`)
  uses `was`; `kits_moved` re-records a kit under `was` and without it. `import --loop` and `loop kit` after a rename use the new
  ID, store under `src/loops/<new>/`, and the latest `kit` Decision wins.
- **The freeze.** `_current_ids` takes `declared_ids(...)` (the Loops declared after replay), so a Loop removed or renamed after
  export fails `export.id_frozen`.
- **Refused up front.** `loop_edit_findings` and `frozen_loop_findings` (`export/checks.py`, called by `decide` and `redo` in
  `commands/decisions.py`, as for a Layer's `remove`) refuse, before anything is recorded and for a whole array: an unknown
  Loop (`loop.unknown`, `fix`), a `to` a Look or another Loop has, or the Loop's own ID (`loop.id_taken`, `loop.rename_same`,
  `owner_action`), and an exported Loop (`export.id_frozen`, `owner_action`). Exit 1, as the ticket says; the Layer's `remove`
  exits 2 for the same finding, which this ticket left alone.
- Tests: `tests/cli/test_loop_rename.py` (6: cycle and kit rename with undo, remove, the refusals, the freeze for `decide`
  and for `redo`), contract samples in `tests/cli/test_contract.py`.
- For later tickets: a renamed Loop's imported files stay under `src/loops/<original ID>/`. Anything that reads a Loop's kit
  files (0219 edit frames, 0222 `timing.rest`) takes the folder from the kit Decision's `was` (else the Loop's ID), not from
  the Loop's current ID, and reads Decisions through `StageRun.decisions`, not the raw journal.
