"""The room Recipe (spec §6.1): brief, source, fit, layers, masks, palette, place, reach, export."""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from kiripix.checks import Finding, Position
from kiripix.recipes.base import (
    FIT_PARAMS,
    PALETTE_PARAMS,
    PICK,
    PLATE,
    CheckSpec,
    ClickPoint,
    BoxCorners,
    CurrentDecision,
    DecisionSpec,
    KindSpec,
    NeedsInput,
    ParamSpec,
    LayerStatsHooks,
    ReachHooks,
    RunnerCall,
    SegmentHooks,
    SortPosition,
    StageFailure,
    StageInputs,
    StageRun,
    StageSpec,
    box_decision,
    chain,
    point_decision,
)
from kiripix.ops import (
    collision_shapes,
    contours,
    fill_polygon,
    flood_region,
    narrowest_gaps,
    open_edges,
    navigation_polygon,
    paint_stroke,
    parse_hex,
    reachable,
    simplify,
    snap_cell,
    split_painted,
    walkable,
    walkable_islands,
    wall_off,
)
from kiripix.ops.masks import RGB, SIDES
from kiripix.recipes.common import (
    box_of,
    box_params,
    padded_click,
    whole_tiles,
    box_problem,
    check_fit,
    check_unchanged,
    click_groups,
    click_params,
    lift_call,
    read_grid,
    read_rgba,
    run_fit,
    run_source,
    runner_mask_to_target,
    source_needs_input,
    stored_image,
)
from kiripix.recipes.layers import (
    DECISIONS as LAYER_DECISIONS,
    DIFFERENCE,
    GROW,
    MIN_PIECE,
    check_layers,
    needs_input as layers_needs_input,
    run_layers,
    runner_calls as layers_runner_calls,
)
from kiripix.recipes.layers import LAYER_ID, LAYERS_FILE, layer_file, read_layer_files, read_layers, read_removed
from kiripix.recipes.room_palette import (
    after_overrides as palette_after_overrides,
    check_room_palette,
    run_room_palette,
)
from kiripix.runners import SEGMENTER

# brief


def _brief(run: StageRun) -> None:
    """Writes the brief; rendering it into a generation prompt waits for `gen` (M4)."""
    brief = {
        "width": run.params["width"],
        "height": run.params["height"],
        "view": run.asset_params["view"],
        "mood": run.params["mood"],
        "tile": run.settings["project.tile"],
    }
    (run.output_dir / "brief.json").write_text(json.dumps(brief, indent=2) + "\n", encoding="utf-8")


def _whole_tiles(size: int, tile: int) -> int:
    """Rounded up, so that a room asked to fill the screen still does."""
    return whole_tiles(size, tile)


def _check_brief(run: StageRun) -> list[Finding]:
    brief = json.loads((run.output_dir / "brief.json").read_text(encoding="utf-8"))
    width, height, tile = int(brief["width"]), int(brief["height"]), int(brief["tile"])
    if width % tile == 0 and height % tile == 0:
        return []
    return [
        Finding(
            code="brief.size_not_tiles",
            message=f"the brief's size {width}x{height} isn't a whole number of {tile} px tiles",
            position=Position(asset=run.asset_id, stage="brief",
                              field="stages.brief.width" if width % tile else "stages.brief.height"),
            fix=f"kiripix set {run.asset_id} brief width={_whole_tiles(width, tile)} "
                f"height={_whole_tiles(height, tile)}",
        )
    ]


# source: the Variants are src/<hash>.png, imported (or, from M4, generated); the Pick chooses one.


# source and fit: the shared work is in `kiripix.recipes.common`.


def _fit(run: StageRun) -> None:
    run_fit(run, run.upstream["source"] / "source.png")


# layers: the Plate and the foreground Layers, in `kiripix.recipes.layers`.


# masks: the Decisions replayed in order onto the Plate's size, one 1-bit PNG per painted Mask of the room's view.
#
# A `click` segments the object under it: one Runner call, and a positive click adds its result to the Mask, a negative
# click takes it away from the Mask (whatever put it there) at its place in the replay. So a new object keeps the pinned
# results of the earlier ones. The Runner works on the Source, capped; the clicks map to it through the Grid transform,
# and its Mask maps back through the same transform when the Stage replays (ADR 0004).

LAYERS_STAGE = "layers"
MASKS_STAGE = "masks"


@dataclass(frozen=True)
class _ViewMasks:
    """The room's view's Masks from `[masks.<view>]`, partitioned once."""

    painted: dict[str, str]  # name to colour, in the project file's order
    derived: list[str]
    colours: list[tuple[RGB, list[str]]]  # the defined colours in order: each painted Mask's own, then the imports


def _view_masks(run: StageRun) -> _ViewMasks:
    entries: dict[str, Any] = dict(run.settings["masks"][str(run.asset_params["view"])])
    table: dict[str, list[str]] = entries.pop("import", {})
    painted = {name: str(entry["colour"]) for name, entry in entries.items() if not entry.get("derived", False)}
    derived = [name for name, entry in entries.items() if entry.get("derived", False)]
    colours = [(_rgb(colour), [name]) for name, colour in painted.items()]
    colours.extend((_rgb(colour), list(names)) for colour, names in table.items())
    return _ViewMasks(painted, derived, colours)


def _rgb(colour: str) -> RGB:
    entry = parse_hex(colour).entries[0]
    return entry.r, entry.g, entry.b


def _masks_needs_input(run: StageRun) -> NeedsInput | None:
    read = read_grid(run)
    undo = f"Undo it: kiripix undo {run.asset_id} {MASKS_STAGE}"
    for group in click_groups(run.decisions):
        first = group[0]
        if first.name == "box":
            problem = (box_problem(box_of(first), read[0].width, read[0].height, read[0].pad_right, read[0].pad_bottom)
                       if read is not None else None)
            if problem is not None:
                x0, y0, x1, y1 = box_of(first)
                return NeedsInput(f"the box ({x0}, {y0}) to ({x1}, {y1}) {problem}", owner_action=f"{undo}.")
            continue
        if first.name != "click":
            continue
        for decision in group:
            x, y = int(decision.data["x"]), int(decision.data["y"])
            if read is not None and not (x < read[0].width and y < read[0].height):
                return NeedsInput(f"the click at ({x}, {y}) is outside the {read[0].width}x{read[0].height} Plate",
                                  owner_action=f"{undo}.")
            if read is not None and padded_click(read[0], x, y):
                return NeedsInput(f"the click at ({x}, {y}) is in the padded strip of the fit image, which has no "
                                  "Source pixels", owner_action=f"{undo}.")
    return None


def _masks_runner_calls(run: StageRun) -> list[RunnerCall]:
    read = read_grid(run)
    source = run.upstream["source"] / "source.png"
    if read is None or not source.is_file() or _masks_needs_input(run) is not None:
        return []
    return [lift_call(group, read[0], source) for group in click_groups(run.decisions)
            if group[0].name in ("click", "box")]


