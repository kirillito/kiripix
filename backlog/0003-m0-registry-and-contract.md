---
status: review
milestone: M0
agent: core-engineer
type: ticket
parent: 0001-m0-skeleton.md
depends_on: [0002-m0-repo-and-tooling.md]
---

# M0: Command registry, CLI adapter and the JSON contract

ADR 0006 and spec §10.1, §10.2, §10.5. User stories 27–31, 34, 36 and 37 of [0001](0001-m0-skeleton.md).

## What to build

- `commands`: the registry. A Command declares its name, Pydantic input and output, its kind (writing, Probe,
  owner-only), its MCP exposure (exposed, hidden, owner-only), CLI metadata (positional arguments, short aliases, a
  group such as `op`) and its locks.
- The result envelope: `api_version` (1), `ok`, `data`, `findings`. A finding has `code`, `severity`, `message`,
  `position`, `fix` and `owner_action`, with exactly one of `fix` and `owner_action` set.
- Exit codes 0 ok, 1 error, 2 check failed, 3 needs the owner, 4 busy, carried by the result.
- `cli`: a Typer app generated from the registry, with no logic of its own. `--json` prints exactly one object on
  stdout; `--progress=jsonl` streams `{event, stage, done, total, message}` on stderr; text rendering otherwise.
- `kiripix schema [command]`: the JSON Schemas of inputs and outputs, from the same types.
- An unexpected exception becomes an `internal.error` finding with exit 1, still as one JSON object.

## Acceptance criteria

- [ ] A contract test walks every registered Command: `--help` exists, and the `--json` output validates against
      `schema`.
- [ ] `schema` for an unknown Command fails with `command.unknown` and lists the Commands.
