"""Probes (spec §10.1): read-only questions about an Asset. They record nothing, are never pinned, and take no Asset lock.
One that loads a Runner takes the GPU lock, as anything loading a Runner does.

`kiripix probe <name> <id> <args...>` runs one. Over REST the server keeps whatever makes a Probe fast (a warm Runner,
a cached embedding); in the CLI a Probe works too, only slower. A Probe is registered with `@probe(name)`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, command
from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset, list_assets, load_asset
from kiripix.core.match import select
from kiripix.core.previews import NPC_FILE, npc_figure
from kiripix.core import snapshots
from kiripix.core.cast import Figure, NothingToDraw, cast_sheet, read_colours
from kiripix.core.errors import ExitCode, fail
from kiripix.core.file_inspect import inspect_file
from kiripix.core.layer_stats import layer_stats, piece_numbers
from kiripix.core.look_probe import look_difference
from kiripix.core.mask_cells import half_cells
from kiripix.core.project import Project, find_project
from kiripix.core.reach_probe import reach_report
from kiripix.core.style import probe_style
from kiripix.core.graph import AssetGraph, ProgressEvent
from kiripix.core.hashing import HashCache
from kiripix.core.segmenting import click_preview, flood_preview, segment_preview
from kiripix.ops import mask_runs
from kiripix.recipes.base import BoxCorners, ClickPoint, Scalar

class ProbeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="The Probe's name, such as segment-preview or echo.")
    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")
    args: list[str] = Field([], description="The Probe's own arguments. segment-preview takes clicks in target pixels: "
                                            "x,y for a positive one and x,y,neg for a negative one, as does click-preview; or one box, x0,y0,x1,y1, "
                                            "the pixels from (x0, y0) to (x1, y1) both included. flood-preview takes "
                                            "x,y,tolerance, one or more. look-difference takes a Look, x0,y0,x1,y1, then an optional tolerance and specks count. layer-stats, reach and style take none. inspect takes one file name; half-cells one Mask's name.")
    cpu: bool = Field(False, description="Run any Runner on the CPU, without the GPU lock.")
    summary: bool = Field(False, description="Leave `runs` out of a Mask answer; `pixels` and `box` stay.")


ProbeFunction = Callable[[Asset, ProbeInput, Context], dict[str, Any]]


@dataclass(frozen=True)
class Probe:
    name: str
    summary: str
    run: ProbeFunction


PROBES: dict[str, Probe] = {}


def probe(name: str, *, summary: str) -> Callable[[ProbeFunction], ProbeFunction]:
    def register(function: ProbeFunction) -> ProbeFunction:
        if name in PROBES:
            raise ValueError(f"Probe {name} registered twice")
        PROBES[name] = Probe(name, summary, function)
        return function

    return register


@probe("echo", summary="Answer with the Asset's Kind and the arguments given: proves the Probe path.")
def _echo(asset: Asset, arguments: ProbeInput, context: Context) -> dict[str, Any]:
    return {"kind": asset.kind, "args": arguments.args}


def _click_point(text: str, asset: Asset, probe_name: str = "segment-preview") -> ClickPoint:
    parts = text.split(",")
    sign = parts[2] if len(parts) == 3 else ""
    if len(parts) not in (2, 3) or sign not in ("", "neg") or not (parts[0].isdecimal() and parts[1].isdecimal()):
        raise fail("input.invalid", f"'{text}' isn't a click: give x,y for a positive one, or x,y,neg for a negative one",
                   fix=f"kiripix probe {probe_name} {asset.id} 10,12")
    return int(parts[0]), int(parts[1]), sign != "neg"


def _box(text: str, asset: Asset) -> BoxCorners:
    parts = text.split(",")
    if len(parts) != 4 or not all(part.isdecimal() for part in parts):
        raise fail("input.invalid", f"'{text}' isn't a box: give x0,y0,x1,y1 in target pixels, such as 10,12,40,30",
                   fix=f"kiripix probe segment-preview {asset.id} 10,12,40,30")
    x0, y0, x1, y1 = (int(part) for part in parts)
    return x0, y0, x1, y1


@probe("segment-preview", summary="The Mask a click, or a rough box x0,y0,x1,y1, would make, as runs of [y, x, length], on "
                                  "the target grid. Several clicks are one prompt, unlike a lift (one call per click): use "
                                  "click-preview for that.")
def _segment_preview(asset: Asset, arguments: ProbeInput, context: Context) -> dict[str, Any]:
    if not arguments.args:
        raise fail("input.invalid", "segment-preview needs at least one click, or a box",
                   fix=f"kiripix probe segment-preview {asset.id} 10,12")
    boxed = arguments.args[0].count(",") == 3
    if boxed and len(arguments.args) > 1:
        raise fail("input.invalid", "segment-preview takes one box, and no clicks with it",
                   fix=f"kiripix probe segment-preview {asset.id} {arguments.args[0]}")
    box = _box(arguments.args[0], asset) if boxed else None
    points = [] if boxed else [_click_point(text, asset) for text in arguments.args]
    made = segment_preview(find_project(context.cwd), asset, points, keep_warm=context.via == "rest", cpu=arguments.cpu,
                           wait=context.wait, command_line=context.command_line, progress=context.progress, box=box)
    return {
        **_mask_answer(made.mask, arguments),
        "embedding": "computed" if made.computed else "cached",
        "device": made.device,
    }


@probe("click-preview", summary="What a lift of these clicks would make: each click's Mask and their union, replayed "
                                "in order, as a Layer or a Mask would be.")
def _click_preview(asset: Asset, arguments: ProbeInput, context: Context) -> dict[str, Any]:
    if not arguments.args:
        raise fail("input.invalid", "click-preview needs at least one click",
                   fix=f"kiripix probe click-preview {asset.id} 10,12")
    points = [_click_point(text, asset, "click-preview") for text in arguments.args]
    made = click_preview(find_project(context.cwd), asset, points, keep_warm=context.via == "rest", cpu=arguments.cpu,
                         wait=context.wait, command_line=context.command_line, progress=context.progress)
    union = _mask_answer(made.union, arguments)
    union["pieces"] = piece_numbers(made.union)
    return {
        "clicks": [{"x": x, "y": y, "positive": positive, **_mask_answer(mask, arguments)}
                   for (x, y, positive), mask in zip(points, made.masks)],
        "union": union,
        "embedding": "computed" if made.computed else "cached",
        "device": made.device,
    }


def _mask_answer(mask: np.ndarray, arguments: ProbeInput) -> dict[str, Any]:
    """The answer for one Mask: its size, `pixels`, the bounding box (null when empty) and, unless `--summary`, `runs`."""
    runs = mask_runs(mask)
    box = None
    if runs:
        left = min(x for _, x, _ in runs)
        top = min(y for y, _, _ in runs)
        box = {"x": left, "y": top, "width": max(x + n for _, x, n in runs) - left,
               "height": max(y for y, _, _ in runs) - top + 1}
    answer: dict[str, Any] = {"width": mask.shape[1], "height": mask.shape[0], "pixels": int(mask.sum()), "box": box}
    if not arguments.summary:
        answer["runs"] = runs
    return answer


def _flood_point(text: str, asset: Asset) -> tuple[int, int, float]:
    parts = text.split(",")
    try:
        if len(parts) != 3 or not (parts[0].isdecimal() and parts[1].isdecimal()):
            raise ValueError
        tolerance = float(parts[2])
    except ValueError:
        raise fail("input.invalid", f"'{text}' isn't a flood: give x,y,tolerance, such as 30,10,0.04",
                   fix=f"kiripix probe flood-preview {asset.id} 30,10,0.04") from None
    return int(parts[0]), int(parts[1]), tolerance


@probe("flood-preview", summary="The region a flood would fill on the built Plate, one answer per x,y,tolerance given.")
def _flood_preview(asset: Asset, arguments: ProbeInput, context: Context) -> dict[str, Any]:
    if not arguments.args:
        raise fail("input.invalid", "flood-preview needs at least one x,y,tolerance",
                   fix=f"kiripix probe flood-preview {asset.id} 30,10,0.04")
    floods = [_flood_point(text, asset) for text in arguments.args]
    regions = flood_preview(find_project(context.cwd), asset, floods)
    return {"floods": [{"x": x, "y": y, "tolerance": tolerance, **_mask_answer(region, arguments)}
                       for (x, y, tolerance), region in zip(floods, regions)]}


@probe("look-difference", summary="The region a `difference` Decision on a Look would add: args are the Look, x0,y0,x1,y1, "
                                  "then an optional tolerance and an optional specks count (the Decision's defaults). "
                                  "Measured as the `looks` Stage measures it, on the picked edit; records nothing.")
def _look_difference(asset: Asset, arguments: ProbeInput, context: Context) -> dict[str, Any]:
    usage = f"kiripix probe look-difference {asset.id} <look> 10,12,40,30"
    if not 2 <= len(arguments.args) <= 4:
        raise fail("input.invalid", "look-difference takes a Look, a box x0,y0,x1,y1, and optionally a tolerance and a "
                                    "specks count", fix=usage)
    look, text, *rest = arguments.args
    try:
        tolerance = float(rest[0]) if rest else None
        specks = int(rest[1]) if len(rest) > 1 else None
        if (tolerance is not None and tolerance < 0) or (specks is not None and specks < 0):
            raise ValueError
    except ValueError:
        raise fail("input.invalid", f"'{' '.join(rest)}' isn't a tolerance and a specks count: a number, then a whole "
                                    "number, neither negative", fix=usage) from None
    region = look_difference(find_project(context.cwd), asset, look, _box(text, asset), tolerance, specks)
    return _mask_answer(region, arguments)


@probe("layer-stats", summary="Each Layer's pixels, box, pieces, holes, partial pixels, sort and a suggested y-sort line.")
def _layer_stats(asset: Asset, arguments: ProbeInput, context: Context) -> dict[str, Any]:
    if arguments.args:
        raise fail("input.invalid", "layer-stats takes no arguments", fix=f"kiripix probe layer-stats {asset.id}")
    return layer_stats(find_project(context.cwd), asset)


@probe("reach", summary="What the reach Stage would report from the Masks as built (one awaiting review too) and the Markers "
                        "placed now: which Spawns and Exits the Body reaches, the islands and the narrowest gaps.")
def _reach(asset: Asset, arguments: ProbeInput, context: Context) -> dict[str, Any]:
    if arguments.args:
        raise fail("input.invalid", "reach takes no arguments", fix=f"kiripix probe reach {asset.id}")
    return reach_report(find_project(context.cwd), asset)


@probe("style", summary="The Asset's style measures (outline density, pixel scale), each style reference's, the range of the "
                        "references and the findings `check` would give, as numbers: the UI's style scores.")
def _style(asset: Asset, arguments: ProbeInput, context: Context) -> dict[str, Any]:
    if arguments.args:
        raise fail("input.invalid", "style takes no arguments", fix=f"kiripix probe style {asset.id}")
    project = find_project(context.cwd)
    return probe_style(project, asset, HashCache(project.state_dir))


@probe("half-cells", summary="The cells of the room's areas with a `cell` that one Mask, as built, half covers (a quarter to "
                             "three quarters), each by its top-left pixel: the band of `area.ambiguous_cells`, for any "
                             "painted Mask. Takes the Mask's name.")
def _half_cells(asset: Asset, arguments: ProbeInput, context: Context) -> dict[str, Any]:
    if len(arguments.args) != 1:
        raise fail("input.invalid", "half-cells takes one Mask's name", fix=f"kiripix probe half-cells {asset.id} solid")
    return half_cells(find_project(context.cwd), asset, arguments.args[0])


@probe("inspect", summary="What a character's file holds: its armature, bone names, frame rate and actions with their frame "
                          "ranges. The file is a Model Variant, a clip source or `rigged`, by the name `show` gives it. "
                          "Runs Blender once per file; the answer is cached.")
def _inspect(asset: Asset, arguments: ProbeInput, context: Context) -> dict[str, Any]:
    if len(arguments.args) != 1:
        raise fail("input.invalid", "inspect takes one file, by the name `show` gives it",
                   fix=f"kiripix show {asset.id}")

    def progress(done: int, total: int, message: str) -> None:
        context.progress(ProgressEvent(event="probe_progress", stage=None, done=done, total=total, message=message))

    return inspect_file(find_project(context.cwd), asset, arguments.args[0], progress=progress,
                        check_cancel=context.cancel.check)


class ProbeData(BaseModel):
    probe: str
    asset: str
    result: dict[str, Any]

    def text(self) -> str:
        return f"{self.probe} {self.asset}: {self.result}"


@command(
    "probe",
    summary="Run a Probe: a read-only question about an Asset, such as segment-preview. Records nothing.",
    input=ProbeInput,
    output=ProbeData,
    kind="probe",
    mcp="hidden",
    cli=CliMeta(positional=("name", "asset", "args")),
)
def run_probe(arguments: ProbeInput, context: Context) -> Outcome[ProbeData]:
    chosen = PROBES.get(arguments.name)
    if chosen is None:
        raise fail("probe.unknown", f"no Probe '{arguments.name}'; the Probes are {', '.join(sorted(PROBES))}",
                   fix="kiripix probe echo <asset>")
    asset = load_asset(find_project(context.cwd), arguments.asset)
    return Outcome(ProbeData(probe=chosen.name, asset=asset.id, result=chosen.run(asset, arguments, context)))


class CastSheetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assets: str | None = Field(None, description="The figures, comma-separated, left to right: characters or sprites, each with a "
                                    "built `sheet` Stage, such as character.hero,character.elder. A figure may be a "
                                    "stack, a body and the Wearables made for it, joined by +: "
                                    "character.hero+wearable.hair+wearable.coat. An npc is a figure too, drawn from its built "
                                    "`choose`. Give this or --match.")
    match: str | None = Field(None, description="Instead of a list: the characters, sprites and NPCs whose IDs match this glob, "
                                                "such as npc.guards_*, in ID order: a crowd on one sheet (ticket 0359). An NPC "
                                                "without a built `choose` is left out, with a finding.")
    clips: str | None = Field(None, description="The clips to draw, comma-separated; each Asset's first clip when left "
                                                "out.")
    directions: str = Field("s", description="The directions to draw, comma-separated, such as s,sw.")
    frames: int = Field(1, ge=1, le=64, description="Frames per clip and direction, spread evenly from the first.")
    scale: int = Field(1, ge=1, le=8, description="Whole-number zoom, nearest neighbour; 1 is the game's size. The "
                                                  "labels aren't scaled.")
    stack: Literal["order", "depth"] = Field("order", description="How a stack's Wearables go over the body: by their "
                                             "`order` (default), or by the depth pass.")
    colours: Path | None = Field(None, description="A TOML or JSON file that swaps Parts' ramps, one entry per figure in "
                                                  "order, each {part = [[r, g, b], ...]}, dark to light, as long as the "
                                                  "Part's ramp; TOML as [[figure]] tables. The game's rule: a pixel in the "
                                                  "Part's ramp takes the colour at the same place.")
    snapshots: str | None = Field(None, description="Snapshot labels, comma-separated (`kiripix snapshot`): one row per "
                                                    "label, the same Assets in the same order, each row titled with its "
                                                    "label and the parameters that differ between rows. The Assets' "
                                                    "sheets as built now are not read.")


class CastCellData(BaseModel):
    asset: str
    clip: str
    direction: str
    index: int = Field(description="The frame's index in its clip.")
    x: int = Field(description="The cell's left edge in the PNG.")
    y: int = Field(description="The cell's top edge in the PNG.")
    width: int
    height: int
    pivot: dict[str, int] = Field(description="The pivot (the feet) in the cell, from its top left, in PNG pixels.")
    row: str | None = Field(None, description="With --snapshots: the label of the cell's row.")
    swapped: list[str] = Field(default_factory=list, description="With --colours: the Parts whose ramps were swapped.")


class CastRowData(BaseModel):
    label: str
    title: str = Field(description="What the row is titled with: its label and the differing parameters' values in it.")
    y: int = Field(description="The row's top edge in the PNG.")
    height: int
    ground: int = Field(description="The y of this row's ground line in the PNG.")


class DifferingParamData(BaseModel):
    stage: str
    param: str
    values: dict[str, dict[str, Scalar]] = Field(description="By label, then by Asset: the parameter's value in the "
                                                             "snapshot.")


class CastSheetData(BaseModel):
    path: str = Field(description="The PNG, relative to the Project.")
    width: int
    height: int
    scale: int
    ground: int = Field(description="The y of the ground line in the PNG: every cell's pivot is on it. With "
                                    "--snapshots, the first row's; see `rows`.")
    cells: list[CastCellData]
    rows: list[CastRowData] = Field(default_factory=list, description="With --snapshots: one per label that has cells.")
    differing: list[DifferingParamData] = Field(default_factory=list, description="With --snapshots: the parameters "
                                                "that differ between the labels (or are in only some of them).")

    def text(self) -> str:
        return self.path


def _listed(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def _matched_figures(project: Project, glob: str) -> tuple[list[Figure], list[Finding]]:
    """The figures `cast-sheet --match` draws: each matched character, sprite or NPC, in ID order. An NPC is its base with its
    Wearables stacked and its colours swapped, from its built `choose`; one that isn't built is left out with a finding."""
    assets, _ = list_assets(project)
    found = [a for a in select(assets, glob) if a.kind in ("character", "sprite", "npc")]
    if not found:
        raise fail("match.none", f"no character, sprite or npc matches '{glob}'", fix="kiripix status")
    figures: list[Figure] = []
    findings: list[Finding] = []
    cache = HashCache(project.state_dir)
    for asset in found:
        if asset.kind != "npc":
            figures.append(Figure((asset,)))
            continue
        graph = AssetGraph(project, asset, cache)
        path = graph.output_dir(graph.spec("choose")) / NPC_FILE
        if graph.built_hash(graph.spec("choose")) is None:
            findings.append(Finding(code="cast.npc_not_built", severity="warning", message=f"{asset.id} has no built choose, so it is left out",
                                    position=Position(asset=asset.id, stage="choose"), fix=f"kiripix run {asset.id} choose"))
            continue
        figures.append(npc_figure(project, asset, path))
    return figures, findings


