"""`track` and `stats` (ticket 0182): the Owner's measured active time per Asset and Stage."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kiripix.checks import Finding
from kiripix.commands.contract import Context, ExitCode, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import timespans
from kiripix.core.assets import is_asset_id, list_assets, load_asset
from kiripix.core.errors import KiripixError
from kiripix.core.project import find_project


class TrackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")
    stage: str = Field(description="A Stage of the Asset's Kind, or `extend`.")
    seconds: int = Field(description=f"Active seconds, {timespans.MIN_SPAN} to {timespans.MAX_SPAN}.")


class TrackData(BaseModel):
    asset: str
    stage: str
    seconds: int
    source: str = Field(description="`ui` over the UI's session token, `cli` at an interactive terminal.")
    id: str = Field(description="The span's ULID: when it ended.")

    def text(self) -> str:
        return f"{self.asset} {self.stage}: logged {self.seconds} s ({self.source})"


def _asset_lock(arguments: TrackInput) -> str | None:
    return arguments.asset if is_asset_id(arguments.asset) else None


@command(
    "track",
    summary="Log a span of the Owner's active time on an Asset's Stage (the UI sends these; Owner only, so an agent "
            "can't log time). Appends one line to the Asset's time.jsonl.",
    input=TrackInput,
    output=TrackData,
    kind="owner-only",
    mcp="owner-only",
    cli=CliMeta(positional=("asset", "stage")),
    locks=LockNeeds(asset=_asset_lock),
)
def track(arguments: TrackInput, context: Context) -> Outcome[TrackData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    timespans.check_span(asset, arguments.stage, arguments.seconds)
    span = timespans.append_span(asset, arguments.stage, arguments.seconds, "ui" if context.via == "rest" else "cli")
    findings = []
    if not timespans.has_merge_attribute(project):
        findings.append(Finding(
            code="time.merge_attribute_missing",
            message=f"the Project's .gitattributes has no '{timespans.TIME_FILE} merge=union text eol=lf' line, so two "
                    "branches that both log time conflict when merged",
            severity="warning",
            owner_action=f"Add the line '{timespans.TIME_FILE} merge=union text eol=lf' to .gitattributes."))
    return Outcome(TrackData(asset=asset.id, stage=span.stage, seconds=span.seconds, source=span.source, id=span.id),
                   findings)


class StatsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str | None = Field(None, description="The Asset ID. Omit with --all.")
    all: bool = Field(False, description="Every Asset.")
    since: str | None = Field(None, description="Only what happened on or after this date, such as 2026-11-12 (local "
                                                "time), by the ULID's time.")

    @model_validator(mode="after")
    def _asset_or_all(self) -> Self:
        if self.all == (self.asset is not None):
            raise ValueError("give an Asset ID or --all, not both")
        return self


class StageStats(BaseModel):
    stage: str
    ui_minutes: float
    cli_minutes: float
    minutes: float = Field(description="The UI's and the CLI's minutes together.")
    decisions: int
    undos: int
    redos: int


class AssetStats(BaseModel):
    asset: str
    stages: list[StageStats]
    total: StageStats


class StatsData(BaseModel):
    assets: list[AssetStats]
    total: StageStats
    since: str | None = None

    def text(self) -> str:
        lines = []
        for asset in self.assets:
            lines.append(asset.asset)
            lines += [_line(stage, 2) for stage in asset.stages]
            if len(asset.stages) > 1:
                lines.append(_line(asset.total, 2))
        if len(self.assets) != 1:
            lines.append(_line(self.total, 0))
        return "\n".join(lines)


def _line(stats: StageStats, indent: int) -> str:
    return (f"{' ' * indent}{stats.stage:<12} {stats.minutes:>7.1f} min (ui {stats.ui_minutes:.1f}, cli "
            f"{stats.cli_minutes:.1f}), {stats.decisions} Decisions, {stats.undos} undos, {stats.redos} redos")


def _stats(stage: str, time: timespans.StageTime) -> StageStats:
    return StageStats(stage=stage, ui_minutes=round(time.ui / 60, 2), cli_minutes=round(time.cli / 60, 2),
                      minutes=round((time.ui + time.cli) / 60, 2), decisions=time.decisions, undos=time.undos,
                      redos=time.redos)


@command(
    "stats",
    summary="The Owner's measured active minutes per Asset and Stage (UI and CLI apart, and together), with the "
            "Decisions, undos and redos from the Decision journals. An `accept`'s re-recorded entries aren't new "
            "Decisions. The journal doesn't say who decided, so the Decisions include an agent's; the minutes are "
            "the Owner's only.",
    input=StatsInput,
    output=StatsData,
    kind="probe",
    mcp="exposed",
    cli=CliMeta(positional=("asset",)),
)
def stats(arguments: StatsInput, context: Context) -> Outcome[StatsData]:
    project = find_project(context.cwd)
    since = timespans.parse_since(arguments.since) if arguments.since else None
    findings: list[Finding] = []
    if arguments.all:
        assets, findings = list_assets(project)
    else:
        assert arguments.asset is not None
        assets = [load_asset(project, arguments.asset)]
    grand = timespans.StageTime()
    out = []
    for asset in assets:
        try:
            time = timespans.asset_time(asset, since)
        except KiripixError as error:
            findings.extend(error.findings)
            continue
        total = time.total()
        grand.add(total)
        out.append(AssetStats(asset=asset.id, stages=[_stats(name, t) for name, t in time.stages.items()],
                              total=_stats("total", total)))
    return Outcome(StatsData(assets=out, total=_stats("total", grand), since=arguments.since), findings,
                   ExitCode.ERROR if findings else ExitCode.OK)
