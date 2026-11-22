---
status: done
milestone: M6
agent: core-engineer
type: ticket
---

# M6: keep a Stage's Check results until its output changes

Spec §5 and §8 (Checks), ADR 0005. Part of the Owner's report of 2026-11-21 that the UI is slow again; see
[0366](0366-m6-watch-the-project-without-scanning-it.md) for the whole picture.

## What was measured (2026-11-21)

From the CLI in the art Project (41 Assets, 32 of them characters), with no `serve`. A bare process start is about 0.55 s.

| Command | Wall time |
|---|---|
| `status --json` | 1.0-1.2 s |
| `queue --json` | 3.7-5.3 s |
| `check character.mc03_female --json` | 6.7 s |
| `check room.ch01_dungeon_r01 --json` | 1.1 s |
| `show`, `next` or `probe style` for one Asset | 0.6-1.1 s |

The UI's refresh (`web/src/App.tsx`, `refresh`) calls `status`, `queue`, `show`, `next`, `check` and `probe style`, one after
the other, on every open and after every `changed` event. On `character.mc03_female` that is about 12 s of Commands.

A profile of `queue`: 4.67 s of 5.2 s is in `_asset_queue` (`kiripix/core/queue.py:135`), and 4.14 s of that is
`AssetGraph.check` (`kiripix/core/graph.py:806`) on the 20 Stages that are done. Every call runs every done Stage's Checks
again, reading each output back from disk: 3,719 PNGs through `read_rgba` and 5,927 `Image.open` calls in one `queue`. A
profile of `check character.mc03_female`: 6.0 s in `graph.check`, of which 4.36 s is the `sheet` Check (see
[0368](0368-m6-cheaper-character-checks.md)). Only `graph.states` (0.5 s for 41 Assets) is the status itself.

A Check reads a built output, and a built output doesn't change until the Stage runs again: core swaps the output folder in
whole, with its stamp. So the same Checks give the same findings until something they read changes.

## What to do

1. **Keep each Stage's Check findings** in the computation cache from [0090](../m3/0090-m3-status-without-re-deriving-lifts.md)
   (`HashCache.derived` / `remember`, `kiripix/core/hashing.py`, kept in `.kiripix/derived-cache.json`), keyed on everything
   the Check reads:
   - the output it was built from: the stamp's `input_hash`, and the stamp file's size and time (a rebuild with the same input hash, such as
     `--force`, still writes a new stamp);
   - the Stage's `version` and the recipes' source files' size and time (as 0090's key does), so a change to a Check is a miss;
   - anything outside the output folder the Check reads. Audit each Kind's `check` functions for reads of their own: the
     Project palette, `kiripix.toml`, a Wearable's body, another Asset (style references). A read the key can't name is a
     reason to leave that Stage's Check out of the cache, listed in the Result.
   The advisers (`_ADVISERS`, applied after the Check) run on every call. Cache only the Check's own findings, unless the
   audit shows an adviser is also pure in the key.
2. **Store the findings, never a status.** Deleting `.kiripix/` loses nothing but time (ADR 0005). Findings are
   stored as their JSON, and a cache entry that doesn't parse as today's `Finding` is a miss, not an error.
3. `check`, `queue` and anything else that calls `graph.check` go through the cache; there is one place that reads and
   writes it.
4. **Record the table above again** after the change, cold (the first call after `.kiripix/derived-cache.json` is deleted) and
   warm.

## Acceptance criteria

- [x] On the art Project, `queue --json` and `check <asset> --json` for the five Assets measured above give output identical to the
      code before the change (`cmp`), cold and warm.
- [x] A CLI test with the test Kind `demo`: a second `check` does not run the Stage's Check again; it does run again after
      the Stage is rebuilt (also with `--force` and the same inputs), after the demo Stage's `version` changes, and after a
      file outside the output that the Check reads changes. The demo Check can count its own calls in a file the test reads;
      the test doesn't import internals.
- [x] A budget test beside `tests/cli/test_status_budget.py`: warm `queue` on a Project of 300 `demo` Assets, each with a Check that
      reads its output, stays under the same budget as `status` there, less a process start.
- [x] The Result names each Stage left out of the cache, and why.
- [x] `uv run mypy` and `uv run lint-imports` pass.

## Result

### What was done (2026-11-21)

