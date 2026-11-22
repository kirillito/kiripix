"""The Project's Masks as the Commands show them: one row (`describe room`, `masks-add`) and the example that explains it."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from kiripix.core.settings import ProjectSettings

MASKS_EXAMPLE = 'kiripix masks-add cover --colour "#00AA00" --meaning "half cover for a grid battle" --view top'


class MaskRow(BaseModel):
    """One Mask of a view, as `describe room` lists it. A painted Mask has a `colour`; a derived one is computed and has none."""

    view: Literal["top", "side"] = Field(description="The room view the Mask belongs to.")
    name: str = Field(description="The Mask's name: its `<name>.png` in the `masks` Stage's output.")
    colour: str | None = Field(description="The painted Mask's display and import colour, #RRGGBB; null for a derived Mask.")
    meaning: str | None = Field(description="What the Project says the Mask means; null when it says nothing.")
    derived: bool = Field(description="True when the Mask is computed (`walkable`, `foreground`) and never painted.")
    blocks: bool = Field(description="True only for `solid` and `pit`: any other Mask means nothing to Kiripix (`reach`, the "
                                     "walk test) and is the game's to read.")


def mask_rows(settings: ProjectSettings) -> list[MaskRow]:
    """Every Mask of the Project: the top view first, then the side, each in the order of kiripix.toml."""
    rows: list[MaskRow] = []
    for view in ("top", "side"):
        masks = settings.masks.get(view)
        if masks is None:
            continue
        for name, definition in masks.definitions().items():
            rows.append(MaskRow(view=view, name=name, colour=definition.colour, meaning=definition.meaning,
                                derived=definition.derived, blocks=name in ("solid", "pit") and not definition.derived))
    return rows