def _segmented(run: StageRun, group: list[CurrentDecision]) -> np.ndarray:
    """The pinned result of a click or a box, on the target grid."""
    read = read_grid(run)
    assert read is not None  # `fit` is upstream, and built
    path = run.pinned(lift_call(group, read[0], run.upstream["source"] / "source.png"))
    with Image.open(path) as image:
        return runner_mask_to_target(image, read)


def _preview_call(run: StageRun, clicks: list[ClickPoint]) -> RunnerCall | None:
    """The call a `segment-preview` makes. Its `decisions` stay empty, since nothing was decided."""
    read = read_grid(run)
    source = run.upstream["source"] / "source.png"
    if read is None or not source.is_file():
        return None
    for x, y, _ in clicks:
        if not (x < read[0].width and y < read[0].height):
            raise StageFailure(f"the point ({x}, {y}) is outside the {read[0].width}x{read[0].height} Plate")
        if padded_click(read[0], x, y):
            raise StageFailure(f"the point ({x}, {y}) is in the padded strip of the fit image, which has no "
                               "Source pixels")
    return RunnerCall(runner=SEGMENTER, image=source, params=click_params(clicks, read[0]), decisions=[])


def _preview_box_call(run: StageRun, box: BoxCorners) -> RunnerCall | None:
    """The call a `segment-preview` of a box makes: the call a `box` Decision makes, with no `decisions`."""
    read = read_grid(run)
    source = run.upstream["source"] / "source.png"
    if read is None or not source.is_file():
        return None
    problem = box_problem(box, read[0].width, read[0].height, read[0].pad_right, read[0].pad_bottom)
    if problem is not None:
        raise StageFailure(f"the box ({box[0]}, {box[1]}) to ({box[2]}, {box[3]}) {problem}")
    return RunnerCall(runner=SEGMENTER, image=source, params=box_params(box, read[0]), decisions=[])


def _preview_to_target(run: StageRun, mask: np.ndarray) -> np.ndarray:
    read = read_grid(run)
    assert read is not None  # `_preview_call` found it
    return runner_mask_to_target(Image.fromarray(mask), read)


def _decision_mask(run: StageRun, view: _ViewMasks, name: str, decision: str) -> str:
    if name in view.painted:
        return name
    undo = f"undo it with kiripix undo {run.asset_id} {MASKS_STAGE}"
    if name in view.derived:
        raise StageFailure(f"the {decision} Decision paints '{name}', which is derived and never painted; {undo}")
    raise StageFailure(f"the {decision} Decision paints '{name}', which is not a painted Mask of the "
                       f"{run.asset_params['view']} view ({', '.join(view.painted)}); {undo}")


def _write_mask(path: Path, mask: np.ndarray) -> None:
    """A Mask as a 1-bit PNG. The Stage's output folder is swapped into place whole by core, so the write is atomic."""
    Image.fromarray(mask).save(path, format="PNG")


def _read_mask(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("1"), dtype=np.bool_).copy()


def _flood_decision() -> DecisionSpec:
    """`point_decision` requires every property, and `tolerance` is optional: one left out is 0, as every flood was."""
    spec = point_decision("flood", "Fill the region of the Plate under this point whose colour is within `tolerance` "
                          "of the clicked pixel's (OKLab distance, 0 to 0.2; left out or 0 is exactly equal). A "
                          "painted Plate has thousands of colours, so it needs a tolerance (0.04 is a start).",
                          on_image=True, mask={"type": "string"})
    schema = spec.entry_schema
    schema["properties"]["tolerance"] = {"type": "number", "minimum": 0, "maximum": FLOOD_TOLERANCE_MAX}
    return spec


BORDER_THICKNESS = 2  # px: simplifying at the `export` Stage's default tolerance (1) keeps a wall of 1, and this has room


def _border_decision() -> DecisionSpec:
    return DecisionSpec(
        name="border",
        description=f"Wall off the room's edges: set a wall `thickness` px deep (default {BORDER_THICKNESS}, which "
                    "survives the export's simplifying at its default tolerance; a thickness over a side fills it) "
                    "along each of `sides` on a Mask, normally `solid`. It depends only on the room's size, so a "
                    "changed Plate leaves it as it is. It replays in order, so a later brush erase opens a gap in it; "
                    "an Exit needs none, since it stands on walkable ground inside the wall. A side left out stays "
                    "open (`masks.open_edge` says so, as info).",
        entry_schema={
            "type": "object",
            "properties": {
                "mask": {"type": "string"},
                "sides": {"type": "array", "items": {"enum": list(SIDES)}, "minItems": 1, "uniqueItems": True},
                "thickness": {"type": "integer", "minimum": 1, "default": BORDER_THICKNESS},
            },
            "required": ["mask", "sides"],
            "additionalProperties": False,
        },
    )


def _masks(run: StageRun) -> None:
    plate = read_rgba(run.upstream["layers"] / "plate.png")
    height, width = plate.shape[:2]
    view = _view_masks(run)
    masks = {name: np.zeros((height, width), dtype=np.bool_) for name in view.painted}
    floods: list[dict[str, Any]] = []
    for group in click_groups(run.decisions):
        decision = group[0]
        data = decision.data
        if decision.name in ("click", "box"):
            name = _decision_mask(run, view, str(data["mask"]), decision.name)
            if data["positive"]:
                masks[name] |= _segmented(run, group)
            else:
                masks[name] &= ~_segmented(run, group)
        elif decision.name == "flood":
            name = _decision_mask(run, view, str(data["mask"]), "flood")
            try:
                region = flood_region(plate, int(data["x"]), int(data["y"]), float(data.get("tolerance", 0)))
            except ValueError as error:
                raise StageFailure(str(error)) from None
            masks[name] |= region
            floods.append({"mask": name, "x": int(data["x"]), "y": int(data["y"]),
                           "tolerance": float(data.get("tolerance", 0)), "pixels": int(region.sum())})
        elif decision.name == "brush":
            name = _decision_mask(run, view, str(data["mask"]), "brush")
            masks[name] = paint_stroke(masks[name], [(int(x), int(y)) for x, y in data["points"]],
                                       int(data["radius"]), erase=bool(data["erase"]))
        elif decision.name == "polygon":
            name = _decision_mask(run, view, str(data["mask"]), "polygon")
            masks[name] = fill_polygon(masks[name], [(int(x), int(y)) for x, y in data["points"]],
                                       erase=bool(data["erase"]))
        elif decision.name == "border":
            name = _decision_mask(run, view, str(data["mask"]), "border")
            masks[name] = wall_off(masks[name], [str(side) for side in data["sides"]],
                                   int(data.get("thickness", BORDER_THICKNESS)))
        elif decision.name == "import":
            masks.update(_split_import(run, view, str(data["png"]), (width, height)))
    (run.output_dir / FLOODS_FILE).write_text(json.dumps(floods, indent=1) + "\n", encoding="utf-8")
    cell = int(run.params["snap_cell"])
    read = read_grid(run)
    strip = np.zeros((height, width), dtype=np.bool_)  # the padded cells `fit` added: solid, derived from grid.json
    if read is not None:
        strip[:, read[0].cells_x:] = True
        strip[read[0].cells_y:, :] = True
    for name, mask in masks.items():
        written = snap_cell(mask, cell) if cell > 1 else mask
        _write_mask(run.output_dir / f"{name}.png", written | strip if name == "solid" else written)