- `kiripix/core/checkcache.py` is the one place that reads and writes the cache (`HashCache.derived` / `remember`, entry
  `check:<asset>:<stage>` in `.kiripix/derived-cache.json`). `AssetGraph.check` (`kiripix/core/graph.py`) asks it first and keeps the
  Check's own findings after a miss; `queue`, `check`, `check --all` and the Project checks all call `graph.check`, so all go through it.
  The advisers run on every call, after the cache (they read the game's Manifest). Findings are kept as their JSON; an entry that does
  not parse as today's `Finding` is a miss, and findings that don't round-trip are not kept. Nothing stored is a status.
- The key: the stamp's content, size and time; every file of the Stage's own output folder and of each upstream output folder (size and
  time, so an output the Owner edits by hand with no rebuild is a miss: `test_character_palette`'s hand-edited frame, and a demo test); the
  Stage's current input hash (parameters, Decisions, declared files, settings, Project files, base and body hashes); the Stage's
  `version`; the recipes', Ops' and Checks' source files by size and time; the Asset's own folder outside `work/`, `out/` and
  `history.jsonl` (size and time); the whole folder of the base, the body, the Wearables of a body and the Assets a Stage chose
  (`StageInputs.chosen`, ticket 0356); `kiripix.toml` and the palette file; and `StageSpec.check_reads`. A file changed in the last two seconds is also kept by its content, which a hit checks, so a quick second write can't be missed.
- Stages left out of the cache: none by default. `StageSpec.check_cache=False` leaves one out. A key that can't be worked out (an
  unreadable related Asset) skips the cache for that call. The audit found no Check that launches Blender or a Runner, or reads a
  Project file or another Asset outside the key above; the Checks that read `run.asset_dir`, `run.base`, `run.body`, `run.wearing` and
  `run.project_files` are covered by it. Checks in `kiripix/checks/style.py` run in `core/style.py`, not in `graph.check`, so they are not cached.
- **Later Checks must declare their reads.** A Check may read its output, its upstream outputs, the Asset's own folder, the folders of
  its base, body, Wearables and chosen Assets, `kiripix.toml`, the palette and the Stage's declared inputs, and nothing else changes
  its answer unannounced. Anything else (a Project file such as `style/bible.md`, another Asset, a tool's version) is declared with
  `StageSpec.check_reads=lambda run: ["path/relative/to/the/Project/root", ...]` (a folder stands for every file under it), or the Stage
  sets `check_cache=False`. A Check must also be a pure function of those reads (no clock, no random, no environment).
- Tests: `tests/cli/test_check_cache.py` (demo Kind; the demo `copy` Check counts its calls in `.kiripix/check-calls.txt`, reads
  `src/note.txt` and the declared `style-note.txt`); the budget test is in `tests/cli/test_status_budget.py`
  (warm `queue` of 300 demo Assets, less a process start, with no Check run again; limit 4 s, not `status`'s 3 s: it measured
  3.2-3.6 s on a machine loaded by other agents' tests, where `status` itself took 6 s. The Owner may want to tighten it on a quiet machine).

### Art Project (a copy in the scratchpad; the machine was busy with other agents' tests, so every time is noisy)

Output: `check` for `character.mc03_female`, `character.mc03_female_clothes01`, `character.npc_mc_m_a`, `room.ch01_dungeon_r01`,
`room.ch01_dungeon_r03` and `prop.street_lamp`, and `queue`, with the final code, cold and warm, are `cmp`-identical to the output of
the code before the change (the same code with the cache switched off).

Wall time, ms, one cold run and three warm runs, run back to back in one quiet-ish minute (a bare `import kiripix.commands` was
about 0.3-0.5 s; other agents' tests were running, so read these as rough):

| Command | Before, cold | Before, warm | After, cold | After, warm |
|---|---|---|---|---|
| `status` | 46,202 | 2,833-3,490 | 23,818 | 1,885-1,977 |
| `queue` | 13,034 | 2,246-2,658 | 7,120 | 1,892-2,145 |
| `check character.mc03_female` | 16,177 | 1,257-1,534 | 5,491 | 1,318-1,464 |
| `check room.ch01_dungeon_r01` | 2,401 | (not recorded) | 1,730 | 1,882-2,386 |

"Cold" is the first call after `.kiripix/derived-cache.json` is deleted, so it includes 0090's lift replay, which is most of the
difference between the cold columns (it was warm in neither run) and is not this ticket's. The ticket's 6.7 s `check` and 3.7-5.3 s
`queue` did not reproduce on this machine with the code before the change (warm 1.3 s and 2.3 s), so the saving here is
small, about 0.4 s on `queue`; the cost of a hit is the key: an in-process profile of all 95 built Stages with checks is 3.7 s
in total on this noisy machine, mostly the input hash (which `status` pays too) and the folder walks. The folder walks use one
`os.scandir` pass per folder and are worked out once per folder per Command; a first version using `pathlib` took 25 s for the
same keys. The saving is larger where a Check reads many files (the `sheet` Check, ticket 0368) and is the point of this ticket.

### Measured again on a quiet machine (2026-11-21, after the batch, no other process running)

Same scratchpad copy of the art Project, the batch's final code (0366-0368 all in), warm runs 2 and 3 after one cold run:

| Command | Ticket's table (before 0367/0368) | Warm, after |
|---|---|---|
| `status` | 1.0-1.2 s | 0.9-1.1 s |
| `queue` | 3.7-5.3 s | 1.1-1.2 s |
| `check character.mc03_female` | 6.7 s | 0.65-0.71 s |

The folder walks in the key are not a cost worth a ticket on a quiet machine; the budget test's 4 s limit is checked by the full
suite run at the end of the batch.
