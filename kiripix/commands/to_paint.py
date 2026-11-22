"""to-paint, a Probe: every prompt and canvas a district's rooms need, in one folder (ticket 0349). Records nothing in the
Project; it writes only the folder it is given (`.kiripix/to-paint/<date>/` by default).

The Owner paints in the image model's own UI from this folder, and `index.md` names the file each image comes back as, which
`inbox` (ticket 0350) files by name. The names are in `kiripix.core.paint`.
"""

import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from kiripix.checks import Finding
from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, command
from kiripix.core import atomic, cancel, extend, paint, sources
from kiripix.core.assets import Asset, list_assets
from kiripix.core.errors import ExitCode, KiripixError
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import png_bytes
from kiripix.core.match import select
from kiripix.core.project import Project, find_project
from kiripix.recipes.room_prompt import PROMPT_FILE

ROOM_KIND = "room"
PAINT_FOLDER = "to-paint"


class ToPaintInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match: str = Field(description="The district: the Asset IDs this glob matches, such as room.ch01_dungeon_*. Only rooms "
                                   "waiting for their Source are written.")
    out: str | None = Field(None, description="The folder to write, relative to the working directory; "
                                              ".kiripix/to-paint/<date>/ in the Project by default.")


class PaintRoom(BaseModel):
    asset: str
    number: int = Field(description="Its place in the order to paint, from 1.")
    what: str = Field(description="prompt: a room with no Source, paint its prompt. canvas: a room mid-`extend`, paint the "
                                   "canvas, with the prompt beside it. done: its joined image is as big as the brief wants.")
    files: list[str] = Field(description="The files written for it, relative to the folder.")
    sides: list[str] = Field(default_factory=list, description="With canvas: the side the next piece extends.")
    return_name: str | None = Field(description="What to name the image that comes back; null when nothing is to be painted.")
    next: str | None = Field(None, description="With done: the command that makes the joined image a Variant.")


class Unready(BaseModel):
    asset: str
    code: str = Field(description="to_paint.no_brief: its brief isn't built (or is out of date). to_paint.no_prompt: the "
                                  "brief is built but the Project has no room template, so it has no prompt.")
    reason: str
    fix: str | None = None


class ToPaintData(BaseModel):
    folder: str = Field(description="The folder written, relative to the Project when it lies inside it.")
    index: str | None = Field(description="The index file, relative to the Project; null when there was nothing to write.")
    rooms: list[PaintRoom] = Field(description="The rooms to paint, in the order to paint.")
    unready: list[Unready] = Field(description="The rooms the folder can't help yet: no brief, or no prompt.")

    def text(self) -> str:
        lines = [f"{r.number:02d} {r.asset}: {r.what}, comes back as {r.return_name or '-'}" for r in self.rooms]
        lines += [f"{u.asset}: {u.reason}" for u in self.unready]
        return "\n".join(lines + [f"wrote {self.folder}"])


def _folder(project: Project, context: Context, out: str | None) -> Path:
    if out is not None:
        path = Path(out)
        return path if path.is_absolute() else context.cwd / path
    return project.state_dir / PAINT_FOLDER / datetime.date.today().isoformat()


def _brief_size(graph: AssetGraph) -> tuple[int, int]:
    """What the Source must reach, in its own px: the brief's size, times the fit's scale when the Owner has set one."""
    brief, fit = graph.params(graph.spec("brief")), graph.params(graph.spec("fit"))
    scale = int(str(fit.get("scale", 0))) if fit.get("mode") == "grid" else 0
    scale = max(scale, 1)
    return int(str(brief["width"])) * scale, int(str(brief["height"])) * scale


def _prompt(graph: AssetGraph) -> tuple[bytes | None, Unready | None]:
    """The brief's built prompt, or why there is none. Never rendered here: the brief renders it (ticket 0348)."""
    asset = graph.asset.id
    state = graph.state("brief")
    if state.status != "done":
        why = {"stale": "its brief is out of date", "failed": "its brief failed"}.get(state.status, "it has no brief built")
        return None, Unready(asset=asset, code="to_paint.no_brief", reason=why, fix=f"kiripix run {asset} brief")
    path = graph.output_dir(graph.spec("brief")) / PROMPT_FILE
    if not path.is_file():
        return None, Unready(asset=asset, code="to_paint.no_prompt",
                             reason="its brief has no prompt: the Project has no style/prompts/room.<ext>")
    return path.read_bytes(), None


def _unready_finding(unready: Unready) -> Finding:
    if unready.fix is not None:
        return Finding(code=unready.code, severity="info", message=f"{unready.asset}: {unready.reason}", fix=unready.fix)
    return Finding(code=unready.code, severity="info", message=f"{unready.asset}: {unready.reason}",
                   owner_action="Add style/prompts/room.<ext> (a Jinja2 template), then "
                                f"kiripix run {unready.asset} brief.")


