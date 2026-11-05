---
status: done
milestone: M0
agent: core-engineer
type: ticket
parent: 0001-m0-skeleton.md
depends_on: [0006-m0-stage-graph-and-run.md]
---

# M0: locks

Spec §10.4. User stories 38–44 of [0001](0001-m0-skeleton.md).

## What to build

- Project, Asset and GPU lock files in `.kiripix/locks/`, recording the process ID, the host and the start time.
  Taken by core from the Command's declaration, always in the order project, Asset, GPU. Read-only Commands never
  lock.
- Busy: exit 4 and `lock.busy`, with the holder in `data`. `--wait <seconds>` on every writing Command.
- A lock whose process is dead on this host is taken over; another host's lock never is.
- `run --all` locks one Asset at a time.

## Acceptance criteria

- [ ] With two real processes, the second gets exit 4, or succeeds with `--wait` once the first releases.
- [ ] A lock left with a dead process ID is taken over.
