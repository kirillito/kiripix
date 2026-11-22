---
status: done
milestone: M6
agent: core-engineer
type: ticket
---

# M6: tell the UI what changed from Kiripix's own record, instead of scanning the Project

Spec §10.4 (locks), §10.6 (the "changed" event) and §11. Found by the Owner on 2026-11-21: the UI is slow again. Opening the
Project takes a long time on the machine without a GPU, and so does opening a room or a character. This ticket fixes the
largest single cost; [0367](0367-m6-keep-check-results.md), [0368](0368-m6-cheaper-character-checks.md) and
[0369](0369-m6-ui-refresh-asks-less.md) fix the rest.

## What was measured (2026-11-21)

The art Project (`../urban-mystery-club-art`) now has 41 Assets (32 characters, 6 rooms, 2 sprites, 1 Prop) and 126,000
files, 1.9 GB. Outside `.kiripix/` and `.git` there are 35,410 files, most of them a character's frames (`mc02` alone has 7,693).

`ProjectWatch` (`kiripix/commands/watch.py`) polls: every 0.3 s, `snapshot` walks the whole Project and stats every file.

| What | Time |
|---|---|
| One `snapshot` of the art Project | 1.70-1.81 s |
| Its interval | 0.3 s |

So one scan takes about six intervals, and the next starts 0.3 s after the last ends: a thread of `serve` is busy scanning
almost all the time. It is Python code (a `Path` and a `relative_to` per file), so it holds the GIL for much of that time,
and every Command `serve` runs (each on its own job thread) competes with it. `start` also takes one snapshot before the
server answers, about 1.8 s on every `kiripix ui`. On a slower machine, such as the one without a GPU, all of this costs
more. The GPU itself plays no part: nothing on the path that opens the list, a room or a character loads a Runner (as
[0090](../m3/0090-m3-status-without-re-deriving-lifts.md) found, and nothing since has changed that).

## Why there is a watch, and what replaces it

The watch exists so that the UI shows what an agent's CLI call changed while the Owner has the UI open. Locks don't
replace it: the Project, Asset and GPU locks (`kiripix/core/locks.py`) already keep two writers apart, across processes, and
stay as they are. What the UI needs is to be told that something changed and where.

Almost everything in the Project is written by Kiripix itself, through `kiripix.core.atomic` or core's swap of a Stage's
output folder. So Kiripix records what it changed, and `serve` reads that record instead of scanning.

**One change file per process.** A Claude CLI run on one Asset and the Owner's edit in the UI on another hold different
locks and can write at the same moment. A single shared log would need its own lock, because an append on Windows
is a seek to the end and then a write, so two processes can overwrite each other's lines. Instead, each process writes only
its own file, `.kiripix/changes/<pid>-<process start time>.jsonl` (the start time makes a reused pid a new file), and
nothing else ever writes to that file.

## What to do

1. **Record every change, after it is in place.** One function in core, called by every write:
   - `atomic.write_bytes` (and through it `write_text`, `write_json`, `append_jsonl_many`) and `atomic.append_jsonl`;
   - the swap of a Stage's output folder (`kiripix/core/graph.py`, around the rename at line 917): one line naming the
     output folder, not each file in it;
   - the writes that don't go through `core.atomic` today. Audit them all: the inbox move (`kiripix/core/inbox.py:105`),
     the snapshot renames (`kiripix/core/snapshots.py:154-182`), `kiripix/core/editof.py:386`, and anything else
     `grep` finds (`os.replace`, `.rename(`, `.write_bytes(`, `.save(`). A write into a `.tmp-*` folder that is later swapped
     in needs no record of its own. A write a subprocess makes (Blender) is recorded by the Command that ran it, once the
     subprocess is done.
   A line is one JSON object: the Project-relative path(s) and the time. It is written after the file is in place,
   never before, so a refresh it causes always reads the new file. Nothing is recorded for `.kiripix/` itself, `.tmp-*`
   folders or `time.jsonl`, as the watch skips them today.
2. **`serve` reads the change files instead of scanning.** Every 0.3 s it lists `.kiripix/changes/` (a handful of files)
   and, for each file that grew, reads from where it stopped up to the last complete line. A line still being written is
   read on the next tick. Each tick with new lines sends one `changed` event with their paths, as today, so the
   UI's side of the event doesn't change. Each path also says whether `serve`'s own process wrote it (its own file), so
   the UI can tell its own writes from an agent's ([0369](0369-m6-ui-refresh-asks-less.md) uses this).
3. **No snapshot at start-up.** `serve` starts reading each change file at its current end, so it answers at once.
4. **Clean up.** When `serve` starts, it deletes change files whose process is gone (as `locks.py` decides a stale lock) and
   that are more than a day old. A CLI process's file is left for any `serve` that is running to read.
5. **Remove the scan.** `snapshot` and its polling go, and the docstring of `kiripix/commands/watch.py` says what replaces
   them and what isn't seen. A file changed outside Kiripix (an `asset.toml` edited by hand, a file dropped into a folder)
   is no longer noticed. The UI covers that by refreshing when its window gets the focus again, and with a Reload button
   ([0369](0369-m6-ui-refresh-asks-less.md)).

