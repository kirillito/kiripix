"""`import --role sheet` of a Pixelbolt atlas (ticket 0401, spec §6.4).

Pixelbolt writes `<name>.png` and a TexturePacker-style `<name>.atlas.json` (`frames`, `animations`, `meta`). Kiripix runs no
Node and never runs Pixelbolt; it reads what was written. The PNG and the JSON are stored whole beside each other in
`src/sheets/` under the start of the PNG's hash (the recipe, `<name>.pixel.json` or `<name>.fx.json`, beside the atlas, as a
note nothing reads), and the atlas becomes one `sheet` Decision on `frames` that cuts the cells and gives each
clip's playback order, `loop` and `ticks` (a `clip` Decision of the Owner's still wins over them). Everything is checked before anything
is written, so a refusal changes nothing. The whole import is that one Decision (the clips' `loop` and `ticks` are in it), and the
latest atlas Decision is the one that cuts, so a later render replaces an earlier one and one `undo` steps back. The caller holds the Asset lock.
"""

import io
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from kiripix.checks import Finding, Position
from kiripix.core import atomic, editing, sheets
from kiripix.core.assets import Asset
from kiripix.core.errors import KiripixError, fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache, hash_bytes
from kiripix.core.project import Project
from kiripix.core.sources import IMPORTED_FILE, IMPORTED_SCHEMA_VERSION, VARIANT_NAME_LENGTH, imported_as
from kiripix.recipes.clips import NAME_PATTERN
from kiripix.recipes.sprite_names import snake_case

APP = "Pixelbolt"
ATLAS_SUFFIX = ".atlas.json"
NOTE_SUFFIXES = (".pixel.json", ".fx.json")
VERSIONS = ("1",)  # `meta.version` (the atlas format's, not the package's) as read from Pixelbolt 0.19.0 to 0.21.0
TICKS_PER_SECOND = 60


class _Rect(BaseModel):
    x: int
    y: int
    w: int
    h: int


class _Size(BaseModel):
    w: int
    h: int


class _Point(BaseModel):
    x: float
    y: float


class AtlasFrame(BaseModel):
    """One entry of the atlas's `frames`; keys Kiripix doesn't read (`pivot`, `points`...) are ignored."""

    frame: _Rect
    rotated: bool = False
    trimmed: bool = False
    spriteSourceSize: _Rect | None = None
    sourceSize: _Size
    duration: float = Field(ge=0)
    anchorPx: _Point | None = None


class AtlasAnimation(BaseModel):
    frames: list[str] = Field(min_length=1)
    loop: bool = True


class _Meta(BaseModel):
    app: str
    image: str
    version: Any = None


class Atlas(BaseModel):
    frames: dict[str, AtlasFrame]
    animations: dict[str, AtlasAnimation] = Field(min_length=1)
    meta: _Meta


class AtlasClip(BaseModel):
    """One clip the import made, from one animation."""

    name: str = Field(description="The clip's name: the animation's, as snake_case.")
    animation: str = Field(description="The animation's name in the atlas.")
    frames: int = Field(description="The clip's frames, in playback order (a frame played twice counts twice).")
    cells: int = Field(description="The distinct cells cut for it.")
    loop: bool
    ticks: list[int] = Field(description="Each frame's duration in ticks (60 a second), at least 1.")


class AtlasRead(BaseModel):
    """What `import` read of a Pixelbolt atlas."""

    version: str | None = Field(description="The atlas's `meta.version` (the format's version).")
    image: str = Field(description="The PNG the atlas names, `meta.image`.")
    cell: tuple[int, int] = Field(description="The untrimmed cell, width and height.")
    clips: list[AtlasClip]
    anchor: tuple[float, float] | None = Field(description="The anchor every frame shares, `anchorPx`; null when the frames differ or "
                                                           "one has none.")
    stored: list[str] = Field(description="The files stored in src/sheets/, relative to the Project: the PNG, the atlas "
                                          "and the recipe note, if any.")


class AtlasImport(BaseModel):
    name: str
    path: Path
    created: bool
    read: AtlasRead
    findings: list[Finding]


def find(path: Path) -> Path | None:
    """The atlas file `path` names: a `.json` file, or the one `*.atlas.json` of a folder; None for anything else."""
    if path.is_dir():
        found = sorted(path.glob(f"*{ATLAS_SUFFIX}"))
        if len(found) > 1:
            raise fail("import.atlas_ambiguous", f"{path.name} holds {len(found)} atlases ({', '.join(p.name for p in found)})",
                       owner_action="Import one of them: kiripix import <id> <folder>/<name>.atlas.json --role sheet.")
        return found[0] if found else None
    return path if path.suffix.lower() == ".json" and path.is_file() else None


