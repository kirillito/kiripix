"""The room's `layers` Stage (spec §6.1, §7, ticket 0043): lift foreground objects into Layers and fill the Plate behind.

A positive `click` on a Layer ID segments the object under it (one SEGMENTER call per click), in the same way as in
`masks`, and the segments of one Layer ID are added together. A negative click is its own call too, and takes its segment
away from that Layer at its place in the replay (ticket 0070).
The segmentation's alpha is widened by `grow` target pixels, only where it was partial (D2). The hole in the Plate is the
union of those alphas; each connected hole gets one INPAINTER call on the Source, cropped around it, so a new object keeps
the earlier objects' pinned results. The fill maps to the target the way `fit` maps the Source.

A `trim` Decision is a brush stroke, in target pixels, on one Layer's alpha: it takes those pixels out of the Layer and
gives them back to the Plate (D1). It replays in order with the clicks. It changes no Runner call: the fill was made for
the hole before trimming, and a trimmed pixel takes the fit image's colour in the Plate.

Layer pixels are the fit image cut by alpha, the hole equals the union of the alphas, and the Plate outside the hole is the
fit image, so Plate and Layers recompose exactly (ADR 0004). With no Decisions the Plate is a byte copy of the fit image.
"""

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

import kiripix.runners as runners
from kiripix.checks import Finding, Position
from kiripix.ops import (
    Grid,
    connected_regions,
    cut_by_alpha,
    downscale_mode,
    grow_where_partial,
    mask_from_difference,
    mask_to_source,
    mask_to_target,
    paint_stroke,
    partial_cells,
    recompose,
    sample_nearest,
)
from kiripix.recipes.base import (
    PLATE,
    CurrentDecision,
    DecisionSpec,
    NeedsInput,
    ParamSpec,
    RunnerCall,
    StageFailure,
    StageRun,
    point_decision,
)
from kiripix.recipes.common import (
    IMPORT_DIR,
    check_unchanged,
    click_call,
    click_groups,
    read_grid,
    read_rgba,
    runner_mask_on_source,
    stored_image,
    write_rgba,
)
from kiripix.recipes.hole import hole_mask, hole_params

LAYERS_STAGE = "layers"
DEFAULT_DIFFERENCE = 0.05
LAYER_ID ="^(?!plate$)[a-z0-9_]+$"  # `plate` is reserved for the Plate
LAYERS_FILE = "layers.json"
LAYERS_SCHEMA_VERSION = 1
FOREGROUND_FILE = "foreground.png"
FILL_MARGIN = 32  # Source px of context around a hole in a fill call
DEFAULT_GROW = 1

GROW = ParamSpec(
    name="grow",
    type="int",
    description="Widen each lifted Layer's alpha, and so its hole in the Plate, by this many target pixels, only where "
                "the Runner's alpha was partial. 0 widens nothing.",
    default=DEFAULT_GROW,
    minimum=0,
)


DIFFERENCE = ParamSpec(
    name="difference",
    type="float",
    description="With a `plate` Decision: the OKLab distance above which a Source pixel differs between the full image "
                "and the Plate image. A connected region of the difference becomes a Layer when the Owner clicks it.",
    default=DEFAULT_DIFFERENCE,
    minimum=0,
    maximum=1,
)


def layer_file(layer: str) -> str:
    return f"layer.{layer}.png"


def read_layers(folder: Path, asset: str) -> list[dict[str, Any]]:
    """The Layers a built `layers.json` in `folder` lists: `id`, `file` and `pixels`, in order of first click. An older
    file is refused, naming the rebuild."""
    built = json.loads((folder / LAYERS_FILE).read_text(encoding="utf-8"))
    if built.get("schema_version") != LAYERS_SCHEMA_VERSION:
        raise StageFailure(f"{LAYERS_FILE} has schema_version {built.get('schema_version')}; this Kiripix reads "
                           f"{LAYERS_SCHEMA_VERSION}. Rebuild it: kiripix run {asset} {LAYERS_STAGE} --force")
    listed: list[dict[str, Any]] = built["layers"]
    return listed


