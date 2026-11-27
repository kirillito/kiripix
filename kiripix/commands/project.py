"""The Project Commands: init, new, describe, status, next and run."""

from functools import partial
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kiripix.checks import Finding, Position
from kiripix.commands.contract import Context, ExitCode, Outcome
from kiripix.commands.clip_table import CLIPS_EXAMPLE, ClipRow
from kiripix.commands.listing import FORGET_HELP, REFRESH_HELP, named_assets, project_assets
from kiripix.commands.mask_table import MASKS_EXAMPLE, MaskRow, mask_rows
from kiripix.commands.ramp_table import RAMPS_EXAMPLE, RampRow, ramp_row
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import cancel, crowd, sources
from kiripix.core.assets import create_asset, is_asset_id, list_assets, load_asset
from kiripix.core.errors import KiripixError, fail
from kiripix.core.graph import (
    RUNNER_INPUT_CHANGED,
    RUNNER_NOT_RUN,
    AssetGraph,
    StageRunResult,
    StageState,
    run_all,
    run_asset,
)
from kiripix.core.hashing import HashCache
from kiripix.core.kinds import all_kinds, get_kind
from kiripix.core.match import select
from kiripix.core.project import Project, find_project, init_project
from kiripix.core.queue import recall_state, what_next
from kiripix.export import EXPORT_STAGE, export_command, export_pending, export_stamp
from kiripix.recipes.base import BASE_PARAM, BODY_PARAM, CheckSpec, DecisionSpec, KindSpec, ParamSpec, StageInputs


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
    kind: str = Field(description=f"The Asset's Kind: {', '.join(sorted(all_kinds()))}.")
    name: str = Field(description="The Asset's name: lower-case letters, digits and underscores.")
    view: str | None = Field(None, description="top or side. Required for a room; refused for other Kinds.")
    base: str | None = Field(None, description="For a character: the character it is made from, such as "
                                               "character.body_m. Its Model carries the base's skeleton, so it needs no "
                                               "rigged file; it starts with the base's clips; and a Stage parameter it "
                                               "doesn't set takes the base's value. The base has no base of its own. "
                                               "For an npc (required): the character it is made of; its Wearables and "
                                               "colours are `choose`'s parameters.")
    body: str | None = Field(None, description="For a wearable: the character or sprite it is worn on, such as "
                                               "character.body_m. Its Model, rig, clips and cell make the wearable stale "
                                               "when they change; its cell and pivot are the wearable's.")
    use: str | None = Field(None, description="For a sound (required): what it is for, sfx, ui, ambience or music. Picks its "
                                              "row of `[sound.use.<use>]` (loudness target, channels) and its export folder. "
                                              "Frozen once exported.")
    sound_id: str | None = Field(None, description="For a sound: the game's ID, such as sfx.footstep.asphalt. It starts with "
                                                   "the use's prefix (sfx, ui, amb, music); default <prefix>.<name>. Frozen "
                                                   "once exported.")
    from_parameters: Path | None = Field(
        None, description="For a character: a parameter file (.toml or .json) that the Project's generator builds its Model "
                          "from ([character.generators] in kiripix.toml). It is stored in the new character's "
                          "src/parameters/, as `import --role parameters` stores it.")

    count: int | None = Field(None, ge=1, le=500, description="For an npc: make this many NPCs, <name>_01 … <name>_NN (the name "
                                                              "is their prefix), each with a choice picked from --seed that "
                                                              "passes the npc Checks (ticket 0359). Needs --base and --seed.")
    seed: int | None = Field(None, description="For an npc crowd or --reroll: the seed. The same seed in the same Project gives "
                                               "the same NPCs. A re-roll without one takes the next choice after the NPC's own.")
    wearables: str | None = Field(None, description="For an npc crowd or --reroll: the Wearables worn on the base that a pick may "
                                                    "use, IDs or globs comma-separated, such as wearable.hair_*,wearable.coat. "
                                                    "Default: every Wearable worn on the base. Each NPC wears a random subset.")
    choices: list[str] | None = Field(None, description="For an npc crowd or --reroll: narrow a Part's colour choices, part=a,b "
                                                        "(repeat for each Part), such as hair=auburn,blond. A Part not named "
                                                        "may use all its choices.")
    reroll: bool = Field(False, description="For an npc: pick its Wearables and colours again (the name is its ID). It changes "
                                            "that NPC and no other.")

    @property
    def asset_id(self) -> str:
        return f"{self.kind}.{self.name.removeprefix(f'{self.kind}.')}"

    @property
    def bulk(self) -> bool:
        return self.count is not None or self.reroll or any(v is not None for v in (self.seed, self.wearables, self.choices))


