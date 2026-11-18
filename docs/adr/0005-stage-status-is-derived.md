# Stage status is derived, never committed

A Stage's status (todo, stale, done, needs-review, needs-input) is computed every time from input hashes and Decisions,
never stored in `asset.toml`. Committed status would conflict between branches that ran different Stages, and would be
wrong on a fresh checkout. Acceptance of a review is already captured, as Decisions re-recorded against the new input
hash.

## Consequences

- File hashes are cached by modification time and size in the git-ignored `.kiripix/`, so status stays fast.
- `failed` can't be derived, so it lives in that same cache. A fresh checkout shows todo or stale, never an old failure.
- History moves out of `asset.toml` into an append-only `history.jsonl` per Asset, committed with `merge=union`, so both
  branches' lines survive a merge. `asset.toml` holds only the Kind and parameters.
- A Stage's `version` (an int, default 1, declared in its `StageSpec`) is one of its inputs: a change to what the Stage
  writes bumps it, and the Stage and every Stage below it go stale on every Asset. A parameter that holds its default
  stays out of the hash, so adding a parameter is no rebuild. A hash recorded before versions existed reads as version 1
  (core works the older form out too and accepts a match), so landing this changed no Stage's status.
