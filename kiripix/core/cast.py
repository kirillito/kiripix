"""The cast sheet (spec §10, ticket 0226): several characters side by side, at the game's size or a whole-number zoom.

Each Asset's built `sheet` Stage gives its frames (`sheet.json` and the colour atlas). Every cell is drawn with its pivot
(the feet) on one shared ground line, the Assets left to right in the order given, each labelled with its ID above it.
Written to `.kiripix/previews/`, a cache that deleting loses nothing from. Nothing is recorded and no lock is taken.

An Asset whose Kind has no `sheet` Stage is refused whole. One whose sheet isn't built is a finding and left out; one whose
sheet is out of date is drawn, with a warning. A clip or direction the sheet doesn't have is a finding too.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import load_rgba, save_png
from kiripix.core.project import Project
from kiripix.ops.resample import upscale
from kiripix.recipes.character_sheet import SHEET_FILE, SHEET_SCHEMA_VERSION

SHEET_STAGE = "sheet"
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


@dataclass(frozen=True)
class CastSheet:
    path: Path
    width: int
    height: int
    scale: int
    ground: int  # the y of the ground line in the PNG
    cells: tuple[CastCell, ...]
    findings: tuple[Finding, ...]


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


def _picked(count: int, frames: int) -> list[int]:
    """`frames` positions spread evenly over a clip of `count` frames, from the first; all of them when it has fewer."""
    if frames >= count:
        return list(range(count))
    return sorted({i * count // frames for i in range(frames)})


def _sheet(graph: AssetGraph, asset: Asset, findings: list[Finding]) -> tuple[dict[str, Any], np.ndarray] | None:
    """The Asset's sheet.json and colour atlas, or None (with a finding) when it isn't built."""
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
    return document, atlas


def _frames(asset: Asset, document: dict[str, Any], atlas: np.ndarray, clips: list[str] | None, directions: list[str],
            frames: int, findings: list[Finding]) -> list[_Frame]:
    by_name = {clip["name"]: clip for clip in document["clips"]}
    wanted = clips if clips is not None else [document["clips"][0]["name"]] if document["clips"] else []
    pivot = (int(document["pivot"]["x"]), int(document["pivot"]["y"]))
    made: list[_Frame] = []
    for name in wanted:
        clip = by_name.get(name)
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
                r = frame["rect"]
                image = atlas[r["y"]: r["y"] + r["height"], r["x"]: r["x"] + r["width"]]
                made.append(_Frame(asset.id, name, direction, int(frame["index"]), image, pivot, not made))
    return made


def _label_font() -> Any:
    from PIL import ImageFont

    return ImageFont.load_default()


def cast_sheet(project: Project, assets: list[Asset], clips: list[str] | None, directions: list[str], frames: int,
               scale: int) -> CastSheet:
    """Draw the cast sheet. Refuses an Asset with no `sheet` Stage; raises NothingToDraw, with the findings that say
    why, when no Asset has a cell to draw."""
    cache = HashCache(project.state_dir)
    findings: list[Finding] = []
    drawn: list[_Frame] = []
    for asset in assets:
        graph = AssetGraph(project, asset, cache)
        if graph.kind.stage(SHEET_STAGE) is None:
            raise fail("cast.not_a_figure", f"{asset.id} is a {asset.kind}, which has no {SHEET_STAGE} Stage to draw",
                       fix="kiripix cast-sheet character.a,character.b", position=Position(asset=asset.id))
        built = _sheet(graph, asset, findings)
        if built is not None:
            drawn += _frames(asset, *built, clips, directions, frames, findings)
    if not drawn:
        raise NothingToDraw(findings)

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

    figures = upscale(canvas, scale)
    image = np.empty((LABEL_HEIGHT + figures.shape[0], figures.shape[1], 4), np.uint8)
    image[:] = BACKGROUND
    alpha = figures[..., 3:4].astype(np.float32) / 255
    under = image[LABEL_HEIGHT:].astype(np.float32)
    image[LABEL_HEIGHT:] = np.rint(figures.astype(np.float32) * alpha + under * (1 - alpha)).astype(np.uint8)
    image[LABEL_HEIGHT:, :, 3] = 255
    image = _labelled(image, [(left * scale, frame.asset) for frame, left in zip(drawn, places) if frame.first])

    cells = tuple(CastCell(f.asset, f.clip, f.direction, f.index, left * scale,
                           LABEL_HEIGHT + (above - f.pivot[1]) * scale, f.image.shape[1] * scale,
                           f.image.shape[0] * scale, (f.pivot[0] * scale, f.pivot[1] * scale))
                  for f, left in zip(drawn, places))
    key = json.dumps([[a.id for a in assets], clips, directions, frames])
    name = f"cast.{hashlib.sha1(key.encode()).hexdigest()[:10]}.x{scale}.png"
    path = project.state_dir / "previews" / name
    save_png(path, image)
    return CastSheet(path, image.shape[1], image.shape[0], scale, LABEL_HEIGHT + above * scale, cells, tuple(findings))


def _labelled(image: np.ndarray, labels: list[tuple[int, str]]) -> np.ndarray:
    from PIL import Image, ImageDraw

    picture = Image.fromarray(image, "RGBA")
    draw = ImageDraw.Draw(picture)
    font = _label_font()
    for left, text in labels:
        draw.text((left + 1, 1), text, fill=LABEL_COLOUR, font=font)
    return np.asarray(picture, dtype=np.uint8).copy()
