---
status: done
milestone: M6
agent: ui-engineer
type: ticket
depends_on: [0366-m6-watch-the-project-without-scanning-it.md]
---

# M6: UI: a refresh asks for less, at once, and only for what changed

Spec §11. Part of the Owner's report of 2026-11-21 that the UI is slow again; see
[0366](0366-m6-watch-the-project-without-scanning-it.md). The Commands get cheaper in 0366–0368; this ticket makes the UI
ask for fewer of them, and stop waiting for each one before asking the next.

## What was measured (2026-11-21)

`refresh` in `web/src/App.tsx` calls these one after another, each `await`ed before the next starts. The times are from the
CLI on the art Project, less a 0.55 s process start:

| Call | Asks for | About |
|---|---|---|
| `status` | the whole Project | 0.5-0.7 s |
| `queue` | the whole Project, every done Stage's Checks | 3.2-4.7 s |
| `show` | the open Asset | 0.1-0.4 s |
| `next` | the open Asset | 0.1-0.5 s |
| `check` | the open Asset's Checks | 0.2-6.2 s (`character.mc03_female`: 6.2 s) |
| `probe style` | the open Asset, or the first Asset when none is open | 0.1-0.3 s |

So opening `character.mc03_female` is about 12 s, and the room list waits for `queue` before it shows anything.

It runs more often than it needs to:

- **After every action, twice.** `perform` awaits `refresh()` once the Command answers. The same Command's writes reach the
  watch, whose `changed` event (100 ms later) calls `refresh` again, and since the first is still running the loop runs a
  second full refresh.
- **On every `changed` event, for everything.** An agent's run on another Asset still calls `show`, `next` and `check` on the
  open one. The event names the paths (up to 200), and the UI only uses them to decide whether to re-fetch images.
- **Every image, on any PNG.** `imageVersion` goes up when any `.png` in the Project changes, so every image on screen is
  fetched again, whichever Asset the PNG belongs to. The file route sends `Cache-Control: no-cache`, so the browser also asks
  the server about every image before it uses its own copy.
- **`useWearables`** (`web/src/wearableScreens.tsx:79`) depends on `refreshes`: once the Project has any Wearable, every
  refresh calls `show` on every non-Wearable Asset (39 in the art Project) and again on each Wearable, and reads their
  `sheet.json` and `render.json`. It has no Wearable today, so this costs nothing yet.

## What to do

1. **Ask at once.** Start every call of a refresh together (`Promise.all`). `serve` runs each Command on its own job
   thread. Keep the rule in `refresh`'s comment: what shows is never older than a change, and a refresh asked for while one
   runs runs once more after it.
2. **Show each answer as it lands.** The list shows once `status` answers, an Asset once `show` and `next` answer; the queue
   count, the checks and the style scores fill in after them. The working strip says what is still being read.
3. **One refresh per action.** After an action, the refresh it already does is enough: a `changed` event whose paths are
   all marked as `serve`'s own writes (0366 adds the mark) starts no refresh. A path an agent wrote, in the same event or
   not, still does.
4. **Scope a `changed` refresh to its paths.** `status` and `queue` always. `show`, `next`, `check` and `probe style` for the open
   Asset only when a path is under its folder (`assets/<kind>/<name>/`), is Project-wide (`kiripix.toml`, the style
   references), or is the folder of its body or of its Wearables. When the event gives no paths (more than 200 changed,
   or the `hello` after a reconnect), refresh everything as today.
5. **Fetch an image again only when its own file changed.** Keep a version per shown file (or per Asset folder), bumped
   by the `changed` paths, instead of one counter for the whole Project.
6. **`useWearables` re-reads a body only when its files changed**, by the same paths, not on every refresh.
7. **`probe style` with no Asset open** is asked once, and again only when the style references change.
8. **Changes made outside Kiripix.** After 0366, the `changed` event only names what Kiripix itself wrote. A file edited
   by hand (an `asset.toml`, a file dropped into a folder) is picked up by a full refresh when the window gets the focus
   again (no more than one every few seconds), and by a Reload button in the header (with `F5` still reloading the page).

## Acceptance criteria

- [x] Playwright against a real `kiripix serve` (the request log, `page.on("request")`):
  - [x] opening an Asset sends its refresh's calls before the first of them answers;
  - [x] one Decision on the open Asset gives one refresh, not two;
  - [x] a CLI `decide` on another Asset, run while the UI is open, calls `status` and `queue` but not `show`, `next` or
        `check` for the open one, and doesn't fetch the open Asset's images again; the change on the other Asset shows in
        the list;
  - [x] a CLI run of a Stage of the open Asset still updates its image and its checks on screen;
  - [x] a file of the open Asset changed directly on disk (not through Kiripix) shows after the Reload button, and after
        the window loses and gets back the focus.
