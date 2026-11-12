"""How a Kind and its Recipe are declared: Stages with inputs, parameters, Decisions, Checks and a run function."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
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


class SortPosition(BaseModel):
    """A foreground Layer's sort position (spec §9; D3 in ticket 0037): the one number the walk test and the Exporter read,
    never work out again. The Body sorts below the Layer while its y is under `y`."""

    model_config = ConfigDict(extra="forbid")

    layer: str
    above: bool  # always above the Body; `marker` and `y` are then None
    marker: str | None  # the ID of the y-sort line that sorts the Layer
    y: int | None  # the line's mean y, rounded half up; None while the Layer has neither line nor flag
    slope: int  # how far the line's ends differ in y, in px


class StageInputs(BaseModel):
    """What a Stage's input hash covers.

    `files` are globs relative to the Asset folder; `upstream` names earlier Stages; `settings` names project settings
    by dotted path into `kiripix.toml` (`body`, `project.tile`), where `palette` means the palette file's contents, or a
    computed setting (`computed_setting`). `given` names settings the Stage is given but that don't count as inputs, such
    as where a tool is installed: moving it must not make anything stale. Both reach the Stage in `StageRun.settings`.
    """

    model_config = ConfigDict(extra="forbid")

    files: list[str] = []
    upstream: list[str] = []
    settings: list[str] = []
    given: list[str] = []


COMPUTED_SETTINGS: dict[str, Callable[[], Any]] = {}


def computed_setting(name: str, value: Callable[[], Any]) -> None:
    """Declare a setting that isn't in `kiripix.toml` but is worked out when asked, such as the version of a tool a Stage
    runs (ADR 0010). A Stage lists it in `StageInputs.settings`, so a change makes the Stage stale."""
    COMPUTED_SETTINGS[name] = value


class StageFailure(Exception):
    """Raised by a Stage's run function when it can't produce its output. The finding is `stage.failed`, with a `fix` that
    runs the Stage again, unless the failure gives its own `code` or an `owner_action`: something only the Owner can do,
    such as installing Blender, and no agent can fix by running the Stage again. A `fix` is a command that does."""

    def __init__(self, message: str, *, code: str | None = None, owner_action: str | None = None,
                 fix: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.owner_action = owner_action
        self.fix = fix


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
class RunnerCall:
    """One Runner call a Stage's current Decisions need, pinned by core (ADR 0002). `image` is the input image's file,
    `params` are handed to the Runner, and `decisions` are what the Owner decided, as they were recorded: the same
    `decisions` under another key mean the call's input changed. Everything here is part of the key."""

    runner: str
    image: Path
    params: dict[str, Any]
    decisions: list[dict[str, Any]]


def _no_pinned_results(call: RunnerCall) -> Path:
    raise StageFailure(f"this Stage has no pinned result for {call.runner}")


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
    # The run was asked for `--cpu`: it holds no GPU lock, so a Stage that can use the GPU (Blender) must stay off it.
    cpu: bool = False
    # The file of a call's pinned result, which core has made sure exists before the Stage runs. A Stage never calls a
    # Runner itself: it reads what was pinned.
    pinned: Callable[[RunnerCall], Path] = _no_pinned_results
    # The Stage's own last complete output folder (it holds its stamp), or None on a first build or when that folder is
    # missing or half-made. READ-ONLY: copy from it into `output_dir`, never write to it. It is set whether or not the
    # stamp's input hash still matches, so a Stage that reuses old output must check its own finer-grained keys. It is
    # not an input: it never enters a hash, and a Stage that ignores it behaves as before.
    previous: Path | None = None
    # The run was asked for `--force`: "don't trust the cache". A Stage that reuses its `previous` output must build everything.
    forced: bool = False
    # A Stage appends a short sentence about what it did (what it reused); core gives them as the run's message when it is done.
    notes: list[str] = field(default_factory=list)


StageFunction = Callable[[StageRun], None]
RunnerCallsFunction = Callable[[StageRun], "list[RunnerCall]"]


@dataclass(frozen=True)
class NeedsInput:
    """Why a Stage can't run until the Owner acts, and what `next` offers: a `command`, or else an `owner_action`."""

    reason: str
    command: str | None = None
    owner_action: str | None = None


NeedsInputFunction = Callable[[StageRun], NeedsInput | None]
CheckFunction = Callable[[StageRun], list[Finding]]
ClickPoint = tuple[int, int, bool]  # x and y in target pixels, and whether the click is a positive one
BoxCorners = tuple[int, int, int, int]  # x0, y0, x1, y1 in target pixels: the pixels from (x0, y0) to (x1, y1), both included


@dataclass(frozen=True)
class SegmentHooks:
    """What the `segment-preview` Probe needs from a Stage that segments. `call` is the Runner call for clicks in target
    pixels: None until what it needs upstream is built, and StageFailure for a point off the image. `box_call` is the same
    for a box (ticket 0079). `to_target` maps the Runner's result back to the target grid. A preview is never recorded or
    pinned."""

    call: Callable[[StageRun, list[ClickPoint]], RunnerCall | None]
    to_target: Callable[[StageRun, np.ndarray], np.ndarray]
    box_call: Callable[[StageRun, BoxCorners], RunnerCall | None] | None = None


