---
status: todo
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

- [ ] A CLI-seam test: a Command such as `kiripix describe --json`, run in a subprocess, doesn't load `kiripix.server` or
      `fastapi` (for example, check `sys.modules` through a small `-c` wrapper, or `-X importtime`).
- [ ] `kiripix --help` and `kiripix serve --help` print the same as before.
- [ ] `tests/cli/test_serve.py`, `test_warm.py` and `tests/cli/test_wheel.py` (with `web/dist` built) pass, and `npm run
      test:e2e` passes, so `serve` and `ui` still work.
- [ ] `lint-imports` and `mypy` pass.
- [ ] The import time of `kiripix --help`, before and after, is recorded here.
