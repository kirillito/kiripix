---
status: done
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

- [x] CLI seam: a Prop with two declared states, each imported and picked, shows both in `show --json`.
- [x] `import --state` for an undeclared state fails with its fix. A state ID equal to the default's is refused.
- [x] Contract samples for the Decision and the flags. The glossary gets **State** (a Prop's), with _Avoid_: Look (a room's).

## Result

- `brief.state` (str, default `default`; `brief.json` records it only when it isn't `default`, so a Prop without states
  keeps its brief file byte for byte). The `source` Stage takes four Decisions beside `pick`: `state` (`id`, `width`,
  `height`), `state_remove`, `state_rename`, `state_pick` (`state`, `variant`). `StageSpec.decisions_view` replays the
  remove and rename (as for a Loop); a rename keeps the Variants' folder (`src/states/<original id>/`).
- `import <id> <png> --state <s>` and `pick <id> <v> --state <s>` (`kiripix/core/sources.py`); `show` lists `default_state`
  and `states` (size, Variants, pick). A lone Variant of a state gets a `command` pick fix.
- Findings: `prop.state_unknown` (fix declares it at the brief's size), `prop.state_unpicked` (needs-input, code carried by a
  new `NeedsInput.code`, which `run` uses in place of `stage.needs_input`), `prop.state_duplicate` (the default's ID, a taken
  ID, a rename to either), `prop.state_larger_than_resolution`. A state edit that the game's Manifest freezes gives
  `export.id_frozen` before it is recorded (`decide` and `redo`).
- The Manifest's `ids` gains `states` (left out when empty; unioned by `manifest merge`; compared by `check`). Nothing writes
  it yet: the Prop export that records the state IDs is [0260](0260-m5-export-prop-states.md).
- Glossary: **State**.
- Adding `state` to the brief changes the Prop `brief` input hash once, so existing Props rebuild their Stages once (the
  output is identical).

