---
status: review
milestone: M0
agent: core-engineer
type: ticket
parent: 0001-m0-skeleton.md
depends_on: [0005-m0-init-new-describe.md]
---

# M0: stage graph, derived status, run, next and history

ADR 0005 and spec §5. User stories 14–26 and 35 of [0001](0001-m0-skeleton.md).

## What to build

- Stage inputs (files, upstream outputs, project settings, parameters) hashed into an input hash. The hash an output
  was built from is stored next to it in `work/` or `out/`.
- Statuses `todo`, `stale`, `done`, `needs-input` and `failed` (`failed` only in `.kiripix/`). File hashes cached by
  mtime and size in `.kiripix/`; deleting `.kiripix/` is harmless.
- `kiripix status [--kind k]`, `kiripix next <id>`, `kiripix run <id> [stage] [--force]` and `run --all`.
- `history.jsonl`: one JSON object per run (stage, parameters, input hash, duration, outcome), LF, appended.
- Ctrl+C stops a run cleanly; outputs are written atomically.
- The test-only hook `KIRIPIX_TEST_RECIPES` loads a module that registers a test Kind with trivial Stages (copy,
  concatenate, wait on a signal file, fail on purpose).

## Acceptance criteria

- [ ] Changing an input file turns a `done` Stage and every Stage below it `stale`.
- [ ] A killed run leaves no completed output.
- [ ] A fresh checkout (no `.kiripix/`) never shows `failed`.
