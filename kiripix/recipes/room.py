"""The room Recipe (spec §6.1): brief, source, fit, layers, masks, palette, place, reach, export."""

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from kiripix.checks import Finding, Position, check_conformance
from kiripix.recipes.base import (
    FIT_PARAMS,
    PALETTE_PARAMS,
    PICK,
    CheckSpec,
    ClickPoint,
    CurrentDecision,
    DecisionSpec,
    KindSpec,
    NeedsInput,
    ParamSpec,
    RunnerCall,
    SegmentHooks,
    StageFailure,
    StageInputs,
    StageRun,
    StageSpec,
    chain,
    point_decision,
)
from kiripix.ops import (
    BayerSize,
    Grid,
    collision_shapes,
    conformance,
    contours,
    detect_grid,
    downscale_mode,
    flood_region,
    mask_to_target,
    narrowest_gaps,
    navigation_polygon,
    paint_stroke,
    parse_gpl,
    parse_hex,
    quantize,
    reachable,
    remove_orphans,
    sample_nearest,
    simplify,
    snap_cell,
    split_painted,
    target_centre,
    walkable,
    walkable_islands,
)
from kiripix.ops.masks import RGB
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
    return -(-size // tile) * tile


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


def _variants(run: StageRun) -> dict[str, Path]:
    return {Path(name).stem: path for name, path in run.files.items()}


def _picked(run: StageRun) -> str | None:
    picks = [d for d in run.decisions if d.name == PICK.name]
    return str(picks[-1].data["variant"]) if picks else None


def _source_needs_input(run: StageRun) -> NeedsInput | None:
    variants = sorted(_variants(run))
    picked = _picked(run)
    if picked in variants:
        return None
    reason = "no Source picked" if picked is None else f"the picked Variant {picked} was deleted"
    if not variants:
        return NeedsInput(reason, command=f"kiripix import {run.asset_id} <file>")
    if len(variants) == 1:
        return NeedsInput(reason, command=f"kiripix pick {run.asset_id} {variants[0]}")
    return NeedsInput(reason, owner_action=f"Pick one of the Variants {', '.join(variants)}: "
                                           f"kiripix pick {run.asset_id} <variant>")


def _source(run: StageRun) -> None:
    picked = _picked(run)
    assert picked is not None  # `_source_needs_input` holds the Stage back until there is a Pick
    path = _variants(run)[picked]
    if not hashlib.sha256(path.read_bytes()).hexdigest().startswith(picked):
        raise StageFailure(f"the Variant {path.name} was changed after it was imported, and Variants are immutable; "
                           "import the changed image as a new Variant and pick that")
    shutil.copyfile(path, run.output_dir / "source.png")


# fit: the Source's pixel grid (or a mode-filter downscale) down to the brief's exact size. Palette-free.


def _read_rgba(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()


def _write_rgba(path: Path, rgba: np.ndarray) -> None:
    Image.fromarray(rgba, "RGBA").save(path, format="PNG")


def _brief_size(run: StageRun) -> tuple[int, int]:
    brief = json.loads((run.upstream["brief"] / "brief.json").read_text(encoding="utf-8"))
    return int(brief["width"]), int(brief["height"])


def _fit(run: StageRun) -> None:
    source = _read_rgba(run.upstream["source"] / "source.png")
    height, width = source.shape[:2]
    target_width, target_height = _brief_size(run)
    mode = str(run.params["mode"])
    scale = int(run.params["scale"])
    if mode == "downscale":
        try:
            grid = Grid.to_size(width, height, target_width, target_height)
        except ValueError:
            raise StageFailure(f"can't downscale the {width}x{height} Source to the brief's "
                               f"{target_width}x{target_height}: the Source is smaller") from None
        fitted = downscale_mode(source, grid)
    else:
        try:
            grid = (Grid.uniform(scale, int(run.params["offset_x"]), int(run.params["offset_y"]), width, height)
                    if scale > 0 else detect_grid(source))
        except ValueError as error:
            raise StageFailure(str(error)) from None
        fitted = sample_nearest(source, grid)
    _write_rgba(run.output_dir / "fit.png", fitted)
    record = {"mode": mode, "source": [width, height], **grid.to_json()}
    (run.output_dir / "grid.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _check_fit(run: StageRun) -> list[Finding]:
    grid = json.loads((run.output_dir / "grid.json").read_text(encoding="utf-8"))
    width, height = int(grid["width"]), int(grid["height"])
    target_width, target_height = _brief_size(run)
    if (width, height) == (target_width, target_height):
        return []
    source_width, source_height = grid["source"]
    asset = run.asset_id
    ratio = source_width // target_width if target_width else 0
    if source_width == ratio * target_width and source_height == ratio * target_height and ratio >= 1:
        fix = f"kiripix set {asset} fit scale={ratio}"
        if int(run.params["offset_x"]) or int(run.params["offset_y"]):
            fix += " offset_x=0 offset_y=0"
        if grid["mode"] == "grid" and int(run.params["scale"]) == ratio:  # already that: the grid isn't the problem
            fix = f"kiripix set {asset} fit mode=downscale"
    else:
        fix = f"kiripix set {asset} fit mode=downscale"
    return [
        Finding(
            code="fit.size_mismatch",
            message=f"the fit image is {width}x{height}, the brief asks for {target_width}x{target_height}",
            position=Position(asset=asset, stage="fit", field="stages.fit.scale"
                              if grid["mode"] == "grid" else "stages.fit.mode"),
            fix=fix,
        )
    ]


# layers: a pass-through in M1. The Plate is the fit image, and there are no foreground Layers.


def _layers(run: StageRun) -> None:
    shutil.copyfile(run.upstream["fit"] / "fit.png", run.output_dir / "plate.png")
    (run.output_dir / "layers.json").write_text(json.dumps({"layers": []}) + "\n", encoding="utf-8")


# masks: the Decisions replayed in order onto the Plate's size, one 1-bit PNG per painted Mask of the room's view.
#
# A positive `click` segments the object under it, with the negative clicks right after it on the same Mask taking away
# from that segmentation: that is one Runner call, and its result is added to the Mask. So a new object keeps the pinned
# results of the earlier ones. The Runner works on the Source, capped; the clicks map to it through the Grid transform,
# and its Mask maps back through the same transform when the Stage replays (ADR 0004).

MASKS_STAGE = "masks"
IMPORT_DIR = ("decisions", "imports")  # a painted image of an `import` Decision, stored here under its hash
_RUNNER_MAX_SIZE = 1536  # px on the longer side, to fit 8 GB of VRAM (ADR 0004)


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


def _click_groups(decisions: tuple[CurrentDecision, ...]) -> list[list[CurrentDecision]]:
    """The Decisions in order, each in a list of its own, except that a negative `click` joins the `click` before it
    if that is on the same Mask."""
    groups: list[list[CurrentDecision]] = []
    for decision in decisions:
        previous = groups[-1][-1] if groups else None
        if decision.name == "click" and not decision.data["positive"] and previous is not None and \
                previous.name == "click" and previous.data["mask"] == decision.data["mask"]:
            groups[-1].append(decision)
        else:
            groups.append([decision])
    return groups


def _read_grid(run: StageRun) -> tuple[Grid, dict[str, Any]] | None:
    """The Grid transform recorded by `fit`, and the record itself; None until `fit` is built."""
    path = run.upstream["fit"] / "grid.json"
    if not path.is_file():
        return None
    record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return Grid.from_json(record), record


def _masks_needs_input(run: StageRun) -> NeedsInput | None:
    read = _read_grid(run)
    undo = f"Undo it: kiripix undo {run.asset_id} {MASKS_STAGE}"
    for group in _click_groups(run.decisions):
        first = group[0]
        if first.name != "click":
            continue
        if not first.data["positive"]:
            return NeedsInput(f"the negative click at ({first.data['x']}, {first.data['y']}) has no positive click on "
                              f"{first.data['mask']} right before it to take away from", owner_action=f"{undo}.")
        for decision in group:
            x, y = int(decision.data["x"]), int(decision.data["y"])
            if read is not None and not (x < read[0].width and y < read[0].height):
                return NeedsInput(f"the click at ({x}, {y}) is outside the {read[0].width}x{read[0].height} Plate",
                                  owner_action=f"{undo}.")
    return None


def _click_params(clicks: list[ClickPoint], grid: Grid) -> dict[str, Any]:
    points = [[*target_centre(grid, x, y), positive] for x, y, positive in clicks]
    return {"points": points, "max_size": _RUNNER_MAX_SIZE}


def _click_call(group: list[CurrentDecision], grid: Grid, source: Path) -> RunnerCall:
    clicks = [(int(d.data["x"]), int(d.data["y"]), bool(d.data["positive"])) for d in group]
    return RunnerCall(
        runner=SEGMENTER,
        image=source,
        params=_click_params(clicks, grid),
        decisions=[{"x": d.data["x"], "y": d.data["y"], "positive": d.data["positive"]} for d in group],
    )


def _masks_runner_calls(run: StageRun) -> list[RunnerCall]:
    read = _read_grid(run)
    source = run.upstream["source"] / "source.png"
    if read is None or not source.is_file() or _masks_needs_input(run) is not None:
        return []
    return [_click_call(group, read[0], source) for group in _click_groups(run.decisions)
            if group[0].name == "click"]


def _segmented(run: StageRun, group: list[CurrentDecision]) -> np.ndarray:
    """The pinned result of a group of clicks, on the target grid."""
    read = _read_grid(run)
    assert read is not None  # `fit` is upstream, and built
    path = run.pinned(_click_call(group, read[0], run.upstream["source"] / "source.png"))
    with Image.open(path) as image:
        return _runner_mask_to_target(image, read)


def _runner_mask_to_target(mask: Image.Image, read: tuple[Grid, dict[str, Any]]) -> np.ndarray:
    grid, record = read
    source_width, source_height = record["source"]
    on_source = mask.convert("1").resize((int(source_width), int(source_height)), Image.Resampling.NEAREST)
    return mask_to_target(np.asarray(on_source, dtype=np.bool_), grid)


def _preview_call(run: StageRun, clicks: list[ClickPoint]) -> RunnerCall | None:
    """The call a `segment-preview` makes. Its `decisions` stay empty, since nothing was decided."""
    read = _read_grid(run)
    source = run.upstream["source"] / "source.png"
    if read is None or not source.is_file():
        return None
    for x, y, _ in clicks:
        if not (x < read[0].width and y < read[0].height):
            raise StageFailure(f"the point ({x}, {y}) is outside the {read[0].width}x{read[0].height} Plate")
    return RunnerCall(runner=SEGMENTER, image=source, params=_click_params(clicks, read[0]), decisions=[])


def _preview_to_target(run: StageRun, mask: np.ndarray) -> np.ndarray:
    read = _read_grid(run)
    assert read is not None  # `_preview_call` found it
    return _runner_mask_to_target(Image.fromarray(mask), read)


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


def _masks(run: StageRun) -> None:
    plate = _read_rgba(run.upstream["layers"] / "plate.png")
    height, width = plate.shape[:2]
    view = _view_masks(run)
    masks = {name: np.zeros((height, width), dtype=np.bool_) for name in view.painted}
    for group in _click_groups(run.decisions):
        decision = group[0]
        data = decision.data
        if decision.name == "click":
            masks[_decision_mask(run, view, str(data["mask"]), "click")] |= _segmented(run, group)
        elif decision.name == "flood":
            name = _decision_mask(run, view, str(data["mask"]), "flood")
            try:
                masks[name] |= flood_region(plate, int(data["x"]), int(data["y"]))
            except ValueError as error:
                raise StageFailure(str(error)) from None
        elif decision.name == "brush":
            name = _decision_mask(run, view, str(data["mask"]), "brush")
            masks[name] = paint_stroke(masks[name], [(int(x), int(y)) for x, y in data["points"]],
                                       int(data["radius"]), erase=bool(data["erase"]))
        elif decision.name == "import":
            masks.update(_split_import(run, view, str(data["png"]), (width, height)))
    cell = int(run.params["snap_cell"])
    for name, mask in masks.items():
        _write_mask(run.output_dir / f"{name}.png", snap_cell(mask, cell) if cell > 1 else mask)


def _split_import(run: StageRun, view: _ViewMasks, png_hash: str,
                  size: tuple[int, int]) -> dict[str, np.ndarray]:
    """The Masks of a painted image: each Mask the colour table names is replaced by what the image paints in it."""
    path = run.asset_dir.joinpath(*IMPORT_DIR, f"{png_hash}.png")
    if not path.is_file():
        raise StageFailure(f"the import Decision names {path.relative_to(run.asset_dir).as_posix()}, which is "
                           f"missing; undo it with kiripix undo {run.asset_id} {MASKS_STAGE}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != png_hash:
        raise StageFailure(f"{path.name} was changed after it was imported; images named by hash are immutable")
    image = _read_rgba(path)
    if (image.shape[1], image.shape[0]) != size:
        raise StageFailure(f"the imported image is {image.shape[1]}x{image.shape[0]} but the Plate is "
                           f"{size[0]}x{size[1]}; paint it at the Plate's size")
    try:
        split = split_painted(image, view.colours)
    except ValueError as error:
        raise StageFailure(f"the imported image {path.name}: {error}") from None
    return {name: mask for name, mask in split.items() if name in view.painted}


def _check_masks(run: StageRun) -> list[Finding]:
    findings = []
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


# palette: the whole composite mapped once to the palette (ADR 0004), then orphan pixels removed. In M1 the Plate is the
# whole room and there are no foreground Layers; from M2 each Layer is this image cut by its alpha.

_BAYER: dict[str, BayerSize] = {"none": 0, "bayer2": 2, "bayer4": 4, "bayer8": 8}


def _palette_rgb(run: StageRun) -> np.ndarray:
    path: Path = run.settings["palette"]
    try:
        palette = parse_gpl(path.read_text(encoding="utf-8")) if path.suffix.lower() == ".gpl" else parse_hex(
            path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:  # PaletteSyntaxError is a ValueError
        raise StageFailure(f"can't read the palette {path.name}: {error}") from None
    if not palette.entries:
        raise StageFailure(f"the palette {path.name} has no colours")
    return palette.rgb()


def _palette(run: StageRun) -> None:
    plate = _read_rgba(run.upstream["layers"] / "plate.png")
    palette = _palette_rgb(run)
    run.check_cancel()
    try:
        mapped = quantize(plate, palette, _BAYER[str(run.params["dither"])], float(run.params["strength"]))
    except ValueError as error:
        raise StageFailure(f"the Plate can't be mapped: {error}") from None
    run.check_cancel()
    _write_rgba(run.output_dir / "palette.png", remove_orphans(mapped, int(run.params["orphan_size"])))


def _check_palette(run: StageRun) -> list[Finding]:
    # layers.recompose_mismatch: with no foreground Layers (all there is in M1) the Plate is the whole image and
    # recomposes trivially; it is checked from M2, when the Layers exist.
    try:
        palette = _palette_rgb(run)
    except StageFailure:
        return []  # the palette's own Checks report it
    report = conformance(_read_rgba(run.output_dir / "palette.png"), palette)
    findings = check_conformance(report, "palette.png", fix=f"kiripix run {run.asset_id} palette --force")
    for finding in findings:
        assert finding.position is not None
        finding.position.asset, finding.position.stage = run.asset_id, "palette"
    return findings


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
    "ysort": {"x2": {"type": "integer", "minimum": 0}, "y2": {"type": "integer", "minimum": 0}},
}
_ON_WALKABLE = ("exit", "spawn")


def _marker_decision() -> DecisionSpec:
    point = {"type": "integer", "minimum": 0}
    fields = {name: schema for own in _MARKER_FIELDS.values() for name, schema in own.items()}
    return DecisionSpec(
        name="marker",
        description="Place a Marker at a target pixel. A Marker with the same ID and type moves it. An Exit also takes "
                    "target_room and target_exit; a light colour, radius and energy; an emitter name; and a y-sort "
                    "line runs from (x, y) to (x2, y2).",
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
        markers[str(decision.data["id"]), str(decision.data["type"])] = decision.data  # a move keeps its first place
    return list(markers.values())


def _place(run: StageRun) -> None:
    (run.output_dir / "markers.json").write_text(json.dumps({"markers": _current_markers(run.decisions)}, indent=2) + "\n",
                                                 encoding="utf-8")
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


def _check_place(run: StageRun) -> list[Finding]:
    # layer.no_ysort: with no foreground Layers (all there is in M1) there is nothing to check; it is checked from M2.
    markers: list[dict[str, Any]] = json.loads((run.output_dir / "markers.json").read_text(encoding="utf-8"))["markers"]
    asset = run.asset_id
    findings = []
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
    markers: list[dict[str, Any]] = json.loads((place_dir / "markers.json").read_text(encoding="utf-8"))["markers"]
    return [marker for marker in markers if marker["type"] in _ON_WALKABLE]


def _reach_needs_input(run: StageRun) -> NeedsInput | None:
    view = run.asset_params["view"]
    if view != "top":
        reason = f"the {view} view's reachability is over platforms, which is not implemented until M5"
        return NeedsInput(reason, owner_action=f"Wait for M5 to finish {run.asset_id}: {reason}.")
    place_dir = run.upstream["place"]
    if not (place_dir / "markers.json").is_file() or _flood_targets(place_dir):
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


def _reach(run: StageRun) -> None:
    path = run.upstream["place"] / "walkable.png"
    if not path.is_file():
        raise StageFailure(f"reach floods over walkable, and the {run.asset_params['view']} view doesn't derive it; "
                           "add walkable = { derived = true } under [masks] in kiripix.toml")
    ground = _read_mask(path)
    targets = _flood_targets(run.upstream["place"])
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
    _write_mask(run.output_dir / "reachable.png", reached)
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
    (run.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


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

_COLLISION_MASKS = ("pit", "solid")  # any other painted Mask is the game's to read, and blocks nothing here
_NO_TARGET = "Set project under [export.godot] in kiripix.toml to the Godot project's folder."


def _export_needs_input(run: StageRun) -> NeedsInput | None:
    if run.settings["export.godot"].get("project"):
        return None
    return NeedsInput("no Godot project to export into", owner_action=_NO_TARGET)


def _export(run: StageRun) -> None:
    shutil.copyfile(run.upstream["palette"] / "palette.png", run.output_dir / "plate.png")
    tolerance = float(run.params["tolerance"])
    collision = {}
    for name in _COLLISION_MASKS:
        run.check_cancel()
        path = run.upstream[MASKS_STAGE] / f"{name}.png"
        collision[name] = collision_shapes(simplify(contours(_read_mask(path)), tolerance)) if path.is_file() else []
    run.check_cancel()
    ground = _read_mask(run.upstream["place"] / "walkable.png") & _read_mask(run.upstream["reach"] / "reachable.png")
    navigation = navigation_polygon(simplify(contours(ground), tolerance))
    markers = json.loads((run.upstream["place"] / "markers.json").read_text(encoding="utf-8"))["markers"]
    room = {
        "schema_version": 1,
        "asset": run.asset_id,
        "size": [ground.shape[1], ground.shape[0]],
        "collision": collision,
        "navigation": {"vertices": navigation.vertices, "polygons": navigation.polygons,
                       "outlines": navigation.outlines},
        "markers": markers,
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
            run=_source,
            needs_input=_source_needs_input,
        ),
        StageSpec(
            name="fit",
            description="Grid detection or downscale to the target size; records the Grid transform. Palette-free.",
            inputs=StageInputs(upstream=["source", "brief"]),
            params=FIT_PARAMS,
            checks=(CheckSpec(code="fit.size_mismatch", description="The output has the brief's exact size."),),
            owner_input="Tunes the grid.",
            available_from="M1",
            image="fit.png",
            run=_fit,
            check=_check_fit,
        ),
        StageSpec(
            name="layers",
            # The M1 pass-through (ticket 0010): no owner input. The real Stage (M2) adds the `grow` parameter, the
            # `click` Decision ("Clicks objects to lift out.") and the GPU.
            description="Builds the Plate from the fit image; foreground Layers arrive in M2.",
            checks=(
                CheckSpec(code="layers.recompose_mismatch", description="Plate and Layers recompose to the fit image."),
                CheckSpec(code="layers.plate_hole", description="The Plate has no holes."),
            ),
            available_from="M1",
            image="plate.png",
            run=_layers,
        ),
        StageSpec(
            name="masks",
            description="Paints the Masks: click-to-segment, flood, polygon, brush or an imported painted image.",
            inputs=StageInputs(upstream=["layers", "source", "fit"], settings=["masks"]),
            params=(ParamSpec(name="snap_cell", type="int", description="Snap to an N px grid; 0 is off.", default=0,
                              minimum=0),),
            decisions=(
                point_decision("click", "A segmentation click on a Mask: a positive click adds the object under it, and "
                               "a negative one right after it takes away from that object. Needs `run --rerun`.",
                               on_image=True, mask={"type": "string"}, positive={"type": "boolean"}),
                point_decision("flood", "Fill the region of equal colour on the Plate under this point into a Mask.",
                               on_image=True, mask={"type": "string"}),
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
            ),
            checks=(
                CheckSpec(code="mask.not_binary", description="Every Mask is a 1-bit image."),
                CheckSpec(code="mask.none_painted", description="Some Mask has been painted (info)."),
            ),
            owner_input="Clicks and brushes.",
            gpu=True,
            available_from="M1",
            run=_masks,
            needs_input=_masks_needs_input,
            check=_check_masks,
            runner_calls=_masks_runner_calls,
            segment=SegmentHooks(call=_preview_call, to_target=_preview_to_target),
        ),
        StageSpec(
            name="palette",
            description="Maps the composite to the palette in OKLab and removes orphan pixels.",
            inputs=StageInputs(upstream=["layers"], settings=["palette"]),  # ADR 0004: not `masks`
            params=PALETTE_PARAMS,
            checks=(
                CheckSpec(code="palette.off_palette", description="Every pixel is a palette colour."),
                CheckSpec(code="layers.recompose_mismatch", description="Plate and Layers still recompose exactly."),
            ),
            owner_input="Tunes the sliders.",
            available_from="M1",
            image="palette.png",
            run=_palette,
            check=_check_palette,
        ),
        StageSpec(
            name="place",
            description="Places Markers: Exits, Spawns, lights, emitters and y-sort lines.",
            inputs=StageInputs(upstream=["palette", MASKS_STAGE], settings=["body", "masks"]),
            decisions=(_marker_decision(),),
            checks=(
                CheckSpec(code="marker.duplicate_id", description="Marker IDs are unique."),
                CheckSpec(code="marker.not_walkable", description="Exits and Spawns stand on walkable ground."),
                CheckSpec(code="layer.no_ysort", description="Every foreground Layer has a y-sort line or is above."),
            ),
            owner_input="Places Markers.",
            available_from="M1",
            run=_place,
            check=_check_place,
            markers=_current_markers,
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
