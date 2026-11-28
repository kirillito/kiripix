---
status: todo
milestone: M7
agent: none
type: trial
---

# M7: the agent acceptance test, a real run on the M6 code

Moved out of the M6 gate ([0338](../m6/0338-m6-gate.md)) by the Owner, 2026-11-27: a real run spends Claude tokens, which the
Owner isn't spending now. The last real run was M5's ([0256](../m5/0256-m5-gate.md), `docs/acceptance/2026-11-19-m5-2.md`).

## What to do

- The dry run first: `uv run pytest tests/acceptance`. A failure is the harness falling behind M6's Commands (`queue`, `note`,
  the `normals` Stage, the room's new Stages); fix it there.
- One real run on the cheap model, recorded under `docs/acceptance/` with `--milestone m6` (or m7, whichever code it runs on).

## Acceptance criteria

- [ ] The dry run passes.
- [ ] One real run recorded under `docs/acceptance/`, its tokens stated in its Notes, not compared with an earlier
      milestone's.
- [ ] A failure is filed as a ticket in `backlog/`.
