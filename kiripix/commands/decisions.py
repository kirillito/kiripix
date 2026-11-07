"""The Commands that change an Asset's decisions: set, decide, undo, redo, override, mask-import, plate-import and accept."""

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


def current_decisions(decisions: tuple[CurrentDecision, ...]) -> list[DecisionOut]:
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
    file: Path | None = Field(None, description="A file holding that JSON, instead of --decision. It may hold a JSON "
                              "array of Decisions for this Stage: all are recorded in order, or none.")
    brief: bool = Field(False, description="Leave `current` out of the result: give the count of current Decisions.")

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        if (self.decision is None) == (self.file is None):
            raise ValueError("give the Decision with --decision or --file, one of them")
        return self


class DecideData(BaseModel):
    asset: str
    stage: str
    id: str = Field(description="The recorded entry's ID; the last one for an array.")
    parent: str | None
    decision: str
    current: list[DecisionOut] | None = Field(None, description="Every current Decision; null with --brief.")
    count: int = Field(0, description="How many Decisions are current now.")
    ids: list[str] = Field(default_factory=list, description="The IDs recorded, in order.")

    def text(self) -> str:
        recorded = f"{len(self.ids)} Decisions, the last {self.decision}" if len(self.ids) > 1 else self.decision
        return f"{self.asset} {self.stage}: recorded {recorded} ({self.id}); {self.count} current"


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
    documents, is_array = editing.parse_decisions(text, source, asset, arguments.stage)
    if is_array:
        entries, after = editing.record_decisions(project, asset, arguments.stage, documents)
    else:
        entry, after = editing.record_decision(project, asset, arguments.stage, documents[0])
        entries = [entry]
    last = entries[-1]
    return Outcome(DecideData(asset=asset.id, stage=arguments.stage, id=last.id, parent=last.parent,
                              decision=documents[-1].decision,
                              current=None if arguments.brief else current_decisions(after.current),
                              count=len(after.current), ids=[e.id for e in entries]))


# undo and redo


class StepInput(_StageInput):
    brief: bool = Field(False, description="Leave `current` out of the result: give the count of current Decisions.")


class StepData(BaseModel):
    asset: str
    stage: str
    id: str
    target: str
    current: list[DecisionOut] | None = Field(None, description="Every current Decision; null with --brief.")
    count: int = Field(0, description="How many Decisions are current now.")

    def text(self) -> str:
        return f"{self.asset} {self.stage}: {self.count} current Decisions (entry {self.id} on {self.target})"


def _step(entry: journal.JournalEntry, after: journal.Replay, asset_id: str, stage: str, brief: bool) -> StepData:
    target = entry.undo or entry.redo
    assert target is not None
    return StepData(asset=asset_id, stage=stage, id=entry.id, target=target,
                    current=None if brief else current_decisions(after.current), count=len(after.current))


