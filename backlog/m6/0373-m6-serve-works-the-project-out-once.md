---
status: done
milestone: M6
agent: core-engineer
type: ticket
---

# M6: `serve` works out each Asset once, and the list answers before any status

Spec §10.6, §11 and ADR 0005. Part of the Owner's report of 2026-11-21 (see [0372](0372-m6-status-survives-a-code-update.md)
for what was measured). The Owner's aim: hundreds of rooms and characters, and the UI still opens at once.

## The problem

Every `status` and `queue` works out every Asset's state from scratch: about 15 ms an Asset warm (0.6 s for 41, so about 6 s
for 400) and far more cold, and `queue` then runs each done Stage's Checks. Asked together, as the UI does, they do the same work
twice and slow each other down (0.6 s alone, 1.8 s together). Nothing shows until `status` answers. `serve` is one long-lived
process, and since [0366](0366-m6-watch-the-project-without-scanning-it.md) it knows which paths Kiripix wrote.

## What to do

1. **A cheap list.** A Command (or a `status` option; say which and why) that answers the Project's Assets (ID, Kind, name, and
   what the list shows without a graph: the reference star, the base, the body) from `asset.toml` files alone, with no input
   hash. Well under 100 ms for 400 Assets. A contract sample.
2. **One computation per Asset in `serve`.** `serve`'s Session keeps each Asset's derived state (what `status` and `queue` need)
   in memory and works it out at most once at a time: two calls that need the same Asset wait for one computation. A `changed`
   event's paths drop the entries they touch: the Asset's folder; its dependants (a body's Wearables, a base's characters and
   NPCs, an NPC's chosen Assets); everything for a Project-wide path (`kiripix.toml`, the palette, the style references).
   Memory only, never on disk (ADR 0005); the computation cache below it stays as it is. The CLI is unchanged: one process, one
   call. Keep it in `kiripix.commands` / core, not in the server adapter (adapters hold no logic).
3. **Answers by Asset.** `status` and `queue` accept a list of Asset IDs (or reuse `--match`), so the UI can ask for the rows it
   shows; with none, every Asset as today.
4. **Hand edits.** A file changed outside Kiripix isn't in the change record (0366). The full refresh the UI does on Reload and
   on window focus (0369) must drop `serve`'s memory first; say how the UI asks for that (a parameter on the call, or a
   transport route, with ADR 0007's rules if a route).
5. **A budget test:** `serve` on a Project of 400 `demo` Assets: the cheap list under 0.3 s; a second `status` (warm, nothing
   changed) under 0.3 s; after one Asset changes, `status` under 0.5 s.

## Acceptance criteria

- [x] The budget test passes.
- [x] Tests at the CLI / serve seam: a change to one Asset recomputes only it and its dependants; a `kiripix.toml` change
      recomputes every Asset; concurrent `status` and `queue` work out an Asset once.
- [x] On the art Project copy, 0372's open table recorded again: a warm open under 0.5 s for everything the list needs.
- [x] `uv run mypy` and `uv run lint-imports` pass; the contract test passes.

## Result

`serve` keeps each Asset's derived state in memory, worked out at most once at a time, and there is a cheap list. The CLI is
unchanged (one process, one call, no memory). Spec §10.6 and §11 say it.

- **The cheap list is a new Command, `assets`** (not a `status` option: `status` is the Stage graph, and a Command that never
  builds one has its own output). ID, Kind, name, `base`, `body` and `reference` from the `asset.toml` files and `[style]
  references`, no hash. 0.02 s warm in `serve`, about 0.15 s the first time for 400 Assets (it reads 400 files).
- **`kiripix.core.memory.Memory`** (the Session owns one; `Context.memory` carries it to the Commands, None in the CLI). Layers
  per Asset: `state` (the Stage states and `waits_on`, shared by `status` and `queue`), `export` (`export_command`) and `queue`
  (its stops and fixes). Single flight: two calls that need the same entry wait for one computation (a cancelled waiter stops
  waiting; a cancelled or failed owner makes the waiters take it up). A computation that was running when anything dropped is
  not kept. Memory only.
- **Never older than a recorded change.** Every `status`, `queue` and `assets` call first reads the change files from where
  the last call stopped (`core.changes.ChangeReader`), so it has no 0.3 s wait and sees a write recorded before it began,
  from any process. A path inside `assets/<kind>/<name>/` drops that Asset, every entry whose dependencies include it, and,
  for `asset.toml`, the Assets it names now and named before. A dependency set is the Asset, the Assets its parameters name
  (a base, a body, the chosen Wearables, found by their IDs in `[params]` and the Stage tables) and what those name, and the
  Assets that name it (a body's Wearables). Any other path (`kiripix.toml`, the palette, style, a file a Check reads) drops
  everything: conservative, since a Check may declare a read anywhere. The list of Assets is kept in step the same way.
- **The game's files are not recorded**, so `export_command` can't be dropped by the record: `status` asks `export_stamp`
  (a digest of the export root's files by name, time and size, or why the target can't be used) once per call, and an
  Asset's `export` entry made under another stamp is worked out again.
- **The Project checks are not kept** (`run_project_checks` runs on every `queue` call): they read the game's Manifest and
  every Asset, and cost 0.03 s for 41 Assets, so a warm `queue` is about 0.1 s there. Worth a look at 400 real Assets.
- **By Asset ID:** `status` and `queue` take `assets` (`--asset` repeated on the command line); none given is everything, an
  empty list is none, an unknown ID is an `asset.not_found` finding and the others answer. `match` and `kind` work as before.
- **Hand edits:** a `refresh` parameter (a token string) on `assets`, `status` and `queue`, not a route (ADR 0007 untouched).
  The first call with a token `serve` hasn't seen drops everything, the list included; the others with the same token (the UI
  sends all of a refresh's calls together) keep what they work out. No effect on the CLI.
- No Stage changed, so no `version` bump. `kiripix/commands/index.py` was regenerated (`index_gen`); it also gained the lines
  for `note`, `op dither-alpha` and `new`'s help, which earlier tickets had left out of date.
- Tests: `tests/cli/test_serve_memory.py` (19: the list, by ID, the one computation, one Asset and its dependants,
  `kiripix.toml`, the game under `serve`, hand edits and `refresh`, concurrency, a change during a computation, and the
  400-Asset budget). The test Kinds' hook in `tests/fixtures/kiripix_test_recipes.py` logs each Asset's work while
  `.kiripix/log-states` exists. Contract samples for `assets`, `status --asset --refresh` and `queue --asset`, and their REST
  bodies in `test_serve.py`.

Measured on the art copy (41 Assets, a real `serve`; `open_measure2.py` in the session's scratchpad; "before" is the figures
from 0372):

| Call | Before | After |
|---|---|---|
| list (`assets`), first call / warm | - | 0.27 s / 0.02 s |
| `status` + `queue` together, first (the disk caches warm) | 1.5-1.8 s, 1.7-2.0 s | 0.56 s |
| `status` + `queue` together, warm | 1.5-1.8 s, 1.7-2.0 s | 0.03 s, 0.10 s |
| `status` / `queue` of 20 IDs, warm | - | 0.03 s / 0.09 s |
| the same with a new `refresh` token | - | 0.47 s |
| `status` after one Asset changed in another process | 0.5-0.6 s | 0.04 s |

On a Project of 400 `demo` Assets (the budget test, alone): the list 0.03 s warm, a warm `status` 0.05 s, `status` after one
Asset changed 0.04 s.

### API note for 0374

- **Cheap list:** `POST /api/assets`, input `{kind?: string, match?: glob, refresh?: string}`, data `{project: string, assets:
  [{asset, kind, name, base: string|null, body: string|null, reference: boolean}]}`, in ID order. An `asset.toml` that can't
  be read is a finding (exit 1, HTTP 400, the other rows still in `data`). `base` and `body` are as written in `asset.toml`.
- **Status and queue for some Assets:** `POST /api/status {assets: ["room.a", ...]}` and `POST /api/queue {assets: [...]}`. Omit
  `assets` for everything. `[]` asks for nothing, so don't send an empty chunk. Rows come back in ID order, not the order
  asked. An ID that isn't an Asset anymore is an `asset.not_found` finding (`status` then answers HTTP 400 with the other rows
  in `data`; `queue` answers 200 with the finding), and the rest answer. `queue`'s `counts` and `assets_clear` are for the
  Assets asked, so a chunked queue's counts must be added up by the caller; the Project checks' findings count only where they
  name an asked Asset.
- **A full refresh** (Reload, window focus): make up one string per refresh (a counter or a timestamp) and send it as `refresh`
  in the body of every `assets`, `status` and `queue` call of that refresh. The first one `serve` sees drops what it remembers
  (the Assets and every derived state); the others keep what they work out. Only the last token is remembered, so never
  reuse one for a new refresh. `show`, `next`, `check` and `probe` are not remembered and need nothing.
- **`changed` events:** unchanged (`{count, paths, own}`, 0.3 s tick). `serve` drops from the same record without waiting for
  the event, so a `status` or `queue` asked after an action is current whether or not the event has arrived. A UI that
  refreshes only the rows a change names can use `paths` as 0369 does: `assets/<kind>/<name>/...` is that Asset, any path
  outside `assets/` is Project-wide (every row). A body's, a base's or an NPC's Wearable's change can change the rows of its
  Wearables, characters and NPCs, and events don't name dependants, so refresh those rows too, or simply ask again for the
  whole visible window (cheap: unchanged rows come from memory). A row not named can be stale only when a file was changed
  outside Kiripix.

Added after the ticket, in the main session, for 0374's window-focus refresh: `status` takes `forget` (Asset IDs; `--forget` on the
command line): with `serve`, those Assets are forgotten as if each had changed (their `asset.toml` read again, every entry that reads
them dropped) before the answer, and everything else is kept (`Memory.forget`). No effect on the CLI. Test:
`test_forget_sees_a_hand_edit_in_the_named_assets_and_keeps_the_rest`; the contract sample carries it.
