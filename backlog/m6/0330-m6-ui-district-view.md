---
status: done
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

- [x] Playwright against a real `kiripix serve`: a district of three test rooms shows three thumbnails and the Exits with
      their pairing; clicking an unpaired Exit opens its room on `place`.
- [x] Playwright: Check on the district shows the findings of those three rooms only.
- [x] `npm run build` passes.
- [ ] An eye check by the Owner on the ch01 dungeon rooms, noted here.

## Result

Built in `web/src/districtView.tsx`, wired in `App.tsx` (`?district=<glob>`, `district-back` in the header) and `StatusBoard`.

- The status board has a "District" section: a glob field and one shortcut per common prefix of the room IDs
  (`room.ch01_*`, `room.ch01_dungeon_*`; shared by two rooms or more). The prefixes are derived from the room list in the UI as
  presentation; `district` has no prefix list, so nothing was missing.
- The grid shows `district`'s rooms in its order, each thumbnail at the largest whole zoom (up to 8) that fits three of the widest
  room in a row, nearest-neighbour, with ID, size in tiles, the Stage it waits at and its queue counts. A badge counts the
  room's unpaired Exits. Exits are listed under it with their pairing; an unpaired one is marked as an error and opens its room on
  `place`. A room opens as in the room list.
- "Review this district" is `openQueue(glob)`. Run (cancellable, with progress), Check and Export are each one Command with
  `match`; Export runs `dry_run` first, shows what it writes and which game files it overwrites (`backed_up`), and writes only on
  Confirm. Findings of a batch open their Asset on click. The view refetches `district` on every Project change.
- `DistrictView` takes an `extra(data)` render prop under the grid, for 0351's rooms waiting for a Source.
- Playwright: `web/e2e/district.spec.ts` (rooms, Exits, badge, whole zoom, unpaired Exit to `place`; Check shows the district's
  rooms only; Export dry run, cancel, confirm; Review opens the queue with the glob; the view follows an agent's `new`).
- No Stage `version` bump (no Stage changed).
- **The Owner's eye check on the ch01 dungeon rooms is still open and its box is left unticked.**
