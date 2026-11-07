---
status: done
milestone: M2
agent: qa-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0047-m2-export-room-layers.md]
---

# M2: the agent acceptance test with a lifted Layer

Spec §14. Story 17 of [0037](0037-m2-layers-and-props.md). Follows D4 and D16 in [0037](0037-m2-layers-and-props.md).

## What to build

- Extend `tests/acceptance/fixtures/owner.json`: one `click` on `layers`, the `accept` it leads to, and that Layer's y-sort
  line or flag, plus a fixture image with an object to lift.
- The agent still sees only the tool, and must find `run --rerun` from `next`. Keep the task prompt's line about one plain
  command per call, so runs compare.
- Runners per D16. The stand-in owner handles `needs-review` on `layers` and `masks`.
- A pass also needs: the Layer in the export's Manifest, and `check --all` clean.

## Acceptance criteria

- [x] The dry run passes in `uv run pytest tests/acceptance`.
- [x] One real run on the cheap model, recorded under `docs/acceptance/` with `--milestone m2`, compared in its Notes with M1's
      7,629 fresh tokens. A failure is filed as a ticket in `backlog/`.