def _split_import(run: StageRun, view: _ViewMasks, png_hash: str,
                  size: tuple[int, int]) -> dict[str, np.ndarray]:
    """The Masks of a painted image: each Mask the colour table names is replaced by what the image paints in it."""
    path = stored_image(run, png_hash)
    if not path.is_file():
        raise StageFailure(f"the import Decision names {path.relative_to(run.asset_dir).as_posix()}, which is "
                           f"missing; undo it with kiripix undo {run.asset_id} {MASKS_STAGE}")
    check_unchanged(path, png_hash)
    image = read_rgba(path)
    if image.shape[1] > size[0] or image.shape[0] > size[1]:
        raise StageFailure(f"the imported image is {image.shape[1]}x{image.shape[0]} but the Plate is "
                           f"{size[0]}x{size[1]}; paint it at the Plate's size")
    try:
        split = split_painted(image, view.colours)
    except ValueError as error:
        raise StageFailure(f"the imported image {path.name}: {error}") from None
    result = {}
    for name, mask in split.items():
        if name in view.painted:
            full = np.zeros((size[1], size[0]), dtype=np.bool_)  # an image smaller than the Plate (the fit before it was
            full[:mask.shape[0], :mask.shape[1]] = mask           # padded) is "off" right and bottom: coordinates kept
            result[name] = full
    return result


# A flood that fills fewer pixels than this is probably a miss on painted art, which has no two equal colours.
FLOOD_MIN_PIXELS = 16
FLOOD_TOLERANCE_MAX = 0.2
FLOODS_FILE = "floods.json"


def _flood_findings(run: StageRun) -> list[Finding]:
    path = run.output_dir / FLOODS_FILE
    if not path.is_file():
        return []
    findings = []
    for flood in json.loads(path.read_text(encoding="utf-8")):
        if flood["pixels"] >= FLOOD_MIN_PIXELS:
            continue
        findings.append(
            Finding(
                code="mask.flood_filled_almost_nothing",
                severity="warning",
                message=f"the flood at ({flood['x']}, {flood['y']}) into {flood['mask']} filled {flood['pixels']} px "
                        f"at a tolerance of {flood['tolerance']:g}",
                position=Position(asset=run.asset_id, stage=MASKS_STAGE, x=flood["x"], y=flood["y"]),
                owner_action=f"Undo it and flood again with a `tolerance` (0 to {FLOOD_TOLERANCE_MAX:g}, in OKLab "
                             f"distance; try 0.04) in the decision, or paint the region with the brush "
                             f"(kiripix decide {run.asset_id} {MASKS_STAGE} --help).",
            )
        )
    return findings


def _open_edge_findings(run: StageRun) -> list[Finding]:
    """Info: a room edge the Body can walk off, since no wall of `solid` or `pit` lies along all of it. Silent when
    neither is painted."""
    solid = run.output_dir / "solid.png"
    if not solid.is_file():
        return []
    blocked = _read_mask(solid)
    pit = run.output_dir / "pit.png"
    if pit.is_file():
        blocked = blocked | _read_mask(pit)
    if not blocked.any():
        return []  # nothing painted: `mask.none_painted` says so already, and four open edges would only repeat it
    height, width = blocked.shape
    findings = []
    for side, (first, last) in open_edges(blocked).items():
        along = last - first + 1
        box = {"top": (first, 0, along, 1), "bottom": (first, height - 1, along, 1),
               "left": (0, first, 1, along), "right": (width - 1, first, 1, along)}[side]
        decision = {"decision": "border", "data": {"mask": "solid", "sides": [side]}}
        findings.append(
            Finding(
                code="masks.open_edge",
                severity="info",
                message=f"the {side} edge of the room has no wall along {along} px of it, so the Body can walk off it",
                position=Position(asset=run.asset_id, stage=MASKS_STAGE, x=box[0], y=box[1], width=box[2], height=box[3]),
                fix=f"kiripix decide {run.asset_id} {MASKS_STAGE} --decision '{json.dumps(decision)}'",
            )
        )
    return findings


def _check_masks(run: StageRun) -> list[Finding]:
    findings = _flood_findings(run) + _open_edge_findings(run)
    names = []
    painted = False
    for path in sorted(run.output_dir.glob("*.png")):
        names.append(path.stem)
        with Image.open(path) as image:  # opened once: its mode, and whether any pixel is set
            mode = image.mode
            painted = painted or bool(np.asarray(image.convert("1")).any())
        if mode != "1":
            findings.append(
                Finding(
                    code="mask.not_binary",
                    message=f"the Mask {path.stem} is a {mode} image, not a 1-bit one",
                    position=Position(asset=run.asset_id, stage=MASKS_STAGE, file=path.name),
                    fix=f"kiripix run {run.asset_id} {MASKS_STAGE} --force",
                )
            )
    if not painted:
        paint = "solid" if "solid" in names else (names[0] if names else "solid")
        findings.append(
            Finding(
                code="mask.none_painted",
                severity="info",
                message=f"no Mask is painted yet, so nothing blocks movement ({run.asset_id} masks is empty)",
                position=Position(asset=run.asset_id, stage=MASKS_STAGE),
                owner_action=f"Paint the {paint} Mask: flood a region, brush it, or import a painted image "
                             f"(kiripix decide {run.asset_id} {MASKS_STAGE} --help).",
            )
        )
    return findings


# palette: the whole composite mapped once to the palette (ADR 0004), then orphan pixels removed; each Layer is that image
# cut by its alpha, after the Overrides. The work is in `kiripix.recipes.room_palette`.


# place: the `marker` Decisions replayed into markers.json, and walkable derived from `solid` and the Body's footprint.