class CrowdNpc(BaseModel):
    asset: str
    wearables: list[str] = Field(description="The Wearables worn, in stack order.")
    colours: dict[str, str] = Field(description="Each Part's colour choice.")
    tries: int = Field(description="Picks tried until this one passed the Checks.")
    changed: bool = Field(True, description="With --reroll: false when no other choice could be found.")


class NewData(BaseModel):
    asset: str = Field(description="The new Asset; for a crowd, the IDs comma-separated.")
    path: str
    created: list[str]
    crowd: list[CrowdNpc] = Field(default_factory=list, description="With --count or --reroll: each NPC and its choice.")

    def text(self) -> str:
        if self.crowd:
            return "\n".join(f"{n.asset}: {','.join(n.wearables) or 'bare'} {','.join(f'{p}={c}' for p, c in n.colours.items())}"
                             for n in self.crowd)
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


def _new_locks(arguments: NewInput) -> list[str]:
    """The Assets `new` makes or changes: one, or a crowd's N (`<prefix>_01`…). A re-roll changes the named NPC."""
    if arguments.kind == "npc" and arguments.count is not None and not arguments.reroll:
        width = max(2, len(str(arguments.count)))
        ids = [f"npc.{arguments.name.removeprefix('npc.')}_{n:0{width}d}" for n in range(1, arguments.count + 1)]
    else:
        ids = [arguments.asset_id]
    return [i for i in ids if is_asset_id(i)]


def _new_bulk(arguments: NewInput, project: Project) -> Outcome[NewData]:
    """`new npc` with --count (a crowd from a seed) or --reroll (one NPC again): ticket 0359."""
    example = f"kiripix new npc {arguments.name} --base character.body_m --count 5 --seed 1"
    if arguments.kind != "npc":
        raise fail("new.crowd_needs_npc", f"--count, --seed, --wearables, --choices and --reroll are for an npc; this is a {arguments.kind}",
                   fix=example)
    if arguments.reroll:
        if arguments.count is not None or arguments.base is not None:
            raise fail("new.crowd_reroll_args", "--reroll re-picks the NPC named; --count and --base belong to a new crowd",
                       fix=f"kiripix new npc {arguments.asset_id} --reroll")
        result = crowd.reroll(project, arguments.asset_id, arguments.seed, arguments.wearables, arguments.choices, cancel.check)
    else:
        if arguments.count is None or arguments.base is None or arguments.seed is None:
            raise fail("new.crowd_incomplete", "a crowd needs --base, --count and --seed (the same seed in the same Project gives "
                       "the same NPCs)", fix=example)
        result = crowd.make_crowd(project, arguments.name, arguments.base, arguments.count, arguments.seed, arguments.wearables,
                                  arguments.choices, cancel.check)
    members = [CrowdNpc(asset=m.asset, wearables=list(m.choice.wearables), colours=dict(m.choice.colours), tries=m.tries,
                        changed=m.changed) for m in result.members]
    ids = ",".join(m.asset for m in members)
    return Outcome(NewData(asset=ids, path="assets/npc", created=result.created, crowd=members), result.findings)


