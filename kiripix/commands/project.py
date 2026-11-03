"""The Project Commands: init, new, describe, status, next and run."""

from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kiripix.checks import Finding
from kiripix.commands.contract import Context, ExitCode, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core.assets import create_asset, is_asset_id, list_assets, load_asset
from kiripix.core.errors import KiripixError
from kiripix.core.graph import AssetGraph, StageRunResult, StageState, run_all, run_asset
from kiripix.core.hashing import HashCache
from kiripix.core.kinds import all_kinds, get_kind
from kiripix.core.project import find_project, init_project
from kiripix.recipes.base import CheckSpec, DecisionSpec, KindSpec, ParamSpec, StageInputs


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


# init


class InitInput(_Input):
    dir: Path = Field(Path("."), description="The folder to create the Project in.")


class InitData(BaseModel):
    root: str
    created: list[str]

    def text(self) -> str:
        return f"Created a Kiripix project in {self.root}\n" + "\n".join(f"  {c}" for c in self.created)


@command(
    "init",
    summary="Create a new Project: kiripix.toml, style/, assets/, .gitattributes and .gitignore.",
    input=InitInput,
    output=InitData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("dir",)),
)
def init(arguments: InitInput, context: Context) -> Outcome[InitData]:
    root = (context.cwd / arguments.dir).resolve()
    created = init_project(root)
    return Outcome(InitData(root=str(root), created=created))


# new


class NewInput(_Input):
    kind: str = Field(description="The Asset's Kind: room, prop or character.")
    name: str = Field(description="The Asset's name: lower-case letters, digits and underscores.")
    view: str | None = Field(None, description="top or side. Required for a room; refused for other Kinds.")

    @property
    def asset_id(self) -> str:
        return f"{self.kind}.{self.name.removeprefix(f'{self.kind}.')}"


class NewData(BaseModel):
    asset: str
    path: str
    created: list[str]

    def text(self) -> str:
        return f"Created {self.asset} in {self.path}"


@command(
    "new",
    summary="Create a new Asset from its Kind's Recipe.",
    input=NewInput,
    output=NewData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("kind", "name")),
    locks=LockNeeds(asset=lambda a: a.asset_id if is_asset_id(a.asset_id) else None),
)
def new(arguments: NewInput, context: Context) -> Outcome[NewData]:
    project = find_project(context.cwd)
    params = {"view": arguments.view} if arguments.view is not None else {}
    asset, created = create_asset(project, arguments.kind, arguments.name, params)
    return Outcome(NewData(asset=asset.id, path=project.relative(asset.dir), created=created))


# describe


class DescribeInput(_Input):
    target: str = Field(description="'project' for every Kind and its Recipe, or a Kind for its Stages in detail.")


class StageDescription(BaseModel):
    name: str
    description: str
    inputs: StageInputs
    params: list[ParamSpec]
    decisions: list[DecisionSpec]
    checks: list[CheckSpec]
    owner_input: str | None
    gpu: bool
    implemented: bool
    available_from: str | None


class KindDescription(BaseModel):
    name: str
    description: str
    params: list[ParamSpec]
    recipe: list[str]
    stages: list[StageDescription] | None = None


class DescribeData(BaseModel):
    kinds: list[KindDescription]

    def text(self) -> str:
        lines = []
        for kind in self.kinds:
            lines.append(f"{kind.name}: {kind.description}")
            lines.append("  recipe: " + " -> ".join(kind.recipe))
            for param in kind.params:
                lines.append(f"  --{param.name}: {param.description}")
            for stage in kind.stages or []:
                status = "" if stage.implemented else f" (from {stage.available_from})"
                lines.append(f"  {stage.name}{status}: {stage.description}")
                for param in stage.params:
                    lines.append(f"    {param.name} = {param.default!r}  {param.type}  {param.description}")
                for decision in stage.decisions:
                    lines.append(f"    decision {decision.name}: {decision.description}")
                for check in stage.checks:
                    lines.append(f"    check {check.code}: {check.description}")
        return "\n".join(lines)


def _describe(kind: KindSpec, detail: bool) -> KindDescription:
    stages = [
        StageDescription(
            name=s.name,
            description=s.description,
            inputs=s.inputs,
            params=list(s.params),
            decisions=list(s.decisions),
            checks=list(s.checks),
            owner_input=s.owner_input,
            gpu=s.gpu,
            implemented=s.run is not None,
            available_from=s.available_from,
        )
        for s in kind.stages
    ]
    return KindDescription(
        name=kind.name,
        description=kind.description,
        params=list(kind.params),
        recipe=[s.name for s in kind.stages],
        stages=stages if detail else None,
    )


@command(
    "describe",
    summary="Describe the Kinds and their Recipes, or one Kind's Stages: parameters, Decisions and Checks.",
    input=DescribeInput,
    output=DescribeData,
    kind="probe",
    mcp="exposed",
    cli=CliMeta(positional=("target",)),
)
def describe(arguments: DescribeInput, context: Context) -> Outcome[DescribeData]:
    if arguments.target == "project":
        kinds = [_describe(k, detail=False) for _, k in sorted(all_kinds().items())]
    else:
        kinds = [_describe(get_kind(arguments.target), detail=True)]
    return Outcome(DescribeData(kinds=kinds))


# status


class StatusInput(_Input):
    kind: str | None = Field(None, description="Show only the Assets of this Kind.")


class AssetStatus(BaseModel):
    asset: str
    kind: str
    stages: list[StageState]


class StatusData(BaseModel):
    project: str
    assets: list[AssetStatus]

    def text(self) -> str:
        if not self.assets:
            return f"{self.project}: no Assets yet"
        lines = [self.project]
        for asset in self.assets:
            lines.append(f"  {asset.asset}")
            for stage in asset.stages:
                reason = f"  ({stage.reason})" if stage.reason else ""
                lines.append(f"    {stage.stage:<10} {stage.status}{reason}")
        return "\n".join(lines)