The change files are a record of writes, never of status (ADR 0005). Deleting `.kiripix/changes/` loses nothing but events
the UI hasn't seen yet. They are `.jsonl`, append-only, one object per line, LF, as the conventions require. They are only
ever read in `.kiripix/`, so they need no `schema_version` and no migration; a line that doesn't parse is skipped.

## Acceptance criteria

- [x] The `changed` tests in `tests/cli/test_serve.py` (such as `test_an_agents_change_pushes_a_changed_event`) pass
      unchanged: a file written by a CLI call outside the UI still reaches the UI as a `changed` event.
- [x] New tests in `tests/cli/test_serve.py`, against a running `serve`:
  - [x] a Stage run from the CLI gives a `changed` event naming its output folder, and nothing under `.kiripix/` or a
        `.tmp-*` folder;
  - [x] two CLI processes writing to two different Assets at the same time (for example two `decide` loops of 50 each):
        every one of their changes reaches the event stream, none is lost;
  - [x] a change made by `serve`'s own Command is marked as its own; a CLI change isn't;
  - [x] after a restart of `serve`, a change file of a process that is gone and more than a day old is deleted, and a
        live one is kept.
- [x] Each write the audit in step 1 found outside `core.atomic` is listed in the Result, with how it is now recorded.
- [x] Recorded here, on the art Project: `serve`'s CPU use over 30 s with the UI open and nothing happening (for example
      with `psutil.Process().cpu_percent`), and the time from `kiripix ui` to its ready line, before and after. These are
      recorded for information; there is no budget on them.
- [x] `uv run mypy` and `uv run lint-imports` pass.

## Result

`serve` no longer scans the Project. Each process records its writes in `.kiripix/changes/<pid>-<start ms>.jsonl`
(`kiripix/core/changes.py`), and `ProjectWatch` (`kiripix/commands/watch.py`) reads those files every 0.3 s. Spec §10.6
has a paragraph on it. No Stage `version` is bumped, no data file changes.

**The `changed` event** is `{"count": <all paths>, "paths": [first 200, sorted], "own": [...]}`. `own` is the subset of
`paths` (so also at most 200) that only `serve`'s own process wrote in that tick: the Commands it ran, including their
subprocesses. A path an agent's CLI also wrote in the same tick is not in `own`. A path in `paths` and not in `own` is an
agent's. A Stage's output is its folder (`assets/room/a/work/masks`), not each file in it. `own` is new, the rest is as
before. The UI (0369) tells its own writes from an agent's by `own`.

**One change line** is `{"t": <epoch seconds>, "paths": [...]}`, Project-relative with `/`. `core.changes.record(*paths)`
finds the Project from the path (the nearest `kiripix.toml` above it), appends after the write, never raises, and skips
`.kiripix/`, `.git`, `.tmp-*` and `.old-*` folders and `time.jsonl`, and anything outside a Project (an export into Godot).
`changes.remove(path)` deletes a file and records it. `serve` starts at the end of every file, so it answers at once, and
at start-up deletes the files of dead processes older than a day (`is_stale` is the pid plus start time, as in `locks`).

**The audit of writes outside `core.atomic`** (`atomic.write_bytes`, `write_text`, `write_json`, `append_jsonl_many` and
`append_jsonl` record themselves):
- The Stage output swap (`graph._swap_into_place`): records the output folder once, after the rename.
- Inbox move (`inbox._move`): `os.replace`, now records the source and the `imported/<day>/` target.
- Snapshot entry (`snapshots._store`) and `snapshots.drop`: record the entry folder, or the dropped label folder.
- `editof._move_legacy`: the two `unlink`s record the files.
- File deletions beside a write, `clipcopy` (stale clips), `loopkit` (stale kit frames), `sources` (three old-source
  removals) and `things.remove`: `changes.remove`.
- `editof.placed_file` writes into a `TemporaryDirectory` outside the Project: no record needed.
- Stage writes into `run.output_dir` (all of `kiripix/recipes/`): inside the folder that is swapped in, recorded with it.
- Blender: its subprocesses write into the Stage's output or scratch folders, so the Stage's swap records them; no Command
  runs Blender outside a Stage.
- `runners/weights.py` (weights folder) and `export/` (a Godot project, written through `atomic`, which skips what is
  outside a Project): not Project files.
- Not recorded: `commands/index_gen.py` (a source file of Kiripix itself).

**Tests changed:** `test_the_state_folder_does_not_cause_changed_events` waited for a `marker.txt` written by hand, which
the watch no longer sees (by design); it now makes the marker with `kiripix new`. The other `changed` tests are unchanged.

**Measured** on a copy of the art Project (without `.git` and `.kiripix`; 35,000-odd files), while other agents were
running tests, so only a rough guide:
- Before (the old `ProjectWatch` run alone in a process): `start()` 16.7 s (a cold copy and a busy machine; the ticket
  measured 1.8 s for one scan), CPU 92.9% of one core over 30 s of idle.
- After (`kiripix serve`, nothing happening): ready line in 3.78 s (`uv run` start-up included), CPU 0.0-0.4% per process
  over 30 s.

Changed after the batch's code review: the change record's own append goes through `kiripix.core.atomic` (`append_line`, the
unrecorded single-write append that `append_jsonl` also uses), not a hand-written `open("ab")`; `editof`'s two removals use
`changes.remove` as every other one does.
