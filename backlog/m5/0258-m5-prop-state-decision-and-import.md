---
status: todo
milestone: M5
agent: core-engineer
type: ticket
parent: 0257-m5-prop-states.md
---

# M5: a Prop's `state` Decision, and `import --state`, `pick --state`

Part of [0257](0257-m5-prop-states.md): declaring states and their sources. The Stages per state are
[0259](0259-m5-prop-stages-per-state.md).

## What to build

- **`brief`:** a `state` parameter (the default state's ID, default `default`).
- **A `state` Decision on `source`:** an ID (snake_case, unique among the Prop's states, never the default's) and a size
  (w, h, within the Project's resolution). `remove` and `rename` before export; after export the ID is frozen (ADR 0003), and
  a `remove` or `rename` is refused before it's recorded.
- **`import <id> <png> --state <s>`** stores a Variant under `src/states/<s>/`. **`pick <id> <v> --state <s>`** picks it. A
  lone Variant may be picked by an agent, as for a Source.
- `show` lists the states, each with its Variants and pick. `describe prop` documents them.
- Findings: `prop.state_unknown` (with a fix that declares it), `prop.state_unpicked` (needs-input, naming the state),
  `prop.state_duplicate`.
- A Prop with no `state` Decision behaves exactly as today.

## Acceptance criteria

- [ ] CLI seam: a Prop with two declared states, each imported and picked, shows both in `show --json`.
- [ ] `import --state` for an undeclared state fails with its fix. A state ID equal to the default's is refused.
- [ ] Contract samples for the Decision and the flags. The glossary gets **State** (a Prop's), with _Avoid_: Look (a room's).
