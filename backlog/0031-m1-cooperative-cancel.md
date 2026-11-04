---
status: done
milestone: M1
agent: core-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0023-m1-serve.md]
---

# M1: cooperative cancel: a cancel token checked between chunks of work and in every wait

Spec §10.1 and §10.6. A follow-up to [0023](0023-m1-serve.md). Its server cancel raises KeyboardInterrupt in the
Command's thread. CPython only delivers that between bytecodes, so it can't break a worker thread out of `time.sleep`,
a lock wait or a long native call. Ctrl+C on the CLI's main thread does break out of sleeps and waits.

## What to build

- A cancel token (a `threading.Event`, or a small type around one) on the Command's `Context`. It's set by Ctrl+C in
  the CLI and by the cancel route in the server. Core raises one exception for it, which ends up as the existing
  `run.cancelled` finding and the `cancelled` history entry.
- Every wait in core waits on the token, not `time.sleep`: the polls in `kiripix/core/atomic.py`, `graph.py` and
  `locks.py`. So a Command waiting for a lock (`--wait`) stops at once on cancel.
- Checkpoints: core checks the token between Stages, after each Stage's `run`, and wherever a long loop already
  reports progress. A Stage can check it via its `StageRun` (a `run.check_cancel()` or equivalent) between chunks
  (tiles, frames, batches).
- Keep the async KeyboardInterrupt in `kiripix/commands/jobs.py` as a backstop for code with no checkpoint.
- Add the rule to CLAUDE.md's conventions (see below), so later Stages and Runners follow it.

## Acceptance criteria

- [x] A `run` waiting on a held Asset lock, with `--wait 60`, stops within a second of a cancel over REST, with
      `run.cancelled`, no lock files and no `.tmp-*` folders.
- [x] The `demo` Kind gets a Stage that loops in chunks and checks the token. Cancelling it mid-loop stops at the next
      chunk, and a later `run` succeeds.
- [ ] Ctrl+C on the CLI still behaves as before (the existing test). Not yet run: the test is skipped on Windows.
- [x] No `time.sleep` is left in `kiripix/core` outside the token's own wait.

## Notes

- **The token** is `kiripix.core.cancel.CancelToken`, on `Context.cancel`. `invoke` makes it the current token for the
  call, so core reaches it without passing it down: `cancel.sleep` is the one wait, `cancel.check` the checkpoint, and
  `Cancelled` the one exception (a BaseException, so a Stage's `except Exception` can't swallow it).
- **The backstop**: a server cancel sets the token at once, and raises KeyboardInterrupt in the job's thread only if
  the Command is still running 2 s later. Raising both at once could interrupt core's own cancelled-history write.
- **The demo Stage**: `hold` now checks the token between its 50 ms chunks, instead of a sixth `demo` Stage, which
  would have changed every whole-status assertion on `demo`. The cancel test asserts the stop comes before the
  backstop could.