def hole_of(alphas: list[np.ndarray], shape: tuple[int, ...]) -> np.ndarray:
    """The hole behind the Layers: the union of their alphas (each a bool Mask, or an RGBA image's alpha above 0)."""
    hole = np.zeros(shape[:2], dtype=np.bool_)
    for alpha in alphas:
        hole |= alpha[..., 3] > 0 if alpha.ndim == 3 else alpha
    return hole


def click_decision() -> DecisionSpec:
    return point_decision(
        "click",
        "Lift an object into a foreground Layer: a positive click on a Layer ID segments the object under it, and a "
        "negative one takes the object under it away from the Layer, wherever it came from; a later positive click can "
        "add it back. The Layer ID is lower-case letters, digits and "
        "underscores, and `plate` is reserved. The Plate is filled behind the lifted object. Needs `run --rerun`.",
        on_image=True, layer={"type": "string", "pattern": LAYER_ID}, positive={"type": "boolean"},
    )


def trim_decision() -> DecisionSpec:
    return DecisionSpec(
        name="trim",
        description="A brush stroke, in target pixels, on one Layer's alpha: those pixels leave the Layer and go back "
                    "to the Plate, for a rim the segmentation left. It replays in order with the clicks, and needs no "
                    "Runner call.",
        entry_schema={
            "type": "object",
            "properties": {
                "layer": {"type": "string", "pattern": LAYER_ID},
                "radius": {"type": "integer", "minimum": 0},
                "points": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2,
                                                       "maxItems": 2}, "minItems": 1},
            },
            "required": ["layer", "radius", "points"],
            "additionalProperties": False,
        },
        on_image=True,
    )


DECISIONS = (PLATE, click_decision(), trim_decision())


def plate_hash(run: StageRun) -> str | None:
    """The stored Plate image the latest `plate` Decision names: the Layers come from a difference, not a Runner."""
    found = [d for d in run.decisions if d.name == PLATE.name]
    return str(found[-1].data["png"]) if found else None


def _plate_needs_input(run: StageRun, png_hash: str) -> NeedsInput | None:
    undo = f"Undo it: kiripix undo {run.asset_id} {LAYERS_STAGE}"
    path = stored_image(run, png_hash)
    if not path.is_file():
        return NeedsInput(f"the plate Decision names {'/'.join(IMPORT_DIR)}/{path.name}, which is missing",
                          owner_action=f"{undo}.")
    source = run.upstream["source"] / "source.png"
    if not source.is_file():
        return None
    with Image.open(path) as image, Image.open(source) as full:
        if image.size != full.size:
            return NeedsInput(f"the Plate image is {image.width}x{image.height} but the Source is "
                              f"{full.width}x{full.height}",
                              owner_action=f"{undo}, then import a Plate image of the Source's size.")
    return None


def _relevant(run: StageRun) -> tuple[CurrentDecision, ...]:
    """The lifting Decisions; the `plate` Decision only changes where a click gets its Layer (ticket 0044)."""
    return tuple(d for d in run.decisions if d.name in ("click", "trim"))


def needs_input(run: StageRun) -> NeedsInput | None:
    read = read_grid(run)
    undo = f"Undo it: kiripix undo {run.asset_id} {LAYERS_STAGE}"
    png_hash = plate_hash(run)
    if png_hash is not None and (wrong := _plate_needs_input(run, png_hash)) is not None:
        return wrong
    seen: set[str] = set()
    for group in click_groups(_relevant(run)):
        first = group[0]
        layer = str(first.data["layer"])
        if first.name == "trim":
            if layer not in seen:
                return NeedsInput(f"the trim on {layer} comes before any click lifted {layer}", owner_action=f"{undo}.")
            continue
        if not first.data["positive"] and layer not in seen:
            # A Layer has no source but its positive clicks, so there is nothing yet to take away from.
            return NeedsInput(f"the negative click at ({first.data['x']}, {first.data['y']}) comes before any positive "
                              f"click lifted {layer}", owner_action=f"{undo}.")
        seen.add(layer)
        for decision in group:
            x, y = int(decision.data["x"]), int(decision.data["y"])
            if read is not None and not (x < read[0].width and y < read[0].height):
                return NeedsInput(f"the click at ({x}, {y}) is outside the {read[0].width}x{read[0].height} fit image",
                                  owner_action=f"{undo}.")
    if png_hash is not None and read is not None:
        return _missed_click(run, read, png_hash, undo)
    return None


