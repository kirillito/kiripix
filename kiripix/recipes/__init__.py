"""The Kinds and their Recipes. Uses `ops`, `checks`, `runners` and `providers`; never `core` or above."""

from kiripix.recipes.base import KindSpec
from kiripix.recipes.character import CHARACTER
from kiripix.recipes.prop import PROP
from kiripix.recipes.room import ROOM
from kiripix.recipes.sprite import SPRITE

_KINDS: dict[str, KindSpec] = {}


def register_kind(kind: KindSpec) -> None:
    """Add a Kind. The built-in Kinds register here; the test harness adds its own."""
    _KINDS[kind.name] = kind


def kinds() -> dict[str, KindSpec]:
    return dict(_KINDS)


for _kind in (ROOM, PROP, CHARACTER, SPRITE):
    register_kind(_kind)
