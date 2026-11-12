"""The character's `sheet` Stage (spec §6.3, ticket 0112).

Packs `finish`'s colour frames into one atlas and its normal frames into a second atlas with the same layout (`pack_atlas`).
Every cell is the render's frame size, and each frame's pivot (the feet) lands on the render's pivot in the cell, so the pivot
is the same pixel in every cell of every clip and direction. Nothing reads `render`'s files after this: `sheet.json` is what
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
                "directions": {"s": [{"index": 0, "rect": {"x": 0, "y": 0, "width": 78, "height": 78}}, ...]}}]}

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
    columns = max(1, math.ceil(math.sqrt(len(frames))))
    colour, rects = pack_atlas([f.image for f in frames], pivots, cell, columns, cell_pivot)
    run.check_cancel()
    run.progress(1, 2, "packing the normal atlas")
    normal_frames: list[np.ndarray] = []
    for f in frames:
        assert f.normal is not None
        normal_frames.append(f.normal)
    normal, normal_rects = pack_atlas(normal_frames, pivots, cell, columns, cell_pivot)
    if normal_rects != rects:
        raise StageFailure("the two atlases don't share a layout")  # can't happen: one cell, one count
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
                                  strict=True))}
                for frame in listed if (entry["name"], direction, int(frame["index"])) in found]
        clips.append({"name": entry["name"], "fps": int(entry["fps"]), "loop": bool(entry["loop"]),
                      "stationary": bool(entry["stationary"]), "directions": directions})
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
    frames, names = _frames(run, source, document, normals=False)
    stationary = {str(c["name"]) for c in document["clips"] if c["stationary"]}
    findings = (check_pivot_drift(frames, stationary, rerender) + check_frame_overflow(frames, cell, rerender, cell_pivot)
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
