"""The Project Commands: init, new, describe, status, next and run."""

from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kiripix.checks import Finding, Position
from kiripix.commands.contract import Context, ExitCode, Outcome
from kiripix.commands.ramp_table import RAMPS_EXAMPLE, RampRow
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import cancel, sources
from kiripix.core.assets import create_asset, is_asset_id, list_assets, load_asset
from kiripix.core.errors import KiripixError, fail
from kiripix.core.graph import AssetGraph, StageRunResult, StageState, run_all, run_asset
from kiripix.core.hashing import HashCache
from kiripix.core.kinds import all_kinds, get_kind
from kiripix.core.project import find_project, init_project
from kiripix.export import EXPORT_STAGE, export_command, export_pending
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
    kind: str = Field(description="The Asset's Kind: room, prop, character or sprite.")
    name: str = Field(description="The Asset's name: lower-case letters, digits and underscores.")
    view: str | None = Field(None, description="top or side. Required for a room; refused for other Kinds.")
    base: str | None = Field(None, description="For a character: the character it is made from, such as "
                                               "character.body_m. Its Model carries the base's skeleton, so it needs no "
                                               "rigged file; it starts with the base's clips; and a Stage parameter it "
                                               "doesn't set takes the base's value. The base has no base of its own.")
    from_parameters: Path | None = Field(
        None, description="For a character: a parameter file (.toml or .json) that the Project's generator builds its Model "
                          "from ([character.generators] in kiripix.toml). It is stored in the new character's "
                          "src/parameters/, as `import --role parameters` stores it.")

    @property
    def asset_id(self) -> str:
        return f"{self.kind}.{self.name.removeprefix(f'{self.kind}.')}"


class NewData(BaseModel):
    asset: str
    path: str
    created: list[str]

    def text(self) -> str:
        return f"Created {self.asset} in {self.path}"


def _parameters_to_import(arguments: NewInput, context: Context) -> Path | None:
    """The parameter file `new --from-parameters` names, checked before the Asset is made, so a refused file leaves none."""
    if arguments.from_parameters is None:
        return None
    shown = str(arguments.from_parameters)
    if arguments.kind != sources.CHARACTER:
        raise fail("new.parameters_need_character", f"--from-parameters is for a character; this is a {arguments.kind}",
                   fix=f"kiripix new character {arguments.name} --from-parameters {shown}")
    path = context.cwd / arguments.from_parameters
    if not path.is_file():
        raise fail("import.not_found", f"no file at {shown}", owner_action=f"Check the path {shown}.")
    return path


@command(
    "new",
    summary="Create a new Asset from its Kind's Recipe.",
    input=NewInput,
    output=NewData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("kind", "name")),
    locks=LockNeeds(asset=lambda a: a.asset_id if is_asset_id(a.asset_id) else None),
    files=("from_parameters",),
)
def new(arguments: NewInput, context: Context) -> Outcome[NewData]:
    project = find_project(context.cwd)
    params = {name: value for name, value in (("view", arguments.view), ("base", arguments.base)) if value is not None}
    parameters = _parameters_to_import(arguments, context)
    if parameters is not None:
        sources.check_parameters(parameters, str(arguments.from_parameters))
    asset, created = create_asset(project, arguments.kind, arguments.name, params)
    if parameters is not None:
        _, stored, _ = sources.import_file(asset, parameters, str(arguments.from_parameters), "parameters")
        created = [*created, project.relative(stored)]
    return Outcome(NewData(asset=asset.id, path=project.relative(asset.dir), created=created))


# describe


class DescribeInput(_Input):
    target: str = Field(description="'project' for every Kind and its Recipe, or a Kind for its Stages in detail.")
    stage: str | None = Field(None, description="With a Kind: describe only this Stage.")


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
    ramps: list[RampRow] | None = Field(
        None, description="With `describe project`: the Project's ramp table, in row order (null for a Kind).")
    ramps_example: str | None = Field(None, description="With `describe project`: how to fill the ramp table.")

    def text(self) -> str:
        lines = []
        if self.ramps is not None:
            lines.append(f"ramp table ({len(self.ramps)} rows; e.g. {self.ramps_example}):")
            for row, ramp in enumerate(self.ramps):
                colours = "shared colours" if ramp.rgb else "colours fitted per character"
                lines.append(f"  row {row}: {ramp.name}, {ramp.length} steps, {colours}")
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
            gpu=s.gpu or s.runner_calls is not None,
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
        if arguments.stage is not None:
            raise fail("describe.stage_needs_kind", "--stage needs a Kind, not 'project'",
                       fix="kiripix describe project")
        kinds = [_describe(k, detail=False) for _, k in sorted(all_kinds().items())]
        try:  # `describe project` also works outside a Project, with no table
            ramps = find_project(context.cwd).settings.character.ramps
        except KiripixError:
            return Outcome(DescribeData(kinds=kinds, ramps_example=RAMPS_EXAMPLE))
        table = [RampRow(name=r.name, length=r.length, rgb=[list(c) for c in r.rgb] if r.rgb is not None else None)
                 for r in ramps]
        return Outcome(DescribeData(kinds=kinds, ramps=table, ramps_example=RAMPS_EXAMPLE))
    else:
        kind = _describe(get_kind(arguments.target), detail=True)
        if arguments.stage is not None:
            names = [s.name for s in kind.stages or []]
            if arguments.stage not in names:
                raise fail("describe.unknown_stage",
                           f"the {kind.name} Recipe has no Stage '{arguments.stage}'; its Stages are "
                           f"{', '.join(names)}", fix=f"kiripix describe {kind.name}")
            kind = kind.model_copy(update={"stages": [s for s in kind.stages or [] if s.name == arguments.stage]})
        kinds = [kind]
    return Outcome(DescribeData(kinds=kinds))


