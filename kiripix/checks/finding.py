"""The finding: what a Check, or any failed Command, reports. Part of the JSON contract (spec §10.2)."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

Severity = Literal["error", "warning", "info"]


class Position(BaseModel):
    """Where a finding is: any of an Asset, a Stage, a file, a pixel or a field path."""

    model_config = ConfigDict(extra="forbid")

    asset: str | None = None
    stage: str | None = None
    file: str | None = None
    line: int | None = None
    x: int | None = None
    y: int | None = None
    field: str | None = None


class Finding(BaseModel):
    """A located problem with a stable dotted `code`, and exactly one of `fix` or `owner_action`.

    `fix` is a command an agent can run. `owner_action` says what only the Owner can do.
    """

    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Severity = "error"
    message: str
    position: Position | None = None
    fix: str | None = None
    owner_action: str | None = None

    @model_validator(mode="after")
    def _one_remedy(self) -> Self:
        if (self.fix is None) == (self.owner_action is None):
            raise ValueError(f"finding {self.code}: set exactly one of fix and owner_action")
        return self
