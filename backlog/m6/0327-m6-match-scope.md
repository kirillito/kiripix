---
status: todo
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

- [ ] CLI seam: each of the five Commands with `--match` touches only the matched Assets, and a glob matching nothing is
      `match.none`.
- [ ] CLI seam: an `exit.not_paired` for a matched room pointing at an unmatched one is reported; one between two unmatched
      rooms isn't.
- [ ] CLI seam: `run --match` on characters made from an unmatched base builds the base first.
- [ ] The contract samples cover the new option.