def _missed_click(run: StageRun, read: tuple[Grid, dict[str, Any]], png_hash: str, undo: str) -> NeedsInput | None:
    """A click on the difference path that isn't on any region the full image and the Plate image differ in."""
    fit_path = run.upstream["fit"] / "fit.png"
    if not fit_path.is_file() or not (run.upstream["source"] / "source.png").is_file():
        return None
    try:
        difference = _difference(run, read, png_hash, read_rgba(fit_path)[..., 3] == 255)
    except StageFailure:
        return None  # a Plate image changed after import: the run fails and says so
    for decision in (d for d in _relevant(run) if d.name == "click"):
        x, y = int(decision.data["x"]), int(decision.data["y"])
        if difference.label[y, x] < 0:
            return NeedsInput(f"the click at ({x}, {y}) is not on a region the full image and the Plate image differ "
                              f"in", owner_action=f"{undo}, or lower `difference`: kiripix set {run.asset_id} "
                                                  f"{LAYERS_STAGE} difference=<lower>.")
    return None


@dataclass
class _Lift:
    """What the Decisions lift, from the pinned segmentations, in target pixels."""

    layers: dict[str, np.ndarray] = field(default_factory=dict)  # each Layer's final alpha, in order of first click
    fills: list[tuple[RunnerCall, np.ndarray]] = field(default_factory=list)  # each fill call, and its hole's target Mask
    mapped_plate: np.ndarray | None = None  # on the difference path: the Plate image mapped to the target, no fills


def _clicks_of(group: list[CurrentDecision]) -> list[dict[str, Any]]:
    return [{"x": d.data["x"], "y": d.data["y"], "positive": d.data["positive"]} for d in group]


@dataclass
class _Difference:
    """Where the full image and the Plate image differ, mapped to the target through the Grid transform."""

    label: np.ndarray  # each target pixel's connected region of the difference, or -1
    partial: np.ndarray
    mapped_plate: np.ndarray


def _difference(run: StageRun, read: tuple[Grid, dict[str, Any]], png_hash: str, opaque: np.ndarray) -> _Difference:
    grid, record = read
    path = stored_image(run, png_hash)
    check_unchanged(path, png_hash)
    full, plate = read_rgba(run.upstream["source"] / "source.png"), read_rgba(path)
    difference = mask_from_difference(full, plate, float(run.params["difference"]))
    label = np.full(opaque.shape, -1, dtype=np.int64)
    for number, region in enumerate(connected_regions(mask_to_target(difference, grid) & opaque)):
        label[region[:, 0], region[:, 1]] = number
    mapped = downscale_mode(plate, grid) if record["mode"] == "downscale" else sample_nearest(plate, grid)
    return _Difference(label, partial_cells(difference, grid), mapped)


def _region_at(run: StageRun, difference: _Difference, x: int, y: int) -> np.ndarray:
    number = difference.label[y, x]
    if number < 0:  # `needs_input` stops this first; kept so a run never lifts nothing in silence
        raise StageFailure(f"the click at ({x}, {y}) is not on a region the full image and the Plate image differ in; "
                           f"undo it (kiripix undo {run.asset_id} {LAYERS_STAGE}), or lower `difference`")
    result: np.ndarray = difference.label == number
    return result


