"""The known Kinds: the built-in Recipes, plus a test Kind when the test harness asks for one."""

import importlib
import os

from kiripix.core.errors import fail
from kiripix.recipes import kinds
from kiripix.recipes.base import KindSpec

# Names a module that registers a test Kind. For the test harness only: agents never set it.
TEST_RECIPES_ENV = "KIRIPIX_TEST_RECIPES"


def all_kinds() -> dict[str, KindSpec]:
    module = os.environ.get(TEST_RECIPES_ENV)
    if module:
        importlib.import_module(module)
    return kinds()


def get_kind(name: str) -> KindSpec:
    known = all_kinds()
    if name not in known:
        raise fail(
            "kind.unknown",
            f"unknown Kind '{name}'; the Kinds are {', '.join(sorted(known))}",
            fix="kiripix describe project",
        )
    return known[name]