@command(
    "new",
    summary="Create a new Asset from its Kind's Recipe. For an npc, --count N --seed S makes a crowd, and --reroll picks one "
            "NPC again.",
    input=NewInput,
    output=NewData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("kind", "name")),
    locks=LockNeeds(assets=_new_locks),
    files=("from_parameters",),
)
def new(arguments: NewInput, context: Context) -> Outcome[NewData]:
    project = find_project(context.cwd)
    if arguments.bulk:
        return _new_bulk(arguments, project)
    params = {name: value for name, value in (("view", arguments.view), ("base", arguments.base), ("body", arguments.body),
                                       ("use", arguments.use), ("sound_id", arguments.sound_id)) if value is not None}
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
    clips: list[ClipRow] | None = Field(
        None, description="With `describe project`: the Project's clip table (null for a Kind).")
    clips_example: str | None = Field(None, description="With `describe project`: how to fill the clip table.")
    masks: list[MaskRow] | None = Field(
        None, description="With `describe room`: the Project's Masks, each view's in file order, with colour and meaning "
                          "(null for other targets, and outside a Project).")
    masks_example: str | None = Field(None, description="With `describe room`: how to add a named Mask.")

    def text(self) -> str:
        lines = []
        if self.masks is not None:
            lines.append(f"masks (add one: {self.masks_example}):")
            for mask in self.masks:
                what = "derived, never painted" if mask.derived else f"painted {mask.colour}"
                role = "; blocks movement in Kiripix" if mask.blocks else ""
                lines.append(f"  {mask.view} {mask.name}: {what}{role}{f' - {mask.meaning}' if mask.meaning else ''}")
        if self.clips is not None:
            lines.append(f"clip table ({len(self.clips)} rows; e.g. {self.clips_example}):")
            for clip in self.clips:
                lines.append(f"  {clip.name}: {clip.frames} frames at {clip.fps} fps, {'loops' if clip.loop else 'plays once'}"
                             f"{', with foot frames' if clip.foot else ''}")
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
            character = find_project(context.cwd).settings.character
            ramps = character.ramps
        except KiripixError:
            return Outcome(DescribeData(kinds=kinds, ramps_example=RAMPS_EXAMPLE, clips_example=CLIPS_EXAMPLE))
        table = [ramp_row(r) for r in ramps]
        clip_table = [ClipRow.from_spec(c) for c in character.clips]
        return Outcome(DescribeData(kinds=kinds, ramps=table, ramps_example=RAMPS_EXAMPLE, clips=clip_table,
                                    clips_example=CLIPS_EXAMPLE))
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
        if kind.name == "room":  # the Project's Masks, so a session finds the named ones (ticket 0344)
            try:
                rows = mask_rows(find_project(context.cwd).settings)
            except KiripixError:  # outside a Project: the Recipe alone
                return Outcome(DescribeData(kinds=kinds, masks_example=MASKS_EXAMPLE))
            return Outcome(DescribeData(kinds=kinds, masks=rows, masks_example=MASKS_EXAMPLE))
    return Outcome(DescribeData(kinds=kinds))


# status


class StatusInput(_Input):
    kind: str | None = Field(None, description="Show only the Assets of this Kind.")
    match: str | None = Field(None, description="Show only the Assets whose IDs match this glob, such as room.ch01_dungeon_*.")
    assets: list[str] | None = Field(
        None, description="Show only these Assets, by ID (the rows a list shows); none given is every Asset. An ID that "
                          "isn't an Asset is a finding. Repeat `--asset` on the command line.")
    refresh: str | None = Field(None, description=REFRESH_HELP)
    forget: list[str] | None = Field(None, description=FORGET_HELP)


class AssetStatus(BaseModel):
    asset: str
    kind: str
    stages: list[StageState]
    export_command: str | None = Field(
        None, description="While every Stage is done and the game doesn't have what is built: the Command that exports it.")
    waits_on: dict[str, str] = Field(default_factory=dict, exclude=True)  # human output only: Stage -> first open one it reads


