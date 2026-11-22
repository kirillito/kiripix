---
status: done
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
---

# M6: `--match`: work on a district's Assets by an ID glob

Spec §10.5 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md), written to the Owner's Q1 there: a
district is the rooms whose IDs share a prefix.

## The gap

`run`, `check`, `export` and `stats` take one Asset or `--all`, and `status` takes `--kind`. A chapter is about 30 rooms in
districts (`room.ch01_dungeon_r01` to `r0N`). Working on one district means listing its IDs, or working on the whole Project.

## What to build

- `--match <glob>` on `status`, `check`, `run`, `export` and `stats`, with `--all` where the Command has one: the Assets
  whose IDs match the glob (`fnmatch`, case-sensitive), such as `room.ch01_dungeon_*`. It narrows `--all`; on its own it
  means `--all --match`.
- A glob that matches nothing is an error (`match.none`), naming the glob, so a typo isn't an empty success.
- **Project checks under `--match`:** they run against the whole Project and report only findings that name a matched Asset.
  An Exit in the district that points outside it is still checked against its target.
- `run --match` keeps `run --all`'s order: a base before the characters made from it, even when the base doesn't match (it
  is built, and the result says so).
- `export --match` keeps `export --all`'s rules (a Wearable's body counts when it's exported in the same call; `--prune`
  works as it does with `--all`).
- Spec §10.5 and the glossary: "district" is the word for the rooms a glob matches, nothing stored.

## Acceptance criteria

- [x] CLI seam: each of the five Commands with `--match` touches only the matched Assets, and a glob matching nothing is
      `match.none`.
- [x] CLI seam: an `exit.not_paired` for a matched room pointing at an unmatched one is reported; one between two unmatched
      rooms isn't.
- [x] CLI seam: `run --match` on characters made from an unmatched base builds the base first.
- [x] The contract samples cover the new option.

## Result

`--match <glob>` is on `status`, `check`, `run`, `export` and `stats`. The matching is one module, `kiripix/core/match.py`
(`matches`, `select`, `no_match`, `only_named`), for `queue` and `district` to call too. `fnmatch`, case-sensitive; alone it
means `--all --match`; with an Asset ID it is refused. A glob matching no Asset is `match.none` (exit 1, `fix` is
`kiripix status`).

- `check --match`: `check_all(..., match)` checks the matched Assets; Project checks run over the whole Project and keep only
  findings whose position names a matched Asset, so a matched room's Exit to an unmatched one is reported and one between two
  unmatched rooms isn't. Findings that name no Asset are left out under `--match`.
- `run --match`: `run_all(..., match)`; a base of a matched Asset is built first even when it doesn't match, with an info
  finding `match.base_built`. `--kind` narrows a match further.
- `export --match`: `export_assets(..., match)` applies the `--all` rules (pairing, clip table) to the matched Assets; with
  `--prune` only deleted Assets whose IDs match are pruned (`plan_prune(..., match)`). `match.none` also for a glob that names
  no existing Asset and no deleted one.
- `stats --match`, `status --match` filter the list.
- Spec §10.5 and the glossary ("district") updated. No Stage `version` bump.

Tests: `tests/cli/test_match.py`; contract samples for `status`, `check` and `stats` use `--match`.
Left for the Owner: nothing measured; the district words in the skill docs (`docs/` guides) are not touched.


**Review fixes (2026-11-20):** The `export` contract sample (and its REST body in `test_serve.py`) is now `export --match room.*`, so a `--match` input is in the contract. `run`'s keeps `--from`; `test_match.py` covers `run --match`.
