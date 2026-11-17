---
status: todo
milestone: M5
agent: core-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: start faster: the rest of the start-up time

[0163](../m4/0163-m4-start-faster.md)'s follow-up ([docs/test-speed.md](../../docs/test-speed.md), "Done", item 2). The M4
gate measured `kiripix --help` at 1.02 s against 0.08 s for `python -c pass`. Every CLI call in the test suite pays that,
and so does every Command an agent or the Owner runs.

## The gap

0163 deferred numpy, jsonschema and the weights download. What's left is pydantic and typer, which the contract needs, and the
import of every Command module to build the registry. 0163 put the 0.3 s goal out of reach without a different path for them.

## What to do

1. **Measure first:** `python -X importtime -m kiripix --help` and a typical `kiripix status --json`, and list the 20 largest
   imports. Record them here.
2. **Then cut what the numbers point to**, keeping the contract identical (`schema`, `describe` and every result
   byte-equal). For example:
   - a registry built from a static index of Command names and modules, importing a Command's module only when it's called,
     or when `schema` or `describe` asks for all of them;
   - typer's app built for the called Command only;
   - pydantic models made lazily, and `defer_build`.
3. Record `kiripix --help` and `kiripix status --json` before and after (median of 7), and the full suite's time if the Owner
   runs it.

## Acceptance criteria

- [ ] The import-time table above, before and after.
- [ ] `schema --json` and `describe` give the same output as before, and the contract test passes.
- [ ] `kiripix --help` at least 30 % faster on the same machine, or the reason it can't be, recorded here.
