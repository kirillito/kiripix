"""What the room's `looks` and `loops` Stages share (tickets 0130 and 0189, ADR 0009): the edit pipeline and the region.

A Look is cut from an edit of the room's Source, a Loop from the room itself, and both are cut to a region that the
Owner draws. This module holds the parts that are the same:

- `EditRoom`: what everything is cut against (the fit, Source, palette image, Layer alphas, solid and the `palette`
  Stage's own parameters), read once;
- `registered` and `fitted`: an edit laid on the Source, then through the room's Grid transform;
- `paint_region`: the region, `polygon`, `brush`, `flood` and `difference` Decisions replayed in order on one owner's
  Mask. The owner is named by the Decision's `look` or `loop` field (`key`), so one set of Decisions serves both Stages;
- the Decision specs for the region, built for either Stage.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
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

from kiripix.ops import (
    difference_region,
    dilate,
    downscale,
    fill_polygon,
    flood_region,
    mask_to_source,
    paint_stroke,
    register,
    sample_nearest,
    snap_cell,
    warp_nearest,
)
from kiripix.recipes.base import BoxCorners, CurrentDecision, DecisionSpec, StageFailure, StageRun
from kiripix.recipes.common import read_grid, read_rgba
from kiripix.recipes.layers import read_layers

LOOKS_STAGE = "looks"
MASKS_STAGE = "masks"
PALETTE_STAGE = "palette"
OWNER_ID = "^[a-z0-9_]+(\\.[a-z0-9_]+)*$"  # the Marker ID rule: a Look's and a Loop's ID

# From trial 0128 (ΔE is the OKLab distance times 100, on the 3x3 mean of the fitted difference).
DIFFERENCE_TOLERANCE = 4.0  # a `difference` picks out a door leaf or a broken object whole at this
DIFFERENCE_SPECKS = 16  # pixels: a smaller piece of a `difference` is noise
SCALE_LIMIT = 0.015  # registration: the scale may differ from 1 by this much on an axis
SHIFT_LIMIT = 4.0  # registration: the shift, in target px
MISALIGNED_RESIDUAL = 0.5  # target px: the median miss of the tiles after registration
REGISTER_GROW = 48  # Source px of the region's reach that registration leaves out
FLOOD_TOLERANCE = 0.03  # OKLab distance: a `flood` Decision's default (trial 0184: 0.04 leaked into a TV's bezel)
FLOOD_TOLERANCE_MAX = 0.2

_POINTS: dict[str, Any] = {"type": "array", "items": {"type": "array", "items": {"type": "integer"},
                                                       "minItems": 2, "maxItems": 2}}


def owner_property() -> dict[str, Any]:
    return {"type": "string", "pattern": OWNER_ID}


# the region's Decisions


def polygon_decision(key: str, noun: str, shows: str) -> DecisionSpec:
    return DecisionSpec(
        name="polygon",
        description=f"Fill a polygon of a {noun}'s region (or clear it with `erase`): `points` are at least three corners "
                    f"in target pixels; the polygon closes itself and its outline is included, as in `masks`. {shows} "
                    "Regions replay in order.",
        entry_schema={
            "type": "object",
            "properties": {key: owner_property(), "erase": {"type": "boolean"}, "points": {**_POINTS, "minItems": 3}},
            "required": [key, "points"],
            "additionalProperties": False,
        },
    )


def brush_decision(key: str, noun: str) -> DecisionSpec:
    return DecisionSpec(
        name="brush",
        description=f"A brush stroke on a {noun}'s region, in target pixels (`erase` clears).",
        entry_schema={
            "type": "object",
            "properties": {key: owner_property(), "erase": {"type": "boolean"},
                           "radius": {"type": "integer", "minimum": 0}, "points": _POINTS},
            "required": [key, "radius", "points"],
            "additionalProperties": False,
        },
    )


def difference_decision(key: str, description: str) -> DecisionSpec:
    corner: dict[str, Any] = {"type": "integer", "minimum": 0}
    properties: dict[str, Any] = {
        key: owner_property(), "x0": corner, "y0": corner, "x1": corner, "y1": corner,
        "tolerance": {"type": "number", "minimum": 0},
        "specks": {"type": "integer", "minimum": 0},
    }
    return DecisionSpec(
        name="difference",
        description=description,
        entry_schema={
            "type": "object",
            "properties": properties,
            "required": [key, "x0", "y0", "x1", "y1"],
            "additionalProperties": False,
        },
        on_image=True,
    )


def flood_decision(key: str, noun: str) -> DecisionSpec:
    return DecisionSpec(
        name="flood",
        description=f"Add to a {noun}'s region the pixels of the fitted room (before the palette) that join the clicked "
                    "pixel (`x`, `y`, target px) and whose colour is within `tolerance` of its own (OKLab distance, 0 to "
                    f"{FLOOD_TOLERANCE_MAX:g}; default {FLOOD_TOLERANCE:g}; 0 is exactly equal), as `flood` on `masks` "
                    "does. Made on the fitted room: a refit or a Layer change puts it in needs-review.",
        entry_schema={
            "type": "object",
            "properties": {key: owner_property(), "x": {"type": "integer", "minimum": 0},
                           "y": {"type": "integer", "minimum": 0},
                           "tolerance": {"type": "number", "minimum": 0, "maximum": FLOOD_TOLERANCE_MAX}},
            "required": [key, "x", "y"],
            "additionalProperties": False,
        },
        on_image=True,
    )


# replaying them


def decisions_of(run: StageRun, key: str, owner: str, *names: str) -> list[CurrentDecision]:
    """The owner's current Decisions of these kinds, in order."""
    return [d for d in run.decisions if d.name in names and d.data.get(key) == owner]