def _parse(file: Path, position: Position) -> Atlas | None:
    """The atlas, or None when the file isn't a Pixelbolt atlas (the plain import then says what it is)."""
    try:
        raw = json.loads(file.read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("meta"), dict) or raw["meta"].get("app") != APP:
        return None
    try:
        return Atlas.model_validate(raw)
    except ValidationError as error:
        first = error.errors()[0]
        raise fail("import.atlas_invalid", f"{position.file} is a Pixelbolt atlas, but {'.'.join(map(str, first['loc']))}: "
                   f"{first['msg']}", owner_action="Render the effect again with Pixelbolt.", position=position) from None


def ticks_of(milliseconds: float) -> int:
    """A duration in game ticks: ms x 60 / 1000, rounded half up, at least 1."""
    return max(1, math.floor(milliseconds * TICKS_PER_SECOND / 1000 + 0.5))


def _number(value: float) -> str:
    return f"{int(value)}" if float(value).is_integer() else f"{value:g}"


def _put(path: Path, data: bytes) -> bool:
    if path.is_file() and path.read_bytes() == data:
        return False
    atomic.write_bytes(path, data)
    return True


@dataclass
class Loaded:
    """An atlas read and checked: the atlas, the PNG it names (the bytes) and that PNG's size."""

    atlas: Atlas
    png: bytes
    image: str
    width: int
    height: int


def load(atlas_file: Path, position: Position) -> Loaded | None:
    """Read the atlas and the PNG beside it, and refuse what Kiripix can't take (`import.atlas_image_missing`,
    `import.atlas_rotated`, `import.atlas_rect`, `import.atlas_invalid`), all before anything is written. None when the file
    isn't a Pixelbolt atlas. Shared by the sprite's sheet import and a room Loop's."""
    atlas = _parse(atlas_file, position)
    if atlas is None:
        return None
    image_name = atlas.meta.image
    image_file = atlas_file.parent / image_name
    if Path(image_name).name != image_name or not image_file.is_file():
        raise fail("import.atlas_image_missing", f"{atlas_file.name} names the image {image_name}, and there is none beside it",
                   owner_action=f"Put {image_name} in the same folder as {atlas_file.name}, or render the effect again.",
                   position=position)
    png = image_file.read_bytes()
    if sheets.check(png, image_name, position) != ".png":
        raise fail("import.atlas_invalid", f"{image_name} is a ZIP, and an atlas's image is a PNG",
                   owner_action="Render the effect again with Pixelbolt.", position=position)
    from PIL import Image  # here: the module is loaded when an atlas is imported

    with Image.open(io.BytesIO(png)) as image:
        width, height = image.size
    problems: list[Finding] = []
    rotated = [name for name, frame in atlas.frames.items() if frame.rotated]
    if rotated:
        problems.append(Finding(
            code="import.atlas_rotated", position=position,
            message=f"{atlas_file.name} has rotated frames ({', '.join(rotated[:5])}{' ...' if len(rotated) > 5 else ''}); "
                    "Kiripix doesn't unrotate a packed frame",
            owner_action="Render the effect again without rotating frames in the sheet."))
    outside = [name for name, f in atlas.frames.items()
               if f.frame.x < 0 or f.frame.y < 0 or f.frame.w < 1 or f.frame.h < 1
               or f.frame.x + f.frame.w > width or f.frame.y + f.frame.h > height]
    if outside:
        problems.append(Finding(
            code="import.atlas_rect", position=position,
            message=f"{atlas_file.name} has frames outside {image_name} ({width} x {height} px): "
                    f"{', '.join(outside[:5])}{' ...' if len(outside) > 5 else ''}",
            owner_action=f"Render the effect again, or give the atlas that matches {image_name}."))
    if problems:
        raise KiripixError(problems)
    return Loaded(atlas, png, image_name, width, height)


def frames_of(atlas: Atlas, animation: str, position: Position) -> list[str]:
    """An animation's frame names in playback order, each one the atlas has."""
    spec = atlas.animations[animation]
    for frame_name in spec.frames:
        if frame_name not in atlas.frames:
            raise fail("import.atlas_invalid", f"the animation {animation} plays {frame_name}, which the atlas's frames "
                       "don't have", owner_action="Render the effect again with Pixelbolt.", position=position)
    return list(spec.frames)