@command(
    "cast-sheet",
    summary="Draw several characters side by side, each at its pivot on one ground line, from their built sheets, to "
            ".kiripix/previews/. A figure may be a body with Wearables stacked on it (a+b), and --colours swaps Parts' "
            "ramps. A Probe: records nothing.",
    input=CastSheetInput,
    output=CastSheetData,
    kind="probe",
    mcp="exposed",
    cli=CliMeta(positional=("assets",)),
)
def run_cast_sheet(arguments: CastSheetInput, context: Context) -> Outcome[CastSheetData]:
    project = find_project(context.cwd)
    if (arguments.assets is None) == (arguments.match is None):
        raise fail("input.invalid", "give the figures or --match, one of them", fix="kiripix cast-sheet character.a,character.b")
    shown = arguments.assets if arguments.assets is not None else arguments.match
    pre: list[Finding] = []
    if arguments.match is not None:
        figures, pre = _matched_figures(project, arguments.match)
        if arguments.colours is not None:
            entries = read_colours(context.cwd / arguments.colours, str(arguments.colours), len(figures))
            figures = [replace(f, colours=entries[n]) if n < len(entries) else f for n, f in enumerate(figures)]
    else:
        assert arguments.assets is not None
        ids = _listed(arguments.assets)
        if not ids:
            raise fail("input.invalid", "name at least one Asset", fix="kiripix cast-sheet character.a,character.b")
        stacks = [[part.strip() for part in item.split("+")] for item in dict.fromkeys(ids)]
        if any(not all(part) for part in stacks):
            raise fail("input.invalid", "a stack names a body and Wearables joined by +, such as character.a+wearable.b",
                       fix="kiripix cast-sheet character.a+wearable.b")
        entries = read_colours(context.cwd / arguments.colours, str(arguments.colours), len(stacks)) if arguments.colours is not None else []
        figures = []
        for number, stack in enumerate(stacks):
            assets = tuple(load_asset(project, asset_id) for asset_id in dict.fromkeys(stack))
            colours = entries[number] if number < len(entries) else {}
            if len(assets) == 1 and assets[0].kind == "npc":  # an NPC is drawn from its built `choose`
                graph = AssetGraph(project, assets[0], HashCache(project.state_dir))
                figure = npc_figure(project, assets[0], graph.output_dir(graph.spec("choose")) / NPC_FILE)
                figures.append(replace(figure, colours={**figure.colours, **colours}))
            else:
                figures.append(Figure(assets, colours))
    clips = _listed(arguments.clips) if arguments.clips is not None else None
    directions = _listed(arguments.directions)
    if arguments.snapshots is not None and not _listed(arguments.snapshots):
        raise fail("input.invalid", "--snapshots names at least one label", fix="kiripix snapshot --list")
    if clips == [] or not directions:
        raise fail("input.invalid", "--clips and --directions each name at least one",
                   fix=f"kiripix cast-sheet {shown} --clips idle --directions s")
    if not figures:
        return Outcome(None, [*pre, Finding(code="cast.empty", message="no figure has a built choose to draw; the findings before "
                                                                       "this say why", fix="kiripix status")], ExitCode.ERROR)
    try:
        made = cast_sheet(project, figures, clips, directions, arguments.frames, arguments.scale,
                          _listed(arguments.snapshots) if arguments.snapshots is not None else None, arguments.stack)
    except NothingToDraw as empty:
        finding = Finding(code="cast.empty", message="no Asset has a cell to draw; the findings before this say why",
                          fix="kiripix status")
        return Outcome(None, [*pre, *empty.findings, finding], ExitCode.ERROR)
    cells = [CastCellData(asset=c.asset, clip=c.clip, direction=c.direction, index=c.index, x=c.x, y=c.y,
                          width=c.width, height=c.height, pivot={"x": c.pivot[0], "y": c.pivot[1]}, row=c.row,
                          swapped=list(c.swapped))
             for c in made.cells]
    rows = [CastRowData(label=r.label, title=r.title, y=r.y, height=r.height, ground=r.ground) for r in made.rows]
    differing = [DifferingParamData(stage=d.stage, param=d.param, values=d.values) for d in made.differing]
    return Outcome(CastSheetData(path=project.relative(made.path), width=made.width, height=made.height,
                                 scale=made.scale, ground=made.ground, cells=cells, rows=rows,
                                 differing=differing), [*pre, *made.findings])


class SnapshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assets: str | None = Field(None, description="The Assets to snapshot, comma-separated: characters or sprites with "
                                                 "a built `sheet` Stage, such as character.hero,character.elder.")
    label: str | None = Field(None, description="The snapshot's name, snake_case, such as outline.")
    replace: bool = Field(False, description="Replace the Assets' snapshots under a label that already exists; the "
                                             "label's other Assets are kept.")
    list_: bool = Field(False, description="List the labels and the Assets under each.")
    drop: str | None = Field(None, description="Delete this label and every snapshot under it.")


class SnapshotAssetData(BaseModel):
    asset: str
    path: str = Field(description="The folder holding the copy, relative to the Project.")
    params: dict[str, dict[str, Scalar]] = Field(description="The parameters of every Stage the sheet was built from, "
                                                             "by Stage.")
    stale: list[str] = Field(description="The Stages among those that were not current when it was taken.")


class SnapshotLabelData(BaseModel):
    label: str
    assets: list[str]


class SnapshotData(BaseModel):
    label: str | None = None
    snapshots: list[SnapshotAssetData] = Field(default_factory=list, description="What this call kept.")
    labels: list[SnapshotLabelData] | None = Field(None, description="With --list: every label.")
    dropped: SnapshotLabelData | None = Field(None, description="With --drop: the label that was deleted.")

    def text(self) -> str:
        if self.labels is not None:
            return "\n".join(f"{entry.label}: {', '.join(entry.assets)}" for entry in self.labels) or "no snapshots"
        if self.dropped is not None:
            return f"dropped {self.dropped.label}"
        return "\n".join(f"{s.asset}: {s.path}" for s in self.snapshots)


