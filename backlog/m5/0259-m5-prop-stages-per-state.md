---
status: todo
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0257-m5-prop-states.md
depends_on: [0258-m5-prop-state-decision-and-import.md]
---

# M5: the Prop's Stages run per state

Part of [0257](0257-m5-prop-states.md); its table is the design.

## What to build

- **`cutout`, `fit`, `palette`, `finish`, `footprint`** run once per state. Each state's Decisions name it (a `state`
  field, absent meaning the default), and its outputs go under `states/<s>/` in the Stage's output folder. The default
  state's outputs stay where they are today, so an existing Prop rebuilds byte-equal.
- **One scale:** `fit` takes the default's scale for every state. In `grid` mode a state whose detected scale differs is
  `fit.scale_differs` (error). In `downscale` mode the state is fitted at the default's scale into its own size, cropped by
  its own offsets, and `fit.cropped` names the state.
- **Footprint:** each state has its own polygon and origin. `footprint.no_origin` names the state.
- **Status:** a change to one state's Decisions rebuilds that state only, where the Stage can tell. A palette change rebuilds
  all of them.
- Per-state loops check the cancel token between states.

## From 0258 (2026-11-17)

0258 made `src/states/**` and the `state_pick` Decisions inputs of `source`, so today a state's `import` or `pick` makes the
default state's `cutout` and every Stage after it stale (they rebuild to identical output). When the Stages run per state, a
state's files and picks should be inputs of that state's Stages only.

## Acceptance criteria

- [ ] CLI seam: a Prop with a default and a `toppled` state of another size builds both through `footprint`, at one scale,
      each with its own origin and polygon.
- [ ] A Prop with no states rebuilds byte-equal to today's outputs.
- [ ] A state missing an origin raises `footprint.no_origin` naming it. A `grid` scale mismatch raises `fit.scale_differs`.
- [ ] `uv run lint-imports` and `uv run mypy` pass.
