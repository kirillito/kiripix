---
status: todo
milestone: M2
agent: qa-engineer
type: ticket
depends_on: [0067-m2-cli-start-without-the-server.md]
---

# M2: run the Python tests in parallel

The full `pytest` run takes well over an hour, and more when the machine is locked: on 2026-11-05 it was at 49% after 100
minutes. Nearly all of the time is in CLI-seam tests, which wait on `kiripix` subprocesses one after another while most CPU cores
sit idle. Each test already works in its own temporary Project, so the tests should run in parallel.

## What to do

- Add `pytest-xdist` to the `dev` dependency group and update `uv.lock` (`uv add --group dev pytest-xdist`).
- Make parallel runs safe. Find and fix anything tests share outside their temporary Project:
  - fixed ports in `test_serve.py`, `test_warm.py` and any other server test (use a free port per test);
  - user-level directories: weights, caches and settings under the home folder. Point them into `tmp_path` in the harness;
  - a warm Runner process or lock files that one test leaves for another;
  - the golden seam's `--update-golden`, which must not run in parallel workers. Refuse it, or document that it runs without
    `-n`.
- Set a sensible default in `[tool.pytest.ini_options]` (for example `-n auto --dist loadfile`) only if every test passes that
  way on Windows and Linux. Otherwise, document the command in CLAUDE.md's "Commands to run".
- Leave CI's own commands alone unless the parallel run passes there too.

## Acceptance criteria

- [ ] `uv run pytest -n auto` passes on Windows, three times in a row, with the same result as a serial run.
- [ ] The serial `uv run pytest` still passes.
- [ ] `uv sync --locked --no-group cuda` works with the updated lock file.
- [ ] The wall time of a full serial run and a parallel run, on the owner's machine, is recorded here.
- [ ] CLAUDE.md's "Commands to run" names the parallel command.
