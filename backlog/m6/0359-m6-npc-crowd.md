---
status: done
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0356-m6-npc-kind-and-choose-stage.md, 0357-m6-npc-checks.md]
---

# M6: NPCs in bulk from a seed

Spec §6.3, §10 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md), the Owner's Q3 in
[0336](0336-m6-npc-variants-from-a-base.md): a second step, after one NPC works.

## What to build

- `kiripix new npc <prefix> --base <character> --count N --seed S [--wearables <glob or list>] [--choices part=a,b ...]`
  makes N ordinary `npc` Assets, `<prefix>_01` … `<prefix>_NN`, each with a choice picked by the seed from the allowed
  Wearables (one per slot, if slots exist) and colour choices. Same seed, same Project: same NPCs. "Allowed" is the command's
  flags, defaulting to every Wearable on the base and every choice (ADR 0015).
- Each result passes 0357's Checks, or it's re-picked (bounded tries; then a finding naming what couldn't be satisfied).
- `kiripix new npc <id> --reroll [--seed S]` re-picks one NPC's choice; the Owner deletes one with the usual Command.
- `cast-sheet --match <prefix>_*` shows the crowd in one sheet (0337 and 0327 already give this; say so, or fill the gap).

## Acceptance criteria

- [x] CLI seam: `--count 5 --seed 3` twice in two fresh Projects gives the same five choices; every one passes the Checks.
- [x] CLI seam: `--reroll` changes one NPC and no other.
- [x] A contract sample for the new options.

## Result

No Stage `version` bump (no Stage output changed). Spec §6.3 has the section "NPCs in bulk".

- **Command:** `new` gains `--count`, `--seed`, `--wearables`, `--choices` (repeatable, `part=a,b`) and `--reroll`; `NewData.crowd` lists each NPC
  (`asset`, `wearables`, `colours`, `tries`, `changed`). The logic is `kiripix/core/crowd.py`. A crowd is only the IDs `npc.<prefix>_NN`;
  nothing is stored. Refusals (exit 1, nothing made): `new.crowd_incomplete`, `new.crowd_needs_npc`, `new.crowd_reroll_args`,
  `new.crowd_wearables_unknown`, `new.crowd_choice_unknown`, `asset.duplicate_id`.
- **"Allowed Wearables", decided:** no slot exists, so each NPC wears a random subset (none to all) of the allowed Wearables, stacked by
  `order`. Default: every Wearable worn on the base; `--wearables` is IDs or globs among them. Each Part with choices gets one of its allowed
  choices; `--choices hair=auburn` narrows that Part and leaves the others open.
- **Determinism:** `random.Random` seeded by a string of seed, base, prefix, number and try, over sorted lists and the ramp table's row
  order. A test runs the second Project under another `PYTHONHASHSEED`.
- **Checks before a build, decided:** the Assets are always made and nothing needs `choose` built, because a choice is parameters. The pick is
  judged by 0357's own functions (`check_wearable_body`, `check_colour_choice`, and `stack_findings`, which is `check_choose`'s stacking code
  made callable on the `render` folders; `stack_frames` is the shared body). Where the base or a Wearable has no built `render`, `npc.stack`
  can't judge (as the Check is silent), and the result carries `new.crowd_stack_unchecked` (info, fix `kiripix run <id> render`). Refusing
  until the builds exist would have blocked making the Assets that the builds then follow.
- **Re-pick:** an error, an `npc.stack` warning or a twin of another NPC on the base is picked again, 12 tries at most; then the closest is kept
  with `new.crowd_unsatisfied` (warning, fix the re-roll). `npc.part_unset` is information and never re-picks.
- **Re-roll:** picks other than the NPC's own and the others' on the base, and writes only that NPC. Without `--seed` it is derived from the
  current choice, so no clock is read. When no other choice exists it changes nothing (`changed: false`, `new.crowd_unsatisfied`).
- **`cast-sheet --match <glob>`** was missing (0327 gave `--match` to other Commands, 0337's `cast-sheet` took a list, and an NPC wasn't a figure).
  Filled: `--match` draws the matched characters, sprites and NPCs in ID order; an NPC (also in a list) is its base, Wearables and swapped
  colours from its built `choose`, titled with its ID (`Figure.title`); one not built is left out with `cast.npc_not_built`. `assets` became optional
  (one of the two is required).
- Tests: `tests/cli/test_npc_crowd.py` (determinism across Projects, flags, unsatisfied, re-roll, refusals; a built crowd passes `check` and
  `cast-sheet --match`), `test_an_npc_crowd_validates` in `tests/cli/test_contract.py`.

Changed after the batch's code review: in `new.crowd_unsatisfied`'s `data.reasons` a pick that repeats another NPC's is the code
`new.crowd_twin`, not a sentence (the message still says it in words).