def decision_box(decision: CurrentDecision) -> BoxCorners:
    data = decision.data
    return int(data["x0"]), int(data["y0"]), int(data["x1"]), int(data["y1"])


def paint_region(run: StageRun, key: str, owner: str, shape: tuple[int, int], room: Any, fitted: Any | None) -> Any:
    """The owner's region: its `polygon`, `brush`, `flood` and `difference` Decisions replayed in order. `room` is the
    fitted room, what a `flood` is measured on and a `difference` is measured against. Without `fitted` (the edit,
    fitted) a `difference` adds nothing: that is the part registration and regrade may measure outside of."""
    region = np.zeros(shape, dtype=np.bool_)
    for decision in decisions_of(run, key, owner, "polygon", "brush", "flood", "difference"):
        data = decision.data
        if decision.name == "polygon":
            region = fill_polygon(region, [(int(x), int(y)) for x, y in data["points"]],
                                  erase=bool(data.get("erase", False)))
        elif decision.name == "brush":
            region = paint_stroke(region, [(int(x), int(y)) for x, y in data["points"]], int(data["radius"]),
                                  erase=bool(data.get("erase", False)))
        elif decision.name == "flood":
            try:
                region |= flood_region(room, int(data["x"]), int(data["y"]), float(data.get("tolerance", FLOOD_TOLERANCE)))
            except ValueError as error:
                raise StageFailure(str(error)) from None
        elif fitted is not None:
            region |= difference_region(room, fitted, decision_box(decision),
                                        float(data.get("tolerance", DIFFERENCE_TOLERANCE)),
                                        int(data.get("specks", DIFFERENCE_SPECKS)))
    return region


# the edit pipeline


def write_mask(path: Path, mask: Any) -> None:
    """A Mask as a 1-bit PNG; core swaps the Stage's folder into place whole, so the write is atomic."""
    Image.fromarray(mask).save(path, format="PNG")


def read_mask(path: Path) -> Any:
    with Image.open(path) as image:
        return np.asarray(image.convert("1"), dtype=np.bool_).copy()


