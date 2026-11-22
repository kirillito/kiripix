"""The cast sheet (spec §10, ticket 0226): several characters side by side, at the game's size or a whole-number zoom.

Each Asset's built `sheet` Stage gives its frames (`sheet.json` and the colour atlas). Every cell is drawn with its pivot
(the feet) on one shared ground line, the Assets left to right in the order given, each labelled with its ID above it.
Written to `.kiripix/previews/`, a cache that deleting loses nothing from. Nothing is recorded and no lock is taken.

A figure may be a stack (ticket 0337): a body and its Wearables, `character.a+wearable.b`, drawn over the body by their `order`
or by depth, with the Op of ticket 0294; and `colours` swap Parts' ramps, as the game does (`swap_ramps`).

An Asset whose Kind has no `sheet` Stage is refused whole. One whose sheet isn't built is a finding and left out; one whose
sheet is out of date is drawn, with a warning. A clip or direction the sheet doesn't have is a finding too.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset, body_of
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import load_gray16, load_palette, load_rgba, save_png
from kiripix.core.project import Project
from kiripix.core import snapshots
from kiripix.ops import stack_by_depth, stack_by_order, swap_ramps
from kiripix.ops.resample import upscale
from kiripix.recipes.base import Scalar
from kiripix.recipes.wearable_sheet import DEFAULT_ORDER
from kiripix.recipes.character_palette import PALETTE_FILE
from kiripix.recipes.character_sheet import SHEET_FILE, SHEET_SCHEMA_VERSION, restore_cell

SHEET_STAGE = "sheet"
PALETTE_STAGE = "palette"
Rgb = tuple[int, int, int]
StackBy = Literal["order", "depth"]
CELL_GAP = 2  # target px between the cells of one Asset
ASSET_GAP = 10  # target px between Assets
LABEL_HEIGHT = 14  # PNG px above the figures, for the labels; not scaled
BACKGROUND = (43, 43, 48, 255)
LABEL_COLOUR = (220, 220, 220, 255)


@dataclass(frozen=True)
class CastCell:
    asset: str
    clip: str
    direction: str
    index: int
    x: int  # the cell's top left in the PNG
    y: int
    width: int
    height: int
    pivot: tuple[int, int]  # in the cell, from its top left, in PNG px
    row: str | None = None  # with `--snapshots`: the label of the cell's row
    swapped: tuple[str, ...] = ()  # the Parts whose ramps `colours` swapped in this figure


@dataclass(frozen=True)
class CastRow:
    """One snapshot's row of a sheet with `--snapshots`: its label and title, and its band of the PNG."""

    label: str
    title: str
    y: int
    height: int
    ground: int


@dataclass(frozen=True)
class DifferingParam:
    """A parameter whose value is not the same in every snapshot: its value in each label, for each Asset."""

    stage: str
    param: str
    values: dict[str, dict[str, Scalar]]


@dataclass(frozen=True)
class Figure:
    """One figure of the sheet: a body, alone or with Wearables over it (in the order given), and the ramps to swap on it,
    by Part, dark to light (ticket 0337)."""

    assets: tuple[Asset, ...]
    colours: dict[str, list[Rgb]] = field(default_factory=dict)
    orders: dict[str, int] = field(default_factory=dict)  # a Wearable's stacking order here, instead of its sheet's (ticket 0356)
    title: str = ""  # what the figure is called, when it isn't its Assets: an NPC's ID (ticket 0359)

    @property
    def name(self) -> str:
        return self.title or "+".join(a.id for a in self.assets)


@dataclass(frozen=True)
class CastSheet:
    path: Path
    width: int
    height: int
    scale: int
    ground: int  # the y of the ground line in the PNG
    cells: tuple[CastCell, ...]
    findings: tuple[Finding, ...]
    rows: tuple[CastRow, ...] = ()
    differing: tuple[DifferingParam, ...] = ()


class NothingToDraw(Exception):
    def __init__(self, findings: list[Finding]) -> None:
        super().__init__("nothing to draw")
        self.findings = findings


@dataclass(frozen=True)
class _Frame:
    asset: str
    clip: str
    direction: str
    index: int
    image: np.ndarray
    pivot: tuple[int, int]
    first: bool  # the Asset's first frame, which starts its label
    depth: np.ndarray | None = None  # the frame's 16 bit depth pass in its cell, when the sheet has one
    label: str = ""  # what the label above the figure says; the Asset's ID when empty
    swapped: tuple[str, ...] = ()  # the Parts whose ramps `colours` swapped


