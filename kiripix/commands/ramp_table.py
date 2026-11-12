"""The ramp table as the Commands show it: one row (`describe project`, `ramps-add`) and the example that explains it."""

from pydantic import BaseModel, Field

RAMPS_EXAMPLE = "kiripix ramps-add character.hero --parts skin,hair --colours"


class RampRow(BaseModel):
    name: str
    length: int
    rgb: list[list[int]] | None = Field(description="The shared colours dark to light, or null when each character fits its own.")
