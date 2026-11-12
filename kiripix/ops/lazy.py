"""Import a heavy library when it is first used, not when the module that names it is imported (ticket 0163).

`kiripix --help` and `status` don't touch numpy or PIL, so they shouldn't pay for them. A module writes

    if TYPE_CHECKING:
        import numpy as np
    else:
        np = lazy_module("numpy")

The type checker sees the real module; at run time `np` loads numpy on its first attribute access. Annotations that
name `np` need `from __future__ import annotations`, or they load it when the module is imported. Stdlib only.
"""

import importlib
from typing import Any


class LazyModule:
    """Stands in for a module until an attribute is read, then becomes a copy of its namespace."""

    def __init__(self, name: str) -> None:
        self.__dict__["_lazy_name"] = name

    def __getattr__(self, attribute: str) -> Any:
        if attribute.startswith("__") or attribute == "_lazy_name":
            raise AttributeError(attribute)
        module = importlib.import_module(self.__dict__["_lazy_name"])
        self.__dict__.update(vars(module))
        return getattr(module, attribute)

    def __repr__(self) -> str:
        return f"<lazy module {self.__dict__['_lazy_name']!r}>"


def lazy_module(name: str) -> Any:
    return LazyModule(name)
