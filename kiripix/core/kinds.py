"""The known Kinds and Runners: the built-in ones, plus the test ones when the test harness asks for them."""

import importlib
import os

from kiripix.core.errors import fail
from kiripix.recipes import kinds
from kiripix.recipes.base import KindSpec
from kiripix.runners import Runner, runners

# Names a module that registers a test Kind and fake Runners. For the test harness only: agents never set it.
TEST_RECIPES_ENV = "KIRIPIX_TEST_RECIPES"


def _load_test_recipes() -> None:
    module = os.environ.get(TEST_RECIPES_ENV)
    if module:
        importlib.import_module(module)


def all_kinds() -> dict[str, KindSpec]:
    _load_test_recipes()
    return kinds()


def all_runners() -> dict[str, Runner]:
    _load_test_recipes()
    return runners()


def get_kind(name: str) -> KindSpec:
    known = all_kinds()
    if name not in known:
        raise fail(
            "kind.unknown",
            f"unknown Kind '{name}'; the Kinds are {', '.join(sorted(known))}",
            fix="kiripix describe project",
        )
    return known[name]
