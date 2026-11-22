"""The character's `sheet` Stage (spec §6.3, ticket 0112).

Packs `finish`'s colour frames into one atlas and its normal frames into a second atlas with the same layout (ticket 0308: each
frame is cut to the opaque box it has over every layer, `pack_trimmed`; `rect` is the box's place in the atlas and `offset` its place in the
clip's logical cell, so `cell[offset.y:offset.y + rect.height, offset.x:offset.x + rect.width] = atlas[rect]` restores the cell exactly;
an empty frame has a 1 x 1 rect at offset 0, 0). The logical cell is its clip's frame size
(ticket 0303: the render's `frame` and `pivot` per clip, the character's when the clip has none), and each frame's pivot (the feet) lands
on the clip's pivot in the cell, so the pivot is the same pixel in every cell of a clip and direction. Most clips have the body's cell,
which is the top-level `cell` and `pivot`; a clip's own `cell` and `pivot` are its logical cell, which the game restores each frame to.
Frames are packed in shelves with a 1 px gap, so there is no grid and no `columns`; a reader never computes a place, `rect` gives it.
Nothing reads `render`'s files after this: `sheet.json` is what the exporter and the UI read.

Output in `work/sheet/`: `color.png`, `normal.png` and `sheet.json`. `color.png` is an indexed PNG with transparency (index 0) when
the frames hold at most 256 colours, which a palette-mapped character always does (`atlas_png.py`); `sheet.colour_atlas_rgba`
(info) names the count when it stays RGBA. `normal.png` and `depth.png` are not palette images and stay as they are:

    {"schema_version": 2,
     "files": {"color": "color.png", "normal": "normal.png"},
     "cell": {"width": 78, "height": 78},
     "pivot": {"x": 39, "y": 72},                    # in the cell, from its top left
     "atlas": {"width": 640, "height": 520},
     "directions": ["s", "se", ...],
     "clips": [{"name": "idle", "fps": 12, "loop": true, "stationary": true,
                "cell": {"width": 78, "height": 78}, "pivot": {"x": 39, "y": 72},   # this clip's; the body's for most
                "directions": {"s": [{"index": 0, "rect": {"x": 0, "y": 0, "width": 31, "height": 52},   # in the atlas
                                    "offset": {"x": 22, "y": 14}}, ...]}}]}        # in the clip's cell

With named points (ticket 0237, `render`'s `points`), each frame also has `"points": {"hand_r": {"x": 12, "y": -20, "hidden":
false}}`: the point's pixel relative to the pivot, whole px, y down, as Godot draws: the pixel of the frame that holds it, counted
from the pivot's pixel edge (`floor(render x - the frame's rounded pivot)`). A character without points has no such key.

The Checks read `finish`'s frames again and judge them in the logical cell, never the packed rect (the cell has cut off what overflows it) and `clips`' frame counts. A finding
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
from kiripix.ops import pack_trimmed, place_in_cell
from kiripix.recipes.atlas_png import write_colour_atlas
from kiripix.recipes.base import CheckFunction, StageFailure, StageFunction, StageRun
from kiripix.recipes.character_palette import RENDER_FILE
from kiripix.recipes.common import read_rgba, write_rgba

# 2: each frame is cut to its opaque box (ticket 0308): `rect` is the box's place in the atlas, `offset` its place in the clip's cell;
#    `columns` is gone (the atlas is packed, not a grid)
SHEET_SCHEMA_VERSION = 2
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


Cell = tuple[tuple[int, int], tuple[int, int]]  # (width, height), (pivot x, pivot y)


def _cell(document: dict[str, Any]) -> tuple[tuple[int, int], tuple[int, int]]:
    frame, pivot = document["frame"], document["pivot"]
    return (int(frame["width"]), int(frame["height"])), (_round(pivot[0]), _round(pivot[1]))


def _render_clip_cell(document: dict[str, Any], entry: dict[str, Any]) -> tuple[tuple[int, int], tuple[int, int]]:
    """A clip's cell and pivot (ticket 0303): its own `frame` and `pivot` in `render.json`, else the character's."""
    if "frame" in entry and "pivot" in entry:
        return _cell(entry)
    return _cell(document)


def restore_cell(atlas: Any, cell: tuple[int, int], frame: dict[str, Any]) -> Any:
    """A frame's whole logical cell (width, height) from the atlas: its `rect`'s pixels at its `offset` (0, 0 in a sheet of schema 1,
    whose rect is the cell), the rest transparent."""
    rect, offset = frame["rect"], frame.get("offset", {"x": 0, "y": 0})
    restored = np.zeros((cell[1], cell[0], atlas.shape[2]), dtype=atlas.dtype)
    x, y, w, h = int(rect["x"]), int(rect["y"]), int(rect["width"]), int(rect["height"])
    restored[offset["y"]:offset["y"] + h, offset["x"]:offset["x"] + w] = atlas[y:y + h, x:x + w]
    return restored


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


def _run_sheet(run: StageRun, source: str, depth: bool = False) -> dict[str, Any]:
    """Cuts every frame to one box over its layers (colour, normal, and the render's depth when `depth`), packs them, writes
    the atlases and `sheet.json`, and returns `sheet.json`'s document."""
    document = _json(run.upstream[source] / RENDER_FILE, RENDER_FILE, source)
    cell, cell_pivot = _cell(document)
    frames, _ = _frames(run, source, document, normals=True)
    if not frames:
        raise StageFailure(f"{source} has no frames to pack; run it again", fix=f"kiripix run {run.asset_id} {source} --force")
    run.progress(0, 2, "cutting the frames to their boxes")
    own = {str(e["name"]): _render_clip_cell(document, e) for e in document["clips"]}
    colour_cells: list[np.ndarray] = []
    normal_cells: list[np.ndarray] = []
    for f in frames:
        run.check_cancel()
        assert f.normal is not None
        size, own_pivot = own[f.clip]
        colour_cells.append(place_in_cell(f.image, f.pivot, size, own_pivot))
        normal_cells.append(place_in_cell(f.normal, f.pivot, size, own_pivot))
    layers = [colour_cells, normal_cells]
    if depth:
        layers.append(_depth_cells(run, frames, own))
    run.progress(1, 2, "packing the atlases")
    atlases, rects, offsets = pack_trimmed(layers, share=True)  # a repeated cell once (ticket 0375)
    colour = atlases[0]
    write_colour_atlas(run.output_dir / COLOR_ATLAS, colour)  # indexed when it fits (ticket 0310)
    write_rgba(run.output_dir / NORMAL_ATLAS, atlases[1])
    files = {"color": COLOR_ATLAS, "normal": NORMAL_ATLAS}
    if depth:
        _write_depth_atlas(run, atlases[2])
        files["depth"] = DEPTH_ATLAS

    found = {(f.clip, f.direction, f.index): (rect, offset) for f, rect, offset in zip(frames, rects, offsets, strict=True)}
    clips = []
    for entry in document["clips"]:
        directions: dict[str, list[dict[str, Any]]] = {}
        for direction, listed in entry["directions"].items():
            directions[direction] = [
                {"index": int(frame["index"]),
                 "rect": dict(zip(("x", "y", "width", "height"), found[(entry["name"], direction, int(frame["index"]))][0],
                                  strict=True)),
                 "offset": dict(zip(("x", "y"), found[(entry["name"], direction, int(frame["index"]))][1], strict=True)),
                 **_points(frame)}
                for frame in listed if (entry["name"], direction, int(frame["index"])) in found]
        (own_width, own_height), own_pivot = own[str(entry["name"])]
        clips.append({"name": entry["name"], "fps": int(entry["fps"]), "loop": bool(entry["loop"]),
                      "stationary": bool(entry["stationary"]),
                      "cell": {"width": own_width, "height": own_height}, "pivot": {"x": own_pivot[0], "y": own_pivot[1]},
                      **({"ticks": [int(t) for t in entry["ticks"]]} if "ticks" in entry else {}),  # a sprite clip's (ticket 0362)
                      "directions": directions})
    sheet = {
        "schema_version": SHEET_SCHEMA_VERSION,
        "files": files,
        "cell": {"width": cell[0], "height": cell[1]},
        "pivot": {"x": cell_pivot[0], "y": cell_pivot[1]},
        "atlas": {"width": int(colour.shape[1]), "height": int(colour.shape[0])},
        "directions": list(document["directions"]),
        **({"effect": True} if document.get("effect") else {}),  # a sprite's effect mode (ticket 0362): the export is flat
        "clips": clips,
    }
    (run.output_dir / SHEET_FILE).write_text(json.dumps(sheet, indent=1) + "\n", encoding="utf-8")
    return sheet


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
        clip_cell, clip_pivot = _render_clip_cell(document, entry)
        overflow += check_frame_overflow([f for f in frames if f.clip == entry["name"]], clip_cell, rerender, clip_pivot)
    blank = check_empty_frame(frames, fix)
    if document.get("effect"):  # an effect's one-shot may end on a blank frame (ticket 0362)
        for finding in blank:
            finding.severity = "warning"
    findings = (check_pivot_drift(frames, stationary, drift) + overflow
                + check_frame_count(frames, expected, fix, list(document["directions"])) + blank)
    for finding in findings:
        if finding.position is None:
            finding.position = Position()
        finding.position.asset, finding.position.stage = run.asset_id, "sheet"
        parts = (finding.position.field or "").split("/")
        if len(parts) == 3 and (parts[0], parts[1], int(parts[2])) in names:
            finding.position.file = names[(parts[0], parts[1], int(parts[2]))]
    return findings + _check_colour_atlas(run)


def _check_colour_atlas(run: StageRun) -> list[Finding]:
    """`sheet.colour_atlas_rgba` (info): the colour atlas has more than 256 colours, so it stays RGBA (a larger file)."""
    from PIL import Image

    try:
        with Image.open(run.output_dir / COLOR_ATLAS) as atlas:
            if atlas.mode == "P":
                return []
            rgba = np.ascontiguousarray(np.asarray(atlas.convert("RGBA")))
            # one uint32 per pixel: counting 1-D values is far cheaper than sorting 4-column rows
            count = len(np.unique(rgba.reshape(-1, 4).view("<u4")))
    except OSError:
        return []
    return [Finding(code="sheet.colour_atlas_rgba", severity="info",
                    position=Position(asset=run.asset_id, stage="sheet", file=COLOR_ATLAS),
                    message=f"the colour atlas has {count} colours, more than the 256 of an indexed PNG, so it is RGBA and larger; "
                            f"a palette-mapped character has at most the palette's",
                    fix=f"kiripix run {run.asset_id} palette --force", data={"colours": count})]


def sheet_stage(frames: str = "finish") -> tuple[StageFunction, CheckFunction]:
    """The Stage's `run` and `check` for a Recipe whose finished frames and frame list (`render.json`) are in the Stage named
    `frames` (ticket 0176). The Stage must list it upstream; `clips`, when listed, gives the expected frame counts."""
    def run_sheet(run: StageRun) -> None:
        _run_sheet(run, frames)

    return run_sheet, (lambda run: _check_sheet(run, frames))


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


def _depth_cells(run: StageRun, frames: list[SheetFrame],
                 own: dict[str, tuple[tuple[int, int], tuple[int, int]]]) -> list[Any]:
    """Each frame's depth pass from `render` as a whole cell of its clip: the 16 bit value in red and green, alpha 255 where
    the render drew something (nearer than `FAR`), so the frame's one box covers its depth too (ticket 0308)."""
    document: dict[str, Any] = json.loads((run.upstream["render"] / RENDER_FILE).read_text(encoding="utf-8"))
    listed = {(c["name"], d, int(f["index"])): f for c in document["clips"] for d, fs in c["directions"].items() for f in fs}
    cells: list[Any] = []
    for f in frames:
        run.check_cancel()
        found = listed[(f.clip, f.direction, f.index)]
        depth = _depth_frame(run.upstream["render"] / str(found["files"]["depth"]), run.asset_id)
        drawn = depth != FAR
        rgba = np.zeros((*depth.shape, 4), dtype=np.uint8)
        rgba[..., 0] = np.where(drawn, depth >> 8, 0)
        rgba[..., 1] = np.where(drawn, depth & 255, 0)
        rgba[..., 3] = np.where(drawn, 255, 0)
        size, own_pivot = own[f.clip]
        cells.append(place_in_cell(rgba, (_round(found["pivot"][0]), _round(found["pivot"][1])), size, own_pivot))
    return cells


def _write_depth_atlas(run: StageRun, atlas: Any) -> None:
    """`depth.png`, 16 bit gray: the packed depth layer decoded, `FAR` wherever nothing is drawn."""
    from PIL import Image

    depth = (atlas[..., 0].astype(np.uint16) << 8) | atlas[..., 1].astype(np.uint16)
    depth[atlas[..., 3] == 0] = FAR
    Image.fromarray(depth).save(run.output_dir / DEPTH_ATLAS)


def run_sheet_with_depth(run: StageRun, order: int | None) -> None:
    """A `sheet` with `depth.png` in the same layout, listed in `sheet.json` (`files.depth`; `order` too when given, a
    Wearable's). The character's `sheet` (ticket 0296) and a Wearable's."""
    sheet = _run_sheet(run, "finish", depth=True)
    if order is not None:
        sheet["order"] = order
        (run.output_dir / SHEET_FILE).write_text(json.dumps(sheet, indent=1) + "\n", encoding="utf-8")


def run_body_sheet(run: StageRun) -> None:
    """The character's `sheet`: the colour and normal atlases, and `depth.png` in the same layout (ticket 0296)."""
    run_sheet_with_depth(run, None)
