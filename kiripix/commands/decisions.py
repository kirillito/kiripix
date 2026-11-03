"""The Commands that change an Asset's decisions: set, decide, undo and redo."""

from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import editing, journal
from kiripix.core.errors import fail
from kiripix.core.assets import is_asset_id, load_asset
from kiripix.core.graph import AssetGraph, StageState
from kiripix.core.hashing import HashCache
from kiripix.core.project import find_project
from kiripix.recipes.base import CurrentDecision, Scalar


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _asset_lock(arguments: "_StageInput") -> str | None:
    return arguments.asset if is_asset_id(arguments.asset) else None


class _StageInput(_Input):
    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")
    stage: str = Field(description="The Stage's name; `kiripix describe <kind>` lists them.")


class DecisionOut(BaseModel):
    id: str
    name: str
    data: dict[str, object]
    image_hash: str | None = None


def _current(decisions: tuple[CurrentDecision, ...]) -> list[DecisionOut]:
    return [DecisionOut(id=d.id, name=d.name, data=d.data, image_hash=d.image_hash) for d in decisions]


# set


class SetInput(_StageInput):
    assignments: list[str] = Field(description="key=value pairs: the Stage's parameters and their new values.")


class SetData(BaseModel):
    asset: str
    stage: str
    params: dict[str, Scalar]
    stages: list[StageState]

    def text(self) -> str:
        lines = [f"{self.asset} {self.stage}: " + ", ".join(f"{k}={v}" for k, v in self.params.items())]
        lines += [f"  {s.stage:<10} {s.status}" for s in self.stages]
        return "\n".join(lines)


@command(
    "set",
    summary="Set a Stage's parameters (key=value ...), checked against the Stage's declared parameters.",
    input=SetInput,
    output=SetData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset", "stage", "assignments")),
    locks=LockNeeds(asset=_asset_lock),
)
def set_params(arguments: SetInput, context: Context) -> Outcome[SetData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    params = editing.set_params(project, asset, arguments.stage, arguments.assignments)
    asset = load_asset(project, arguments.asset)
    states = AssetGraph(project, asset, HashCache(project.state_dir)).states()
    return Outcome(SetData(asset=asset.id, stage=arguments.stage, params=params, stages=states))


# decide


class DecideInput(_StageInput):
    decision: str | None = Field(
        None, description='The Decision as JSON: {"decision": name, "data": {...}, "image_hash": optional}.')
    file: Path | None = Field(None, description="A file holding that JSON, instead of --decision.")

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        if (self.decision is None) == (self.file is None):
            raise ValueError("give the Decision with --decision or --file, one of them")
        return self


class DecideData(BaseModel):
    asset: str
    stage: str
    id: str
    parent: str | None
    decision: str
    current: list[DecisionOut]

    def text(self) -> str:
        return f"{self.asset} {self.stage}: recorded {self.decision} ({self.id}); {len(self.current)} current"


@command(
    "decide",
    summary="Record a Decision in a Stage's journal, validated against the Stage's Decision schema.",
    input=DecideInput,
    output=DecideData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset", "stage")),
    locks=LockNeeds(asset=_asset_lock),
)
def decide(arguments: DecideInput, context: Context) -> Outcome[DecideData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    if arguments.file is not None:
        path = context.cwd / arguments.file
        try:
            text, source = path.read_text(encoding="utf-8"), str(arguments.file)
        except (OSError, UnicodeDecodeError) as error:
            raise fail("decide.unreadable", f"can't read {arguments.file}: {error}",
                               fix=f"kiripix decide {asset.id} {arguments.stage} --help") from None
    else:
        assert arguments.decision is not None
        text, source = arguments.decision, "--decision"
    document = editing.parse_decision(text, source, asset, arguments.stage)
    entry, after = editing.record_decision(project, asset, arguments.stage, document)
    return Outcome(DecideData(asset=asset.id, stage=arguments.stage, id=entry.id, parent=entry.parent,
                              decision=document.decision, current=_current(after.current)))


# undo and redo


class StepData(BaseModel):
    asset: str
    stage: str
    id: str
    target: str
    current: list[DecisionOut]

    def text(self) -> str:
        return f"{self.asset} {self.stage}: {len(self.current)} current Decisions (entry {self.id} on {self.target})"


def _step(entry: journal.JournalEntry, after: journal.Replay, asset_id: str, stage: str) -> StepData:
    target = entry.undo or entry.redo
    assert target is not None
    return StepData(asset=asset_id, stage=stage, id=entry.id, target=target, current=_current(after.current))


@command(
    "undo",
    summary="Undo a Stage's latest current Decision by appending an undo entry; nothing is removed from the journal.",
    input=_StageInput,
    output=StepData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset", "stage")),
    locks=LockNeeds(asset=_asset_lock),
)
def undo(arguments: _StageInput, context: Context) -> Outcome[StepData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    entry, after = editing.undo(project, asset, arguments.stage)
    return Outcome(_step(entry, after, asset.id, arguments.stage))


@command(
    "redo",
    summary="Redo a Stage's latest undone Decision by appending a redo entry.",
    input=_StageInput,
    output=StepData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset", "stage")),
    locks=LockNeeds(asset=_asset_lock),
)
def redo(arguments: _StageInput, context: Context) -> Outcome[StepData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    entry, after = editing.redo(project, asset, arguments.stage)
    return Outcome(_step(entry, after, asset.id, arguments.stage))