@command(
    "status",
    summary="Show every Asset with each Stage's status, derived from input hashes.",
    input=StatusInput,
    output=StatusData,
    kind="probe",
    mcp="exposed",
)
def status(arguments: StatusInput, context: Context) -> Outcome[StatusData]:
    project = find_project(context.cwd)
    if arguments.kind is not None:
        get_kind(arguments.kind)
    assets, findings = list_assets(project)
    cache = HashCache(project.state_dir)
    rows: list[AssetStatus] = []
    for asset in assets:
        if arguments.kind is not None and asset.kind != arguments.kind:
            continue
        try:
            states = AssetGraph(project, asset, cache).states()
        except KiripixError as error:
            findings.extend(error.findings)
            continue
        rows.append(AssetStatus(asset=asset.id, kind=asset.kind, stages=states))
    cache.save()
    return Outcome(
        StatusData(project=project.settings.project.name, assets=rows),
        findings,
        ExitCode.ERROR if findings else ExitCode.OK,
    )


# next


class NextInput(_Input):
    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")


class NextData(BaseModel):
    """Either a `command` to run or an `owner_action`; both are null only when every Stage is done."""

    asset: str
    done: bool
    stage: str | None = None
    status: str | None = None
    reason: str | None = None
    command: str | None = None
    owner_action: str | None = None

    def text(self) -> str:
        if self.done:
            return f"{self.asset}: every Stage is done"
        todo = f"run: {self.command}" if self.command else f"owner: {self.owner_action}"
        return f"{self.asset} {self.stage} is {self.status}; {todo}"


@command(
    "next",
    summary="The next Stage of an Asset and what it needs: a command to run, or the Owner's action.",
    input=NextInput,
    output=NextData,
    kind="probe",
    mcp="exposed",
    cli=CliMeta(positional=("asset",)),
)
def next_step(arguments: NextInput, context: Context) -> Outcome[NextData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    cache = HashCache(project.state_dir)
    graph = AssetGraph(project, asset, cache)
    data = NextData(asset=asset.id, done=True)
    advice: list[Finding] = []  # info findings of done Stages: carried along, never a reason to stop
    for state in graph.states():
        spec = graph.spec(state.stage)
        if state.status == "done":
            found = graph.check(spec)
            advice.extend(f for f in found if f.severity == "info")
            failed = [f for f in found if f.severity == "error"]
            if not failed:
                continue
            data = NextData(asset=asset.id, done=False, stage=state.stage, status=state.status,
                            reason=failed[0].message, command=failed[0].fix, owner_action=failed[0].owner_action)
            break
        data = NextData(asset=asset.id, done=False, stage=state.stage, status=state.status, reason=state.reason)
        waiting = graph.needs_input(spec) if state.status == "needs-input" and spec.run is not None else None
        if waiting is not None:
            data.command, data.owner_action = waiting.command, waiting.owner_action
        elif state.status == "needs-input":
            data.owner_action = f"{state.reason[0].upper()}{state.reason[1:]}." if state.reason else "Provide input."
        elif state.status == "needs-review":
            data.owner_action = f"Review and accept: kiripix accept {asset.id} {state.stage}"
        else:
            data.command = f"kiripix run {asset.id}"
        break
    cache.save()
    return Outcome(data, advice)


# run


class RunInput(_Input):
    asset: str | None = Field(None, description="The Asset ID. Omit with --all.")
    stage: str | None = Field(None, description="Run only this Stage (its upstream Stages must be done).")
    all: bool = Field(False, description="Run every Asset, locking one at a time.")
    kind: str | None = Field(None, description="With --all: only the Assets of this Kind.")
    force: bool = Field(False, description="Re-run even Stages that are done.")

    @model_validator(mode="after")
    def _asset_or_all(self) -> Self:
        if self.all == (self.asset is not None):
            raise ValueError("give an Asset ID or --all, not both")
        if self.all and self.stage is not None:
            raise ValueError("a Stage can't be given with --all")
        if self.kind is not None and not self.all:
            raise ValueError("--kind works only with --all")
        return self


class RunData(BaseModel):
    results: list[StageRunResult]

    def text(self) -> str:
        lines = []
        for r in self.results:
            took = f" in {r.duration_s:.2f}s" if r.duration_s is not None else ""
            message = f": {r.message}" if r.message else ""
            lines.append(f"{r.asset} {r.stage}: {r.outcome}{took}{message}")
        return "\n".join(lines) or "nothing to run"


@command(
    "run",
    summary="Run an Asset's stale and todo Stages in order, stopping at the first that needs input or fails.",
    input=RunInput,
    output=RunData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset", "stage")),
    locks=LockNeeds(asset=lambda a: a.asset if is_asset_id(a.asset) else None),
)
def run(arguments: RunInput, context: Context) -> Outcome[RunData]:
    project = find_project(context.cwd)
    cache = HashCache(project.state_dir)
    if arguments.all:
        if arguments.kind is not None:
            get_kind(arguments.kind)
        result = run_all(project, cache, kind=arguments.kind, force=arguments.force, progress=context.progress,
                         wait=context.wait, command_line=context.command_line)
    else:
        assert arguments.asset is not None
        asset = load_asset(project, arguments.asset)
        result = run_asset(project, asset, cache, stage=arguments.stage, force=arguments.force,
                           progress=context.progress, wait=context.wait, command_line=context.command_line)
    findings: list[Finding] = result.findings
    return Outcome(RunData(results=result.results), findings, result.exit_code)
