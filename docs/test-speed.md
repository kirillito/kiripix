# Test speed

The full suite took 34 minutes on 2026-11-03 (405 tests, on Windows), before tickets 0019 and 0020 added about 60 more.
The time goes to the CLI seam, not to the logic. Each CLI call in a test starts a new Python process, and one room test
makes many of them: `test_place.py` and `test_reachability.py` took about 16 s per test, while the golden tests take
milliseconds.

The full suite runs once at the end of a batch of tickets, and single test files run until then.

## Done

1. **Run tests in parallel with `pytest-xdist`** (ticket 0068, M2): `uv run pytest -n auto --dist loadfile`.
   `--update-golden` still runs without `-n`.
2. **Trim the start-up time of `kiripix`** (ticket 0163, M4): heavy modules (numpy, jsonschema, the weights download) load
   on first use, so every CLI call pays less. What is left is pydantic and typer, which the contract needs; the 0.3 s goal
   for `kiripix --help` would need a different path for them, and is left for a follow-up if still wanted. The M4 gate
   records `kiripix --help`'s and the full suite's times on the Owner's laptop.

## Still open

- **Build rooms once per test module.** A shared built room, copied for each test, would skip repeating the subprocess
  calls of `built_room` in every test. Not scheduled: an option for when the Owner wants it, not a ticket.