def cells_of(atlas: Atlas, names: list[str], position: Position) -> tuple[list[dict[str, Any]], int, int]:
    """The cells of these frames (each `name`, `rect` and `at`: where a trimmed frame sits in its untrimmed cell) and the cell's
    size, the largest `sourceSize`."""
    cells: list[dict[str, Any]] = []
    width = height = 1
    for frame_name in names:
        frame = atlas.frames[frame_name]
        placed = frame.spriteSourceSize or _Rect(x=0, y=0, w=frame.frame.w, h=frame.frame.h)
        width, height = max(width, frame.sourceSize.w), max(height, frame.sourceSize.h)
        cells.append({"name": frame_name, "rect": [frame.frame.x, frame.frame.y, frame.frame.w, frame.frame.h],
                      "at": [placed.x, placed.y]})
    for cell in cells:
        if (cell["at"][0] < 0 or cell["at"][1] < 0 or cell["at"][0] + cell["rect"][2] > width
                or cell["at"][1] + cell["rect"][3] > height):
            raise fail("import.atlas_invalid", f"the frame {cell['name']} is placed outside its cell (spriteSourceSize)",
                       owner_action="Render the effect again with Pixelbolt.", position=position)
    return cells, width, height


def compose(png: bytes, cell: dict[str, Any], width: int, height: int) -> Any:
    """One cell as an RGBA array of the cell's size: the frame cut from the PNG, set at `at` on a transparent cell."""
    import numpy as np
    from PIL import Image

    x, y, w, h = cell["rect"]
    dx, dy = cell["at"]
    with Image.open(io.BytesIO(png)) as image:
        source = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    canvas = np.zeros((height, width, 4), dtype=np.uint8)
    canvas[dy:dy + h, dx:dx + w] = source[y:y + h, x:x + w]
    return canvas


def drift_finding(what: str, durations: list[float], ticks: list[int], position: Position, owner_action: str) -> Finding | None:
    """`import.ticks_rounded` (info) when rounding the durations to ticks moves their total by more than one tick."""
    exact = sum(durations) * TICKS_PER_SECOND / 1000
    drift = sum(ticks) - exact
    if abs(drift) <= 1:
        return None
    return Finding(
        code="import.ticks_rounded", severity="info", position=position,
        message=f"{what}: its {len(durations)} frame durations ({sum(durations):g} ms) rounded to {sum(ticks)} ticks, "
                f"{drift:+.1f} ticks from {exact:.1f}",
        data={"ticks": sum(ticks), "drift": round(drift, 2)}, owner_action=owner_action)


def version_finding(version: str | None, file_name: str, position: Position) -> Finding | None:
    """`import.atlas_version` (info) for a `meta.version` Kiripix wasn't checked against."""
    if version in VERSIONS:
        return None
    return Finding(
        code="import.atlas_version", severity="info", position=position,
        message=f"{file_name} is Pixelbolt atlas version {version}; Kiripix was checked against version {', '.join(VERSIONS)}",
        data={"version": version},
        owner_action="Look at the imported frames, their order and their ticks against the render; if they are wrong, "
                     "the atlas format changed and the import needs updating.")


