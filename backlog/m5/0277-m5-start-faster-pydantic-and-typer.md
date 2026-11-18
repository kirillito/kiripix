---
status: done
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

- [x] The import-time table above, before and after.
- [x] `schema --json` and `describe` give the same output as before, and the contract test passes.
- [x] `kiripix --help` at least 30 % faster on the same machine, or the reason it can't be, recorded here.

## Result

Measured 2026-11-17 on the Owner's Windows laptop, `python -m kiripix` in an empty Project, median of 7.

**Before** (all Command modules imported at start). First measured under load (`python -c pass` 0.045 s): `--help`
0.684 s, `status --json` 0.669 s. Re-measured on a quiet machine (`python -c pass` 0.035 s) with the same code but every
Command module imported by hand before `main()`, which is what start-up did before: `--help` 0.47 s, `status --json`
0.48 s.

| median of 7 | before (quiet) | after | change |
|---|---|---|---|
| `python -c pass` | 0.035 s | 0.035 s | |
| `kiripix --help` | 0.47 s | **0.135 s** | -71 % |
| `kiripix status --json` | 0.48 s | **0.40 s** | -17 % |
| `kiripix describe room --json` | about 0.48 s | 0.40 s | -17 % |

`kiripix.launch` import time (`-X importtime`, cumulative, under load): 558 ms before, 114 ms for `--help` after.

### Where the time went (`python -X importtime -m kiripix --help`, before, cumulative, under load)

`kiripix.launch` 558 ms; `kiripix.commands` 345; `commands.project` 236; `commands.contract` 108 (of which
`core.graph` 104); `pydantic.fields` 100; `kiripix.checks` 81 (`checks.cutout` 77, `checks.finding` 54); `typer` 68;
`pydantic.types` 44; `core.journal` 44; `kiripix.recipes.base` 42; `core.assets` 37; `core.project` 35; `core.settings`
33; `typer.main` 32; `inspect` 31; `typer._click.*` 27; `pydantic._migration` 26. After, for `--help`: only `typer` (67
of 114), `inspect` and the click copy; no pydantic, checks, core or recipes. For `status --json` what is left is what
`status` itself needs: pydantic, `core.graph` (105), `kiripix.checks` (113, `finding` 85), recipes, the Project, typer.

### What changed

- `kiripix/commands/index.py` (generated): the static index of every Command: name, module, summary, group summary, in
  help order. `kiripix/commands/index_gen.py` writes it: `uv run python -m kiripix.commands.index_gen`. Adding a Command
  is the `@command` plus that one run; `tests/cli/test_command_index.py` fails naming the Command if it is forgotten.
- `REGISTRY` (`commands/registry.py`) is a `dict` that imports a Command's module when the Command is looked up, and all
  of them when it is iterated (`schema`, `describe`, the server, `len`). Registration is unchanged.
- `kiripix.commands` no longer imports its modules or anything heavy: its names load on first use (PEP 562). The module
  `commands/invoke.py` is now `commands/calling.py`, so the name `invoke` is only the function.
- The CLI lists every Command from the index with stub callbacks (name and summary, no parameters) and builds the real
  Typer callback only for the Command that runs (`called_command`). `--help` of the root and of groups imports no
  Command module and not pydantic. Typer's output is the same: the test builds both apps and compares every `--help`.
- The server adapter: `kiripix.server` holds only `LAUNCHER_LISTING` and `load_launchers`; `serve` and `ui` live in
  `kiripix.server.launchers`, loaded when one of them runs. `kiripix.launch` passes both to `cli.main`.

### Tests

- `tests/cli/test_command_index.py`: the index lists every `@command` and matches the registry (and says what to run);
  `schema --json` and `describe` (two forms) are byte-equal with every Command module imported first; the root's, every
  group's, every Command's and every Launcher's `--help` match an app built from the whole registry; `status` imports
  one Command module, `schema` all of them.
- Passed: that file, `test_contract.py`, `test_start_imports.py`, `test_startup.py`, `test_serve.py`, `test_time.py`,
  `test_check.py`, `test_decisions.py`; `uv run mypy`; `uv run lint-imports`. The full suite was not run.
- The `schema` output differs from the one taken at the start only in `new`, which another ticket (the `icon` Kind)
  changed meanwhile.

### Still open

`status --json` is at 0.40 s, not 0.3 s: pydantic (about 0.1 s), typer (0.07 s) and the stage graph with `checks` and
the recipes (0.1 s) are what a Command that reads the Project needs. Cutting the last needs `checks`/`recipes` split so
that `core.graph` doesn't import every Kind's Stage code, which is a change to those layers, not to start-up.
