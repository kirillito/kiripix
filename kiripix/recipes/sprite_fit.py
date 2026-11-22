"""The sprite Kind's `fit` Stage (spec §6.4, ticket 0179): every frame onto the target pixel grid, its feet found, and every frame
placed on one cell around one pivot. It writes the character's frame list, so `palette`, `finish`, `sheet` and `export` read it as
they read `render`'s.

`grid` (the default) detects each frame's pixel grid (`detect_grid`; PixelLab's 1:1 frames have scale 1 and an upscaled export is
undone) and samples it. All frames must share one scale: the most common one is used for every frame, and a frame that detects
another is named by `fit.grid_differs`. `downscale` is for AI images: one Grid for the whole Asset, the scale that brings the
reference frame's opaque height (the first frame of `idle` in `s`, else the first frame) to `height`, with the line-keeping
downscale. Either way the alpha ends binary, and `chroma` first clears a flat background colour.

The feet of a frame are `feet_point` of its alpha. A direction's pivot is the ground point a body's would be (ticket 0318): the
median of its stationary clips' feet (of all its frames when it has no stationary clip), raised by `GROUND_RATIO` (0.08) of the figure's
height (the median height of those frames over every direction, so the offset is the same in each), unless a `pivot` Decision
says where it is (the Decision's point is the pivot, with no offset). A frame is placed with its direction's pivot on
the cell's pivot, so the figure keeps its place on the canvas it came on and a walk's stride doesn't move the body; with
`align_feet`, a stationary clip's frame is placed by its own feet instead. The cell is the smallest that holds every frame's opaque
pixels around the pivot with 1 px to spare on each side for `finish`'s outline.

`anchor` (ticket 0362) says where the pivot is instead: `feet` (the default, all of the above), `centre` or `x,y`, in each direction's
first fitted frame; a `pivot` Decision still wins. `effect` (ticket 0362, default off) is for a battle effect: the cell holds every
frame's whole area around the anchor, not its opaque box (a 32 px telegraph stays 32), `render.json` says `effect`, `fit.height` is
quiet, and `finish` with `outline=false` cuts the spare pixel again. A clip's `ticks` (a `clip` Decision) go on into `render.json`.

Output in `work/fit/`: `color/<clip>/<dir>/<NNN>.png` (every frame the cell's size), `render.json` (the character's schema: `frame`,
`pivot`, `directions`, `clips`, each frame's `files.color`, `pivot` (the cell's) and `feet` (measured, in the cell)) and
`fit.json` (the grid, the pivots, `ground` (the ratio, figure height and px offset used), and what the Checks report).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks import Finding, Position
from kiripix.ops import (Grid, alpha_by_vote, alpha_coverage, chroma_key, detect_grid, dither_alpha, downscale, feet_point,
                         sample_nearest)
from kiripix.recipes.base import DecisionSpec, ParamSpec, StageFailure, StageRun
from kiripix.recipes.clips import DIRECTIONS
from kiripix.recipes.common import read_rgba, write_rgba
from kiripix.recipes.render import RENDER_SCHEMA_VERSION
from kiripix.recipes.sprite_frames import FRAMES_FILE

FIT_FILE = "fit.json"
RENDER_FILE = "render.json"
FIT_SCHEMA_VERSION = 1
GAME_BAND = (46, 58)  # the game's adults are this many px tall (DEC-043)
GROW_NOTICE = 4  # px a frame must reach past every other frame for `fit.cell_grew`
_CHROMA = re.compile("^#[0-9A-Fa-f]{6}$")
OPAQUE_FROM = 128
# A body's pivot is the ground point under its centre, and in the 30 degree view its shoes reach below it on screen (ticket
# 0318): measured on the mc03 bodies' built `idle` (56 to 60 px, outline included), 4 to 5 px in `s`, 2 to 6 in the other
# diagonals. A sprite's pivot sits this share of its figure's height above its measured feet, so both stand on one ground line.
GROUND_RATIO = 0.08
ANCHOR_FEET = "feet"
ANCHOR_CENTRE = "centre"
_ANCHOR_POINT = re.compile(r"^(\d+),(\d+)$")
ALPHA_VOTE = "vote"
ALPHA_DITHER = "dither"

FIT_PARAMS = (
    ParamSpec(name="mode", type="choice", choices=["grid", "downscale"], default="grid",
              description="grid: detect each frame's pixel grid (a PixelLab export is pixel art already; an upscaled one is "
                          "undone); downscale: one scale for every frame, for AI images, that brings the reference frame's "
                          "figure to `height`."),
    ParamSpec(name="height", type="int", minimum=1,
              description="With mode=downscale, the figure's height in px; the Project's [character] height when unset."),
    ParamSpec(name="chroma", type="str", default="",
              description="A #RRGGBB background colour to clear before fitting, or empty for none."),
    ParamSpec(name="align_feet", type="bool", default=False,
              description="Place each frame of a stationary clip by its own feet, not its direction's pivot, so a figure that "
                          "hops by a pixel doesn't move (the sheet's pivot-drift Check). Off keeps the source as it is."),
    ParamSpec(name="anchor", type="str", default=ANCHOR_FEET,
              description="Where the pivot is: `feet` (the figure's ground point, as for a body), `centre` (the middle of the "
                          "direction's first frame), or `x,y` in the fitted frame's pixels from its top left, such as 11,18. An "
                          "effect's pivot is its own anchor, not a ground point. A `pivot` Decision still wins."),
    ParamSpec(name="effect", type="bool", default=False,
              description="A battle effect, not a figure: the cell is the frames' own size around the anchor (not the opaque "
                          "box), fit.height and palette.sprite_regions stay quiet, a blank frame is a sheet.empty_frame warning, "
                          "and the export has no normal.png (the sprite is flat). With finish outline=false the cell takes no "
                          "spare pixel."),
    ParamSpec(name="alpha", type="choice", choices=[ALPHA_VOTE, ALPHA_DITHER], default=ALPHA_VOTE,
              description="What partial alpha (a glow's haze) becomes: `vote`, each cell opaque or clear by the majority of its "
                          "pixels (a haze under half is lost), or `dither`, a fixed ordered pattern of opaque and clear pixels "
                          "whose density is the haze's alpha. fit.alpha_partial says how much the source had either way."),
    ParamSpec(name="alpha_pattern", type="int", minimum=2, maximum=8, default=4,
              description="With alpha=dither, the Bayer matrix's side: 2 (coarse), 4 or 8 (fine); no other number."),
)

PIVOT = DecisionSpec(
    name="pivot",
    description="Where the pivot (the ground point under the figure) is, when the measured one is wrong (a shadow or a tail at "
                "the lowest row): `x` and `y` in the frame's target pixels, from its top left, for one `direction` or, with "
                "none, for all of them. It is used as it is, with no ground offset above the feet. A later "
                "Decision wins; `undo` brings the old pivot back.",
    entry_schema={
        "type": "object",
        "properties": {"x": {"type": "integer", "minimum": 0}, "y": {"type": "integer", "minimum": 0},
                       "direction": {"enum": list(DIRECTIONS)}},
        "required": ["x", "y"], "additionalProperties": False,
    },
)


@dataclass
class _Frame:
    clip: str
    direction: str
    index: int
    image: np.ndarray  # fitted, binary alpha
    feet: tuple[int, int] | None
    box: tuple[int, int, int, int] | None  # x0, y0, x1, y1 of the opaque pixels, both included


def _json(path: Any, what: str) -> dict[str, Any]:
    try:
        document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StageFailure(f"{what} has no {path.name}; run it again") from None
    return document


def _key(run: StageRun) -> tuple[int, int, int] | None:
    colour = str(run.params.get("chroma", ""))
    if not colour:
        return None
    if not _CHROMA.match(colour):
        raise StageFailure(f"the chroma colour {colour!r} isn't #RRGGBB or empty; kiripix set {run.asset_id} fit chroma=#00FF00",
                           fix=f"kiripix set {run.asset_id} fit chroma=")
    return int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)


def anchor_of(run: StageRun) -> str | tuple[int, int]:
    """The `anchor` parameter: `feet`, `centre`, or the point `x,y` it names; a StageFailure for anything else."""
    text = str(run.params.get("anchor", ANCHOR_FEET)).strip().replace(" ", "")
    if text in (ANCHOR_FEET, ANCHOR_CENTRE):
        return text
    found = _ANCHOR_POINT.match(text)
    if found is None:
        raise StageFailure(f"the anchor {text!r} isn't feet, centre or x,y (whole pixels); kiripix set {run.asset_id} fit anchor=centre",
                           code="fit.anchor_invalid", fix=f"kiripix set {run.asset_id} fit anchor=feet")
    return int(found.group(1)), int(found.group(2))


def _scale_text(scale: Fraction) -> str:
    return str(scale.numerator) if scale.denominator == 1 else f"{scale.numerator}/{scale.denominator}"


def _box(alpha: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(alpha > 0)
    return None if len(xs) == 0 else (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def _median(values: list[int]) -> int:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle] + 1) // 2  # halves round up


def _downscale_grid(reference: np.ndarray, height: int, asset: str) -> tuple[Fraction, int, int]:
    """The scale that brings `reference`'s figure to `height` rows, and the offsets that put its top and left on cell edges, so
    the figure is exactly `height` cells tall when its rows are all there."""
    box = _box(np.where(reference[..., 3] >= OPAQUE_FROM, 255, 0))
    if box is None:
        raise StageFailure("the reference frame is empty, so there is no figure to scale")
    x0, y0, _, y1 = box
    figure = y1 - y0 + 1
    if figure < height:
        raise StageFailure(f"the figure is {figure} px tall, shorter than the {height} px asked for, and downscale only shrinks",
                           code="fit.too_small", fix=f"kiripix set {asset} fit height={figure}")
    scale = Fraction(figure, height)
    offsets = []
    for start in (x0, y0):
        cells = int(start / scale)
        offsets.append(start - (cells * scale.numerator) // scale.denominator)
    return scale, offsets[0], offsets[1]


def _grid_for(scale: Fraction, offset_x: int, offset_y: int, width: int, height: int) -> Grid:
    """The one Grid of an Asset over a frame of this size: as many whole cells as fit after the offsets."""

    def cells(size: int, offset: int) -> int:
        count = int((size - offset) / scale)
        while count > 0 and offset + (count * scale.numerator) // scale.denominator > size:
            count -= 1
        return count

    columns, rows = cells(width, offset_x), cells(height, offset_y)
    if columns < 1 or rows < 1:
        raise StageFailure(f"a {width} x {height} frame holds no whole cell of the scale {_scale_text(scale)}")
    return Grid(scale, scale, offset_x, offset_y, columns, rows)


def _listed(document: dict[str, Any]) -> list[tuple[dict[str, Any], str, dict[str, Any]]]:
    return [(clip, direction, frame) for clip in document["clips"] for direction in DIRECTIONS
            for frame in clip["directions"].get(direction, [])]


def run_sprite_fit(run: StageRun) -> None:
    document = _json(run.upstream["frames"] / FRAMES_FILE, "frames")
    listed = _listed(document)
    mode = str(run.params.get("mode", "grid"))
    anchor = anchor_of(run)
    key = _key(run)
    alpha_mode = str(run.params.get("alpha", ALPHA_VOTE))
    pattern = int(run.params.get("alpha_pattern", 4))
    if pattern not in (2, 4, 8):
        raise StageFailure(f"the alpha_pattern {pattern} isn't 2, 4 or 8; kiripix set {run.asset_id} fit alpha_pattern=4",
                           code="fit.alpha_pattern_invalid", fix=f"kiripix set {run.asset_id} fit alpha_pattern=4")
    partial: list[dict[str, Any]] = []
    target = int(run.params.get("height") or run.settings.get("character.height") or 52)
    folder = run.upstream["frames"]

    def load(frame: dict[str, Any]) -> np.ndarray:
        image = read_rgba(folder / str(frame["file"]))
        return chroma_key(image, key) if key is not None else image

    grids: list[Grid | None] = []
    differs: list[dict[str, Any]] = []
    grid_record: dict[str, Any] = {}
    if mode == "downscale":
        idle = next(((c, d, f) for c, d, f in listed if c["name"] == "idle" and d == "s"), listed[0])
        reference = load(idle[2])
        scale, offset_x, offset_y = _downscale_grid(reference, target, run.asset_id)
        grid_record = {"scale": _scale_text(scale), "offset_x": offset_x, "offset_y": offset_y}
    else:
        detected: list[Grid] = []
        for number, (clip, direction, frame) in enumerate(listed):
            run.check_cancel()
            run.progress(number, len(listed) * 2, "finding the pixel grid")
            detected.append(detect_grid(load(frame)))
        common = Counter((g.scale_x, g.scale_y) for g in detected)
        (scale_x, scale_y), _ = sorted(common.items(), key=lambda item: (-item[1], item[0]))[0]
        grid_record = {"scale": _scale_text(scale_x) if scale_x == scale_y else f"{_scale_text(scale_x)}x{_scale_text(scale_y)}"}
        for (clip, direction, frame), grid in zip(listed, detected, strict=True):
            if (grid.scale_x, grid.scale_y) == (scale_x, scale_y):
                grids.append(grid)
                continue
            differs.append({"clip": clip["name"], "direction": direction, "index": int(frame["index"]),
                            "scale": _scale_text(grid.scale_x) if grid.scale_x == grid.scale_y
                            else f"{_scale_text(grid.scale_x)}x{_scale_text(grid.scale_y)}"})
            grids.append(None)

    fitted: list[_Frame] = []
    for number, (clip, direction, frame) in enumerate(listed):
        run.check_cancel()
        run.progress(len(listed) + number if mode == "grid" else number, len(listed) * (2 if mode == "grid" else 1),
                     f"fitting {clip['name']}/{direction}/{int(frame['index']):03d}")
        source = load(frame)
        height_px, width_px = source.shape[:2]
        if mode == "downscale":
            grid = _grid_for(scale, offset_x, offset_y, width_px, height_px)
        else:
            found = grids[number]
            try:
                grid = found if found is not None else Grid.uniform(int(scale_x), 0, 0, width_px, height_px)
            except ValueError as error:
                raise StageFailure(str(error)) from None
        coverage = alpha_coverage(source, grid)
        hazy = int(((coverage != 0) & (coverage != 255)).sum())
        if hazy:
            partial.append({"clip": clip["name"], "direction": direction, "index": int(frame["index"]), "cells": hazy,
                            "of": int((coverage != 0).sum())})
        colour = source
        if alpha_mode == ALPHA_DITHER and hazy:  # every pixel with any alpha carries its colour into the vote
            colour = source.copy()
            colour[..., 3] = np.where(source[..., 3] > 0, 255, 0)
        if mode == "downscale":
            image = downscale(colour, grid)
        else:
            image = alpha_by_vote(sample_nearest(colour, grid), colour, grid)
        if alpha_mode == ALPHA_DITHER and hazy:
            image = image.copy()
            image[..., 3] = np.where(image[..., 3] > 0, coverage, 0)
            image = dither_alpha(image, pattern)
            image[image[..., 3] == 0] = 0
        fitted.append(_Frame(clip["name"], direction, int(frame["index"]), image, feet_point(image[..., 3]), _box(image[..., 3])))

    wanted = [d for d in DIRECTIONS if d in document["directions"]]
    stationary = {str(c["name"]) for c in document["clips"] if c["stationary"]}
    measured = [f for f in fitted if f.feet is not None and f.box is not None]
    standing = [f for f in measured if f.clip in stationary] or measured
    standing_height = _median([f.box[3] - f.box[1] + 1 for f in standing if f.box]) if standing else 0
    ground = int(GROUND_RATIO * standing_height + 0.5)  # one offset for every direction, halves round up
    pivots: dict[str, tuple[int, int]] = {}
    for direction in wanted:
        here = [f for f in fitted if f.direction == direction and f.feet is not None]
        chosen = [f for f in here if f.clip in stationary] or here
        if chosen:
            pivots[direction] = (_median([f.feet[0] for f in chosen if f.feet]),
                                 _median([f.feet[1] for f in chosen if f.feet]) - ground)
        else:
            first = next((f for f in fitted if f.direction == direction), None)
            if first is not None:
                pivots[direction] = (first.image.shape[1] // 2, first.image.shape[0] - 1)
    if anchor != ANCHOR_FEET:  # an effect's own anchor, in the direction's first frame, instead of the ground point
        for direction in wanted:
            first = next((f for f in fitted if f.direction == direction), None)
            if first is not None:
                pivots[direction] = (anchor if isinstance(anchor, tuple)
                                     else (first.image.shape[1] // 2, first.image.shape[0] // 2))
    for decision in run.decisions:
        if decision.name != PIVOT.name:
            continue
        for direction in ([decision.data["direction"]] if "direction" in decision.data else wanted):
            if direction in pivots:
                pivots[direction] = (int(decision.data["x"]), int(decision.data["y"]))
    align = bool(run.params.get("align_feet", False))
    effect = bool(run.params.get("effect", False))

    def used(frame: _Frame) -> tuple[int, int]:
        if align and frame.clip in stationary and frame.feet is not None:
            return frame.feet[0], frame.feet[1] - ground
        return pivots[frame.direction]

    needs: dict[str, list[tuple[int, int]]] = {"left": [], "right": [], "top": [], "bottom": []}  # px each frame needs, by index
    for number, current in enumerate(fitted):
        px, py = used(current)
        reach: list[tuple[str, int]]
        if effect:  # the frame as it came, blank or not: an effect keeps its size around its anchor
            frame_h, frame_w = current.image.shape[:2]
            reach = [("left", px), ("right", frame_w - px), ("top", py), ("bottom", frame_h - py)]
        elif current.box is None:
            continue
        else:
            x0, y0, x1, y1 = current.box
            reach = [("left", px - x0), ("right", x1 + 1 - px), ("top", py - y0), ("bottom", y1 + 1 - py)]
        for side, value in reach:
            needs[side].append((max(value, 0), number))
    room = {side: max((v for v, _ in found), default=0) + 1 for side, found in needs.items()}
    cell_width, cell_height = room["left"] + room["right"], room["top"] + room["bottom"]
    cell_pivot = (room["left"], room["top"])

    grew: list[dict[str, Any]] = []
    reaching: dict[int, list[str]] = {}
    extra: dict[int, int] = {}
    for side, needed in needs.items():
        ranked = sorted(needed, reverse=True)
        if len(ranked) >= 2 and ranked[0][0] - ranked[1][0] >= GROW_NOTICE:
            reaching.setdefault(ranked[0][1], []).append(side)
            extra[ranked[0][1]] = max(extra.get(ranked[0][1], 0), ranked[0][0] - ranked[1][0])
    for number, sides in sorted(reaching.items()):
        f = fitted[number]
        grew.append({"clip": f.clip, "direction": f.direction, "index": f.index, "sides": sides, "by": extra[number]})

    entries: list[dict[str, Any]] = []
    placed: dict[tuple[str, str, int], tuple[int, int] | None] = {}
    tallest: dict[str, Any] | None = None
    for number, current in enumerate(fitted):
        run.check_cancel()
        px, py = used(current)
        dx, dy = cell_pivot[0] - px, cell_pivot[1] - py
        cell = np.zeros((cell_height, cell_width, 4), dtype=np.uint8)
        h, w = current.image.shape[:2]
        x0, y0, x1, y1 = max(dx, 0), max(dy, 0), min(dx + w, cell_width), min(dy + h, cell_height)
        if x1 > x0 and y1 > y0:
            cell[y0:y1, x0:x1] = current.image[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
        name = f"color/{current.clip}/{current.direction}/{current.index:03d}.png"
        (run.output_dir / name).parent.mkdir(parents=True, exist_ok=True)
        write_rgba(run.output_dir / name, cell)
        placed[(current.clip, current.direction, current.index)] = None if current.feet is None else (current.feet[0] + dx, current.feet[1] + dy)
        if current.box is not None:
            figure = current.box[3] - current.box[1] + 1
            if tallest is None or figure > tallest["height"]:
                tallest = {"height": figure, "clip": current.clip, "direction": current.direction, "index": current.index}

    for clip in document["clips"]:
        directions: dict[str, list[dict[str, Any]]] = {}
        for direction in wanted:
            frames = []
            for frame in clip["directions"].get(direction, []):
                index = int(frame["index"])
                item: dict[str, Any] = {"index": index, "source_frame": index,
                                        "files": {"color": f"color/{clip['name']}/{direction}/{index:03d}.png"},
                                        "pivot": [float(cell_pivot[0]), float(cell_pivot[1])]}
                feet = placed[(clip["name"], direction, index)]
                if feet is not None:
                    item["feet"] = [float(feet[0]), float(feet[1])]
                frames.append(item)
            if frames:
                directions[direction] = frames
        entries.append({"name": clip["name"], "fps": int(clip["fps"]), "loop": bool(clip["loop"]),
                        "stationary": bool(clip["stationary"]), "root_motion": False,
                        **({"ticks": [int(t) for t in clip["ticks"]]} if "ticks" in clip else {}), "directions": directions})
    render = {"schema_version": RENDER_SCHEMA_VERSION, "kind": "sprite", "height": target,
              "frame": {"width": cell_width, "height": cell_height},
              "pivot": [float(cell_pivot[0]), float(cell_pivot[1])], "materials": [], "passes": ["color"],
              **({"effect": True} if effect else {}),
              "directions": [d for d in wanted if any(d in e["directions"] for e in entries)], "clips": entries}
    (run.output_dir / RENDER_FILE).write_text(json.dumps(render, indent=1) + "\n", encoding="utf-8")
    record = {"schema_version": FIT_SCHEMA_VERSION, "mode": mode, **grid_record, "chroma": str(run.params.get("chroma", "")),
              "align_feet": align, "target_height": target, "tallest": tallest, "grid_differs": differs, "grew": grew,
              "pivots": {d: list(p) for d, p in pivots.items()},
              "ground": {"ratio": GROUND_RATIO, "figure": standing_height, "offset": ground}, "cell": [cell_width, cell_height],
              **({"anchor": anchor if isinstance(anchor, str) else list(anchor)} if anchor != ANCHOR_FEET else {}),
              **({"effect": True} if effect else {}),
              # only when there is some, so a sprite without partial alpha writes the same bytes as before
              **({"alpha": alpha_mode, "alpha_pattern": pattern, "alpha_partial": partial} if partial else {})}
    (run.output_dir / FIT_FILE).write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")


def check_sprite_fit(run: StageRun) -> list[Finding]:
    """`fit.grid_differs`, `fit.alpha_partial` (on the source, and on the output), `fit.height` and `fit.cell_grew`."""
    try:
        record = json.loads((run.output_dir / FIT_FILE).read_text(encoding="utf-8"))
        render = json.loads((run.output_dir / RENDER_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    asset = run.asset_id
    findings: list[Finding] = []
    if record["grid_differs"]:
        named = ", ".join(f"{d['clip']}/{d['direction']}/{d['index']} ({d['scale']})" for d in record["grid_differs"])
        first = record["grid_differs"][0]
        findings.append(Finding(
            code="fit.grid_differs",
            message=f"every frame must share one scale ({record['scale']}), and these detect another: {named}",
            position=Position(asset=asset, stage="fit", field=f"{first['clip']}/{first['direction']}/{first['index']}"),
            owner_action="Export every frame at the same scale, or, for an AI image, set mode=downscale: "
                         f"kiripix set {asset} fit mode=downscale"))
    if record.get("alpha_partial"):  # the source's own partial alpha, whatever `alpha` did with it
        hazy = record["alpha_partial"]
        cells, of = sum(int(i["cells"]) for i in hazy), sum(int(i["of"]) for i in hazy)
        first = hazy[0]
        named = f"{first['clip']}/{first['direction']}/{first['index']}"
        share = f"{cells} of {of} pixels ({100 * cells / of:.0f} %) in {len(hazy)} frame{'s' if len(hazy) != 1 else ''}, from {named}"
        if record["alpha"] == ALPHA_DITHER:
            findings.append(Finding(
                code="fit.alpha_partial", severity="warning",
                message=f"the source has partial alpha on {share}; alpha=dither turned it into a Bayer {record['alpha_pattern']} "
                        "pattern of opaque and clear pixels",
                position=Position(asset=asset, stage="fit", field=named),
                owner_action="Nothing is needed if the pattern is the haze you want. alpha=vote would make each pixel opaque "
                             f"or clear by its cell's majority instead: kiripix set {asset} fit alpha=vote"))
        else:
            findings.append(Finding(
                code="fit.alpha_partial", severity="warning",
                message=f"the source has partial alpha on {share}; alpha=vote made each of them opaque or clear by its cell's "
                        "majority, so a haze under half is lost; alpha=dither would keep it as a fixed pattern of opaque and "
                        "clear pixels",
                position=Position(asset=asset, stage="fit", field=named),
                fix=f"kiripix set {asset} fit alpha=dither"))
    for clip in render["clips"]:
        for direction, frames in clip["directions"].items():
            for frame in frames:
                name = str(frame["files"]["color"])
                path = run.output_dir / name
                if not path.is_file():
                    continue
                alpha = read_rgba(path)[..., 3]
                if bool(((alpha != 0) & (alpha != 255)).any()):
                    findings.append(Finding(
                        code="fit.alpha_partial", message=f"{name} has partial alpha; a pixel is opaque or clear",
                        position=Position(asset=asset, stage="fit", file=name,
                                          field=f"{clip['name']}/{direction}/{frame['index']}"),
                        fix=f"kiripix run {asset} fit --force"))
    tallest = record["tallest"]
    if tallest is not None and not record.get("effect"):  # an effect is no figure: its height is its own
        low, high = GAME_BAND
        findings.append(Finding(
            code="fit.height", severity="info",
            message=f"the tallest figure is {tallest['height']} px ({tallest['clip']}/{tallest['direction']}/"
                    f"{tallest['index']}); the target height is {record['target_height']} px and the game's characters are "
                    f"{low} to {high} px",
            position=Position(asset=asset, stage="fit", field=f"{tallest['clip']}/{tallest['direction']}/{tallest['index']}"),
            owner_action="Nothing is needed if this is the size you want. To scale an AI image to a height: "
                         f"kiripix set {asset} fit mode=downscale height=<px>."))
    for item in record["grew"]:
        findings.append(Finding(
            code="fit.cell_grew", severity="info",
            message=f"{item['clip']}/{item['direction']}/{item['index']} widened the cell: it reaches {item['by']} px further "
                    f"than any other frame ({', '.join(item['sides'])}); the cell is {record['cell'][0]} x {record['cell'][1]} px",
            position=Position(asset=asset, stage="fit", field=f"{item['clip']}/{item['direction']}/{item['index']}"),
            owner_action="Check the frame for stray pixels. If its feet were found wrong, put them where they belong with a "
                         f"`pivot` Decision on {asset} fit."))
    return findings