def import_atlas(project: Project, asset: Asset, file: Path, shown: str) -> AtlasImport | None:
    """Import a Pixelbolt atlas (a `.atlas.json`, or a folder holding one) into a sprite as a sheet, its `sheet` and `clip`
    Decisions recorded. None when `file` isn't one, so the plain import runs. Raises the refusals before any write."""
    atlas_file = find(file)
    if atlas_file is None:
        return None
    position = Position(asset=asset.id, file=shown)
    loaded = load(atlas_file, position)
    if loaded is None:
        return None
    atlas, png, image_name = loaded.atlas, loaded.png, loaded.image
    findings: list[Finding] = []

    # the cells and each clip's playback
    names: dict[str, int] = {}  # a frame's name to its cell, in the order it is first played
    plays: dict[str, list[int]] = {}
    clips: list[AtlasClip] = []
    clip_data: dict[str, dict[str, Any]] = {}
    for animation, spec in atlas.animations.items():
        clip = snake_case(animation)
        if re.match(NAME_PATTERN, clip) is None:
            raise fail("import.atlas_invalid", f"the animation {animation} would be the clip {clip}, which can't be a clip name: "
                       "lower-case snake_case that doesn't end in a direction suffix (_s, _sw, _w, _nw, _n, _ne, _e, _se)",
                       owner_action=f"Rename the animation {animation} in the Pixelbolt recipe and render again.",
                       position=position)
        if clip in plays:
            raise fail("import.atlas_invalid", f"the animations {animation} and another are both the clip {clip}",
                       owner_action="Render the effect again with animation names that differ in their letters or digits.",
                       position=position)
        order: list[int] = []
        durations: list[float] = []
        for frame_name in frames_of(atlas, animation, position):
            order.append(names.setdefault(frame_name, len(names)))
            durations.append(atlas.frames[frame_name].duration)
        plays[clip] = order
        ticks = [ticks_of(d) for d in durations]
        clips.append(AtlasClip(name=clip, animation=animation, frames=len(order), cells=len(set(order)), loop=spec.loop,
                               ticks=ticks))
        clip_data[clip] = {"loop": spec.loop, "ticks": ticks}
        found = drift_finding(f"the clip {clip}", durations, ticks, position,
                              f"the exact ticks can be decided: kiripix decide {asset.id} frames.")
        if found is not None:
            found.data["clip"] = clip
            findings.append(found)
    cells, cell_width, cell_height = cells_of(atlas, list(names), position)

    # the anchor
    anchors: dict[str, tuple[float, float]] = {}
    for frame_name in names:
        point = atlas.frames[frame_name].anchorPx
        if point is not None:
            anchors[frame_name] = (point.x, point.y)
    shared = set(anchors.values())
    anchor: tuple[float, float] | None = None
    if len(anchors) == len(names) and len(shared) == 1:
        anchor = next(iter(shared))
        text = f"{_number(round(anchor[0]))},{_number(round(anchor[1]))}"
        findings.append(Finding(
            code="import.anchor", severity="info", position=position,
            message=f"every frame has the anchor {_number(anchor[0])},{_number(anchor[1])} (px in the cell); import sets no "
                    "parameter, `fit anchor` does",
            data={"x": anchor[0], "y": anchor[1]}, fix=f"kiripix set {asset.id} fit anchor={text}"))
    elif len(shared) > 1:
        by_anchor: dict[tuple[float, float], list[str]] = {}
        for frame_name, point_ in anchors.items():
            by_anchor.setdefault(point_, []).append(frame_name)
        common = max(by_anchor, key=lambda p: len(by_anchor[p]))
        shown_anchors = "; ".join(f"{_number(p[0])},{_number(p[1])}: {', '.join(f[:5])}{' ...' if len(f) > 5 else ''}"
                                  for p, f in by_anchor.items())
        findings.append(Finding(
            code="import.anchor_varies", severity="warning", position=position,
            message=f"the frames have {len(shared)} different anchors ({shown_anchors}); an effect has one pivot",
            data={"anchors": [{"x": p[0], "y": p[1], "frames": f} for p, f in by_anchor.items()]},
            owner_action=f"Choose the pivot: kiripix set {asset.id} fit anchor=x,y (the most common is "
                         f"{_number(round(common[0]))},{_number(round(common[1]))}), or render the effect with one anchor."))

    version = None if atlas.meta.version is None else str(atlas.meta.version)
    found_version = version_finding(version, atlas_file.name, position)
    if found_version is not None:
        findings.append(found_version)

    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    if str(graph.params(graph.spec("frames")).get("directions")) != "1":
        findings.append(Finding(
            code="import.directions", severity="info", position=position,
            message="an atlas's clips have one direction (s), and this sprite asks for more", fix=f"kiripix set {asset.id} frames directions=1"))

    # the one Decision, checked before anything is written
    name = hash_bytes(png)[:VARIANT_NAME_LENGTH]
    sheet_data = {"file": name, "cell": [cell_width, cell_height], "cells": cells, "plays": plays, "clips": clip_data}
    document = editing.DecisionDocument(decision="sheet", data=sheet_data)
    editing.check_decision(project, asset, "frames", document)

    # the writes: the files, the name record, then the Decisions
    folder = asset.dir / "src" / sheets.SHEETS_DIR
    png_path = folder / f"{name}.png"
    created = not png_path.is_file()
    stored = [png_path, folder / f"{name}{ATLAS_SUFFIX}"]
    created |= _put(png_path, png)
    created |= _put(stored[1], atlas_file.read_bytes())
    stem = atlas_file.name[: -len(ATLAS_SUFFIX)] if atlas_file.name.endswith(ATLAS_SUFFIX) else atlas_file.stem
    for suffix in NOTE_SUFFIXES:
        note = atlas_file.parent / f"{stem}{suffix}"
        if note.is_file():
            stored.append(folder / f"{name}{suffix}")
            created |= _put(stored[-1], note.read_bytes())
    if imported_as(asset, png_path) != atlas_file.name:
        atomic.append_jsonl_many(asset.dir / IMPORTED_FILE, [
            {"schema_version": IMPORTED_SCHEMA_VERSION, "file": png_path.relative_to(asset.dir).as_posix(),
             "imported_as": atlas_file.name}])

    latest = [d for d in graph.replay("frames").current if d.name == "sheet" and "plays" in d.data]
    if not latest or latest[-1].data != sheet_data:  # the latest atlas Decision is the one that cuts; the same again records nothing
        editing.record_decision(project, asset, "frames", document)
        created = True

    read = AtlasRead(version=version, image=image_name, cell=(cell_width, cell_height), clips=clips, anchor=anchor,
                     stored=[project.relative(p) for p in stored])
    return AtlasImport(name=name, path=png_path, created=created, read=read, findings=findings)