# status


class StatusInput(_Input):
    kind: str | None = Field(None, description="Show only the Assets of this Kind.")


class AssetStatus(BaseModel):
    asset: str
    kind: str
    stages: list[StageState]
    export_command: str | None = Field(
        None, description="While every Stage is done and the game doesn't have what is built: the Command that exports it.")


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
            if asset.export_command:
                lines.append(f"    built, but not in the game yet: {asset.export_command}")
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
        rows.append(AssetStatus(asset=asset.id, kind=asset.kind, stages=states,
                                export_command=export_command(project, asset, cache, states)))
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
    advice: list[Finding] = []  # warnings and info findings of done Stages: carried along, never a reason to stop
    for state in graph.states():
        spec = graph.spec(state.stage)
        if state.status == "done":
            found = graph.check(spec)
            advice.extend(f for f in found if f.severity != "error")
            failed = [f for f in found if f.severity == "error"]
            if not failed:
                continue
            data = NextData(asset=asset.id, done=False, stage=state.stage, status=state.status,
                            reason=failed[0].message, command=failed[0].fix, owner_action=failed[0].owner_action)
            break
        data = NextData(asset=asset.id, done=False, stage=state.stage, status=state.status, reason=state.reason)
        waiting = graph.needs_input(spec) if state.status == "needs-input" and (
            spec.run is not None or spec.needs_input is not None) else None
        if waiting is not None:
            data.command, data.owner_action = waiting.command, waiting.owner_action
        elif state.status == "needs-input":
            data.owner_action = f"{state.reason[0].upper()}{state.reason[1:]}." if state.reason else "Provide input."
        elif state.status == "needs-review":
            data.owner_action = f"Review and accept: kiripix accept {asset.id} {state.stage}"
        else:
            data.command = f"kiripix run {asset.id}"
        break
    if data.done and export_pending(project, asset, cache):
        data = NextData(asset=asset.id, done=False, stage=EXPORT_STAGE, status="done",
                        reason="the game doesn't have what is built yet", command=f"kiripix export {asset.id}")
    cache.save()
    return Outcome(data, advice)


# run


class RunInput(_Input):
    asset: str | None = Field(None, description="The Asset ID. Omit with --all.")
    stage: str | None = Field(None, description="Run only this Stage (its upstream Stages must be done).")
    all: bool = Field(False, description="Run every Asset, locking one at a time.")
    kind: str | None = Field(None, description="With --all: only the Assets of this Kind.")
    force: bool = Field(False, description="Re-run even Stages that are done.")
    rerun: bool = Field(False, description="Also make the Runner calls with no pinned result; they land in needs-review.")
    cpu: bool = Field(False, description="Run Runners on the CPU, without the GPU lock.")

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
                         wait=context.wait, command_line=context.command_line, rerun=arguments.rerun, cpu=arguments.cpu,
                         keep_warm=context.via == "rest")
    else:
        assert arguments.asset is not None
        asset = load_asset(project, arguments.asset)
        result = run_asset(project, asset, cache, stage=arguments.stage, force=arguments.force,
                           progress=context.progress, wait=context.wait, command_line=context.command_line,
                           rerun=arguments.rerun, cpu=arguments.cpu, keep_warm=context.via == "rest")
    findings: list[Finding] = result.findings
    if result.exit_code == ExitCode.OK:
        for asset_id in sorted({r.asset for r in result.results}):
            cancel.check()
            if wanted := export_command(project, load_asset(project, asset_id), cache):
                findings.append(Finding(
                    code="export.pending", severity="info",
                    message=f"{asset_id} is built, but the game doesn't have it yet: `run` writes nothing into the game",
                    position=Position(asset=asset_id, stage=EXPORT_STAGE),
                    fix=wanted))
    return Outcome(RunData(results=result.results), findings, result.exit_code)
