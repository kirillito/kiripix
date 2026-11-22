---
status: done
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0355-m6-adr-npc-kind.md]
---

# M6: the `npc` Kind, its `choose` Stage, and named colour choices in the ramp table

Spec §3, §4 (`kiripix.toml`), §6.3 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md), to the ADR
of [0355](0355-m6-adr-npc-kind.md) and the Owner's answers in [0336](0336-m6-npc-variants-from-a-base.md).

## What to build

- **`kiripix new npc <name> --base <character>`:** an Asset of Kind `npc` with `base` in its `asset.toml`. A base that is
  missing, a Wearable, a sprite or itself made from a base is `npc.base_unknown` (as `wearable.body_unknown`).
- **`choose`:** the NPC's Wearables (IDs), their order (default each Wearable's `order`) and one colour choice per Part, as
  `choose`'s parameters `wearables` and `colours` (ADR 0015: parameters, not Decisions). It writes `npc.json` (`schema_version` 1: `base`, `wearables` in stack order,
  `colours` by Part, each the choice's name and its ramp). Its input hash covers the base's and each Wearable's `sheet` and
  `palette` outputs. No render, no Runner.
- **`[[character.ramps]]` gains `choices`**, a table of named ramps per Part (`choices = { auburn = ["#…", …] }`), each as
  long as the Part's row. `kiripix.toml`'s `schema_version` bump with a pure migration (no `choices` → an empty table). A
  choice of the wrong length or off the Project palette is a settings finding. [0334](0334-m6-style-references-and-wiring.md)
  took `schema_version` 11, so this is 11 → 12.
- **`preview --stage choose`** shows the stacked, swapped figure from `cast-sheet`'s code (0337: `stack_by_order`,
  `swap_ramps`), one frame per direction of the base's idle. No copy of the stack code.
- `describe npc` lists the Kind; `schema` covers the new settings; a contract sample for `new npc`.

## Acceptance criteria

- [x] CLI seam: an NPC on a test base with two test Wearables and a choice per Part builds `npc.json`; a base's re-render
      (its `sheet` hash) makes it stale.
- [x] CLI seam: an older `kiripix.toml` migrates and gains empty `choices`; a choice of the wrong length is a finding.
- [x] CLI seam: `npc.base_unknown` for each wrong base.
- [x] Spec §4 and §6.3 updated.

## Result

Built to ADR 0015. No Stage `version` bump (the `npc` Stages are new).

- **`npc` Kind** (`kiripix/recipes/npc.py`): `kiripix new npc <name> --base <character>`; recipe `choose` -> `export` (`export` is declared, not built: ticket 0358). The base reuses ADR 0012's `takes_base`, with two new `KindSpec` fields: `base_kind="character"` and `base_refusal="npc.base_unknown"`. A base that is missing, a Wearable, a sprite, itself made from a base, itself, or not an Asset ID is `npc.base_unknown` (`fix`; read from an edited `asset.toml` it is an `owner_action`). `run --all` builds NPCs after everything else.
- **`choose`** has two `str` parameters (default empty, so at their default they stay out of the hash): `wearables` (Wearable IDs, comma-separated, `id@25` for this NPC's own order) and `colours` (`part=choice` pairs). It writes `npc.json` (`schema_version` 1): `{base, wearables: [{id, order}] in stack order (order, then ID), colours: {part: {choice, rgb}} in ramp-table row order}`. Its input hash holds the base's and each listed Wearable's `sheet` and `palette` input hashes, the ramp table (`character.ramps`) and the Wearables' kind and body. New core mechanism: `StageInputs.chosen` (`ChosenInputs(param, built)`) gives `StageRun.chosen` (`ChosenView`), and `choose` waits (needs-input, with the build command) until each listed Wearable's `sheet` and `palette` are done.
- **Findings of `choose`** (needs-input, and the code `run` refuses with, exit 3): `npc.wearable_unknown`, `npc.wearable_body`, `npc.wearable_twice`, `npc.wearable_order`, `npc.colours_invalid`, `npc.part_unknown`, `npc.choice_unknown`; each has a `fix`. The list is checked before the wait for builds.
- **Ramp `choices`** (`RampSpec.choices`, `kiripix.toml` `schema_version` 11 -> 12, migration `_add_ramp_choices` changes only the version: no `choices` reads as an empty table, and an empty one is never written). A colour is `[r, g, b]` or `"#rrggbb"` text, held as `[r, g, b]`. Settings findings: `ramps.choice_length`, `ramps.choice_not_in_palette`, `ramps.choice_name`. `describe project` rows (`RampRow`) gain `choices`; `schema` covers it.
- **`preview --stage choose`** (`StageSpec.preview_figure`): `core/previews.py` reads `npc.json` and draws the figure with `cast_sheet` (`Figure` gained `orders`), one frame per direction of the base's `idle` clip. It takes no overlay.
- Spec §4 and §6.3 updated. Tests: `tests/cli/test_npc.py`, a sample in `tests/cli/test_contract.py`; the tests that read the current `schema_version` now read 12.
- Left open: the Checks (0357), the export (0358), the crowd maker (0359), the UI (0360). A Wearable's `order` default is read from its built `sheet.json` in `choose` (its `order` parameter is not read directly).