def _plan(project: Project, asset: Asset, cache: HashCache) -> tuple[AssetGraph, list[extend.ExtendEntry] | None]:
    """The room's graph, and its live `extend` pieces when it has a Source worth waiting on; None when it needs nothing
    painted (its Source is picked, and no `extend` is in progress)."""
    graph = AssetGraph(project, asset, cache)
    live = extend.live_pieces(extend.read_journal(asset))
    if not live and sources.picked(graph) in sources.variants(asset):
        return graph, None
    return graph, live


def _index(glob: str, rooms: list[PaintRoom], unready: list[Unready]) -> str:
    lines = [f"# To paint: {glob}", ""]
    if rooms:
        lines += ["In the order to paint. Name each image that comes back as shown; `kiripix inbox` files it by that name.", ""]
    for room in rooms:
        if room.what == "done":
            lines.append(f"{room.number}. {room.asset}: nothing to paint; its joined image is big enough: `{room.next}`")
            continue
        made = [f"`{name}`" for name in room.files]
        lines.append(f"{room.number}. {room.asset}: paint from {' and '.join(made)}; name the image that comes back "
                     f"`{room.return_name}`")
    if not rooms:
        lines.append("No room is waiting on its Source.")
    for code, title in (("to_paint.no_brief", "No brief yet"), ("to_paint.no_prompt", "No prompt")):
        group = [u for u in unready if u.code == code]
        if group:
            lines += ["", f"## {title}", ""]
            lines += [f"- {u.asset}: {u.reason}" + (f"; `{u.fix}`" if u.fix else "; add style/prompts/room.<ext>")
                      for u in group]
    return "\n".join(lines) + "\n"


@command(
    "to-paint",
    summary="Write, into one folder, what a district's rooms need painted: for each room waiting on its Source its prompt "
            "(`<nn>-<room>.prompt.txt`), and for one mid-`extend` its next canvas (`<nn>-<room>.<side>.png`) with the "
            "prompt, plus `index.md` naming the file each image comes back as (`<room>.png`, `<room>.<side>.png`) for "
            "`inbox`. Rooms with no brief are listed with the command to write one. Records nothing in the Project.",
    input=ToPaintInput,
    output=ToPaintData,
    kind="probe",
    mcp="exposed",
    cli=CliMeta(),
)
def to_paint(arguments: ToPaintInput, context: Context) -> Outcome[ToPaintData]:
    project = find_project(context.cwd)
    every, findings = list_assets(project)
    matched = select(every, arguments.match)
    folder = _folder(project, context, arguments.out)
    cache = HashCache(project.state_dir)
    rooms: list[PaintRoom] = []
    unready: list[Unready] = []
    writes: dict[str, bytes] = {}
    exit_code = ExitCode.OK  # a room that can't be read is an error; the others are still packed
    for asset in matched:
        cancel.check()
        if asset.kind != ROOM_KIND:
            findings.append(Finding(code="to_paint.not_a_room", severity="info",
                                    message=f"{asset.id} is a {asset.kind}, not a room, so to-paint leaves it out",
                                    fix="kiripix status --kind room"))
            continue
        try:
            graph, live = _plan(project, asset, cache)
            if live is None:
                continue
            prompt, missing = _prompt(graph)
            if prompt is None:
                assert missing is not None
                unready.append(missing)
                findings.append(_unready_finding(missing))
                continue
            number = len(rooms) + 1
            files = [paint.prompt_name(number, asset)]
            writes[files[0]] = prompt
            if not live:
                rooms.append(PaintRoom(asset=asset.id, number=number, what="prompt", files=files,
                                       return_name=paint.return_name(asset)))
                continue
            _, rgba, _ = extend.current_image(project, asset)
            side = extend.next_side(rgba.shape[1], rgba.shape[0], _brief_size(graph))
            if side is None:
                rooms.append(PaintRoom(asset=asset.id, number=number, what="done", files=[], return_name=None,
                                       next=f"kiripix extend {asset.id} done"))
                del writes[files[0]]
                continue
            sides = [side]
            example = f"kiripix extend {asset.id} canvas"
            image = extend.plan_canvas(project, asset, sides, project.settings.extend.canvas, None, 0, example).image
            files.append(paint.canvas_name(number, asset, sides))
            writes[files[1]] = png_bytes(image)
            rooms.append(PaintRoom(asset=asset.id, number=number, what="canvas", files=files, sides=sides,
                                   return_name=paint.return_name(asset, sides)))
        except KiripixError as error:
            findings.extend(error.findings)
            exit_code = max(exit_code, error.exit_code)
    cache.save()
    if not rooms and not unready:
        shown = project.relative(folder)
        return Outcome(ToPaintData(folder=shown, index=None, rooms=[], unready=[]), findings, exit_code)
    for name, data in writes.items():
        cancel.check()
        atomic.write_bytes(folder / name, data)
    atomic.write_text(folder / paint.INDEX, _index(arguments.match, rooms, unready))
    shown = project.relative(folder)
    return Outcome(ToPaintData(folder=shown, index=project.relative(folder / paint.INDEX), rooms=rooms, unready=unready),
                   findings, exit_code)
