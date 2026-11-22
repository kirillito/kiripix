"""The room's `normals` Stage (ticket 0341, ADR 0014): the room's normal map from a depth Runner, between `masks` and `palette`.

With `mode` `off` (the default) the Stage is done and writes nothing. With `depth` the depth Runner reads the Source (one
pinned call, its input `size` part of the key); the depth goes through the Grid transform to target pixels, becomes a height
(`strength`), and each foreground Layer's normals come from the height refilled outside its alpha, so the cut makes no step.
The Sobel tilt stays flat inside the `deadzone` and is quantised to `levels` per side. Output, in the Stage's folder:

- `normal.png`: the room's size, RGBA, alpha 255, Godot's encoding (flat is 128, 128, 255), each pixel the normal of its
  front-most Layer by the Layers' alpha, then the `flatten` Decisions. It is the Stage's image: an Override paints over it,
  and it is never palette-mapped. The Plate's and each Layer's maps are cut from it at `export`.
- `depth.png`: the height as an 8-bit greyscale picture, for the review of a new depth result.

The pinned depth is a 16-bit greyscale PNG (`runners.depth.decode`); a Layer or Grid change rebuilds the Stage from it with no
Runner call. A palette change doesn't touch it (the Stage doesn't read `palette`).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
if TYPE_CHECKING:
    from PIL import Image
else:
    Image = lazy_module("PIL.Image")

from kiripix.checks import Finding, Position
from kiripix.ops import fill_polygon, paint_stroke, walkable, walkable_islands
from kiripix.ops.normals import cell_means, flatten, front_normals, heights, tilt_of
from kiripix.recipes.base import (
    CheckSpec,
    CurrentDecision,
    DecisionSpec,
    NeedsInput,
    ParamSpec,
    RunnerCall,
    StageFailure,
    StageRun,
)
from kiripix.recipes.common import read_grid, read_rgba, write_rgba
from kiripix.recipes.layers import read_layer_files
from kiripix.runners import DEPTH
from kiripix.runners.depth import SIZES, decode

NORMALS_STAGE = "normals"
NORMAL_FILE = "normal.png"
DEPTH_FILE = "depth.png"
MASKS = "masks"
TILT_LIMIT = 0.4  # `normals.not_flat_walkable`: a walkable pixel tilts more than this (the length of its x and y, about 24 degrees)
_LISTED_AREAS = 8
_SIZE_FIX = SIZES[-1]


def _mode(run: StageRun) -> str:
    return str(run.params["mode"])


def _size(run: StageRun) -> int:
    return int(run.params["size"])


def needs_input(run: StageRun) -> NeedsInput | None:
    if _mode(run) == "depth" and _size(run) not in SIZES:
        return NeedsInput(f"the depth Runner's `size` is one of {', '.join(map(str, SIZES))}, not {_size(run)}",
                          command=f"kiripix set {run.asset_id} {NORMALS_STAGE} size={SIZES[0]}")
    return None


def runner_calls(run: StageRun) -> list[RunnerCall]:
    """The one depth call, on the Source, when `mode` is `depth`. No clicks: its key is the Source, `size` and the weights."""
    source = run.upstream["source"] / "source.png"
    if _mode(run) != "depth" or _size(run) not in SIZES or not source.is_file():
        return []
    return [RunnerCall(runner=DEPTH, image=source, params={"size": _size(run)}, decisions=[])]


def _flatten_problem(data: dict[str, Any]) -> str | None:
    points = data["points"]
    if data["shape"] == "brush":
        return None if "radius" in data else "a brush `flatten` needs a `radius`"
    if "radius" in data:
        return "a polygon `flatten` has no `radius`"
    return None if len(points) >= 3 else "a polygon needs at least 3 points"


def flatten_decision() -> DecisionSpec:
    return DecisionSpec(
        name="flatten",
        description="Make the normals inside a shape face the camera (flat), in target pixels: a `brush` (a disc of "
                    "`radius` stamped along `points`) or a `polygon` (at least three corners; the outline's pixels are "
                    "included). With `erase`, the shape gives the normals back as the Stage made them. With `walkable`, "
                    "only the walkable pixels inside the shape are flattened (the normals of a wall in the shape stay). It "
                    "replays in order and depends on no image, so a new depth result, new weights or a changed Layer keep "
                    "it. To paint normals by hand instead, make an Override over `normal.png`.",
        entry_schema={
            "type": "object",
            "properties": {
                "shape": {"enum": ["brush", "polygon"]},
                "points": {"type": "array", "minItems": 1,
                           "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2}},
                "radius": {"type": "integer", "minimum": 0},
                "erase": {"type": "boolean"},
                "walkable": {"type": "boolean"},
            },
            "required": ["shape", "points"],
            "additionalProperties": False,
        },
        problem=_flatten_problem,
    )


PARAMS = (
    ParamSpec(name="mode", type="choice", choices=["off", "depth"], default="off",
              description="`off`: no normal map, and the Stage is done with no output and no Runner call. `depth`: the "
                          "room's normal map from the depth Runner (Depth Anything V2 Small) on the Source."),
    ParamSpec(name="size", type="int", default=SIZES[0], minimum=SIZES[-1], maximum=SIZES[0],
              description=f"The depth Runner's input size, px on the long side: {SIZES[0]}, or {SIZES[-1]} where the GPU "
                          "is short of memory. Part of the call's key: it is set, never lowered from free VRAM."),
    ParamSpec(name="strength", type="float", default=60.0, minimum=0.01,
              description="The height, in target px, that the depth's 1st to 99th percentile spans: how steeply walls tilt."),
    ParamSpec(name="deadzone", type="float", default=0.10, minimum=0.0, maximum=0.7,
              description="A slope below this stays flat: it keeps floors exactly flat."),
    ParamSpec(name="levels", type="int", default=3, minimum=1, maximum=8,
              description="The steps of tilt per side. 3 gives a quarter, a half and three quarters of the largest tilt."),
)

CHECKS = (
    CheckSpec(code="normals.not_flat_walkable", description="Walkable ground has flat normals: a walkable pixel whose "
                                                            f"normal tilts more than {TILT_LIMIT} (warning; top view)."),
    CheckSpec(code="normals.size", description="The normal map is the room's size."),
)


def _plate_size(run: StageRun) -> tuple[int, int]:
    with Image.open(run.upstream["layers"] / "plate.png") as plate:
        return plate.size


def _walkable(run: StageRun) -> np.ndarray:
    """Where the Body can stand: the Op `place` uses, from `solid`, `pit` and the Body (`place`'s own walkable.png comes later)."""
    solid = run.upstream[MASKS] / "solid.png"
    if not solid.is_file():
        raise StageFailure(f"walkable is derived from the 'solid' Mask, and the {run.asset_params['view']} view doesn't "
                           "define one; add it under [masks] in kiripix.toml")
    blocked = _read_mask(solid)
    pit = run.upstream[MASKS] / "pit.png"
    if pit.is_file():
        blocked = blocked | _read_mask(pit)
    width, height = run.settings["body"]["size"]
    return walkable(blocked, (int(width), int(height)))


def _read_mask(path: Any) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("L"), dtype=np.uint8) > 127


