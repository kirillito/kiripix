"""The finding: what a Check, or any failed Command, reports. Part of the JSON contract (spec §10.2)."""

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer, model_validator

Severity = Literal["error", "warning", "info"]


class Position(BaseModel):
    """Where a finding is: any of an Asset, a Stage, a file, a pixel, a box from that pixel, a field path or a Prop's state."""

    model_config = ConfigDict(extra="forbid")

    asset: str | None = None
    stage: str | None = None
    file: str | None = None
    line: int | None = None
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None
    field: str | None = None
    state: str | None = None
    """A Prop's state the finding is about (ticket 0259), when not the default. Left out of the JSON when null."""

    @model_serializer(mode="wrap")
    def _omit_no_state(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if data.get("state") is None:
            data.pop("state", None)
        return data


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
    points: list[tuple[int, int]] = Field(default_factory=list)
    """Further pixels, `[x, y]` in target px, that the finding is about. Left out of the JSON when empty."""

    data: dict[str, Any] = Field(default_factory=dict)
    """What the finding says as data for a reader that shouldn't parse `message` (ticket 0296). Each code that has some
    documents its keys. Left out of the JSON when empty."""

    @model_serializer(mode="wrap")
    def _omit_empty_points(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        found: dict[str, Any] = handler(self)
        for key in ("points", "data"):
            if not found.get(key):
                found.pop(key, None)
        return found

    @model_validator(mode="after")
    def _one_remedy(self) -> Self:
        if (self.fix is None) == (self.owner_action is None):
            raise ValueError(f"finding {self.code}: set exactly one of fix and owner_action")
        return self