@command(
    "undo",
    summary="Undo a Stage's latest current Decision by appending an undo entry; nothing is removed from the journal.",
    input=StepInput,
    output=StepData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset", "stage")),
    locks=LockNeeds(asset=_asset_lock),
)
def undo(arguments: StepInput, context: Context) -> Outcome[StepData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    entry, after = editing.undo(project, asset, arguments.stage)
    return Outcome(_step(entry, after, asset.id, arguments.stage, arguments.brief))


@command(
    "redo",
    summary="Redo a Stage's latest undone Decision by appending a redo entry.",
    input=StepInput,
    output=StepData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset", "stage")),
    locks=LockNeeds(asset=_asset_lock),
)
def redo(arguments: StepInput, context: Context) -> Outcome[StepData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    entry, after = editing.redo(project, asset, arguments.stage)
    return Outcome(_step(entry, after, asset.id, arguments.stage, arguments.brief))


# override


class OverrideInput(_StageInput):
    stage: str = Field(description="The Stage whose image output was painted over.")
    png: Path = Field(description="The painted PNG, the same size as the Stage's image.")


class OverrideData(BaseModel):
    asset: str
    stage: str
    id: str
    file: str
    image_hash: str
    stages: list[StageState]

    def text(self) -> str:
        return f"{self.asset} {self.stage}: recorded an Override ({self.file}); run to apply it"


@command(
    "override",
    summary="Record an Override: a PNG painted over a Stage's image output, applied each time the Stage runs.",
    input=OverrideInput,
    output=OverrideData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("asset", "stage", "png")),
    locks=LockNeeds(asset=_asset_lock),
    files=("png",),
)
def override(arguments: OverrideInput, context: Context) -> Outcome[OverrideData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    entry, stored = editing.record_override(project, asset, arguments.stage, context.cwd / arguments.png,
                                            str(arguments.png))
    assert entry.image_hash is not None
    states = AssetGraph(project, asset, HashCache(project.state_dir)).states()
    return Outcome(OverrideData(asset=asset.id, stage=arguments.stage, id=entry.id, file=project.relative(stored),
                                image_hash=entry.image_hash, stages=states))


# mask-import


class MaskImportInput(_Input):
    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")
    png: Path = Field(description="The painted PNG, the Plate's size, in the Masks' colours from `describe`.")


class MaskImportData(BaseModel):
    asset: str
    stage: str
    id: str
    file: str
    stages: list[StageState]

    def text(self) -> str:
        return f"{self.asset} {self.stage}: recorded an import of {self.file}; run to split it into Masks"


@command(
    "mask-import",
    summary="Import a painted mask image: store it by its hash and record the masks Stage's import Decision.",
    input=MaskImportInput,
    output=MaskImportData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("asset", "png")),
    locks=LockNeeds(asset=_asset_lock),
    files=("png",),
)
def mask_import(arguments: MaskImportInput, context: Context) -> Outcome[MaskImportData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    entry, stored = editing.record_mask_import(project, asset, context.cwd / arguments.png, str(arguments.png))
    states = AssetGraph(project, asset, HashCache(project.state_dir)).states()
    return Outcome(MaskImportData(asset=asset.id, stage=editing.MASKS_STAGE, id=entry.id,
                                  file=project.relative(stored), stages=states))


# plate-import


class PlateImportInput(_Input):
    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")
    png: Path = Field(description="The Plate image, a PNG or JPEG, the Asset's size.")


class PlateImportData(BaseModel):
    asset: str
    stage: str
    id: str
    file: str
    stages: list[StageState]

    def text(self) -> str:
        return f"{self.asset} {self.stage}: recorded a Plate image {self.file}; run to apply it"


@command(
    "plate-import",
    summary="Import a Plate image: store it by its hash and record the layers Stage's plate Decision.",
    input=PlateImportInput,
    output=PlateImportData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("asset", "png")),
    locks=LockNeeds(asset=_asset_lock),
    files=("png",),
)
def plate_import(arguments: PlateImportInput, context: Context) -> Outcome[PlateImportData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    entry, stored = editing.record_plate_import(project, asset, context.cwd / arguments.png, str(arguments.png))
    states = AssetGraph(project, asset, HashCache(project.state_dir)).states()
    return Outcome(PlateImportData(asset=asset.id, stage=editing.LAYERS_STAGE, id=entry.id,
                                   file=project.relative(stored), stages=states))


# accept


class AcceptData(BaseModel):
    asset: str
    stage: str
    recorded: list[str]
    stages: list[StageState]

    def text(self) -> str:
        return f"{self.asset} {self.stage}: accepted ({len(self.recorded)} journal entries)"


@command(
    "accept",
    summary="Accept a needs-review Stage: re-record its Decisions against the current image (owner-only).",
    input=_StageInput,
    output=AcceptData,
    kind="owner-only",
    mcp="owner-only",
    cli=CliMeta(positional=("asset", "stage")),
    locks=LockNeeds(asset=_asset_lock),
)
def accept(arguments: _StageInput, context: Context) -> Outcome[AcceptData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    appended = editing.accept(project, asset, arguments.stage)
    states = AssetGraph(project, asset, HashCache(project.state_dir)).states()
    return Outcome(AcceptData(asset=asset.id, stage=arguments.stage, recorded=[e.id for e in appended],
                              stages=states))
