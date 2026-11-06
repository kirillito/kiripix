"""The fake Runners for the agent acceptance test (ticket 0057, D16 of 0037), loaded through KIRIPIX_TEST_RECIPES.

The harness's own calls get the variable directly. The agent never has it: its `kiripix` and `kpx` are two shims, made by
the harness, that set it for that one process. So the agent sees the tool and nothing of the test.

It reuses the fake Runners of `tests/fixtures/kiripix_test_recipes.py` and then removes what else that module registers
(the test Kinds `demo`, `sketch`, ... and its project Check), so `describe`, `status` and `--help` show only what a real
Project shows, and a Runner list shows only the roles (`segmenter`, `inpainter`, `matter`).
"""

import kiripix.runners
from kiripix.core import project_checks
from kiripix.recipes import _KINDS
from kiripix.runners import INPAINTER, MATTER, SEGMENTER
from kiripix.runners.base import _RUNNERS

_kinds_before = set(_KINDS)
_checks_before = len(project_checks._PROJECT_CHECKS)

import kiripix_test_recipes  # noqa: E402,F401  (registers the fakes, and what is removed below)

for _name in set(_KINDS) - _kinds_before:
    del _KINDS[_name]
del project_checks._PROJECT_CHECKS[_checks_before:]
for _id in set(_RUNNERS) - {SEGMENTER, INPAINTER, MATTER}:
    del _RUNNERS[_id]

assert kiripix.runners.INPAINTER == INPAINTER
