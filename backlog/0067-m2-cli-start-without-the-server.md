---
status: done
milestone: M2
agent: core-engineer
type: ticket
---

# M2: the CLI starts without importing the server

Every `kiripix … --json` call spends about 1.2 s importing before it does any work (`python -X importtime -m kiripix --help`,
2026-11-05, measured while the full suite was running). About 0.4 s of that is `kiripix.server`, with FastAPI. It's imported
because [launch.py](../kiripix/launch.py) imports `LAUNCHERS` from `kiripix.server` at the top, for every Command. Only `serve`
and `ui` need it. The CLI tests spawn thousands of these calls, so the suite pays this cost on each one, and so does an agent
driving Kiripix.

## What to do

- `launch.py` hands the CLI the Launchers without importing `kiripix.server` until `serve` or `ui` runs: by name, with a
  function that imports on first use, or another way that keeps the import rule (`cli` and `server` import only
  `kiripix.commands`).
- `kiripix --help` still lists `serve` and `ui`, with the same help text and options.
- Look at the rest of the import time while you're there (`kiripix.commands.project` imports about 0.4 s). Move only what's
  safe, and record the before and after in this ticket.

## Acceptance criteria

- [x] A CLI-seam test: a Command such as `kiripix describe --json`, run in a subprocess, doesn't load `kiripix.server` or
      `fastapi` (for example, check `sys.modules` through a small `-c` wrapper, or `-X importtime`).
- [x] `kiripix --help` and `kiripix serve --help` print the same as before.
- [x] `tests/cli/test_serve.py`, `test_warm.py` and `tests/cli/test_wheel.py` (with `web/dist` built) pass, and `npm run
      test:e2e` passes, so `serve` and `ui` still work.
- [x] `lint-imports` and `mypy` pass.
- [x] The import time of `kiripix --help`, before and after, is recorded here.

## Notes

Done 2026-11-05. `kiripix.server`'s `__init__` imported `uvicorn` and `kiripix.server.app` (FastAPI) at the top. They now
load inside `_serve`, so the package defines `ServeInput` and `LAUNCHERS` cheaply and `kiripix.launch` is unchanged. `create_app`
is no longer re-exported from `kiripix.server`; nothing used it. `kiripix --help`, `serve --help` and `ui --help` print
byte-identical text before and after.

Import time (`python -c "import kiripix.launch"`, median of 7 process runs, Windows, quiet machine): about 1.00 s before, 0.78 s
after (about 0.22 s saved). `python -X importtime -m kiripix --help` (single, noisy runs): `kiripix.launch` 1.14 s before, about
1.0 s after, with `kiripix.server` (0.37 s) gone.

What remains is `kiripix.commands` (about 0.5-0.65 s). `kiripix.commands.project` takes about 0.4 s of it, from
`kiripix.checks` (numpy, via `checks.cutout` and `ops`) and `jsonschema`. These are real dependencies of the registry's input
types and the Stage graph, so I moved nothing more. A deferral there would mean lazy-loading numpy inside `checks`/`ops`
and `jsonschema` inside the contract validation. That is a larger change and its own ticket if wanted.

Test: `tests/cli/test_startup.py` runs `describe project --json` and `--help` in a subprocess and checks that no `fastapi`,
`uvicorn`, `starlette` or `kiripix.server.*` module loaded. `test_serve.py`, `test_warm.py`, `test_wheel.py`,
`test_contract.py` pass; `npm run test:e2e` passed 47 of 50 with 3 timeouts under load (layers x2, prop x1), and those
specs pass when re-run alone.
