"""queue, a Probe: everything on the Project that waits on the Owner (ticket 0325)."""

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, ExitCode, Outcome
from kiripix.commands.listing import REFRESH_HELP, named_assets, project_assets
from kiripix.commands.registry import CliMeta, command
from kiripix.core import cliptable as _cliptable  # noqa: F401 - registers its Project check (commands load lazily, 0277)
from kiripix.core import ramps as _ramps  # noqa: F401 - registers `palette.parts_differ`
from kiripix.core.hashing import HashCache
from kiripix.core.kinds import get_kind
from kiripix.core.match import select
from kiripix.core.project import find_project
from kiripix.core.queue import AssetFixable, QueueStop, build_queue
from kiripix.export import pairing_findings as _pairing  # noqa: F401 - importing the Exporter registers `exit.not_paired`


class QueueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match: str | None = Field(None, description="Only the Assets whose IDs match this glob, such as room.ch01_dungeon_*. "
                                                "The Project checks report only findings that name a matched Asset.")
    kind: str | None = Field(None, description="Only the Assets of this Kind.")
    assets: list[str] | None = Field(
        None, description="Only these Assets, by ID (the rows a list shows); none given is every Asset. An ID that isn't "
                          "an Asset is a finding. The Project checks report only findings that name one of them. Repeat "
                          "`--asset` on the command line.")
    refresh: str | None = Field(None, description=REFRESH_HELP)


class QueueCounts(BaseModel):
    review: int
    input: int
    finding: int
    total: int
    agent_fixable: int = Field(description="Findings an agent can fix: not stops, counted here and per Asset.")
    assets_clear: list[str] = Field(description="The Assets with nothing waiting and nothing agent-fixable.")


class QueueData(BaseModel):
    stops: list[QueueStop] = Field(description="Each stop the Owner owns, in Asset ID order, then Stage order.")
    agent_fixable: list[AssetFixable] = Field(description="Per Asset, the findings with a `fix` and their commands.")
    counts: QueueCounts

    def text(self) -> str:
        if not self.stops and not self.agent_fixable:
            return "nothing waits on the Owner"
        lines: list[str] = []
        for stop in self.stops:
            where = f"{stop.asset} {stop.stage}" if stop.stage else stop.asset
            what = stop.reason or stop.owner_action or ""
            lines.append(f"{stop.type:<8} {where}: {what}")
            if stop.owner_action and stop.owner_action != what:
                lines.append(f"           {stop.owner_action}")
            lines.extend(f"           note: {n.text}" for n in stop.notes)
        for asset in self.agent_fixable:
            lines.append(f"agent    {asset.asset}: {asset.count} finding(s) an agent can fix")
        c = self.counts
        lines.append(f"{c.total} stop(s): {c.review} review, {c.input} input, {c.finding} finding; "
                     f"{c.agent_fixable} agent-fixable; {len(c.assets_clear)} Asset(s) clear")
        return "\n".join(lines)


@command(
    "queue",
    summary="Everything waiting on the Owner across the Assets: reviews, owner-only inputs and findings, with hand-over notes.",
    input=QueueInput,
    output=QueueData,
    kind="probe",
    mcp="exposed",
    cli=CliMeta(options={"assets": ("--asset",)}),
)
def queue(arguments: QueueInput, context: Context) -> Outcome[QueueData]:
    project = find_project(context.cwd)
    if arguments.kind is not None:
        get_kind(arguments.kind)
    every, findings = project_assets(project, context, arguments.refresh)
    assets = every if arguments.match is None else select(every, arguments.match)
    if arguments.kind is not None:
        assets = [a for a in assets if a.kind == arguments.kind]
    assets, findings = named_assets(assets, findings, arguments.assets)
    cache = HashCache(project.state_dir)
    found = build_queue(project, assets, cache, every, context.memory)
    cache.save()
    findings.extend(found.errors)
    data = QueueData(stops=found.stops, agent_fixable=found.agent_fixable,
                     counts=QueueCounts(**found.counts(), assets_clear=found.clear))
    return Outcome(data, findings, ExitCode.OK)  # a listing isn't a failure: an unreadable Asset is a finding, not exit 1