- [x] The e2e specs that exist today pass (at `--workers=2` if they time out at the default, as noted for character specs).
- [x] `npm run build` passes.

## Result

The UI's refresh asks together, once per action, and for what changed. No Python changed, no Command is missing.

- **At once, each answer as it lands** (`refresh` in `web/src/App.tsx`, `readOnce`). `status`, `queue`, `show`, `next`, `check` and
  `probe style` start together; each `setData`s its own part. The list shows once `status` answers, the Asset once `show`
  answers. The strip's label says what is still read ("Opening room.alley: reading the checks, the style"). A refresh asked
  for while one runs is merged into one more; `refresh()` returns the promise of the running loop, so an action awaits it.
  `show` and `next` land separately, so the Stage an Asset opens on waits for both (`coreFor`); the first version took
  `show.stages[0]` too early.
- **Scope.** `refresh(paths)` asks `status` and `queue` always, and the Asset's four calls only when a path is under its folder,
  its base's, its body's or its Wearables' folder, or lies outside `assets/` (`kiripix.toml`, the style references). `null`
  paths (more than 200, or a reconnect's `hello`) ask everything. Opening an Asset asks only its four calls, and the list only
  when `status` has never answered. Going back to the list asks nothing (it is current from the events).
- **One refresh per action.** The `changed` event's `own` paths start no refresh of their own. Exception, kept on purpose: while an
  action's Command is still running (`running`, in `perform`), its own paths do refresh, so a Decision shows while the rebuild
  that follows it (the Mask brush, a clip) is still running; `work.spec.ts` "a brush stroke stays drawn" depends on it. The
  first `hello` starts none (the page's first refresh covers it) unless the stream failed before it connected (`shell.spec.ts` "a change made while the event stream was down"); one after a reconnect does. An agent's path, in the same
  event or not, always does.
- **Images.** `fileUrl` (`web/src/api.ts`) takes its `v` from the newest change that touches that file or a folder above it
  (`changeStamp`), not from a counter; its second argument is now unused. The page-wide `imageVersion` goes up only when a
  changed path touches a file the page has shown, so a screen's effects reload then and not for another Asset's PNG.
  Own writes count here too: the image changed, though no refresh follows.
- **`refreshes` is now two counters.** `refreshes` goes up when the open Asset's `show` and `next` have answered (what the
  Asset's screens read from files follows it, so a scoped refresh that skipped the Asset re-reads none of it);
  `listRefreshes` goes up when `status` answers (the district view and the waiting rooms follow it).
- **`useWearables`** keeps a read per body and reads it again only when the stamp of its folder or of one of its Wearables'
  folders changed, or the set of Assets changed. With no Wearable it asks nothing.
- **`probe style` with no Asset open** is asked once (`styleFresh`) and again when a path outside `assets/` changes, or on a
  full refresh.
- **Outside changes.** A Reload button in the header (`data-testid="reload"`), and a full refresh when the window gets the focus,
  at most once every 5 s since the last full read (`FOCUS_REFRESH_MS`). `F5` still works.

**Specs.** New `web/e2e/refresh.spec.ts`: the five flows of the acceptance, from a request log (`page.on("request")`). Changed
`web/e2e/work.spec.ts` "opening the room list and a room show the strip before the response" (now "reading the Project and
opening a room ..."): it held `**/api/status` while opening a room, and opening a room no longer asks `status`; it now holds
`status` on the page's first load and `show` on opening a room, and the label is matched with `toContainText` because it
carries the "reading ..." list. No spec depended on a hand-written file reaching the UI through the old scan.

**Run** (`--workers=3`): the full suite, 176 tests, had 11 failures on the first pass; after the two fixes above and the spec
change, all pass but `sprite.spec.ts` "a click on fit sets the pivot ..." (the measured pivot of the CLI is `[7, 13]`, the spec
expects `[7, 14]`, before the UI is opened: the Python side, another agent's work in the tree) and the
`loops-follow-ups.spec.ts:141` timeout, which passes alone. Screenshot: `web/shots/0369-reload.png` (the header with Reload).


Follow-up in the same batch: `sprite.spec.ts` "a click on fit sets the pivot ..." failed before the UI opened, expecting the pivot
on row 14. That was stale since M5's ticket 0318 (the pivot sits `GROUND_RATIO` of the figure's height above the measured feet: 1 px
for its 13 px figure), not a regression of this batch (git HEAD gives the same pivot). The spec now expects `[7, 13]` and works out
the clicked points from the measured pivot.