def _shape(decision: CurrentDecision, shape: tuple[int, int]) -> np.ndarray:
    data = decision.data
    empty = np.zeros(shape, dtype=np.bool_)
    points = [(int(x), int(y)) for x, y in data["points"]]
    if data["shape"] == "brush":
        return paint_stroke(empty, points, int(data["radius"]))
    return fill_polygon(empty, points)


def _flat_mask(run: StageRun, shape: tuple[int, int]) -> np.ndarray:
    """Where the `flatten` Decisions, replayed in order, leave the normals flat."""
    flat = np.zeros(shape, dtype=np.bool_)
    ground: np.ndarray | None = None
    for decision in run.decisions:
        if decision.name != "flatten":
            continue
        inside = _shape(decision, shape)
        if decision.data.get("walkable"):
            ground = _walkable(run) if ground is None else ground
            inside &= ground
        flat = flat & ~inside if decision.data.get("erase") else flat | inside
    return flat


def _depth_on_target(run: StageRun) -> np.ndarray:
    read = read_grid(run)
    if read is None:
        raise StageFailure("fit has no Grid transform yet")
    grid, record = read
    [call] = runner_calls(run)
    with Image.open(run.pinned(call)) as pinned:
        if pinned.mode != "I;16":
            raise StageFailure(f"the pinned depth is a {pinned.mode} image, not the 16-bit greyscale one the depth Runner "
                               f"makes; make it again: kiripix run {run.asset_id} {NORMALS_STAGE} --rerun --force")
        depth = decode(np.asarray(pinned))
    source_width, source_height = (int(n) for n in record["source"])
    on_source = np.asarray(Image.fromarray(depth, "F").resize((source_width, source_height), Image.Resampling.BICUBIC))
    return cell_means(on_source, grid.edges_x(), grid.edges_y())