def _lift(run: StageRun, read: tuple[Grid, dict[str, Any]]) -> _Lift | None:
    """The Layers' alphas and the fill calls, or None while a segmentation isn't pinned yet."""
    grid, record = read
    source = run.upstream["source"] / "source.png"
    fit = read_rgba(run.upstream["fit"] / "fit.png")
    opaque = fit[..., 3] == 255
    grow = int(run.params["grow"])
    lift = _Lift()
    png_hash = plate_hash(run)
    difference = _difference(run, read, png_hash, opaque) if png_hash is not None else None
    if difference is not None:
        lift.mapped_plate = difference.mapped_plate
    lifted: list[tuple[list[CurrentDecision], np.ndarray]] = []  # each click group's grown alpha, before any trim
    for group in click_groups(_relevant(run)):
        run.check_cancel()
        layer = str(group[0].data["layer"])
        if group[0].name == "trim":
            data = group[0].data
            stroke = paint_stroke(np.zeros_like(opaque), [(int(x), int(y)) for x, y in data["points"]],
                                  int(data["radius"]))
            lift.layers[layer] = lift.layers[layer] & ~stroke
            continue
        positive = bool(group[0].data["positive"])
        if difference is not None:  # one click names a connected region
            alpha = grow_where_partial(_region_at(run, difference, int(group[0].data["x"]), int(group[0].data["y"])),
                                       difference.partial, grow) & opaque
        else:
            path = run.pinned(click_call(group, grid, source))
            if not path.is_file():
                return None
            with Image.open(path) as image:
                on_source = runner_mask_on_source(image, read)
            alpha = grow_where_partial(mask_to_target(on_source, grid), partial_cells(on_source, grid), grow) & opaque
        if not positive:  # takes its segment away from the Layer, whatever put it there
            lift.layers[layer] = lift.layers[layer] & ~alpha
            continue
        if difference is None:
            lifted.append((group, alpha))
        lift.layers[layer] = lift.layers.get(layer, np.zeros_like(opaque)) | alpha
    if difference is not None:
        return lift
    union = np.zeros_like(opaque)
    for _, alpha in lifted:
        union |= alpha
    source_width, source_height = record["source"]
    for region in connected_regions(union):
        run.check_cancel()
        hole = np.zeros_like(opaque)
        hole[region[:, 0], region[:, 1]] = True
        # What the Owner decided that made this hole: the clicks whose alpha lies in it. A new `grow` moves the hole but
        # not these, so a changed hole is "Runner input changed" rather than a call never made.
        clicks = [_clicks_of(group) for group, alpha in lifted if (alpha & hole).any()]
        params = hole_params(mask_to_source(hole, grid, int(source_width), int(source_height)), FILL_MARGIN)
        call = RunnerCall(runner=runners.INPAINTER, image=source, params=params, decisions=[{"fill": clicks}])
        lift.fills.append((call, hole))
    return lift


def runner_calls(run: StageRun) -> list[RunnerCall]:
    """The segmentations, and once they are all pinned, a fill for each hole they leave."""
    read = read_grid(run)
    source = run.upstream["source"] / "source.png"
    if read is None or not source.is_file() or not (run.upstream["fit"] / "fit.png").is_file() \
            or plate_hash(run) is not None or needs_input(run) is not None:  # a Plate image: no Runner call
        return []
    segmentations = [click_call(group, read[0], source) for group in click_groups(_relevant(run))
                     if group[0].name == "click"]
    if not segmentations:
        return []
    lift = _lift(run, read)
    if lift is None:
        return segmentations
    return segmentations + [call for call, _ in lift.fills]


def _filled_plate(run: StageRun, read: tuple[Grid, dict[str, Any]], fit: np.ndarray, lift: _Lift,
                  hole: np.ndarray) -> np.ndarray:
    """The fit image with each hole filled: the fills pasted onto the Source, which `fit` maps again, the same way."""
    grid, record = read
    filled = read_rgba(run.upstream["source"] / "source.png")
    for call, _ in lift.fills:
        run.check_cancel()
        path = run.pinned(call)
        if not path.is_file():
            raise StageFailure("a fill has no pinned result; run it with --rerun")
        top, left, bottom, right = call.params["crop"]
        patch = read_rgba(path)
        if patch.shape[:2] != (bottom - top, right - left):
            raise StageFailure(f"the inpainting Runner returned {patch.shape[1]}x{patch.shape[0]}, not its "
                               f"{right - left}x{bottom - top} crop")
        inside = hole_mask(call.params, filled.shape[:2])[top:bottom, left:right]
        region = filled[top:bottom, left:right]
        region[inside] = patch[inside]
    mapped = downscale_mode(filled, grid) if record["mode"] == "downscale" else sample_nearest(filled, grid)
    plate = fit.copy()
    plate[hole] = mapped[hole]
    return plate