_MARKER_ID = "^[a-z0-9_]+(\\.[a-z0-9_]+)*$"
# Each Marker type's own fields, and the JSON Schema of each: a type requires its own and refuses the others'.
_MARKER_FIELDS: dict[str, dict[str, dict[str, Any]]] = {
    "exit": {
        "target_room": {"type": "string", "pattern": "^room\\.[a-z0-9_]+$"},
        "target_exit": {"type": "string", "pattern": _MARKER_ID},
    },
    "spawn": {},
    "interactable": {},
    "light": {
        "colour": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
        "radius": {"type": "number", "exclusiveMinimum": 0},
        "energy": {"type": "number", "minimum": 0},
    },
    "emitter": {"name": {"type": "string", "minLength": 1}},
    "ysort": {
        "layer": {"type": "string", "pattern": LAYER_ID},
        "x2": {"type": "integer", "minimum": 0},
        "y2": {"type": "integer", "minimum": 0},
    },
}
_ON_WALKABLE = ("exit", "spawn")


def _marker_decision() -> DecisionSpec:
    point = {"type": "integer", "minimum": 0}
    fields = {name: schema for own in _MARKER_FIELDS.values() for name, schema in own.items()}
    return DecisionSpec(
        name="marker",
        description="Place a Marker at a target pixel. A Marker with the same ID and type moves it. An Exit also takes "
                    "target_room and target_exit; a light colour, radius and energy; an emitter name; and a y-sort "
                    "line runs from (x, y) to (x2, y2) and sorts the Layer it names (a sloped line sorts at its mean y).",
        entry_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "pattern": _MARKER_ID},
                "type": {"enum": list(_MARKER_FIELDS)},
                "x": point,
                "y": point,
                **fields,
            },
            "required": ["id", "type", "x", "y"],
            "additionalProperties": False,
            "allOf": [
                {
                    "if": {"properties": {"type": {"const": marker_type}}, "required": ["type"]},
                    "then": {"required": list(own)},
                    "else": {"properties": {name: False for name in own}},
                }
                for marker_type, own in _MARKER_FIELDS.items() if own
            ],
        },
    )


def _no_walking(run: StageRun) -> np.ndarray:
    """Where the Body can't walk: `solid`, and `pit` where the project defines it."""
    solid = _read_mask(run.upstream[MASKS_STAGE] / "solid.png")
    pit = run.upstream[MASKS_STAGE] / "pit.png"
    return solid | _read_mask(pit) if pit.is_file() else solid


def _current_markers(decisions: tuple[CurrentDecision, ...]) -> list[dict[str, Any]]:
    markers: dict[tuple[str, str], dict[str, Any]] = {}
    for decision in decisions:
        if decision.name == "marker":
            markers[str(decision.data["id"]), str(decision.data["type"])] = decision.data  # a move keeps its first place
    return list(markers.values())


def _above_decision() -> DecisionSpec:
    return DecisionSpec(
        name="above",
        description="Put a Layer always above the Body (above true), or take that back (above false). A Layer that is "
                    "always above needs no y-sort line, and its sort position is none. The latest Decision on a Layer "
                    "counts.",
        entry_schema={
            "type": "object",
            "properties": {"layer": {"type": "string", "pattern": LAYER_ID}, "above": {"type": "boolean"}},
            "required": ["layer", "above"],
            "additionalProperties": False,
        },
    )


def _sort_positions(decisions: tuple[CurrentDecision, ...], layers: list[str] | None = None,
                    removed: list[str] | None = None) -> list[SortPosition]:
    """Each Layer's sort position (see `SortPosition`): the first y-sort line placed on it, its `y` the line's mean y
    rounded half up, `(y + y2 + 1) // 2`, unless an `above` Decision puts it always above. With `layers` (the built
    Layers) every one is listed, in their order, with `y` None when it has neither line nor flag, then any other Layer a
    line or flag names; without it only Layers a line or flag names are listed (`show`, before any build). A line or
    flag naming a `removed` Layer (ticket 0091) counts for nothing.
    """
    gone = set(removed or [])
    flags: dict[str, bool] = {}
    for decision in decisions:
        if decision.name == "above" and decision.data["layer"] not in gone:
            flags[str(decision.data["layer"])] = bool(decision.data["above"])  # the latest counts
    lines: dict[str, dict[str, Any]] = {}
    for marker in _current_markers(decisions):
        if marker["type"] == "ysort" and "layer" in marker and marker["layer"] not in gone:
            lines.setdefault(str(marker["layer"]), marker)
    named = list(dict.fromkeys([*lines, *(layer for layer, above in flags.items() if above)]))
    order = list(dict.fromkeys([*(layers or []), *named]))
    positions = []
    for layer in order:
        line = lines.get(layer)
        above = flags.get(layer, False)
        if above or line is None:
            positions.append(SortPosition(layer=layer, above=above, marker=None, y=None, slope=0))
        else:
            y1, y2 = int(line["y"]), int(line["y2"])
            positions.append(SortPosition(layer=layer, above=False, marker=str(line["id"]), y=(y1 + y2 + 1) // 2,
                                          slope=abs(y2 - y1)))
    return positions


def _ysort_line(layer: str, left: int, right: int, bottom: int) -> dict[str, Any]:
    """A y-sort line along a Layer's lowest row, from its left to its right column: `data` for a `marker` Decision."""
    return {"id": f"ysort.{layer}", "type": "ysort", "layer": layer, "x": left, "y": bottom, "x2": right, "y2": bottom}


def _built_layers(run: StageRun) -> list[str]:
    layers_dir = run.upstream[LAYERS_STAGE]
    if not (layers_dir / LAYERS_FILE).is_file():
        return []
    return [str(entry["id"]) for entry in read_layers(layers_dir, run.asset_id)]


def _removed_layers(run: StageRun) -> list[str]:
    layers_dir = run.upstream[LAYERS_STAGE]
    return read_removed(layers_dir) if (layers_dir / LAYERS_FILE).is_file() else []


MARKERS_FILE = "markers.json"
MARKERS_SCHEMA_VERSION = 1  # 1: `sort`, each Layer's sort position, beside `markers` (ticket 0046)


def _read_markers(place_dir: Path, asset: str) -> tuple[list[dict[str, Any]], list[SortPosition]]:
    """The Markers and sort positions a built `markers.json` holds. An older file is refused, naming the rebuild."""
    built = json.loads((place_dir / MARKERS_FILE).read_text(encoding="utf-8"))
    if built.get("schema_version") != MARKERS_SCHEMA_VERSION:
        raise StageFailure(f"{MARKERS_FILE} has schema_version {built.get('schema_version')}; this Kiripix reads "
                           f"{MARKERS_SCHEMA_VERSION}. Rebuild it: kiripix run {asset} place --force")
    markers: list[dict[str, Any]] = built["markers"]
    return markers, [SortPosition.model_validate(entry) for entry in built["sort"]]