def registered(run: StageRun, source: Any, edit: Any, static: Any, grid: Any) -> tuple[Any, dict[str, Any] | None]:
    """The edit laid on the Source, and what the registration found (None when `register` is off)."""
    if not bool(run.params["register"]):
        return edit, None
    height, width = source.shape[:2]
    exclude = dilate(mask_to_source(static, grid, width, height), REGISTER_GROW) if static.any() else None
    run.check_cancel()
    alignment = register(source, edit, exclude)
    scale = (float(grid.scale_x), float(grid.scale_y))
    problems = []
    for axis, value in (("x", alignment.scale_x), ("y", alignment.scale_y)):
        if abs(value - 1) > SCALE_LIMIT:
            problems.append(f"the edit's scale on {axis} is {value:.4f}, outside {1 - SCALE_LIMIT:.3f} to "
                            f"{1 + SCALE_LIMIT:.3f}")
    for axis, shift, per in (("x", alignment.shift_x, scale[0]), ("y", alignment.shift_y, scale[1])):
        if abs(shift) / per > SHIFT_LIMIT:
            problems.append(f"the edit is shifted {abs(shift) / per:.1f} target px on {axis}, over {SHIFT_LIMIT:g}")
    residual = alignment.residual / ((scale[0] + scale[1]) / 2)
    if alignment.tiles and residual > MISALIGNED_RESIDUAL:
        problems.append(f"the edit's tiles still miss the Source by {residual:.2f} target px (median) after "
                        f"registration, over {MISALIGNED_RESIDUAL:g}: it isn't a rescaled or shifted copy of it")
    applied = alignment.tiles > 0 and not problems and not alignment.negligible(width, height)
    record = {"scale": [alignment.scale_x, alignment.scale_y], "shift": [alignment.shift_x, alignment.shift_y],
              "residual": residual, "tiles": alignment.tiles, "applied": applied, "problems": problems}
    return (warp_nearest(edit, alignment) if applied else edit), record


def fitted(record: dict[str, Any], grid: Any, edit: Any) -> Any:
    """The edit through the room's Grid transform, as `fit` did the Source."""
    return downscale(edit, grid) if record["mode"] == "downscale" else sample_nearest(edit, grid)


class EditRoom:
    """What every Look and Loop is cut against, read once."""

    def __init__(self, run: StageRun) -> None:
        read = read_grid(run)
        assert read is not None  # `fit` is upstream, and built
        self.grid, self.record = read
        self.source = read_rgba(run.upstream["source"] / "source.png")
        self.fit = read_rgba(run.upstream["fit"] / "fit.png")
        self.composite = read_rgba(run.upstream[PALETTE_STAGE] / "palette.png")
        upstream = run.upstream["layers"]
        self.layers = [(str(entry["id"]), read_rgba(upstream / str(entry["file"]))[..., 3] > 0)
                       for entry in read_layers(upstream, run.asset_id)]
        self.mapping = replace(run, params=dict(run.upstream_params[PALETTE_STAGE]))  # the Stage's own parameters
        solid = run.upstream[MASKS_STAGE] / "solid.png"
        self.solid = read_mask(solid) if solid.is_file() else np.zeros(self.fit.shape[:2], dtype=np.bool_)
        self.strip = np.zeros(self.fit.shape[:2], dtype=np.bool_)  # the padded cells `fit` added: solid, from grid.json
        self.strip[:, self.grid.cells_x:] = True
        self.strip[self.grid.cells_y:, :] = True
        self.cell = int(run.upstream_params[MASKS_STAGE].get("snap_cell", 0))

    def own_solid(self, decisions: list[CurrentDecision]) -> Any | None:
        """A `solid`: the room's with these `solid` Decisions replayed, or None when there are none."""
        if not decisions:
            return None
        mask = self.solid & ~self.strip
        for decision in decisions:
            data = decision.data
            points = [(int(x), int(y)) for x, y in data["points"]]
            erase = bool(data.get("erase", False))
            mask = (paint_stroke(mask, points, int(data["radius"]), erase=erase) if "radius" in data
                    else fill_polygon(mask, points, erase=erase))
        return (snap_cell(mask, self.cell) if self.cell > 1 else mask) | self.strip