def _picked(count: int, frames: int) -> list[int]:
    """`frames` positions spread evenly over a clip of `count` frames, from the first; all of them when it has fewer."""
    if frames >= count:
        return list(range(count))
    return sorted({i * count // frames for i in range(frames)})


Sheet = tuple[dict[str, Any], "np.ndarray", "np.ndarray | None"]  # sheet.json, the colour atlas, the depth atlas when wanted


def _depth_atlas(folder: Path, document: dict[str, Any], asset: Asset) -> np.ndarray | None:
    name = document["files"].get("depth")
    if name is None or not (folder / name).is_file():
        return None
    return load_gray16(folder / name)


def _sheet(graph: AssetGraph, asset: Asset, findings: list[Finding], depth: bool = False) -> Sheet | None:
    """The Asset's sheet.json and colour atlas (and depth atlas when `depth`), or None (with a finding) when it isn't built."""
    spec = graph.spec(SHEET_STAGE)
    folder = graph.output_dir(spec)
    position = Position(asset=asset.id, stage=SHEET_STAGE)
    path = folder / SHEET_FILE
    document: dict[str, Any] | None = None
    if path.is_file():
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            document = None
    if document is None or document.get("schema_version") != SHEET_SCHEMA_VERSION:
        why = "has no built sheet" if document is None else "has a sheet from an older Kiripix"
        findings.append(Finding(code="cast.not_built", severity="warning", position=position,
                                message=f"{asset.id} {why}, so it is left out of the cast sheet",
                                fix=f"kiripix run {asset.id} {SHEET_STAGE}"))
        return None
    atlas = load_rgba(folder / document["files"]["color"], f"{asset.id}'s {SHEET_STAGE} atlas")
    status = graph.state(SHEET_STAGE).status
    if status != "done":
        findings.append(Finding(code="cast.sheet_stale", severity="warning", position=position,
                                message=f"{asset.id}'s sheet is {status}: it is drawn as last built",
                                fix=f"kiripix run {asset.id} {SHEET_STAGE}"))
    return document, atlas, _depth_atlas(folder, document, asset) if depth else None


def _frames(asset: Asset, document: dict[str, Any], atlas: np.ndarray, depth: np.ndarray | None, clips: list[str] | None, directions: list[str],
            frames: int, findings: list[Finding]) -> list[_Frame]:
    by_name = {clip["name"]: clip for clip in document["clips"]}
    wanted = clips if clips is not None else [document["clips"][0]["name"]] if document["clips"] else []
    made: list[_Frame] = []
    for name in wanted:
        clip = by_name.get(name)
        own = (clip or {}).get("pivot", document["pivot"])  # a clip's own pivot (ticket 0303), else the character's
        pivot = (int(own["x"]), int(own["y"]))
        for direction in directions:
            listed = clip["directions"].get(direction, []) if clip is not None else []
            if not listed:
                missing = f"has no clip '{name}'" if clip is None else f"has no frames of '{name}' facing '{direction}'"
                findings.append(Finding(code="cast.cell_missing", severity="warning",
                                        position=Position(asset=asset.id, stage=SHEET_STAGE, field=f"{name}/{direction}"),
                                        message=f"{asset.id}'s sheet {missing}; its clips are "
                                                f"{', '.join(by_name) or 'none'}",
                                        fix=f"kiripix show {asset.id}"))
                continue
            for position in _picked(len(listed), frames):
                frame = listed[position]
                cell = (clip or {}).get("cell", document["cell"])  # trimmed frames (ticket 0308) are put back in the clip's cell
                image = restore_cell(atlas, (int(cell["width"]), int(cell["height"])), frame)
                cut = None if depth is None else restore_cell(depth[..., None], (int(cell["width"]), int(cell["height"])), frame)[..., 0]
                made.append(_Frame(asset.id, name, direction, int(frame["index"]), image, pivot, not made, cut))
    return made


def _label_font() -> Any:
    from PIL import ImageFont

    return ImageFont.load_default()


def _compose(drawn: list[_Frame], scale: int, title: str | None) -> tuple[np.ndarray, int, list[CastCell]]:
    """One row: the Assets' cells with their pivots on one ground line, a strip of Asset labels above them and, when
    there is a `title`, a strip with it above that. Returns the picture, the ground line's y in it and the cells, whose
    positions are in the picture."""
    # Lay out in target px: the ground line is the lowest pivot's y, so the tallest figure above its feet fits.
    above = max(f.pivot[1] for f in drawn)
    below = max(f.image.shape[0] - f.pivot[1] for f in drawn)
    places: list[int] = []
    x = 0
    for previous, frame in zip([None, *drawn], drawn):
        if previous is not None:
            x += ASSET_GAP if frame.first else CELL_GAP
        places.append(x)
        x += frame.image.shape[1]
    canvas = np.zeros((above + below, x, 4), np.uint8)
    for frame, left in zip(drawn, places):
        top = above - frame.pivot[1]
        height, width = frame.image.shape[:2]
        canvas[top: top + height, left: left + width] = frame.image

    strip = LABEL_HEIGHT * (2 if title is not None else 1)
    figures = upscale(canvas, scale)
    image = np.empty((strip + figures.shape[0], figures.shape[1], 4), np.uint8)
    image[:] = BACKGROUND
    alpha = figures[..., 3:4].astype(np.float32) / 255
    under = image[strip:].astype(np.float32)
    image[strip:] = np.rint(figures.astype(np.float32) * alpha + under * (1 - alpha)).astype(np.uint8)
    image[strip:, :, 3] = 255
    texts = [(left * scale, strip - LABEL_HEIGHT, frame.label or frame.asset) for frame, left in zip(drawn, places) if frame.first]
    if title is not None:
        texts.append((0, 0, title))
    image = _labelled(image, texts)
    cells = [CastCell(f.asset, f.clip, f.direction, f.index, left * scale, strip + (above - f.pivot[1]) * scale,
                      f.image.shape[1] * scale, f.image.shape[0] * scale, (f.pivot[0] * scale, f.pivot[1] * scale),
                      swapped=f.swapped)
             for f, left in zip(drawn, places)]
    return image, strip + above * scale, cells


def _check_stack(project: Project, figure: Figure) -> None:
    """A stack is a body, then Wearables whose body it is (ticket 0337)."""
    body, *worn = figure.assets
    if body_of(project, body) is not None:
        raise fail("cast.stack_body", f"{body.id} is a Wearable: a stack starts with its body, then the Wearables over it",
                   fix="kiripix cast-sheet character.a+wearable.b", position=Position(asset=body.id))
    for wearable in worn:
        owner = body_of(project, wearable)
        if owner is None:
            raise fail("cast.stack_wearable", f"{wearable.id} is a {wearable.kind}, not a Wearable, so it can't be stacked on "
                       f"{body.id}", fix="kiripix cast-sheet character.a+wearable.b", position=Position(asset=wearable.id))
        if owner.id != body.id:
            raise fail("cast.wearable_body", f"{wearable.id} is made for {owner.id}, not for {body.id}, so it can't be "
                       f"stacked on it", fix=f"kiripix cast-sheet {owner.id}+{wearable.id}",
                       position=Position(asset=wearable.id))


def _ramps(project: Project, asset: Asset, cache: HashCache) -> dict[str, list[Rgb]]:
    """The Asset's Parts and their ramps (dark to light) as its built `palette` has them; empty when it has none."""
    graph = AssetGraph(project, asset, cache)
    if graph.kind.stage(PALETTE_STAGE) is None:
        return {}
    path = graph.output_dir(graph.spec(PALETTE_STAGE)) / PALETTE_FILE
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        return {str(p["name"]): [(int(c[0]), int(c[1]), int(c[2])) for c in p["rgb"]] for p in record.get("parts", [])}
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return {}


def _check_colours(project: Project, figures: list[Figure], cache: HashCache,
                   findings: list[Finding]) -> dict[str, dict[str, list[Rgb]]]:
    """The ramps of every Asset in a figure that has `colours`. `cast.colours_length` (an error) when a new ramp isn't as long as
    the Part's; `cast.part_missing` and `cast.colour_off_palette` are warnings. Returns the ramps by Asset ID."""
    ramps: dict[str, dict[str, list[Rgb]]] = {}
    palette: set[Rgb] | None = None
    for figure in figures:
        if not figure.colours:
            continue
        for asset in figure.assets:
            if asset.id not in ramps:
                ramps[asset.id] = _ramps(project, asset, cache)
        for part, colours in figure.colours.items():
            position = Position(asset=figure.assets[0].id, field=part)
            having = [a for a in figure.assets if part in ramps[a.id]]
            if not having:
                findings.append(Finding(code="cast.part_missing", severity="warning", position=position,
                                        message=f"{figure.name} has no Part '{part}' in its built palette, so its colours are "
                                                "not swapped", fix=f"kiripix show {figure.assets[0].id} palette"))
                continue
            for asset in having:
                if len(ramps[asset.id][part]) != len(colours):
                    raise fail("cast.colours_length", f"the ramp of '{part}' in {asset.id} has {len(ramps[asset.id][part])} "
                               f"colours, and the colours given for it have {len(colours)}",
                               fix=f"kiripix show {asset.id} palette", position=position)
            if palette is None:
                shown = project.settings.project.palette
                palette = {(int(r), int(g), int(b)) for r, g, b in load_palette(project.root / shown, shown).rgb()}
            off = [c for c in colours if c not in palette]
            if off:
                findings.append(Finding(code="cast.colour_off_palette", severity="warning", position=position,
                                        message=f"the colours for '{part}' of {figure.name} include {len(off)} off the Project "
                                                f"palette, such as {off[0]}", fix="kiripix palette"))
    return ramps


Loader = Callable[[Asset], Sheet | None]


def _figure_frames(figure: Figure, load: Loader, ramps: dict[str, dict[str, list[Rgb]]], clips: list[str] | None,
                   directions: list[str], frames: int, stack: StackBy, findings: list[Finding]) -> list[_Frame]:
    """The figure's frames: the body's, with each Wearable's frame of the same clip, direction and index stacked over it (by
    `order`, the Wearable's own `order` from its sheet, ties by ID; or by depth), each Asset's Parts swapped first."""
    layers: list[tuple[Asset, int, list[_Frame]]] = []
    for position, asset in enumerate(figure.assets):
        built = load(asset)
        if built is None:
            if position == 0:
                return []  # no body, no figure; a Wearable that isn't built is left out (the finding says so)
            continue
        document, atlas, depth = built
        own = _frames(asset, document, atlas, depth, clips, directions, frames, findings if position == 0 else [])
        swaps = [(ramps[asset.id][part], colours) for part, colours in figure.colours.items()
                 if part in ramps.get(asset.id, {})]
        if swaps:
            own = [replace(f, image=swap_ramps(f.image, swaps)) for f in own]
        layers.append((asset, 0 if position == 0 else figure.orders.get(asset.id, int(document.get("order", DEFAULT_ORDER))), own))
    swapped = tuple(part for part in figure.colours if any(part in ramps.get(a.id, {}) for a in figure.assets))
    body = layers[0][2]
    worn = sorted(layers[1:], key=lambda layer: (layer[1], layer[0].id))
    by_depth = stack == "depth" and all(f.depth is not None for _, _, fs in layers for f in fs)
    if stack == "depth" and not by_depth and worn:
        findings.append(Finding(code="cast.no_depth", severity="warning", position=Position(asset=figure.assets[0].id),
                                message=f"{figure.name} has a sheet without a depth atlas, so it is stacked by order",
                                fix=f"kiripix run {figure.assets[0].id} {SHEET_STAGE} --force"))
    label = figure.name + (" ~" + ",".join(swapped) if swapped else "")
    wrong: set[str] = set()
    made: list[_Frame] = []
    for frame in body:
        key = (frame.clip, frame.direction, frame.index)
        picked = [frame]
        for asset, _, fs in worn:
            found = next((f for f in fs if (f.clip, f.direction, f.index) == key), None)
            if found is None:
                continue
            if found.image.shape != frame.image.shape:
                if asset.id not in wrong:
                    wrong.add(asset.id)
                    findings.append(Finding(code="cast.wearable_cell", severity="warning",
                                            position=Position(asset=asset.id, stage=SHEET_STAGE),
                                            message=f"{asset.id}'s sheet has another cell than {figure.assets[0].id}'s, so it is "
                                                    "left out of the stack", fix=f"kiripix status {asset.id}"))
                continue
            picked.append(found)
        image = frame.image
        if len(picked) > 1:
            images = [f.image for f in picked]
            if by_depth:
                image = stack_by_depth(images, [f.depth for f in picked if f.depth is not None])
            else:
                image = stack_by_order(images)
        made.append(replace(frame, asset=figure.name, label=label, image=image, depth=None, swapped=swapped))
    return made


def cast_sheet(project: Project, figures: list[Figure], clips: list[str] | None, directions: list[str], frames: int,
               scale: int, labels: list[str] | None = None, stack: StackBy = "order") -> CastSheet:
    """Draw the cast sheet. Refuses an Asset with no `sheet` Stage, or a stack that isn't a body with its own Wearables; raises
    NothingToDraw, with the findings that say why, when no Asset has a cell to draw. With `labels`, one row per snapshot label
    (ticket 0248) instead of the Assets' sheets as built now."""
    cache = HashCache(project.state_dir)
    findings: list[Finding] = []
    for figure in figures:
        for asset in figure.assets:
            if AssetGraph(project, asset, cache).kind.stage(SHEET_STAGE) is None:
                raise fail("cast.not_a_figure", f"{asset.id} is a {asset.kind}, which has no {SHEET_STAGE} Stage to draw",
                           fix="kiripix cast-sheet character.a,character.b", position=Position(asset=asset.id))
        if len(figure.assets) > 1:
            _check_stack(project, figure)
            if labels is not None and stack == "depth":
                raise fail("cast.snapshot_depth", "a snapshot keeps no depth atlas, so a stack from snapshots is stacked by order",
                           fix=f"kiripix cast-sheet {figure.name} --snapshots {','.join(labels)} --stack order")
    ramps = _check_colours(project, figures, cache, findings)
    key = json.dumps([[f.name for f in figures], clips, directions, frames, labels, stack,
                      [sorted(f.colours.items()) for f in figures],
                      *([[sorted(f.orders.items()) for f in figures]] if any(f.orders for f in figures) else [])])
    name = f"cast.{hashlib.sha1(key.encode()).hexdigest()[:10]}.x{scale}.png"
    path = project.state_dir / "previews" / name

    if labels is None:
        drawn: list[_Frame] = []

        def live(asset: Asset) -> Sheet | None:
            return _sheet(AssetGraph(project, asset, cache), asset, findings, stack == "depth")

        for figure in figures:
            drawn += _figure_frames(figure, live, ramps, clips, directions, frames, stack, findings)
        if not drawn:
            raise NothingToDraw(findings)
        image, ground, cells = _compose(drawn, scale, None)
        save_png(path, image)
        return CastSheet(path, image.shape[1], image.shape[0], scale, ground, tuple(cells), tuple(findings))
    return _snapshot_rows(project, figures, ramps, clips, directions, frames, scale, labels, path, findings)


def _differing(notes: dict[str, dict[str, snapshots.SnapshotNote]]) -> list[DifferingParam]:
    """The parameters (of any Stage) whose value isn't the same in every label, for any Asset that is in them."""
    found: dict[tuple[str, str], dict[str, dict[str, Scalar]]] = {}
    for label, by_asset in notes.items():
        for asset, note in by_asset.items():
            for stage, params in note.params.items():
                for param, value in params.items():
                    found.setdefault((stage, param), {}).setdefault(label, {})[asset] = value
    differing = []
    for (stage, param), values in found.items():
        seen = {json.dumps(sorted(v.items())) for v in values.values()}
        if len(seen) > 1 or len(values) < len(notes):
            differing.append(DifferingParam(stage, param, values))
    return sorted(differing, key=lambda d: (d.stage, d.param))


def _title(label: str, differing: list[DifferingParam]) -> str:
    parts = []
    for d in differing:
        values = d.values.get(label)
        if values is None:
            continue
        shown = {str(v) for v in values.values()}
        parts.append(f"{d.stage}.{d.param}={shown.pop() if len(shown) == 1 else 'mixed'}")
    return label + (": " + " ".join(parts) if parts else "")


def _snapshot_rows(project: Project, figures: list[Figure], ramps: dict[str, dict[str, list[Rgb]]], clips: list[str] | None, directions: list[str], frames: int,
                   scale: int, labels: list[str], path: Path, findings: list[Finding]) -> CastSheet:
    notes: dict[str, dict[str, snapshots.SnapshotNote]] = {}
    rows: dict[str, list[_Frame]] = {}
    for label in dict.fromkeys(labels):
        snapshots.require(project, label)
        notes[label], rows[label] = {}, []

        def held_sheet(asset: Asset, label: str = label) -> Sheet | None:
            held = snapshots.read(project, label, asset.id)
            position = Position(asset=asset.id, stage=SHEET_STAGE)
            if held is None:
                findings.append(Finding(code="cast.not_snapshotted", severity="warning", position=position,
                                        message=f"the label '{label}' has no snapshot of {asset.id}, so it is left out "
                                                "of that row", fix=f"kiripix snapshot {asset.id} --label {label} --replace"))
                return None
            notes[label][asset.id] = held.note
            if held.note.stale:
                findings.append(Finding(code="cast.snapshot_stale", severity="warning", position=position,
                                        message=f"{asset.id}'s snapshot '{label}' was taken with "
                                                f"{', '.join(held.note.stale)} not current",
                                        fix=f"kiripix snapshot {asset.id} --label {label} --replace"))
            return held.document, held.atlas, None

        for figure in figures:
            rows[label] += _figure_frames(figure, held_sheet, ramps, clips, directions, frames, "order", findings)
    differing = _differing({label: by_asset for label, by_asset in notes.items() if by_asset})
    pictures = []
    for label, drawn in rows.items():
        if drawn:
            pictures.append((label, *_compose(drawn, scale, _title(label, differing))))
    if not pictures:
        raise NothingToDraw(findings)
    width = max(picture.shape[1] for _, picture, _, _ in pictures)
    height = sum(picture.shape[0] for _, picture, _, _ in pictures)
    image = np.empty((height, width, 4), np.uint8)
    image[:] = BACKGROUND
    placed: list[CastRow] = []
    cells: list[CastCell] = []
    top = 0
    for label, picture, ground, row_cells in pictures:
        image[top: top + picture.shape[0], : picture.shape[1]] = picture
        placed.append(CastRow(label, _title(label, differing), top, picture.shape[0], top + ground))
        cells += [replace(c, y=c.y + top, row=label) for c in row_cells]
        top += picture.shape[0]
    save_png(path, image)
    return CastSheet(path, width, height, scale, placed[0].ground, tuple(cells), tuple(findings), tuple(placed),
                     tuple(differing))


def _labelled(image: np.ndarray, labels: list[tuple[int, int, str]]) -> np.ndarray:
    from PIL import Image, ImageDraw

    picture = Image.fromarray(image, "RGBA")
    draw = ImageDraw.Draw(picture)
    font = _label_font()
    for left, top, text in labels:
        draw.text((left + 1, top + 1), text, fill=LABEL_COLOUR, font=font)
    return np.asarray(picture, dtype=np.uint8).copy()


def read_colours(path: Path, shown: str, figures: int) -> list[dict[str, list[Rgb]]]:
    """A `--colours` file (ticket 0337): TOML (`[[figure]]` tables) or JSON (a list, or `{"figure": [...]}`), one entry per figure
    in order, each `{part = [[r, g, b], ...]}` dark to light. An empty entry leaves its figure as built; fewer entries than
    figures leave the last figures as built; more are `cast.colours_invalid`."""
    def invalid(why: str) -> Exception:
        return fail("cast.colours_invalid", f"{shown}: {why}", fix="kiripix cast-sheet --help")

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise invalid(f"can't be read ({error.strerror or error})") from None
    try:
        if path.suffix.lower() == ".toml":
            import tomllib

            document: Any = tomllib.loads(text)
        else:
            document = json.loads(text)
    except ValueError as error:
        raise invalid(f"isn't valid {'TOML' if path.suffix.lower() == '.toml' else 'JSON'}: {error}") from None
    entries = document.get("figure") if isinstance(document, dict) else document
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise invalid("holds one entry per figure: a list of {part = [[r, g, b], ...]} (in TOML, [[figure]] tables)")
    if len(entries) > figures:
        raise invalid(f"has {len(entries)} entries and the sheet has {figures} figures")
    made: list[dict[str, list[Rgb]]] = []
    for number, entry in enumerate(entries, 1):
        parsed: dict[str, list[Rgb]] = {}
        for part, ramp in entry.items():
            ok = isinstance(ramp, list) and bool(ramp) and all(
                isinstance(c, list) and len(c) == 3 and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 255
                                                            for v in c) for c in ramp)
            if not ok:
                raise invalid(f"entry {number}, part '{part}' isn't a list of [r, g, b] colours, each 0 to 255")
            parsed[str(part)] = [(c[0], c[1], c[2]) for c in ramp]
        made.append(parsed)
    return made
