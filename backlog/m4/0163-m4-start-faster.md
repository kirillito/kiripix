---
status: todo
milestone: M4
agent: core-engineer
type: ticket
---

# M4: `kiripix` starts in 0.7 s: import less at start

Spec §8 (the CLI is the agent's interface) and §13 (layers). Found while closing M3, 2026-11-11.

## The gap

`kiripix --help` takes 0.70 s on the Owner's laptop, where `python -c pass` takes 0.05 s: 0.65 s is imports
(`python -X importtime -c "import kiripix.launch"`: 0.56 s warm). Every Command pays it before doing any work. Today
`status` on the art Project takes 1.2 s, nearly all start-up.

It adds up:
- **Agents:** an agent's every step is a Command. The acceptance test makes dozens.
- **The tests:** the CLI seam runs `kiripix ... --json` as a subprocess, thousands of times. The full suite takes 44 minutes
  in parallel (2026-11-11).
- **The UI** is a long-running `serve`, so it doesn't pay this per click, but `kiripix ui` does once.

Where it goes (cumulative, warm): `kiripix.commands` 0.38 s, of which `commands.project` 0.26 s, which pulls in `checks`
(`checks.cutout` 0.14 s) and through it numpy (0.09 s). Also pydantic (about 0.1 s), `jsonschema` 0.06 s (`core.editing`),
`typer` 0.06 s, `core.graph` 0.09 s, and every Kind's recipe (`recipes.character` 0.04 s) at import.

## What to build

- Import heavy modules where they're used, not at a module's top: numpy, PIL, `jsonschema`, `kiripix.checks`, the recipes'
  Stage code and the Runners. A Command's module may still be imported to register it, as long as registering is cheap.
- `kiripix --help`, `describe`, `schema` and `status` on an empty Project don't import numpy, PIL or onnxruntime.
- A test holds the budget: `python -X importtime -c "import kiripix.launch"` under 0.25 s on CI, or the set of modules
  `kiripix.launch` imports excludes numpy, PIL, onnxruntime and jsonschema (a check that doesn't depend on machine speed).
- The import rule (`lint-imports`) still holds: function-level imports count too.

## Acceptance criteria

- [ ] `kiripix --help` and `kiripix status --json` on an empty Project take under 0.3 s on the Owner's laptop (record before
      and after here).
- [ ] The test of what `kiripix.launch` imports.
- [ ] The full suite's time before and after, recorded here.
