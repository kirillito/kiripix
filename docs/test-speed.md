# Test speed

Not scheduled yet: these are options for when the owner wants them, not tickets.

The full suite took 34 minutes on 2026-11-03 (405 tests, on Windows), before tickets 0019 and 0020 added about 60 more.
The time goes to the CLI seam, not to the logic. Each CLI call in a test starts a new Python process, and one room test
makes many of them: `test_place.py` and `test_reachability.py` took about 16 s per test, while the golden tests take
milliseconds.

For now, the full suite runs once at the end of a batch of tickets, and single test files run until then.

## Options

1. **Run tests in parallel with `pytest-xdist`.** Probably the biggest gain for the least work, because each test already
   has its own temporary Project. It adds a dev dependency. The lock and serve tests need checking first, since they
   rely on timing and real processes.
2. **Build rooms once per test module.** A shared built room, copied for each test, would skip repeating the subprocess
   calls of `built_room` in every test.
3. **Measure the start-up time of `kiripix`.** Every call pays it, so trimming imports would speed up the whole suite and
   the real CLI too. `python -X importtime -m kiripix --help` shows where it goes.
