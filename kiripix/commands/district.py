"""district, a Probe: a district's rooms, their Exits and what waits on them (ticket 0328). Records nothing; it only fills
the thumbnail cache in `.kiripix/previews/`."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kiripix.checks import Finding
from kiripix.commands.contract import Context, ExitCode, Outcome
from kiripix.commands.registry import CliMeta, command
from kiripix.core import atomic
from kiripix.core import cliptable as _cliptable  # noqa: F401 - registers its Project check (commands load lazily, 0277)
from kiripix.core import ramps as _ramps  # noqa: F401 - registers `palette.parts_differ`
from kiripix.core.assets import Asset, list_assets
from kiripix.core.errors import KiripixError
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.match import select
from kiripix.core.project import Project, find_project
from kiripix.core.queue import build_queue
from kiripix.export import exit_pairings
from kiripix.export.checks import Pairing
from kiripix.recipes.room_prompt import parse_exits

THUMBNAIL_STAGES = ("export", "palette", "fit", "source")
ROOM_KIND = "room"


class DistrictCounts(BaseModel):
    review: int
    input: int
    finding: int
    agent_fixable: int = Field(description="Findings an agent can fix: not stops, counted here as `queue` counts them.")


class DistrictStage(BaseModel):
    stage: str
    status: str
    reason: str | None = None


class DistrictRoom(BaseModel):
    asset: str
    width: int = Field(description="The brief's width in px.")
    height: int = Field(description="The brief's height in px.")
    tiles_wide: int = Field(description="The width in whole tiles (rounded down).")
    tiles_high: int
    built: DistrictStage | None = Field(description="The furthest Stage with a build, with its status; null when none.")
    waiting: DistrictStage | None = Field(description="The first Stage that isn't done, with its status; null when all are.")
    queue: DistrictCounts
    thumbnail: str | None = Field(description="The 1x image, relative to the Project; null when the room has none.")
    thumbnail_stage: str | None = Field(description="The Stage the thumbnail shows: export, palette, fit or source.")
    thumbnail_reason: str | None = Field(None, description="Why there is no thumbnail.")


class DistrictExit(BaseModel):
    room: str
    exit: str
    side: str | None = Field(description="The room brief's side for this Exit (top, right, bottom, left); null when the "
                                         "brief names none.")
    target_room: str
    target_exit: str
    pairing: Pairing = Field(description="paired: the target Exit points back. one_way: the Exit is marked `one_way` (no return "
                                     "is meant) and its target exists. unpaired: the rule `exit.not_paired` (and `exit.no_exit`, "
                                     "`exit.no_room`) gives, with `code` and `reason`. outside: the target room isn't in "
                                     "the district; `code` and `reason` are set when the Project's check of it fails.")
    code: str | None = Field(None, description="The finding's code when the Exit isn't sound.")
    reason: str | None = Field(None, description="Why, in words.")


class DistrictLink(BaseModel):
    room: str
    id: str
    kind: str
    two_way: bool
    start: list[int] = Field(description="The Link's `from` end, [x, y] in target px.")
    end: list[int] = Field(description="The Link's `to` end, [x, y] in target px; a one-way Link is crossed from start to end.")


class DistrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    glob: str = Field(description="The district: the Asset IDs this glob matches, such as room.ch01_dungeon_*. Only rooms "
                                  "are shown.")


class DistrictData(BaseModel):
    rooms: list[DistrictRoom] = Field(description="The district's rooms in ID order.")
    exits: list[DistrictExit] = Field(description="Every Exit of every room, in room then Exit ID order.")
    links: list[DistrictLink] = Field(description="The rooms' traversal Links, as `place` holds them.")

    def text(self) -> str:
        lines = []
        for room in self.rooms:
            at = f"waits at {room.waiting.stage} ({room.waiting.status})" if room.waiting else "all done"
            q = room.queue
            lines.append(f"{room.asset}  {room.tiles_wide}x{room.tiles_high} tiles  {at}  review {q.review} input "
                         f"{q.input} finding {q.finding} fixable {q.agent_fixable}  "
                         f"{room.thumbnail or 'no thumbnail'}")
        for x in self.exits:
            lines.append(f"{x.room} {x.exit} -> {x.target_room} {x.target_exit}: {x.pairing}")
        return "\n".join(lines)


def _stage(graph: AssetGraph, name: str) -> DistrictStage:
    state = graph.state(name)
    return DistrictStage(stage=name, status=state.status, reason=state.reason)


def _thumbnail(project: Project, graph: AssetGraph) -> tuple[str | None, str | None, str | None]:
    """The latest built image of export, palette, fit or the Source, copied at 1x to `.kiripix/previews/` under its input
    hash (a second call finds it there and writes nothing). Returns (path, stage, why not)."""
    asset = graph.asset.id
    for name in THUMBNAIL_STAGES:
        spec = graph.spec(name)
        built = graph.built_hash(spec)
        if spec.image is None or built is None:
            continue
        source = graph.output_dir(spec) / spec.image
        if not source.is_file():
            continue
        folder = project.state_dir / "previews"
        target = folder / f"{asset}.thumb.{name}.{built[:16]}.png"
        if not target.is_file():
            atomic.write_bytes(target, source.read_bytes())
            for old in folder.glob(f"{asset}.thumb.*.png"):
                if old != target:
                    old.unlink(missing_ok=True)
        return project.relative(target), name, None
    return None, None, "no Source built yet, so no image to show"


def _sides(graph: AssetGraph) -> dict[str, str]:
    brief = graph.params(graph.spec("brief"))
    try:
        return {e["name"]: e["side"] for e in parse_exits(str(brief.get("exits", "")), graph.asset.id) if e["side"]}
    except KiripixError:
        return {}


def _room(project: Project, asset: Asset, cache: HashCache, queue: Any) -> tuple[DistrictRoom, dict[str, str]]:
    graph = AssetGraph(project, asset, cache)
    states = graph.states()
    built = next((s for s in reversed(states) if graph.built_hash(graph.spec(s.stage)) is not None), None)
    waiting = next((s for s in states if s.status != "done"), None)
    brief = graph.params(graph.spec("brief"))
    width, height = int(str(brief["width"])), int(str(brief["height"]))
    tile = project.settings.project.tile
    counts, fixable = queue.by_asset(asset.id)
    path, shown, why = _thumbnail(project, graph)
    return DistrictRoom(
        asset=asset.id, width=width, height=height, tiles_wide=width // tile, tiles_high=height // tile,
        built=_stage(graph, built.stage) if built else None, waiting=_stage(graph, waiting.stage) if waiting else None,
        queue=DistrictCounts(**counts, agent_fixable=fixable), thumbnail=path, thumbnail_stage=shown, thumbnail_reason=why,
    ), _sides(graph)


@command(
    "district",
    summary="A district's rooms in ID order, each with its size, furthest built and waiting Stage, queue counts and a 1x "
            "thumbnail; every Exit with its pairing (paired, one_way, unpaired, outside); and the rooms' Links. A Probe: "
            "records nothing.",
    input=DistrictInput,
    output=DistrictData,
    kind="probe",
    mcp="exposed",
    cli=CliMeta(positional=("glob",)),
)
def district(arguments: DistrictInput, context: Context) -> Outcome[DistrictData]:
    project = find_project(context.cwd)
    every, findings = list_assets(project)
    matched = select(every, arguments.glob)
    rooms = [a for a in matched if a.kind == ROOM_KIND]
    for other in matched:
        if other.kind != ROOM_KIND:
            findings.append(Finding(code="district.not_a_room", severity="info",
                                    message=f"{other.id} is a {other.kind}, not a room, so the district leaves it out",
                                    fix="kiripix status --kind room"))
    cache = HashCache(project.state_dir)
    queue = build_queue(project, rooms, cache, every)
    findings.extend(queue.errors)
    shown: list[DistrictRoom] = []
    sides: dict[str, dict[str, str]] = {}
    for asset in rooms:
        try:
            room, sides[asset.id] = _room(project, asset, cache, queue)
        except KiripixError as error:
            findings.extend(error.findings)
            continue
        shown.append(room)
    cache.save()
    pairings, links = exit_pairings(project, every, {r.asset for r in shown})
    exits = [DistrictExit(room=p.room, exit=p.exit, side=sides.get(p.room, {}).get(p.exit), target_room=p.target_room,
                          target_exit=p.target_exit, pairing=p.pairing, code=p.code,
                          reason=p.reason if p.pairing != "paired" else None)
             for p in pairings]
    linked = [DistrictLink(room=room, id=str(m["id"]), kind=str(m["kind"]), two_way=bool(m.get("two_way", True)),
                           start=[int(v) for v in m["from"]], end=[int(v) for v in m["to"]])
              for room, markers in links.items() for m in markers]
    errors = [f for f in findings if f.severity != "info"]
    return Outcome(DistrictData(rooms=shown, exits=exits, links=linked), findings,
                   ExitCode.ERROR if errors else ExitCode.OK)
