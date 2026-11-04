"""How a Kind and its Recipe are declared: Stages with inputs, parameters, Decisions, Checks and a run function."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from kiripix.checks import Finding

Scalar = str | int | float | bool
ParamType = Literal["int", "float", "bool", "str", "choice"]


class ParamSpec(BaseModel):
    """A parameter of a Kind or a Stage, with its type, default and range."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: ParamType
    description: str
    default: Scalar | None = None
    required: bool = False
    minimum: float | None = None
    maximum: float | None = None
    choices: list[str] | None = None

    def problem(self, value: object) -> str | None:
        """Why `value` isn't valid for this parameter, or None."""
        expected: dict[str, tuple[type, ...]] = {
            "int": (int,),
            "float": (int, float),
            "bool": (bool,),
            "str": (str,),
            "choice": (str,),
        }
        if isinstance(value, bool) and self.type != "bool" or not isinstance(value, expected[self.type]):
            return f"expected {self.type}, got {value!r}"
        if self.choices is not None and value not in self.choices:
            return f"expected one of {', '.join(self.choices)}, got {value!r}"
        if isinstance(value, int | float) and not isinstance(value, bool):
            if self.minimum is not None and value < self.minimum:
                return f"must be at least {self.minimum:g}, got {value}"
            if self.maximum is not None and value > self.maximum:
                return f"must be at most {self.maximum:g}, got {value}"
        return None


class DecisionSpec(BaseModel):
    """A kind of Decision a Stage accepts, with the JSON Schema of one entry.

    An `on_image` Decision (a click) is made on the Stage's input image: core records that image's hash with it, and
    replaying it onto a changed image puts the Stage in needs-review.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    entry_schema: dict[str, Any]
    on_image: bool = False


class CheckSpec(BaseModel):
    """A Check a Stage runs, by the finding code it reports."""

    model_config = ConfigDict(extra="forbid")

    code: str
    description: str


class StageInputs(BaseModel):
    """What a Stage's input hash covers.

    `files` are globs relative to the Asset folder; `upstream` names earlier Stages; `settings` names project settings
    by dotted path into `kiripix.toml` (`body`, `project.tile`), where `palette` means the palette file's contents.
    """

    model_config = ConfigDict(extra="forbid")

    files: list[str] = []
    upstream: list[str] = []
    settings: list[str] = []


class StageFailure(Exception):
    """Raised by a Stage's run function when it can't produce its output."""


ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class CurrentDecision:
    """One of a Stage's current Decisions: the journal replayed. `image_hash` is the hash of the image a click or
    Override was made on, when the entry recorded one."""

    id: str
    name: str
    data: dict[str, Any]
    image_hash: str | None = None


@dataclass(frozen=True)
class StageRun:
    """What core hands a Stage's run function. Outputs go into `output_dir`, which core moves into place."""

    asset_id: str
    asset_dir: Path
    output_dir: Path
    files: dict[str, Path]
    upstream: dict[str, Path]
    params: dict[str, Scalar]
    settings: dict[str, Any]
    progress: ProgressCallback
    decisions: tuple[CurrentDecision, ...] = ()
    asset_params: dict[str, Scalar] = field(default_factory=dict)
    # Raises if the Command was cancelled. Call it between chunks of work (tiles, frames, batches); `progress` calls it
    # too. A Stage never catches what it raises.
    check_cancel: Callable[[], None] = lambda: None


StageFunction = Callable[[StageRun], None]


@dataclass(frozen=True)
class NeedsInput:
    """Why a Stage can't run until the Owner acts, and what `next` offers: a `command`, or else an `owner_action`."""

    reason: str
    command: str | None = None
    owner_action: str | None = None


NeedsInputFunction = Callable[[StageRun], NeedsInput | None]
CheckFunction = Callable[[StageRun], list[Finding]]


@dataclass(frozen=True)
class StageSpec:
    """One Stage of a Recipe.

    A Stage without a run function is declared but not built yet; it reports needs-input with `available_from`.
    `image` names the file in its output that is its image: what the next Stage's clicks are made on, and what an
    Override paints over. `needs_input` says, from the Stage's inputs alone, why it can't run yet. `check` runs the
    Stage's Checks on its output (`output_dir` is the built output).
    """

    name: str
    description: str
    inputs: StageInputs = field(default_factory=StageInputs)
    params: tuple[ParamSpec, ...] = ()
    decisions: tuple[DecisionSpec, ...] = ()
    checks: tuple[CheckSpec, ...] = ()
    owner_input: str | None = None
    gpu: bool = False
    output_root: Literal["work", "out"] = "work"
    run: StageFunction | None = None
    available_from: str | None = None
    image: str | None = None
    needs_input: NeedsInputFunction | None = None
    check: CheckFunction | None = None


@dataclass(frozen=True)
class KindSpec:
    """A Kind and its Recipe: the ordered Stages, plus the Asset-level parameters given to `new`."""

    name: str
    description: str
    stages: tuple[StageSpec, ...]
    params: tuple[ParamSpec, ...] = ()

    def stage(self, name: str) -> StageSpec | None:
        return next((s for s in self.stages if s.name == name), None)


def chain(*stages: StageSpec) -> tuple[StageSpec, ...]:
    """Make each Stage's upstream the Stage before it, unless it declares its own."""
    result: list[StageSpec] = []
    for stage in stages:
        if result and not stage.inputs.upstream:
            inputs = stage.inputs.model_copy(update={"upstream": [result[-1].name]})
            stage = replace(stage, inputs=inputs)
        result.append(stage)
    return tuple(result)


def point_decision(name: str, description: str, *, on_image: bool = False, **extra: dict[str, Any]) -> DecisionSpec:
    """A Decision placed at a target pixel, with any extra properties."""
    properties: dict[str, Any] = {"x": {"type": "integer", "minimum": 0}, "y": {"type": "integer", "minimum": 0}}
    properties.update(extra)
    return DecisionSpec(
        name=name,
        description=description,
        entry_schema={
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
        on_image=on_image,
    )


PICK = DecisionSpec(
    name="pick",
    description="Choose one Variant as the Source.",
    entry_schema={
        "type": "object",
        "properties": {"variant": {"type": "string"}},
        "required": ["variant"],
        "additionalProperties": False,
    },
)

PALETTE_PARAMS = (
    ParamSpec(
        name="dither",
        type="choice",
        description="Ordered dithering before mapping.",
        default="none",
        choices=["none", "bayer2", "bayer4", "bayer8"],
    ),
    ParamSpec(name="strength", type="float", description="Dither strength.", default=1.0, minimum=0, maximum=1),
    ParamSpec(
        name="orphan_size",
        type="int",
        description="Remove pixel islands up to this size.",
        default=1,
        minimum=0,
        maximum=16,
    ),
)

FIT_PARAMS = (
    ParamSpec(
        name="mode",
        type="choice",
        description="Detect the Source's pixel grid, or downscale with a mode filter.",
        default="grid",
        choices=["grid", "downscale"],
    ),
    ParamSpec(name="scale", type="int", description="Source pixels per target pixel; 0 detects it.", default=0, minimum=0),
    ParamSpec(name="offset_x", type="int", description="Grid offset in Source pixels.", default=0, minimum=0),
    ParamSpec(name="offset_y", type="int", description="Grid offset in Source pixels.", default=0, minimum=0),
)
