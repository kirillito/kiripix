"""The ramp table as the Commands show it: one row (`describe project`, `ramps-add`) and the example that explains it."""

from pydantic import BaseModel, Field

from kiripix.core.settings import RampSpec

RAMPS_EXAMPLE = "kiripix ramps-add character.hero --parts skin,hair --colours"


class RampRow(BaseModel):
    name: str
    length: int
    rgb: list[list[int]] | None = Field(description="The shared colours dark to light, or null when each character fits its own.")
    choices: dict[str, list[list[int]]] = Field(
        default_factory=dict,
        description="The part's named ramps (an NPC names one, ADR 0015), each `length` colours dark to light; empty for none.")


def ramp_row(ramp: RampSpec) -> RampRow:
    """One row of the table as the Commands show it."""
    return RampRow(name=ramp.name, length=ramp.length, rgb=[list(c) for c in ramp.rgb] if ramp.rgb is not None else None,
                   choices={name: [list(c) for c in colours] for name, colours in ramp.choices.items()})