def _stage_line(asset: AssetStatus, stage: StageState, first_open: str | None) -> str:
    """One Stage of `status`'s human output, written so that agent work reads as work, not as a question (0233)."""
    reason = stage.reason
    hint = ""
    if stage.stage == first_open and stage.status == "todo":  # its inputs are all there
        hint = f" (ready: kiripix run {asset.asset})"
    elif stage.status == "needs-input" and reason in (RUNNER_NOT_RUN, RUNNER_INPUT_CHANGED):  # only its Runner calls
        hint = f" (run: kiripix run {asset.asset} {stage.stage} --rerun)"
    elif stage.stage in asset.waits_on and stage.status in ("needs-input", "needs-review", "failed"):
        first = asset.waits_on[stage.stage]  # what it says may be about a build from before `first` changed
        reason = f"waits on {first}; may change once {first} is done: {reason}" if reason else f"waits on {first}"
    return f"    {stage.stage:<10} {stage.status}{hint}{f'  ({reason})' if reason else ''}"


class StatusData(BaseModel):
    project: str
    assets: list[AssetStatus]

    def text(self) -> str:
        if not self.assets:
            return f"{self.project}: no Assets yet"
        lines = [self.project]
        for asset in self.assets:
            lines.append(f"  {asset.asset}")
            first_open = next((s.stage for s in asset.stages if s.status != "done"), None)
            lines.extend(_stage_line(asset, stage, first_open) for stage in asset.stages)
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
    cli=CliMeta(options={"assets": ("--asset",), "forget": ("--forget",)}),
)
def status(arguments: StatusInput, context: Context) -> Outcome[StatusData]:
    project = find_project(context.cwd)
    if arguments.kind is not None:
        get_kind(arguments.kind)
    assets, findings = project_assets(project, context, arguments.refresh, arguments.forget)
    if arguments.match is not None:
        assets = select(assets, arguments.match)
    assets, findings = named_assets(assets, findings, arguments.assets)
    cache = HashCache(project.state_dir)
    memory = context.memory
    stamp = export_stamp(project) if memory is not None else ""  # the game's files: asked once for every Asset of this call
    rows: list[AssetStatus] = []
    for asset in assets:
        if arguments.kind is not None and asset.kind != arguments.kind:
            continue
        state = recall_state(project, asset, cache, memory)
        if state.errors:
            findings.extend(state.errors)
            continue
        built = all(s.status == "done" for s in state.states)
        if not built:
            pending = None
        elif memory is None:
            pending = export_command(project, asset, cache, state.states)
        else:
            pending = memory.recall("export", asset, partial(export_command, project, asset, cache, state.states),
                                    stamp=lambda _: stamp)
        rows.append(AssetStatus(asset=asset.id, kind=asset.kind, stages=state.states, waits_on=state.waits_on,
                                export_command=pending))
    cache.save()
    return Outcome(
        StatusData(project=project.settings.project.name, assets=rows),
        findings,
        ExitCode.ERROR if findings else ExitCode.OK,
    )


class AssetsInput(_Input):
    kind: str | None = Field(None, description="List only the Assets of this Kind.")
    match: str | None = Field(None, description="List only the Assets whose IDs match this glob, such as room.ch01_dungeon_*.")
    refresh: str | None = Field(None, description=REFRESH_HELP)


class AssetRow(BaseModel):
    asset: str
    kind: str
    name: str
    base: str | None = Field(None, description="The Asset it is made from (its `base` parameter), as written.")
    body: str | None = Field(None, description="The Asset it is worn on (a Wearable's `body` parameter), as written.")
    reference: bool = Field(False, description="Whether it is one of the Project's style references (`[style] references`).")


class AssetsData(BaseModel):
    project: str
    assets: list[AssetRow]

    def text(self) -> str:
        if not self.assets:
            return f"{self.project}: no Assets yet"
        return "\n".join([self.project, *(f"  {a.asset}{'  *' if a.reference else ''}" for a in self.assets)])


