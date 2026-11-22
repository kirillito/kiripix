---
status: done
milestone: M6
agent: ui-engineer
type: ticket
depends_on: [0373-m6-serve-works-the-project-out-once.md]
---

# M6: UI: the Project opens at once, and a long list costs only what is on screen

Spec §11. Part of the Owner's report of 2026-11-21: opening the Project takes too long, and with hundreds of rooms and
characters the UI must still be usable. Over [0373](0373-m6-serve-works-the-project-out-once.md)'s cheap list and per-Asset
answers; no logic in the UI beyond drawing.

## What to do

1. **Paint first.** On open the list and the status board show from the cheap list at once; each row's status fills in when it
   arrives (a quiet placeholder until then). The queue count, the district view, the waiting rooms and the style scores never
   hold the first paint.
2. **Only what is on screen.** Long lists (the Asset list, the status board, the review queue, the district view) render the
   rows in view (windowing), and ask `status` for those rows first, then the rest in the background in chunks.
3. **Images when visible.** Thumbnails and previews load when they scroll into view (`loading="lazy"` or an
   IntersectionObserver), never for rows off screen.
4. **A refresh after a change** asks only for the rows the change names (0369's scoping, now per row).
5. The working strip says what is still being read, as 0369's does.

## Acceptance criteria

- [x] Playwright against a real `kiripix serve` on a Project of a few hundred light Assets: the list's first rows show before
      any `status` answers; a scroll asks for the rows it reaches; no image of a row off screen is fetched.
- [x] The existing e2e specs pass.
- [x] `npm run build` passes.
- [x] Measured on the art Project copy (`../urban-mystery-club-art` copied to the scratchpad, never the original): time to the
      first rows and to a full list, before and after, in the Result.

## Result

The Project opens from the cheap list, and a long list costs what is on screen. No Python changed; no Command is missing.

- **Paint first.** `web/src/rows.ts` (`Rows`) asks `assets` and the lists draw at once; each row shows a quiet placeholder (`data-pending`,
  a "·" in the Asset list, "reading…" on the board) until its `status` lands. The queue count, the district view, the waiting rooms and
  the style probe start after the first status chunk and never hold the first paint.
- **Windowing** (`web/src/virtualRows.tsx`, `VirtualRows`): the Asset list and the status board draw the rows in view and a little
  beyond, each row measured once drawn (the board's rows wrap, so heights differ). The visible IDs go to `Rows.see`, which asks `status` for
  them first (chunks of 30), then the rest in the background (chunks of 60, two at a time). The review queue shows one stop at a time and has
  no long list; the district view's rooms come from its own Probe and are not windowed, but their thumbnails are `loading="lazy"` (sized
  from the room until they load, so a lazy image has a place) and a crowd's strip is drawn (its `cast-sheet` call made) only while the crowd
  is in view (`useInView`).
- **Refresh per row.** A `changed` event names Assets by path (`assetOfPath`); `Rows.related` adds the rows that name them or are named by
  them in the cheap list (a base's characters, a body's Wearables). Those rows are asked again at once, the rows in view too, and every
  other row is marked unverified: it is asked again when it scrolls in (cheap, the server remembers unchanged rows). A path outside
  `assets/` asks every row. An action's refresh (`perform`) names the open Asset and its dependants, or every row for a batch action, a new
  Asset, a re-roll and a style reference (`perform`'s new last argument). Reload, the window focus and the page's first read make one new
  `refresh` token, sent on every `assets`, `status` and `queue` call until the next; nothing else sends a new one.
- **Queue** is asked in chunks of 100 IDs and added up in `Rows` (per-Asset buckets, counts recomputed from the stops); it shows once all
  chunks have answered, and a change asks `queue` only for the named rows and merges them in. A new match asks everything.
- **Strip.** Still says what is read: "the list", "the status", "the queue", the Asset's calls.
- **Other changes.** The style stars come from the list's `reference` flag; `useWearables` asks `show` only for the bodies the Wearables name
  (before: every Asset). `StatusData.assets[].stages` is null until the row's status answers; a row without a status shows only under the
  "All" filter, so under "Needs me" the rows appear as their statuses land.
- **Specs.** New `web/e2e/opens-at-once.spec.ts` (4 flows, 300 light Assets written as `asset.toml` files: first rows before any status
  answer and only about 40 rows drawn; a scroll to the end asks for the last rows within the first requests, in a chunk of 30, and no image is
  fetched; a change to two Assets, one off screen, asks for those and the window, not the 300; the district thumbnail is lazy). Changed
  `web/e2e/icon.spec.ts`: it found the Kind's heading as the `section` that contains the row, and the heading and its rows are now separate
  items of one virtual list; it checks the heading and the board row instead. The full suite: 174 of 181 passed on the first pass (3 workers);
  of the 7 failures, 4 (`area`, `emitter`, `loopedits`, `loops-follow-ups`) and `shell` "clicking a finding jumps" passed alone (they clicked a
  Stage while the machine was loaded: the same kind of timeout as 0369's run), `icon` was the spec change above, and the district test
  timed out on its first version (241 rooms in the Probe; now 30 rooms). Those and the new spec pass together with `--workers=2`.
- `npm run build` passes. Screenshot: `web/shots/0374-list.png` (the list, the status board and the placeholders gone).

**Measured** on the art copy (41 Assets, a real `serve`, Chromium via Playwright; `measure.mjs` in the session scratchpad). "Before" is the
UI of 0369 on the 0373 server (the list showed when `status` answered); "after" this ticket. First rows: time from page load to the first Asset
button. All statuses: no "status" in the strip. Cold: `.kiripix/derived-cache.json` deleted; warm: the cache on disk, a new server.

| | before | after |
|---|---|---|
| cold, first rows | 23 s and 39 s (two runs) | 0.35 s |
| cold, all statuses | the same (nothing shows until then) | 20 s (the server's work; the list is usable meanwhile) |
| warm, first rows | 1.0 s | 0.3 s |
| warm, all statuses | 1.0 s | 0.8 to 1.0 s |
| second page open on the same server, first rows / all | 0.15-0.2 s / 0.2-0.3 s | 0.15 s / 0.5-0.8 s |

The last row shows the cost of the page's first read sending a new `refresh` token (the server then drops what it remembers); the old UI
asked without one and kept the server's memory. It is the design of 0373 (a page open is a full read, as Reload is); if the Owner would
rather a page open reuse the server's memory, `Rows.newToken` is not called for the first read. Not measured at 300+ real Assets: only the
300 light ones of the spec.

**Gaps.** None blocks. Noted: `useWearables` still reads each body's and Wearable's `show` and two small files when any Wearable exists
(one call per body and Wearable, in the background, not on the first paint); a row's `base`/`body` from the list is the only
dependency the UI knows, so an NPC's chosen Wearables are covered by the re-ask on scroll, not by name.

Changed after the ticket, in the main session (the Owner's aim: hundreds of Assets): the page's first read and the window's focus no
longer make `serve` forget everything. A focus refresh at 400 Assets would have worked the whole Project out again on every switch
of windows. Now the page's first read sends no `refresh` token (it keeps what `serve` remembers, which is in step with every write
Kiripix recorded), and the window getting the focus back reads again the rows on screen and the open Asset, which `serve` forgets
first through `status`'s new `forget` (0373); every other row is kept. Only Reload (and a reconnect) sends a new token.

Two fixes found by the batch's final e2e run (2026-11-21): the focus marks those Assets' files as changed (`noteChange` of their
folders), since an image's URL carries the number of its file's last change, not `imageVersion` (`refresh.spec` "a file changed by
hand"); and `Rows.queue` keeps for each row only the answer of the newest `queue` call that asked for it, so a call asked during an
action that answers after the one asked when it ended can't put a settled stop back (`queue.spec` "the Owner steps through", which
failed now and then with the count one too high).
