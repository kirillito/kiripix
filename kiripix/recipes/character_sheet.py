"""The character's `sheet` Stage (spec §6.3, ticket 0112).

Packs `finish`'s colour frames into one atlas and its normal frames into a second atlas with the same layout (`pack_atlas`).
Every cell is its clip's frame size (ticket 0303: the render's `frame` and `pivot` per clip, the character's when the clip has
none), and each frame's pivot (the feet) lands on the clip's pivot in the cell, so the pivot is the same pixel in every cell of a
clip and direction. Most clips have the body's cell, which is the top-level `cell` and `pivot`. The atlas is laid out in blocks, one
for each distinct cell: the body's first, as one grid of `columns` columns, then each other cell size below it, a grid of its own.
`rect` gives every frame's place; a reader never computes it. Each clip has its `cell` and `pivot`. Nothing reads `render`'s files after this: `sheet.json` is what
the exporter and the UI read.

Output in `work/sheet/`: `color.png`, `normal.png` and `sheet.json`:

    {"schema_version": 1,
     "files": {"color": "color.png", "normal": "normal.png"},
     "cell": {"width": 78, "height": 78},
     "pivot": {"x": 39, "y": 72},                    # in the cell, from its top left
     "columns": 11,
     "atlas": {"width": 858, "height": 936},
     "directions": ["s", "se", ...],
     "clips": [{"name": "idle", "fps": 12, "loop": true, "stationary": true,
                "cell": {"width": 78, "height": 78}, "pivot": {"x": 39, "y": 72},   # this clip's; the body's for most
                "directions": {"s": [{"index": 0, "rect": {"x": 0, "y": 0, "width": 78, "height": 78}}, ...]}}]}

With named points (ticket 0237, `render`'s `points`), each frame also has `"points": {"hand_r": {"x": 12, "y": -20, "hidden":
false}}`: the point's pixel relative to the pivot, whole px, y down, as Godot draws: the pixel of the frame that holds it, counted
from the pivot's pixel edge (`floor(render x - the frame's rounded pivot)`). A character without points has no such key.

The Checks read `finish`'s frames again (the atlas has cut off what overflows the cell) and `clips`' frame counts. A finding
about a frame has `position.field` = `clip/direction/index` and `position.file` = the frame's colour file in `finish`.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks import (
    Finding,
    Position,
    SheetFrame,
    check_empty_frame,
    check_frame_count,
    check_frame_overflow,
    check_pivot_drift,
)
from kiripix.ops import pack_atlas
from kiripix.ops.sheet import Rect
from kiripix.recipes.base import CheckFunction, StageFailure, StageFunction, StageRun
from kiripix.recipes.character_palette import RENDER_FILE
from kiripix.recipes.common import read_rgba, write_rgba

SHEET_SCHEMA_VERSION = 1
SHEET_FILE = "sheet.json"
COLOR_ATLAS = "color.png"
NORMAL_ATLAS = "normal.png"


def _round(value: float) -> int:
    return math.floor(float(value) + 0.5)


def _json(path: Any, what: str, stage: str) -> dict[str, Any]:
    try:
        document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StageFailure(f"{stage} has no {what}; run it again") from None
    return document


def _cell(document: dict[str, Any]) -> tuple[tuple[int, int], tuple[int, int]]:
    frame, pivot = document["frame"], document["pivot"]
    return (int(frame["width"]), int(frame["height"])), (_round(pivot[0]), _round(pivot[1]))


def _clip_cell(document: dict[str, Any], entry: dict[str, Any]) -> tuple[tuple[int, int], tuple[int, int]]:
    """A clip's cell and pivot (ticket 0303): its own `frame` and `pivot` in `render.json`, else the character's."""
    if "frame" in entry and "pivot" in entry:
        return _cell(entry)
    return _cell(document)


Cell = tuple[tuple[int, int], tuple[int, int]]  # (width, height), (pivot x, pivot y)


def pack_by_cell(images: list[Any], pivots: list[tuple[int, int]], cells: list[Cell], first: Cell) -> tuple[Any, list[Rect], int]:
    """Packs frames into one atlas, a block of rows for each distinct cell (size and pivot): the block of cell `first` (the
    body's) on top, the others in the order their first frame appears, each a grid of its own cells, `ceil(sqrt(count))`
    columns, left aligned. A character whose frames share one cell is one block, the same layout as ever. Returns the atlas,
    each frame's rect in the order given, and the first block's column count."""
    order: list[Cell] = [first] if first in cells else []
    for cell in cells:
        if cell not in order:
            order.append(cell)
    blocks: list[tuple[Any, list[Rect], int]] = []
    members: dict[Cell, list[int]] = {cell: [i for i, c in enumerate(cells) if c == cell] for cell in order}
    for cell in order:
        mine = members[cell]
        columns = max(1, math.ceil(math.sqrt(len(mine))))
        block, rects = pack_atlas([images[i] for i in mine], [pivots[i] for i in mine], cell[0], columns, cell[1])
        blocks.append((block, rects, columns))
    width = max(block.shape[1] for block, _, _ in blocks)
    atlas = np.zeros((sum(block.shape[0] for block, _, _ in blocks), width, 4), dtype=np.uint8)
    found: list[Rect | None] = [None] * len(images)
    top = 0
    for cell, (block, rects, _) in zip(order, blocks, strict=True):
        atlas[top:top + block.shape[0], :block.shape[1]] = block
        for i, (x, y, w, h) in zip(members[cell], rects, strict=True):
            found[i] = (x, y + top, w, h)
        top += block.shape[0]
    placed: list[Rect] = []
    for rect in found:
        assert rect is not None
        placed.append(rect)
    return atlas, placed, blocks[0][2]


def _points(frame: dict[str, Any]) -> dict[str, Any]:
    """A frame's `points` for the sheet, relative to the frame's pivot in whole px; nothing when render followed none."""
    found = frame.get("points")
    if not found:
        return {}
    pivot = (_round(frame["pivot"][0]), _round(frame["pivot"][1]))
    return {"points": {name: {"x": math.floor(float(p["x"]) - pivot[0]), "y": math.floor(float(p["y"]) - pivot[1]),
                              "hidden": bool(p["hidden"])} for name, p in found.items()}}


def _frames(run: StageRun, source: str, document: dict[str, Any], *, normals: bool) -> tuple[list[SheetFrame], dict[tuple[str, str, int], str]]:
    """Every frame render.json lists whose colour file exists in `finish`, in clip, direction, frame order, with its file."""
    finish = run.upstream[source]
    frames: list[SheetFrame] = []
    names: dict[tuple[str, str, int], str] = {}
    for entry in document["clips"]:
        for direction, listed in entry["directions"].items():
            for frame in listed:
                run.check_cancel()
                index, name = int(frame["index"]), str(frame["files"]["color"])
                path = finish / name
                if not path.is_file():
                    continue  # `sheet.frame_count` reports it
                normal = None
                if normals:
                    try:
                        normal = read_rgba(finish / ("normal/" + name.partition("/")[2]))
                    except OSError:
                        raise StageFailure(f"{source} has no normal for {entry['name']}/{direction} frame {index}; run {source} "
                                           f"again", fix=f"kiripix run {run.asset_id} {source} --force") from None
                pivot = (_round(frame["pivot"][0]), _round(frame["pivot"][1]))
                feet = frame.get("feet")  # a sprite's measured feet; a character's render.json has none
                frames.append(SheetFrame(entry["name"], direction, index, read_rgba(path), pivot, normal,
                                         None if feet is None else (_round(feet[0]), _round(feet[1]))))
                names[(entry["name"], direction, index)] = name
    return frames, names


def _run_sheet(run: StageRun, source: str) -> None:
    document = _json(run.upstream[source] / RENDER_FILE, RENDER_FILE, source)
    cell, cell_pivot = _cell(document)
    frames, _ = _frames(run, source, document, normals=True)
    if not frames:
        raise StageFailure(f"{source} has no frames to pack; run it again", fix=f"kiripix run {run.asset_id} {source} --force")
    run.progress(0, 2, "packing the colour atlas")
    pivots = [f.pivot for f in frames]
    own = {str(e["name"]): _clip_cell(document, e) for e in document["clips"]}
    cells = [own[f.clip] for f in frames]
    colour, rects, columns = pack_by_cell([f.image for f in frames], pivots, cells, (cell, cell_pivot))
    run.check_cancel()
    run.progress(1, 2, "packing the normal atlas")
    normal_frames: list[np.ndarray] = []
    for f in frames:
        assert f.normal is not None
        normal_frames.append(f.normal)
    normal, normal_rects, _ = pack_by_cell(normal_frames, pivots, cells, (cell, cell_pivot))
    if normal_rects != rects:
        raise StageFailure("the two atlases don't share a layout")  # can't happen: one cell list, one count
    write_rgba(run.output_dir / COLOR_ATLAS, colour)
    write_rgba(run.output_dir / NORMAL_ATLAS, normal)

    found = {(f.clip, f.direction, f.index): rect for f, rect in zip(frames, rects, strict=True)}
    clips = []
    for entry in document["clips"]:
        directions: dict[str, list[dict[str, Any]]] = {}
        for direction, listed in entry["directions"].items():
            directions[direction] = [
                {"index": int(frame["index"]),
                 "rect": dict(zip(("x", "y", "width", "height"), found[(entry["name"], direction, int(frame["index"]))],
                                  strict=True)),
                 **_points(frame)}
                for frame in listed if (entry["name"], direction, int(frame["index"])) in found]
        (own_width, own_height), own_pivot = own[str(entry["name"])]
        clips.append({"name": entry["name"], "fps": int(entry["fps"]), "loop": bool(entry["loop"]),
                      "stationary": bool(entry["stationary"]),
                      "cell": {"width": own_width, "height": own_height}, "pivot": {"x": own_pivot[0], "y": own_pivot[1]},
                      "directions": directions})
    sheet = {
        "schema_version": SHEET_SCHEMA_VERSION,
        "files": {"color": COLOR_ATLAS, "normal": NORMAL_ATLAS},
        "cell": {"width": cell[0], "height": cell[1]},
        "pivot": {"x": cell_pivot[0], "y": cell_pivot[1]},
        "columns": columns,
        "atlas": {"width": int(colour.shape[1]), "height": int(colour.shape[0])},
        "directions": list(document["directions"]),
        "clips": clips,
    }
    (run.output_dir / SHEET_FILE).write_text(json.dumps(sheet, indent=1) + "\n", encoding="utf-8")


def _check_sheet(run: StageRun, source: str) -> list[Finding]:
    """`sheet.pivot_drift`, `sheet.frame_overflow`, `sheet.frame_count` and `sheet.empty_frame`, from `finish`'s frames."""
    try:
        document = json.loads((run.upstream[source] / RENDER_FILE).read_text(encoding="utf-8"))
        if "clips" in run.upstream:
            expected = {c["name"]: len(c["frames"])
                        for c in json.loads((run.upstream["clips"] / "clips.json").read_text(encoding="utf-8"))["clips"]}
        else:  # a Recipe with no `clips` Stage (the sprite): the frame list is the count
            expected = {c["name"]: len(next(iter(c["directions"].values()), [])) for c in document["clips"]}
        cell, cell_pivot = _cell(document)
    except (OSError, ValueError, KeyError):
        return []  # nothing built to check
    if not (run.output_dir / SHEET_FILE).is_file():
        return []
    fix = f"kiripix run {run.asset_id} {source} --force"
    # The pivots and the cell come from `render`, which fixes a stationary clip's pivot (ticket 0154) and sizes the cell to
    # every pose (0155): rendering again is what changes them.
    rerender = f"kiripix run {run.asset_id} render --force"
    drift = rerender
    if document.get("kind") == "sprite":  # no `render`: `fit` places the frames, and align_feet is what quiets a hop
        rerender = f"kiripix run {run.asset_id} fit --force"
        drift = f"kiripix set {run.asset_id} fit align_feet=true"
    frames, names = _frames(run, source, document, normals=False)
    stationary = {str(c["name"]) for c in document["clips"] if c["stationary"]}
    # Each clip is checked against its own cell (ticket 0303): the overflow of a frame in a clip with a larger cell, and a drift
    # in a stationary clip, are that clip's.
    overflow: list[Finding] = []
    for entry in document["clips"]:
        clip_cell, clip_pivot = _clip_cell(document, entry)
        overflow += check_frame_overflow([f for f in frames if f.clip == entry["name"]], clip_cell, rerender, clip_pivot)
    findings = (check_pivot_drift(frames, stationary, drift) + overflow
                + check_frame_count(frames, expected, fix, list(document["directions"])) + check_empty_frame(frames, fix))
    for finding in findings:
        if finding.position is None:
            finding.position = Position()
        finding.position.asset, finding.position.stage = run.asset_id, "sheet"
        parts = (finding.position.field or "").split("/")
        if len(parts) == 3 and (parts[0], parts[1], int(parts[2])) in names:
            finding.position.file = names[(parts[0], parts[1], int(parts[2]))]
    return findings


def sheet_stage(frames: str = "finish") -> tuple[StageFunction, CheckFunction]:
    """The Stage's `run` and `check` for a Recipe whose finished frames and frame list (`render.json`) are in the Stage named
    `frames` (ticket 0176). The Stage must list it upstream; `clips`, when listed, gives the expected frame counts."""
    return (lambda run: _run_sheet(run, frames)), (lambda run: _check_sheet(run, frames))


run_character_sheet, check_character_sheet = sheet_stage("finish")


DEPTH_ATLAS = "depth.png"
FAR = 65535


def _depth_frame(path: Any, asset: str) -> Any:
    from PIL import Image

    with Image.open(path) as image:
        depth = np.asarray(image, dtype=np.uint16)
    if depth.ndim != 2:
        raise StageFailure("a depth frame of render is not a 16 bit gray image; run render again",
                           fix=f"kiripix run {asset} render --force")
    return depth


def run_body_sheet(run: StageRun) -> None:
    """The character's `sheet`: the colour and normal atlases, and `depth.png` in the same layout (ticket 0296)."""
    run_character_sheet(run)
    add_depth_atlas(run, None)


def add_depth_atlas(run: StageRun, order: int | None) -> None:
    """Write `depth.png` next to the sheet's atlases, in their layout, and list it in `sheet.json` (`files.depth`; `order`
    too when given, a Wearable's)."""
    from PIL import Image

    sheet: dict[str, Any] = json.loads((run.output_dir / SHEET_FILE).read_text(encoding="utf-8"))
    document: dict[str, Any] = json.loads((run.upstream["render"] / RENDER_FILE).read_text(encoding="utf-8"))
    frames = {(c["name"], d, int(f["index"])): f for c in document["clips"] for d, listed in c["directions"].items()
              for f in listed}
    cell = (int(sheet["cell"]["width"]), int(sheet["cell"]["height"]))
    cell_pivot = (int(sheet["pivot"]["x"]), int(sheet["pivot"]["y"]))
    encoded: list[Any] = []
    pivots: list[tuple[int, int]] = []
    cells: list[Cell] = []
    for clip in sheet["clips"]:
        own: Cell = (((int(clip["cell"]["width"]), int(clip["cell"]["height"])), (int(clip["pivot"]["x"]), int(clip["pivot"]["y"])))
                     if "cell" in clip else (cell, cell_pivot))
        for direction, listed in clip["directions"].items():
            for entry in listed:
                run.check_cancel()
                found = frames[(clip["name"], direction, int(entry["index"]))]
                depth = _depth_frame(run.upstream["render"] / str(found["files"]["depth"]), run.asset_id)
                rgba = np.zeros((*depth.shape, 4), dtype=np.uint8)  # the 16 bit value in two bytes; alpha marks a pixel
                rgba[..., 0], rgba[..., 1], rgba[..., 3] = depth >> 8, depth & 255, 255
                encoded.append(rgba)
                pivots.append((int(np.floor(found["pivot"][0] + 0.5)), int(np.floor(found["pivot"][1] + 0.5))))
                cells.append(own)
    atlas, rects, _ = pack_by_cell(encoded, pivots, cells, (cell, cell_pivot))
    expected = [(e["rect"]["x"], e["rect"]["y"], e["rect"]["width"], e["rect"]["height"])
                for c in sheet["clips"] for listed in c["directions"].values() for e in listed]
    if rects != expected:
        raise StageFailure("the depth atlas doesn't share the colour atlas's layout")  # can't happen
    depth_atlas = (atlas[..., 0].astype(np.uint16) << 8) | atlas[..., 1].astype(np.uint16)
    depth_atlas[atlas[..., 3] == 0] = FAR
    Image.fromarray(depth_atlas).save(run.output_dir / DEPTH_ATLAS)
    sheet["files"]["depth"] = DEPTH_ATLAS
    if order is not None:
        sheet["order"] = order
    (run.output_dir / SHEET_FILE).write_text(json.dumps(sheet, indent=1) + "\n", encoding="utf-8")
