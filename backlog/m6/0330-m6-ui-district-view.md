---
status: todo
milestone: M6
agent: ui-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0328-m6-district-probe.md, 0329-m6-ui-review-queue.md]
---

# M6: UI: the batch view for a district

Spec §11 and §14 (M6, moved from Later). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Built on
[0328](0328-m6-district-probe.md)'s `district` and [0327](0327-m6-match-scope.md)'s `--match`.

## The gap

The status board lists Assets by Kind and Stage, in text. A chapter's rooms come in by district, and the Owner wants to see
them together: which are done, which wait, and whether their Exits join.

## What to build

- **The district view**, opened from the status board by a glob (the room list offers each common prefix,
  `room.ch01_dungeon_*`, as a shortcut). A grid of the rooms' thumbnails at the largest whole zoom that fits, in ID order,
  each with its ID, its size in tiles, the Stage it waits at and its queue counts.
- **Exits:** under the grid, every Exit as `room exit → room exit` with its pairing state; an `unpaired` one is marked as an
  error and clicking it opens its room on `place`. A thumbnail's badge counts its unpaired Exits.
- **Clicking a room** opens it as the room list does. **"Review this district"** opens queue mode
  ([0329](0329-m6-ui-review-queue.md)) with the district's glob.
- **Batch actions on the district,** each one Command with `--match` and its result's findings shown: Run, Check, Export
  (`--dry-run` first, then a confirm listing what it overwrites). A long run shows progress and is cancellable, as `run` is
  today.
- The view refreshes when the Project changes.

## Acceptance criteria

- [ ] Playwright against a real `kiripix serve`: a district of three test rooms shows three thumbnails and the Exits with
      their pairing; clicking an unpaired Exit opens its room on `place`.
- [ ] Playwright: Check on the district shows the findings of those three rooms only.
- [ ] `npm run build` passes.
- [ ] An eye check by the Owner on the ch01 dungeon rooms, noted here.