def run_layers(run: StageRun) -> None:
    fit_path = run.upstream["fit"] / "fit.png"
    read = read_grid(run)
    fit = read_rgba(fit_path)
    height, width = fit.shape[:2]
    out = run.output_dir
    layers: dict[str, np.ndarray] = {}
    if read is not None and _relevant(run):
        lift = _lift(run, read)
        if lift is None:
            raise StageFailure("a segmentation isn't pinned yet; run it with --rerun")
        layers = lift.layers
        hole = hole_of(list(layers.values()), fit.shape)
        if lift.mapped_plate is not None:  # inside a hole the Plate image, everywhere else the fit image
            plate = fit.copy()
            plate[hole] = lift.mapped_plate[hole]
        else:
            plate = _filled_plate(run, read, fit, lift, hole)
        write_rgba(out / "plate.png", plate)
    else:
        shutil.copyfile(fit_path, out / "plate.png")
        hole = np.zeros((height, width), dtype=np.bool_)
    listed = []
    for layer, alpha in layers.items():
        run.check_cancel()
        write_rgba(out / layer_file(layer), cut_by_alpha(fit, alpha))
        listed.append({"id": layer, "file": layer_file(layer), "pixels": int(alpha.sum())})
    Image.fromarray(hole).save(out / FOREGROUND_FILE, format="PNG")
    built = {"schema_version": LAYERS_SCHEMA_VERSION, "layers": listed}
    (out / LAYERS_FILE).write_text(json.dumps(built, indent=2) + "\n", encoding="utf-8")


def _box(mask: np.ndarray, asset: str) -> Position:
    ys, xs = np.nonzero(mask)
    return Position(asset=asset, stage=LAYERS_STAGE, x=int(xs.min()), y=int(ys.min()),
                    width=int(xs.max() - xs.min() + 1), height=int(ys.max() - ys.min() + 1))


def check_layers(run: StageRun) -> list[Finding]:
    out = run.output_dir
    fit = read_rgba(run.upstream["fit"] / "fit.png")
    plate = read_rgba(out / "plate.png")  # as the Overrides painted it
    layers = [read_rgba(out / str(entry["file"])) for entry in read_layers(out, run.asset_id)]
    hole = hole_of(layers, fit.shape)
    findings: list[Finding] = []
    asset = run.asset_id
    unfilled = hole & (plate[..., 3] == 0)
    if unfilled.any():
        findings.append(
            Finding(
                code="layers.plate_hole",
                message=f"the Plate is transparent in {int(unfilled.sum())} px of the hole behind the Layers",
                position=_box(unfilled, asset),
                owner_action=f"Paint those pixels with an Override on {LAYERS_STAGE} (inside the hole, so the Layers "
                             f"still recompose), or lift again: undo the click and `kiripix run {asset} {LAYERS_STAGE} "
                             f"--rerun`.",
            )
        )
    differs = (recompose(plate, layers) != fit).any(axis=2)
    outside = differs & ~hole
    inside = differs & hole
    if outside.any():
        findings.append(
            Finding(
                code="layers.recompose_mismatch",
                message=f"the Plate differs from the fit image in {int(outside.sum())} px outside the Layers' hole, so "
                        f"Plate and Layers no longer recompose to it",
                position=_box(outside, asset),
                owner_action=f"Paint on the fit stage instead: an Override on {LAYERS_STAGE} may only paint inside the "
                             f"hole behind a Layer. Undo it: kiripix undo {asset} {LAYERS_STAGE}.",
            )
        )
    if inside.any():
        findings.append(
            Finding(
                code="layers.recompose_mismatch",
                message=f"a Layer differs from the fit image in {int(inside.sum())} px, so Plate and Layers no longer "
                        f"recompose to it",
                position=_box(inside, asset),
                fix=f"kiripix run {asset} {LAYERS_STAGE} --force",
            )
        )
    return findings
