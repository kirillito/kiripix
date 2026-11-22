---
status: done
milestone: M6
agent: imaging-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0356-m6-npc-kind-and-choose-stage.md]
---

# M6: an NPC's Checks: its Wearables fit its base, the stack, and its colours are choices

Spec §6.3 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md), to
[0355](0355-m6-adr-npc-kind.md) and [0356](0356-m6-npc-kind-and-choose-stage.md).

## What to build

Checks in `kiripix/checks/` (importing only `ops`), run on `choose`:

- `npc.wearable_body` (error): a Wearable whose `body` isn't the NPC's base. Its `fix` removes it from the choice.
- `npc.stack` (warning): the stack check from M5's [0294](../m5/0294-m5-wearable-stack-check.md) on the NPC's own stack
  (a Wearable hidden under another in most frames, by order against depth). Reuse 0294's Op; no copy.
- `npc.colour_choice` (error): a Part's colour isn't one of its `choices`, naming the Part and the choices. `npc.part_unset`
  (info): a Part with choices left as built.
- `npc.slot_twice` (warning): two Wearables in one slot (two hair styles), if Wearables carry a slot by then; otherwise left out
  and said so in the Result.

## Acceptance criteria

- [x] Unit tests on each Check, and a CLI-seam test on a test NPC for `npc.wearable_body` and `npc.colour_choice`.
- [x] `uv run lint-imports` passes.
- [x] Spec §6.3's NPC Checks listed.

## Result

No Stage `version` bump: `choose`'s output is unchanged; `choose` gains `check` and four `CheckSpec`s.

- **Checks** (`kiripix/checks/npc.py`, pure; the wiring is `check_choose` in `recipes/npc.py`): `npc.wearable_body` (error),
  `npc.colour_choice` (error), `npc.part_unset` (info), `npc.stack` (warning). Each position is `{asset, stage: "choose", field}`
  with `field` `wearables/<id>` or `colours/<part>`. `data`: `wearable_body` `{wearable, body, base}`; `colour_choice` `{part, choice,
  choices, reason}` (`part_gone`, `choice_gone`, `choice_changed`); `part_unset` `{part, choices}`; `stack` `{wearable, frames,
  buried_frames, buried, worst: [{clip, direction, frame, buried, opaque}]}`. Every one has a `fix`.
- **Overlap with `choose`'s refusals, decided:** `choose` refuses a bad list when the choice is made (needs-input, nothing built). The
  Checks read the built `npc.json` against the Project now, so they find what moved after the build: a Wearable's `body` edited, a
  choice renamed, removed or given another ramp in `kiripix.toml`. `npc.wearable_body` keeps one meaning in both places. The
  colour code is `npc.colour_choice`, not `npc.choice_unknown`: that one is about the `colours` parameter, this about the built output.
  A Wearable listed in `npc.json` but no longer in the `wearables` parameter is a stale choice, which `status` says; no Check on it.
- **`npc.stack`:** a Wearable's pixels that the depth pass puts in front but the order covers (the base and the Wearables, in
  `npc.json`'s order); a frame counts at 10 % of the Wearable's pixels, and the Wearable is flagged when over half its frames count.
  It reuses 0294's Ops by painting each layer with its own number and stacking those, so no stacking code is copied
  (`buried_by_order`). It reads the `render` folder beside each `sheet`; silent until the base and one Wearable have a `render`.
- **`npc.slot_twice` left out:** a Wearable carries no slot (only `order`).
- **Check cache (0367):** no `check_reads`. The key already holds the whole folders of the base and of each chosen Wearable (their
  `render` too) and `kiripix.toml`, which is all `check_choose` reads outside its own output.
- Tests: `tests/golden/test_npc_check_ops.py` (units on each Check and on `buried_by_order`), `tests/cli/test_npc_checks.py` (CLI seam:
  the four codes on a test NPC).

Changed after the batch's code review: `npc.stack`'s `fix` was `kiripix show <npc> choose`, which shows and fixes nothing. It is now
the `set` that puts the buried Wearable over every other layer (`kiripix set <npc> choose wearables=<its id>@<highest order + 1>,...`,
the other entries left as they were). `check_npc_stack` takes the fix as a function of the Wearable; the bulk maker (0359) passes
its re-roll. The CLI test runs the fix and the warning goes. The unit tests moved to `tests/golden/test_npc_check_ops.py`, since
pytest can't collect two test files of one name. `wearable_stack`'s `_frames` and `_read` are public now (`render_frames`,
`read_render_frame`), rather than imported as private names.