@dataclass(frozen=True)
class LayerStatsHooks:
    """What the `layer-stats` Probe needs from a Stage that lifts Layers, read from its output as built (including one
    awaiting review). `read` gives the Layers in order, each as (ID, PNG file), and the IDs removed; it is called with the
    Stage's output folder and the Asset ID, and an empty folder gives none. `sort_stage` is the Stage whose Decisions say
    how each Layer sorts, and `sort` is its `StageSpec.sort` with the built Layers and the removed ones. `ysort` is a
    suggested y-sort line as the `data` of a Decision of that Stage, from the Layer's ID, its left and right columns and
    its lowest row. A Probe records nothing."""

    read: Callable[[Path, str], tuple[list[tuple[str, Path]], list[str]]]
    sort_stage: str
    sort: Callable[[tuple[CurrentDecision, ...], list[str], list[str]], list[SortPosition]]
    ysort: Callable[[str, int, int, int], dict[str, Any]]


@dataclass(frozen=True)
class ReachHooks:
    """What the `reach` Probe needs from a Stage that floods the Body over the Masks (ticket 0078). The Probe answers with
    what the Stage reports, from the Masks as built (one awaiting review too) and the Markers a Stage's current Decisions
    place now. `unsupported` says why the Stage can't answer for this Asset, or None. `targets` are the Markers it floods
    from, given `marker_stage`'s Decisions. `report` is the Stage's own computation, handed the Stage's run (whose
    `upstream` holds `masks_stage`) and those targets; the Stage and the Probe share it. A Probe records nothing."""

    marker_stage: str
    masks_stage: str
    unsupported: Callable[[StageRun], str | None]
    targets: Callable[[tuple[CurrentDecision, ...]], list[dict[str, Any]]]
    report: Callable[[StageRun, list[dict[str, Any]]], dict[str, Any]]


@dataclass(frozen=True)
class StageSpec:
    """One Stage of a Recipe.

    A Stage without a run function is declared but not built yet; it reports needs-input with `available_from`.
    `image` names the file in its output that is its image: what the next Stage's clicks are made on, and what an
    Override paints over. `needs_input` says, from the Stage's inputs alone, why it can't run yet. `check` runs the
    Stage's Checks on its output (`output_dir` is the built output). `runner_calls` lists the Runner calls its current
    Decisions need, from what is built upstream; only `run --rerun` makes one that isn't pinned yet, and takes the GPU lock
    for it. `gpu` holds that lock through the run function, for one that loads a Runner itself; one that only reads pinned
    results must leave it off, or each rebuild makes a warm Runner unload.
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
    # Runs after core paints the Stage's Overrides over its image and before its Checks, on the same output folder
    # (`output_dir`), so it sees the image as painted and its Checks see what it wrote. The image's unpainted hash and
    # the Stage's input hash don't depend on it. A Stage without it behaves as before.
    after_overrides: StageFunction | None = None
    runner_calls: RunnerCallsFunction | None = None
    segment: SegmentHooks | None = None
    layer_stats: LayerStatsHooks | None = None
    reach: ReachHooks | None = None
    markers: Callable[[tuple[CurrentDecision, ...]], list[dict[str, Any]]] | None = None  # for `show`, before any build
    # Each Layer's sort position, from the Decisions alone, for `show` (the Exporter and the walk test read the built file).
    sort: Callable[[tuple[CurrentDecision, ...]], list[SortPosition]] | None = None


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


def box_decision(name: str, description: str, *, on_image: bool = False, **extra: dict[str, Any]) -> DecisionSpec:
    """A Decision on a box in target pixels, from (x0, y0) to (x1, y1), both pixels included, with any extra properties."""
    properties: dict[str, Any] = {corner: {"type": "integer", "minimum": 0} for corner in ("x0", "y0", "x1", "y1")}
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

PLATE = DecisionSpec(
    name="plate",
    description="Take the Plate from an image of the Asset's size, stored under decisions/imports/ by its hash; "
                "`plate-import` records it.",
    entry_schema={
        "type": "object",
        "properties": {"png": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
        "required": ["png"],
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
        description="Detect the Source's pixel grid, or downscale at one scale on both axes, cropping the rest.",
        default="grid",
        choices=["grid", "downscale"],
    ),
    ParamSpec(name="scale", type="int", description="Source pixels per target pixel; 0 detects it.", default=0, minimum=0),
    ParamSpec(name="offset_x", type="int", default=0, minimum=0,
              description="Source pixels from the left to the first cell: the grid's offset, or in downscale mode "
                          "where the crop starts."),
    ParamSpec(name="offset_y", type="int", default=0, minimum=0,
              description="Source pixels from the top to the first cell: the grid's offset, or in downscale mode "
                          "where the crop starts."),
)