def _place(run: StageRun) -> None:
    sort = _sort_positions(run.decisions, _built_layers(run), _removed_layers(run))
    built = {"schema_version": MARKERS_SCHEMA_VERSION, "markers": _current_markers(run.decisions),
             "sort": [position.model_dump() for position in sort]}
    (run.output_dir / MARKERS_FILE).write_text(json.dumps(built, indent=2) + "\n", encoding="utf-8")
    if "walkable" not in _view_masks(run).derived:
        return  # the side view's reachability is over platforms (M5)
    path = run.upstream[MASKS_STAGE] / "solid.png"
    if not path.is_file():
        raise StageFailure(f"walkable is derived from the 'solid' Mask, and the {run.asset_params['view']} view "
                           "doesn't define one; add it under [masks] in kiripix.toml")
    width, height = run.settings["body"]["size"]
    footprint = (int(width), int(height))
    _write_mask(run.output_dir / "walkable.png", walkable(_no_walking(run), footprint))
    # Where a dash may pass: only `solid` stops it. The walk test reads it, as `reach` works it out.
    _write_mask(run.output_dir / "clear.png", walkable(_read_mask(path), footprint))


def _check_sort(run: StageRun, markers: list[dict[str, Any]], sort: list[SortPosition]) -> list[Finding]:
    asset = run.asset_id
    layers = _built_layers(run)
    tile = float(run.settings["project.tile"])
    findings = []
    removed = set(_removed_layers(run))
    lines = [m for m in markers if m["type"] == "ysort" and m.get("layer") not in removed]
    for marker in lines:
        at = Position(asset=asset, stage="place", x=int(marker["x"]), y=int(marker["y"]))
        if "layer" not in marker:
            findings.append(Finding(
                code="ysort.no_layer",
                severity="warning",
                message=f"the ysort '{marker['id']}' sorts no Layer, so it does nothing",
                position=at,
                owner_action=f"Place {marker['id']} again with the Layer it sorts: a marker Decision of the same ID with "
                             "a layer.",
            ))
        elif abs(int(marker["y2"]) - int(marker["y"])) > tile / 2:
            findings.append(Finding(
                code="ysort.sloped",
                severity="warning",
                message=f"the ysort '{marker['id']}' for {marker['layer']} has ends {abs(int(marker['y2']) - int(marker['y']))}"
                        f" px apart in y, more than half a tile ({tile / 2:g} px); it sorts at its mean y",
                position=at,
                owner_action=f"Level {marker['id']} if the whole of {marker['layer']} should sort at one line, or leave it.",
            ))
    sorted_by = {position.layer: position.marker for position in sort}
    for marker in lines:
        if sorted_by.get(str(marker.get("layer"))) not in (None, marker["id"]):
            findings.append(Finding(
                code="ysort.extra_line",
                severity="warning",
                message=f"the ysort '{marker['id']}' is a second line for {marker['layer']}, and only the first line "
                        "placed on a Layer sorts it, so it does nothing",
                position=Position(asset=asset, stage="place", x=int(marker["x"]), y=int(marker["y"])),
                owner_action=f"Keep one y-sort line for {marker['layer']}: undo {marker['id']} (kiripix undo {asset} "
                             "place), or move the first line with a marker Decision of its ID.",
            ))
    for entry in sort:
        layer = entry.layer
        if layer not in layers:
            findings.append(Finding(
                code="ysort.unknown_layer",
                message=f"a y-sort line or flag names the Layer '{layer}', and the room has no such Layer",
                position=Position(asset=asset, stage="place"),
                owner_action=f"Name a Layer the room has ({', '.join(layers) or 'none yet'}) with a new marker or above "
                             f"Decision, or undo it (kiripix undo {asset} place).",
            ))
        elif entry.y is None and not entry.above:
            example = json.dumps({"decision": "above", "data": {"layer": layer, "above": True}})
            findings.append(Finding(
                code="layer.no_ysort",
                message=f"the Layer '{layer}' has no y-sort line and isn't always above",
                position=Position(asset=asset, stage="place", file=layer_file(layer)),
                owner_action=f"Place a ysort Marker with layer {layer}, or mark it always above: kiripix decide {asset} "
                             f"place --decision '{example}'",
            ))
    return findings


def _check_place(run: StageRun) -> list[Finding]:
    markers, sort = _read_markers(run.output_dir, run.asset_id)
    asset = run.asset_id
    findings = _check_sort(run, markers, sort)
    seen: dict[str, str] = {}

    def position(marker: dict[str, Any]) -> Position:
        return Position(asset=asset, stage="place", x=int(marker["x"]), y=int(marker["y"]))

    for marker in markers:
        marker_id, marker_type = str(marker["id"]), str(marker["type"])
        if marker_id in seen:
            findings.append(
                Finding(
                    code="marker.duplicate_id",
                    message=f"the {marker_type} '{marker_id}' has the same ID as the {seen[marker_id]} '{marker_id}'",
                    position=position(marker),
                    owner_action=f"Keep one Marker with the ID {marker_id}: undo the other "
                                 f"(kiripix undo {asset} place) and place it under a new ID.",
                )
            )
        seen.setdefault(marker_id, marker_type)
    path = run.output_dir / "walkable.png"
    if path.is_file():
        ground = _read_mask(path)
        for marker in markers:
            x, y = int(marker["x"]), int(marker["y"])
            inside = y < ground.shape[0] and x < ground.shape[1]
            if marker["type"] in _ON_WALKABLE and not (inside and ground[y, x]):
                findings.append(
                    Finding(
                        code="marker.not_walkable",
                        message=f"the {marker['type']} '{marker['id']}' at ({x}, {y}) is not on walkable ground: the "
                                "Body's footprint doesn't fit there",
                        position=position(marker),
                        owner_action=f"Move {marker['id']} onto walkable ground with a new marker Decision of the same "
                                     "ID, or edit the solid Mask under it.",
                    )
                )
    return findings


# reach: the Body's flood over walkable from each Spawn and Exit (top view; the side view's platforms are M5). A Marker
# is cut off when it isn't in the largest group of Markers that reach each other.


def _flood_targets(place_dir: Path) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = json.loads((place_dir / MARKERS_FILE).read_text(encoding="utf-8"))["markers"]
    return [marker for marker in markers if marker["type"] in _ON_WALKABLE]


def _flood_targets_of(decisions: tuple[CurrentDecision, ...]) -> list[dict[str, Any]]:
    return [marker for marker in _current_markers(decisions) if marker["type"] in _ON_WALKABLE]


def _reach_needs_input(run: StageRun) -> NeedsInput | None:
    view = run.asset_params["view"]
    if view != "top":
        reason = f"the {view} view's reachability is over platforms, which is not implemented until M5"
        return NeedsInput(reason, owner_action=f"Wait for M5 to finish {run.asset_id}: {reason}.")
    place_dir = run.upstream["place"]
    if not (place_dir / MARKERS_FILE).is_file() or _flood_targets(place_dir):
        return None
    example = json.dumps({"decision": "marker", "data": {"id": "spawn.main", "type": "spawn", "x": 0, "y": 0}})
    return NeedsInput("no Spawn or Exit is placed, so the Body has nowhere to start from",
                      owner_action=f"Place a Spawn or an Exit on walkable ground: kiripix decide {run.asset_id} place "
                                   f"--decision '{example}'")