@command(
    "assets",
    summary="List the Assets from their asset.toml files alone: ID, Kind, name, base, body and whether it is a style "
            "reference. No hashes and no Stage status, so it answers at once; `status` has the status.",
    input=AssetsInput,
    output=AssetsData,
    kind="probe",
    mcp="exposed",
)
def assets_list(arguments: AssetsInput, context: Context) -> Outcome[AssetsData]:
    project = find_project(context.cwd)
    if arguments.kind is not None:
        get_kind(arguments.kind)
    assets, findings = project_assets(project, context, arguments.refresh)
    if arguments.match is not None:
        assets = select(assets, arguments.match)
    references = set(project.settings.style.references)
    rows = []
    for asset in assets:
        if arguments.kind is not None and asset.kind != arguments.kind:
            continue
        base, body = asset.settings.params.get(BASE_PARAM), asset.settings.params.get(BODY_PARAM)
        rows.append(AssetRow(asset=asset.id, kind=asset.kind, name=asset.name,
                             base=base if isinstance(base, str) else None, body=body if isinstance(body, str) else None,
                             reference=asset.id in references))
    return Outcome(AssetsData(project=project.settings.project.name, assets=rows), findings,
                   ExitCode.ERROR if findings else ExitCode.OK)


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
        data.command, data.owner_action = what_next(graph, spec, state)
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
    match: str | None = Field(None, description="Run the Assets whose IDs match this glob, such as room.ch01_dungeon_*; "
                                                "alone it means --all --match. A base of a matched Asset is built first, "
                                                "matched or not.")
    kind: str | None = Field(None, description="With --all: only the Assets of this Kind.")
    force: bool = Field(False, description="Re-run even Stages that are done.")
    from_stage: str | None = Field(None, description="With --force: re-run this Stage and every Stage after it "
                                   "in the recipe. Plain --force alone leaves the Stages after a forced one on its old output.")
    rerun: bool = Field(False, description="Also make the Runner calls with no pinned result; they land in needs-review.")
    cpu: bool = Field(False, description="Run Runners on the CPU, without the GPU lock.")

    @model_validator(mode="after")
    def _asset_or_all(self) -> Self:
        scoped = self.all or self.match is not None
        if scoped == (self.asset is not None):
            raise ValueError("give an Asset ID or --all/--match, not both")
        if scoped and self.stage is not None:
            raise ValueError("a Stage can't be given with --all or --match")
        if self.from_stage is not None and (scoped or self.stage is not None or not self.force):
            raise ValueError("--from works with --force and an Asset ID, without a Stage")
        if self.kind is not None and not scoped:
            raise ValueError("--kind works only with --all or --match")
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
    cli=CliMeta(positional=("asset", "stage"), options={"from_stage": ("--from",)}),
    locks=LockNeeds(asset=lambda a: a.asset if is_asset_id(a.asset) else None),
)
def run(arguments: RunInput, context: Context) -> Outcome[RunData]:
    project = find_project(context.cwd)
    cache = HashCache(project.state_dir)
    if arguments.all or arguments.match is not None:
        if arguments.kind is not None:
            get_kind(arguments.kind)
        result = run_all(project, cache, match=arguments.match, kind=arguments.kind, force=arguments.force, progress=context.progress,
                         wait=context.wait, command_line=context.command_line, rerun=arguments.rerun, cpu=arguments.cpu,
                         keep_warm=context.via == "rest")
    else:
        assert arguments.asset is not None
        asset = load_asset(project, arguments.asset)
        result = run_asset(project, asset, cache, stage=arguments.stage, force=arguments.force,
                           progress=context.progress, wait=context.wait, command_line=context.command_line,
                           rerun=arguments.rerun, cpu=arguments.cpu, keep_warm=context.via == "rest",
                           from_stage=arguments.from_stage)
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