def run_normals(run: StageRun) -> None:
    if _mode(run) == "off":
        return
    run.check_cancel()
    target = _depth_on_target(run)
    height = heights(target, float(run.params["strength"]))
    plate = read_rgba(run.upstream["layers"] / "plate.png")
    if height.shape != plate.shape[:2]:
        raise StageFailure(f"the depth on the Grid is {height.shape[1]}x{height.shape[0]} but the Plate is "
                           f"{plate.shape[1]}x{plate.shape[0]}: run fit again")
    found, _ = read_layer_files(run.upstream["layers"], run.asset_id)
    alphas = [read_rgba(path)[..., 3] > 0 for _, path in found]
    normal = front_normals(height, alphas, float(run.params["deadzone"]), int(run.params["levels"]), run.check_cancel)
    flat = _flat_mask(run, height.shape)
    if flat.any():
        normal = flatten(normal, flat)
    write_rgba(run.output_dir / NORMAL_FILE, normal)
    grey = np.clip(np.rint(height / max(float(run.params["strength"]), 1e-9) * 255), 0, 255).astype(np.uint8)
    picture = np.dstack([grey, grey, grey, np.full_like(grey, 255)])
    write_rgba(run.output_dir / DEPTH_FILE, picture)


def check_normals(run: StageRun) -> list[Finding]:
    path = run.output_dir / NORMAL_FILE
    if not path.is_file():
        return []
    asset = run.asset_id
    at = Position(asset=asset, stage=NORMALS_STAGE, file=NORMAL_FILE)
    normal = read_rgba(path)
    width, height = _plate_size(run)
    if normal.shape[:2] != (height, width):
        return [Finding(code="normals.size",
                        message=f"{asset} {NORMALS_STAGE}: {NORMAL_FILE} is {normal.shape[1]}x{normal.shape[0]} but the room "
                                f"is {width}x{height}",
                        position=at, fix=f"kiripix run {asset} {NORMALS_STAGE} --force")]
    if run.asset_params["view"] != "top" or not (run.upstream[MASKS] / "solid.png").is_file():
        return []
    tilted = _walkable(run) & (tilt_of(normal) > TILT_LIMIT)
    areas = walkable_islands(tilted, np.zeros_like(tilted))
    findings = []
    for number, area in enumerate(areas[:_LISTED_AREAS], start=1):
        x1, y1 = area.x + area.width - 1, area.y + area.height - 1
        decision = {"decision": "flatten", "data": {"shape": "polygon", "walkable": True,
                    "points": [[area.x, area.y], [x1, area.y], [x1, y1], [area.x, y1]]}}
        findings.append(Finding(
            code="normals.not_flat_walkable", severity="warning",
            message=f"{asset} {NORMALS_STAGE}: {area.spots} walkable pixels in the box from ({area.x}, {area.y}) to "
                    f"({x1}, {y1}) tilt their normal by more than {TILT_LIMIT} (area {number} of {len(areas)}, the largest first)",
            position=Position(asset=asset, stage=NORMALS_STAGE, file=NORMAL_FILE, x=area.x, y=area.y, width=area.width,
                              height=area.height),
            fix=f"kiripix decide {asset} {NORMALS_STAGE} --decision '{json.dumps(decision)}'"))
    return findings