def _spot_in(mask: np.ndarray, marker: dict[str, Any]) -> bool:
    x, y = int(marker["x"]), int(marker["y"])
    return y < mask.shape[0] and x < mask.shape[1] and bool(mask[y, x])


def _main_group(targets: list[dict[str, Any]], regions: list[np.ndarray]) -> set[int]:
    """The indexes of the largest group of Markers that reach each other; a tie goes to the group with a Spawn, then
    to the one with the earliest Marker. Empty when no Marker stands on walkable ground."""
    groups = {index: {index} for index, region in enumerate(regions) if region.any()}
    for index in list(groups):
        for other in list(groups):
            if groups[index] is not groups[other] and _spot_in(regions[index], targets[other]):
                merged = groups[index] | groups[other]
                for member in merged:
                    groups[member] = merged
    if not groups:
        return set()

    def rank(group: set[int]) -> tuple[int, bool, int]:
        return len(group), any(targets[i]["type"] == "spawn" for i in group), -min(group)

    return max(groups.values(), key=rank)


def _reach_report(run: StageRun, targets: list[dict[str, Any]], ground: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    """The Reachable Mask and the report, over `ground` (walkable) from `targets`, the Masks being `run.upstream`'s. The
    `reach` Stage writes both; the `reach` Probe answers with the report."""
    width, height = run.settings["body"]["size"]
    footprint = (int(width), int(height))
    step, dash = int(run.params["step"]), int(run.settings["body"]["dash"])
    solid = _read_mask(run.upstream[MASKS_STAGE] / "solid.png")
    regions: list[np.ndarray] = []
    for marker in targets:
        run.check_cancel()
        # At step 1 every move can be made both ways, so a Marker another flood reached has that flood's region.
        known = next((region for region in regions if _spot_in(region, marker)), None) if step == 1 else None
        regions.append(known if known is not None else
                       reachable(ground, [(int(marker["x"]), int(marker["y"]))], footprint, step, dash, solid))
    reached = np.logical_or.reduce(regions)
    run.check_cancel()
    main = _main_group(targets, regions)
    report = {
        "markers": [{"id": marker["id"], "type": marker["type"], "x": marker["x"], "y": marker["y"],
                     "on_ground": _spot_in(ground, marker), "reached": index in main}
                    for index, marker in enumerate(targets)],
        "main": [targets[index]["id"] for index in sorted(main)],
        "islands": [vars(island) for island in walkable_islands(ground, reached)],
        "gaps": [vars(gap) for gap in narrowest_gaps(_no_walking(run), footprint)],
    }
    return reached, report


def _reach(run: StageRun) -> None:
    path = run.upstream["place"] / "walkable.png"
    if not path.is_file():
        raise StageFailure(f"reach floods over walkable, and the {run.asset_params['view']} view doesn't derive it; "
                           "add walkable = { derived = true } under [masks] in kiripix.toml")
    reached, report = _reach_report(run, _flood_targets(run.upstream["place"]), _read_mask(path))
    _write_mask(run.output_dir / "reachable.png", reached)
    (run.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _reach_unsupported(run: StageRun) -> str | None:
    view = run.asset_params["view"]
    if view != "top":
        return f"the {view} view's reachability is over platforms, which is not implemented until M5"
    return None


def _reach_probe(run: StageRun, targets: list[dict[str, Any]]) -> dict[str, Any]:
    """The `reach` report from the Masks as built, with the walkable ground `place` would derive from them."""
    if not (run.upstream[MASKS_STAGE] / "solid.png").is_file():
        raise StageFailure(f"walkable is derived from the 'solid' Mask, and the {run.asset_params['view']} view "
                           "doesn't define one; add it under [masks] in kiripix.toml")
    width, height = run.settings["body"]["size"]
    return _reach_report(run, targets, walkable(_no_walking(run), (int(width), int(height))))[1]


def _check_reach(run: StageRun) -> list[Finding]:
    report = json.loads((run.output_dir / "report.json").read_text(encoding="utf-8"))
    asset = run.asset_id
    erase = f"erase with a brush Decision (kiripix decide {asset} {MASKS_STAGE} --help)"
    findings = []
    for marker in report["markers"]:
        if marker["reached"]:
            continue
        x, y = int(marker["x"]), int(marker["y"])
        why = ("is not on walkable ground, so the Body can't get to it" if not marker["on_ground"]
               else f"can't be reached from {', '.join(report['main'])}")
        findings.append(
            Finding(
                code="reach.unreachable_marker",
                message=f"the {marker['type']} '{marker['id']}' at ({x}, {y}) {why}",
                position=Position(asset=asset, stage="reach", x=x, y=y),
                owner_action=f"Open a way to {marker['id']} in the solid Mask: {erase}. Or move it with a new marker "
                             "Decision of the same ID.",
            )
        )
    for island in report["islands"]:
        x, y, width, height = int(island["x"]), int(island["y"]), int(island["width"]), int(island["height"])
        findings.append(
            Finding(
                code="reach.unreachable_island",
                severity="warning",
                message=f"walkable ground at ({x}, {y}), {width}x{height}, can't be reached from any Spawn or Exit",
                position=Position(asset=asset, stage="reach", x=x, y=y, width=width, height=height),
                owner_action=f"If the Body should get there, open a way in the solid Mask: {erase}. If not, paint the "
                             "ground solid or leave it.",
            )
        )
    for gap in report["gaps"]:
        fits = "the Body fits" if gap["width"] >= gap["needed"] else "the Body doesn't fit"
        findings.append(
            Finding(
                code="reach.narrow_gap",
                severity="info",
                message=f"a {gap['width']} px gap at ({gap['x']}, {gap['y']}): {fits}, needing {gap['needed']} px",
                position=Position(asset=asset, stage="reach", x=int(gap["x"]), y=int(gap["y"])),
                owner_action=f"Nothing, if that is what the room wants. To change it, edit the solid Mask: {erase}.",
            )
        )
    return findings


# export: what the game gets, with nothing of Godot in it: the mapped Plate, and `room.json` with the collision shapes, the
# navigation polygon and the Markers. The Exporter (`kiripix.export`) turns those into the engine's files.

ROOM_SCHEMA_VERSION = 2  # 2: `layers`, the foreground Layers with their files and sort positions (ticket 0047)
_COLLISION_MASKS = ("pit", "solid")  # any other painted Mask is the game's to read, and blocks nothing here
_NO_TARGET = "Set project under [export.godot] in kiripix.toml to the Godot project's folder."


def _export_needs_input(run: StageRun) -> NeedsInput | None:
    if run.settings["export.godot"].get("project"):
        return None
    return NeedsInput("no Godot project to export into", owner_action=_NO_TARGET)


def _export(run: StageRun) -> None:
    palette = run.upstream["palette"]
    shutil.copyfile(palette / "plate.png", run.output_dir / "plate.png")  # the mapped Plate, not the composite
    markers, sort = _read_markers(run.upstream["place"], run.asset_id)
    sorts = {position.layer: position for position in sort}
    layers = []
    for entry in read_layers(palette, run.asset_id):
        run.check_cancel()
        shutil.copyfile(palette / str(entry["file"]), run.output_dir / str(entry["file"]))
        position = sorts.get(str(entry["id"]))
        above = position is not None and position.above
        layers.append({"id": entry["id"], "file": entry["file"], "above": above,
                       "y": None if position is None or above else position.y})
    tolerance = float(run.params["tolerance"])
    collision = {}
    for name in _COLLISION_MASKS:
        run.check_cancel()
        path = run.upstream[MASKS_STAGE] / f"{name}.png"
        collision[name] = collision_shapes(simplify(contours(_read_mask(path)), tolerance)) if path.is_file() else []
    run.check_cancel()
    ground = _read_mask(run.upstream["place"] / "walkable.png") & _read_mask(run.upstream["reach"] / "reachable.png")
    navigation = navigation_polygon(simplify(contours(ground), tolerance))
    room = {
        "schema_version": ROOM_SCHEMA_VERSION,
        "asset": run.asset_id,
        "size": [ground.shape[1], ground.shape[0]],
        "collision": collision,
        "navigation": {"vertices": navigation.vertices, "polygons": navigation.polygons,
                       "outlines": navigation.outlines},
        "markers": markers,
        "layers": layers,
    }
    (run.output_dir / "room.json").write_text(json.dumps(room, indent=2) + "\n", encoding="utf-8")


def _check_export(run: StageRun) -> list[Finding]:
    if run.settings["export.godot"].get("project"):
        return []
    return [Finding(code="export.no_target", message="no Godot project to export into",
                    position=Position(asset=run.asset_id, stage="export"), owner_action=_NO_TARGET)]


ROOM = KindSpec(
    name="room",
    description="A background scene with Layers, Masks and Markers, in top or side view.",
    params=(
        ParamSpec(
            name="view",
            type="choice",
            description="Top-down or side-view room.",
            required=True,
            choices=["top", "side"],
        ),
    ),
    stages=chain(
        StageSpec(
            name="brief",
            description="Size, mood, Exits and notes; renders the generation prompt.",
            inputs=StageInputs(settings=["project.tile"]),
            params=(
                ParamSpec(name="width", type="int", description="Width in px.", default=640, minimum=1),
                ParamSpec(name="height", type="int", description="Height in px.", default=368, minimum=1),
                ParamSpec(name="mood", type="str", description="Mood words for the prompt.", default=""),
            ),
            checks=(CheckSpec(code="brief.size_not_tiles", description="The size is a whole number of tiles."),),
            owner_input="Writes the brief.",
            available_from="M1",
            run=_brief,
            check=_check_brief,
        ),
        StageSpec(
            name="source",
            description="Generated Variants or an imported image. The Owner chooses the Source between several; a lone "
                        "Variant is picked by the Command `next` names, which needs no judgement.",
            inputs=StageInputs(files=["src/*.png"]),
            decisions=(PICK,),
            checks=(CheckSpec(code="source.not_picked", description="A Source has been picked."),),
            owner_input="Picks one Variant.",
            available_from="M1",
            image="source.png",
            run=run_source,
            needs_input=source_needs_input,
        ),
        StageSpec(
            name="fit",
            description="Grid detection, or a downscale at one scale on both axes that crops the rest, to the target size; "
                        "a grid output smaller than the brief is padded right and bottom with transparent pixels "
                        "(`fit.padded`; `masks` makes the strip solid). Records the Grid transform. Palette-free.",
            inputs=StageInputs(upstream=["source", "brief"]),
            params=FIT_PARAMS,
            checks=(
                CheckSpec(code="fit.size_mismatch", description="The output has the brief's exact size."),
                CheckSpec(code="fit.padded", description="The grid output was padded up to the brief (info)."),
            ),
            owner_input="Tunes the grid.",
            available_from="M1",
            image="fit.png",
            run=_fit,
            check=check_fit,
        ),
        StageSpec(
            name="layers",
            description="Lifts foreground objects into named Layers and fills the Plate behind them: click an object "
                        "(a Runner segments it, a Runner inpaints the hole, both pinned), widen with `grow`, trim a rim "
                        "or add pixels with a brush, drop specks with `min_piece`. With no Decisions it is done, and the Plate is the fit image. Judge a lift "
                        "without looking: `kiripix probe layer-stats <asset>` gives each Layer's pixels, pieces "
                        "(with the pixels of any speck), holes, sort and a ready y-sort line.",
            # `fit` first: the clicks and trims are made on its image. Not `gpu`: the Runner calls take the lock
            # themselves (D10), and a build only reads their pinned results.
            inputs=StageInputs(upstream=["fit", "source"]),
            params=(GROW, MIN_PIECE, DIFFERENCE),
            decisions=LAYER_DECISIONS,
            checks=(
                CheckSpec(code="layers.recompose_mismatch", description="Plate and Layers recompose to the fit image."),
                CheckSpec(code="layers.plate_hole", description="The Plate has no holes."),
            ),
            owner_input="Clicks objects to lift out; trims a rim with a brush.",
            available_from="M1",
            image="plate.png",
            run=run_layers,
            needs_input=layers_needs_input,
            check=check_layers,
            runner_calls=layers_runner_calls,
            layer_stats=LayerStatsHooks(read=read_layer_files, sort_stage="place", sort=_sort_positions, ysort=_ysort_line),
        ),
        StageSpec(
            name="masks",
            description="Paints the Masks: click-to-segment, flood, polygon, brush or an imported painted image.",
            inputs=StageInputs(upstream=["layers", "source", "fit"], settings=["masks"]),
            params=(ParamSpec(name="snap_cell", type="int", description="Snap to an N px grid; 0 is off.", default=0,
                              minimum=0),),
            decisions=(
                point_decision("click", "A segmentation click on a Mask: a positive click adds the object under it, and "
                               "a negative one takes the object under it away from the Mask, whichever Decision put it there (a "
                               "later positive click, flood or brush can add it back). Needs `run --rerun`.",
                               on_image=True, mask={"type": "string"}, positive={"type": "boolean"}),
                box_decision("box", "Segment the object a rough box holds, from (x0, y0) to (x1, y1) in target pixels, "
                             "both pixels included: the Runner snaps the box to the object's edges. For an object a "
                             "single click returns only a part of, or leaks from. A positive box adds the object to the "
                             "Mask, a negative one takes it away, as a click does. One Runner call, pinned; needs "
                             "`run --rerun`. Try it first: `kiripix probe segment-preview <asset> x0,y0,x1,y1`.",
                             on_image=True, mask={"type": "string"}, positive={"type": "boolean"}),
                _flood_decision(),
                _border_decision(),
                DecisionSpec(
                    name="import",
                    description="Take Masks from a painted image of the Plate's size, stored under "
                                "decisions/imports/ by its hash; the nearest defined colour decides each pixel. It "
                                "replaces each Mask its colours name, discarding earlier floods and brushes on "
                                "those Masks; later Decisions then edit the result.",
                    entry_schema={
                        "type": "object",
                        "properties": {"png": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
                        "required": ["png"],
                        "additionalProperties": False,
                    },
                ),
                DecisionSpec(
                    name="brush",
                    description="A brush stroke on one Mask, in target pixels.",
                    entry_schema={
                        "type": "object",
                        "properties": {
                            "mask": {"type": "string"},
                            "erase": {"type": "boolean"},
                            "radius": {"type": "integer", "minimum": 0},
                            "points": {"type": "array", "items": {"type": "array", "items": {"type": "integer"},
                                                                  "minItems": 2, "maxItems": 2}},
                        },
                        "required": ["mask", "erase", "radius", "points"],
                        "additionalProperties": False,
                    },
                ),
                DecisionSpec(
                    name="polygon",
                    description="Fill a polygon on one Mask, or clear it with `erase`: `points` are at least three "
                                "corners in target pixels, and the polygon closes itself. The pixels on its outline "
                                "are included, so a rectangle through its corner pixels fills exactly that box; a "
                                "self-crossing polygon follows the even-odd rule (where it overlaps itself it is "
                                "clear); points outside the Mask are clipped. Like a brush stroke it depends on the "
                                "Mask, not on the Plate, so a changed Plate leaves it as it is. It replays in order.",
                    entry_schema={
                        "type": "object",
                        "properties": {
                            "mask": {"type": "string"},
                            "erase": {"type": "boolean"},
                            "points": {"type": "array", "minItems": 3,
                                       "items": {"type": "array", "items": {"type": "integer"},
                                                 "minItems": 2, "maxItems": 2}},
                        },
                        "required": ["mask", "erase", "points"],
                        "additionalProperties": False,
                    },
                ),
            ),
            checks=(
                CheckSpec(code="mask.not_binary", description="Every Mask is a 1-bit image."),
                CheckSpec(code="mask.none_painted", description="Some Mask has been painted (info)."),
                CheckSpec(code="masks.open_edge", description="No room edge is left without a wall (info)."),
            ),
            owner_input="Clicks and brushes.",
            available_from="M1",
            run=_masks,
            needs_input=_masks_needs_input,
            check=_check_masks,
            runner_calls=_masks_runner_calls,
            segment=SegmentHooks(call=_preview_call, to_target=_preview_to_target, box_call=_preview_box_call),
        ),
        StageSpec(
            name="palette",
            description="Maps the composite to the palette in OKLab and removes orphan pixels.",
            inputs=StageInputs(upstream=["layers"], settings=["palette"]),  # ADR 0004: not `masks`
            params=PALETTE_PARAMS,
            checks=(
                CheckSpec(code="palette.off_palette", description="Every pixel is a palette colour."),
                CheckSpec(code="palette.mapping_error", description="The palette maps the image without a high error."),
                CheckSpec(code="layers.recompose_mismatch", description="Plate and Layers still recompose exactly."),
            ),
            owner_input="Tunes the sliders.",
            available_from="M1",
            image="palette.png",
            run=run_room_palette,
            after_overrides=palette_after_overrides,
            check=check_room_palette,
        ),
        StageSpec(
            name="place",
            description="Places Markers: Exits, Spawns, lights, emitters and y-sort lines, one for each foreground Layer "
                        "unless it is always above.",
            inputs=StageInputs(upstream=["palette", "layers", MASKS_STAGE], settings=["body", "masks", "project.tile"]),
            decisions=(_marker_decision(), _above_decision()),
            checks=(
                CheckSpec(code="marker.duplicate_id", description="Marker IDs are unique."),
                CheckSpec(code="marker.not_walkable", description="Exits and Spawns stand on walkable ground."),
                CheckSpec(code="layer.no_ysort", description="Every foreground Layer has a y-sort line or is above."),
                CheckSpec(code="ysort.unknown_layer", description="Every y-sort line or flag names a Layer of the room."),
                CheckSpec(code="ysort.no_layer", description="Every y-sort line names the Layer it sorts (warning)."),
                CheckSpec(code="ysort.sloped", description="A y-sort line's ends are within half a tile in y (warning)."),
                CheckSpec(code="ysort.extra_line", description="A Layer has one y-sort line; a later one sorts nothing "
                                                               "(warning)."),
            ),
            owner_input="Places Markers.",
            available_from="M1",
            run=_place,
            check=_check_place,
            markers=_current_markers,
            sort=_sort_positions,
        ),
        StageSpec(
            name="reach",
            description="Reachability of every Marker for the Body's footprint.",
            inputs=StageInputs(upstream=["place", MASKS_STAGE], settings=["body"]),
            params=(ParamSpec(name="step", type="int", description="Flood step in px. 1 is exact; a longer one can "
                              "miss a gap the Body fits only at one exact offset.", default=1, minimum=1),),
            checks=(
                CheckSpec(code="reach.unreachable_marker", description="Every Spawn and Exit is reachable."),
                CheckSpec(code="reach.unreachable_island", description="All walkable ground is reachable (warning)."),
                CheckSpec(code="reach.narrow_gap", description="The narrowest gaps in solid (info)."),
            ),
            available_from="M1",
            run=_reach,
            needs_input=_reach_needs_input,
            check=_check_reach,
            reach=ReachHooks(marker_stage="place", masks_stage=MASKS_STAGE, unsupported=_reach_unsupported,
                             targets=_flood_targets_of, report=_reach_probe),
        ),
        StageSpec(
            name="export",
            description="Builds what the game gets: the mapped Plate, collision shapes, navigation polygon and Markers. "
                        "`kiripix export` then writes them into the Godot project.",
            inputs=StageInputs(upstream=["reach", "place", "palette", MASKS_STAGE], settings=["export.godot"]),
            params=(ParamSpec(name="tolerance", type="float", description="How far collision and navigation outlines "
                              "may stray from the Mask, in px. 0 keeps every corner.", default=1.0, minimum=0),),
            checks=(
                CheckSpec(code="export.no_target", description="The export target is set."),
                CheckSpec(code="exit.unpaired", description="Every Exit points to an Exit that points back."),
            ),
            output_root="out",
            available_from="M1",
            run=_export,
            needs_input=_export_needs_input,
            check=_check_export,
        ),
    ),
)