@command(
    "snapshot",
    summary="Keep the built `sheet` of characters or sprites under a label, in .kiripix/snapshots/, with the parameters "
            "of the Stages it was built from, so `cast-sheet --snapshots` can compare settings across a cast. Also "
            "--list and --drop. A Probe: records nothing in the Project.",
    input=SnapshotInput,
    output=SnapshotData,
    kind="probe",
    mcp="exposed",
    cli=CliMeta(positional=("assets",), options={"list_": ("--list",)}),
)
def run_snapshot(arguments: SnapshotInput, context: Context) -> Outcome[SnapshotData]:
    project = find_project(context.cwd)
    modes = [arguments.assets is not None, arguments.list_, arguments.drop is not None]
    if sum(modes) != 1:
        raise fail("input.invalid", "give the Assets to snapshot (with --label), or --list, or --drop <label>: one of them",
                   fix="kiripix snapshot --help")
    if arguments.list_:
        return Outcome(SnapshotData(labels=[SnapshotLabelData(label=e.label, assets=e.assets)
                                            for e in snapshots.labels(project)]))
    if arguments.drop is not None:
        held = snapshots.drop(project, arguments.drop)
        return Outcome(SnapshotData(dropped=SnapshotLabelData(label=arguments.drop, assets=held)))
    assert arguments.assets is not None
    if arguments.label is None:
        raise fail("input.invalid", "--label names the snapshot, in snake_case", fix="kiripix snapshot --help")
    ids = _listed(arguments.assets)
    if not ids:
        raise fail("input.invalid", "name at least one Asset", fix="kiripix snapshot character.a,character.b --label x")
    assets = [load_asset(project, asset_id) for asset_id in dict.fromkeys(ids)]
    notes, findings = snapshots.take(project, assets, arguments.label, arguments.replace)
    kept = [SnapshotAssetData(asset=n.asset, path=project.relative(snapshots.snapshots_dir(project) / n.label / n.asset),
                              params=n.params, stale=n.stale) for n in notes]
    return Outcome(SnapshotData(label=arguments.label, snapshots=kept), findings)
