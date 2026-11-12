"""What rooms and props share (spec §6.1, §6.2): reading and writing images, the Source Stage, the Grid transform `fit`
records, the fit and palette Stages' work and their Checks. A Recipe passes in what differs, such as the image to map;
which Stage is upstream stays with the Recipe."""

from __future__ import annotations

import hashlib
import json
import shutil
from fractions import Fraction
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

from kiripix.checks import Finding, Position, check_conformance, check_mapping_error
from kiripix.ops import (
    BayerSize,
    Grid,
    alpha_by_vote,
    has_partial_alpha,
    conformance,
    detect_grid,
    downscale,
    mask_to_target,
    parse_gpl,
    mapping_error,
    parse_hex,
    quantize,
    remove_orphans,
    sample_nearest,
    target_centre,
)
from kiripix.recipes.base import (
    PICK,
    BoxCorners,
    ClickPoint,
    CurrentDecision,
    NeedsInput,
    RunnerCall,
    StageFailure,
    StageRun,
)
from kiripix.runners import SEGMENTER

# images


def read_rgba(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()


def write_rgba(path: Path, rgba: np.ndarray) -> None:
    Image.fromarray(rgba, "RGBA").save(path, format="PNG")


# source: the Variants are src/<hash>.png, imported (or, from M4, generated); the Pick chooses one.


def variants(run: StageRun) -> dict[str, Path]:
    return {Path(name).stem: path for name, path in run.files.items()}


def picked(run: StageRun) -> str | None:
    picks = [d for d in run.decisions if d.name == PICK.name]
    return str(picks[-1].data["variant"]) if picks else None


def source_needs_input(run: StageRun) -> NeedsInput | None:
    found = sorted(variants(run))
    chosen = picked(run)
    if chosen in found:
        return None
    reason = "no Source picked" if chosen is None else f"the picked Variant {chosen} was deleted"
    if not found:
        return NeedsInput(reason, command=f"kiripix import {run.asset_id} <file>")
    if len(found) == 1:
        return NeedsInput(reason, command=f"kiripix pick {run.asset_id} {found[0]}")
    return NeedsInput(reason, owner_action=f"Pick one of the Variants {', '.join(found)}: "
                                           f"kiripix pick {run.asset_id} <variant>")


def run_source(run: StageRun) -> None:
    chosen = picked(run)
    assert chosen is not None  # `source_needs_input` holds the Stage back until there is a Pick
    path = variants(run)[chosen]
    if not hashlib.sha256(path.read_bytes()).hexdigest().startswith(chosen):
        raise StageFailure(f"the Variant {path.name} was changed after it was imported, and Variants are immutable; "
                           "import the changed image as a new Variant and pick that")
    shutil.copyfile(path, run.output_dir / "source.png")


# fit: the Source's pixel grid (or a one-scale downscale) down to the brief's exact size. Palette-free.


def brief_size(run: StageRun) -> tuple[int, int]:
    brief = json.loads((run.upstream["brief"] / "brief.json").read_text(encoding="utf-8"))
    return int(brief["width"]), int(brief["height"])


def read_grid(run: StageRun) -> tuple[Grid, dict[str, Any]] | None:
    """The Grid transform recorded by `fit`, and the record itself; None until `fit` is built."""
    path = run.upstream["fit"] / "grid.json"
    if not path.is_file():
        return None
    record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return Grid.from_json(record), record


def run_fit(run: StageRun, image: Path, *, vote_alpha: bool = False) -> None:
    """Fit `image` to the brief's size. In `downscale` mode the scale is the same on both axes and the rest of the Source
    is cropped (`offset_x` and `offset_y` place the crop). With `vote_alpha`, alpha goes to the target grid by majority
    vote in either mode (a prop's matte has partial alpha); a room's alpha is the centre pixel's in grid mode."""
    source = read_rgba(image)
    height, width = source.shape[:2]
    target_width, target_height = brief_size(run)
    mode = str(run.params["mode"])
    scale = int(run.params["scale"])
    if mode == "downscale":
        try:
            grid = Grid.cover(width, height, target_width, target_height, int(run.params["offset_x"]),
                              int(run.params["offset_y"]))
        except ValueError as error:
            if "largest" in str(error):
                raise StageFailure(str(error)) from None
            raise StageFailure(f"can't downscale the {width}x{height} Source to the brief's "
                               f"{target_width}x{target_height}: the Source is smaller") from None
        fitted = downscale(source, grid)
    else:
        try:
            grid = (Grid.uniform(scale, int(run.params["offset_x"]), int(run.params["offset_y"]), width, height)
                    if scale > 0 else detect_grid(source))
        except ValueError as error:
            raise StageFailure(str(error)) from None
        if grid.width < target_width or grid.height < target_height:  # pad right and bottom, so no coordinate moves
            grid = grid.padded_to(max(grid.width, target_width), max(grid.height, target_height))
        fitted = sample_nearest(source, grid)
        if vote_alpha:
            fitted = alpha_by_vote(fitted, source, grid)
    write_rgba(run.output_dir / "fit.png", fitted)
    record = {"mode": mode, "source": [width, height], **grid.to_json()}
    (run.output_dir / "grid.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


CROP_NOTICE = 4  # Source pixels cropped on an axis from which `fit.cropped` is said


def _cropped(run: StageRun, grid: dict[str, Any]) -> list[Finding]:
    """An info finding when `downscale` crops more than a few Source pixels off an axis, with the `set` that centres it."""
    source_width, source_height = grid["source"]
    record = Grid.from_json(grid)
    dropped_x = int(source_width - record.edges_x()[-1] + record.offset_x)
    dropped_y = int(source_height - record.edges_y()[-1] + record.offset_y)
    axes = [(name, dropped) for name, dropped, offset in (("x", dropped_x, record.offset_x),
                                                         ("y", dropped_y, record.offset_y))
            if dropped > CROP_NOTICE and abs(offset - dropped // 2) > 1]  # nothing to say once it is centred
    if not axes:
        return []
    centred = " ".join(f"offset_{name}={dropped // 2}" for name, dropped in axes)
    said = " and ".join(f"{dropped} Source pixels across {name}" for name, dropped in axes)
    return [
        Finding(
            code="fit.cropped",
            severity="info",
            message=f"fit crops {said} to keep one scale on both axes; offset_x={record.offset_x} offset_y="
                    f"{record.offset_y} place the crop from the top left",
            position=Position(asset=run.asset_id, stage="fit", field="stages.fit.offset_x"),
            fix=f"kiripix set {run.asset_id} fit {centred}",
        )
    ]


def whole_tiles(size: int, tile: int) -> int:
    """`size` rounded up to whole tiles."""
    return -(-size // tile) * tile


def _padded(run: StageRun, grid: dict[str, Any]) -> list[Finding]:
    """An info finding when `fit` padded the grid output up to the brief (grid mode only)."""
    right, bottom = int(grid.get("pad_right", 0)), int(grid.get("pad_bottom", 0))
    if not (right or bottom):
        return []
    said = " and ".join(f"{amount} px on the {side}" for amount, side in ((right, "right"), (bottom, "bottom")) if amount)
    return [
        Finding(
            code="fit.padded",
            severity="info",
            message=f"fit padded the {int(grid['width']) - right}x{int(grid['height']) - bottom} grid output up to the "
                    f"brief's {grid['width']}x{grid['height']} with transparent pixels, {said}",
            position=Position(asset=run.asset_id, stage="fit", field="stages.fit.offset_x"),
            owner_action="Nothing is needed for the room to work. If the strip shouldn't be there, widen the Source or "
                         f"move the offset: kiripix set {run.asset_id} fit offset_x=<smaller> offset_y=<smaller>.",
        )
    ]


def check_fit(run: StageRun) -> list[Finding]:
    grid = json.loads((run.output_dir / "grid.json").read_text(encoding="utf-8"))
    width, height = int(grid["width"]), int(grid["height"])
    target_width, target_height = brief_size(run)
    if (width, height) == (target_width, target_height):
        return _cropped(run, grid) if grid["mode"] == "downscale" else _padded(run, grid)
    source_width, source_height = grid["source"]
    asset = run.asset_id
    ratio = source_width // target_width if target_width else 0
    detected = int(run.params["scale"]) == 0
    extra = ""
    exact = source_width == ratio * target_width and source_height == ratio * target_height and ratio >= 1
    if grid["mode"] == "grid" and not (exact and int(run.params["scale"]) != ratio):
        if detected and Fraction(grid["scale_x"]) == 1 and Fraction(grid["scale_y"]) == 1:
            fix = f"kiripix set {asset} fit mode=downscale"  # detection found no grid: the grid itself is wrong
        else:
            # The grid output is larger than the brief on an axis (a smaller one is padded): a brief that holds it
            # pads the rest. An Owner who'd rather crop takes the offsets that cut the extra off the left and top.
            brief = json.loads((run.upstream["brief"] / "brief.json").read_text(encoding="utf-8"))
            tile = int(brief.get("tile", 1))
            fix = (f"kiripix set {asset} brief width={whole_tiles(max(width, target_width), tile)} "
                   f"height={whole_tiles(max(height, target_height), tile)}")
            crops = []
            for name, size, target, scale, offset in (("x", width, target_width, grid["scale_x"], grid["offset_x"]),
                                                      ("y", height, target_height, grid["scale_y"], grid["offset_y"])):
                if size > target:
                    crops.append(f"offset_{name}={int(offset + (size - target) * Fraction(scale))}")
            if crops:
                extra = ("; to crop to the brief instead (a grid crops only from the left and top): "
                         f"kiripix set {asset} fit {' '.join(crops)}")
    else:
        fix = f"kiripix set {asset} fit scale={ratio}"
        if int(run.params["offset_x"]) or int(run.params["offset_y"]):
            fix += " offset_x=0 offset_y=0"
    if grid["mode"] != "grid":
        fix = _downscale_fix(run, asset, exact, ratio)
    return [
        Finding(
            code="fit.size_mismatch",
            message=f"the fit image is {width}x{height}, the brief asks for {target_width}x{target_height}{extra}",
            position=Position(asset=asset, stage="fit", field="stages.fit.scale"
                              if grid["mode"] == "grid" else "stages.fit.mode"),
            fix=fix,
        )
    ]


def _downscale_fix(run: StageRun, asset: str, exact: bool, ratio: int) -> str:
    """The fix when `downscale` mode misses the brief (a Source smaller than it): as before."""
    if exact:
        fix = f"kiripix set {asset} fit scale={ratio}"
        if int(run.params["offset_x"]) or int(run.params["offset_y"]):
            fix += " offset_x=0 offset_y=0"
        return fix
    return f"kiripix set {asset} fit mode=downscale"


# palette: the image mapped to the palette in OKLab (ADR 0004), then orphan pixels removed.

BAYER: dict[str, BayerSize] = {"none": 0, "bayer2": 2, "bayer4": 4, "bayer8": 8}


def palette_rgb(run: StageRun) -> np.ndarray:
    path: Path = run.settings["palette"]
    try:
        palette = parse_gpl(path.read_text(encoding="utf-8")) if path.suffix.lower() == ".gpl" else parse_hex(
            path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:  # PaletteSyntaxError is a ValueError
        raise StageFailure(f"can't read the palette {path.name}: {error}") from None
    if not palette.entries:
        raise StageFailure(f"the palette {path.name} has no colours")
    return palette.rgb()


def quantize_to_palette(run: StageRun, rgba: np.ndarray, what: str) -> np.ndarray:
    """`rgba` (called `what` in a failure) mapped to the palette, its transparent pixels kept, orphans not yet removed."""
    palette = palette_rgb(run)
    run.check_cancel()
    try:
        return quantize(rgba, palette, BAYER[str(run.params["dither"])], float(run.params["strength"]))
    except ValueError as error:
        raise StageFailure(f"the {what} can't be mapped: {error}") from None


def map_to_palette(run: StageRun, rgba: np.ndarray, what: str) -> np.ndarray:
    """`rgba` (called `what` in a failure) mapped to the palette, its transparent pixels kept, orphans removed."""
    mapped = quantize_to_palette(run, rgba, what)
    run.check_cancel()
    return remove_orphans(mapped, int(run.params["orphan_size"]))


def run_palette(run: StageRun, image: Path, what: str) -> None:
    """Map `image` (called `what` in a failure) to the palette, keep its transparent pixels, and write palette.png."""
    write_rgba(run.output_dir / "palette.png", map_to_palette(run, read_rgba(image), what))


def check_palette(run: StageRun) -> list[Finding]:
    try:
        palette = palette_rgb(run)
    except StageFailure:
        return []  # the palette's own Checks report it
    report = conformance(read_rgba(run.output_dir / "palette.png"), palette)
    findings = check_conformance(report, "palette.png", fix=f"kiripix run {run.asset_id} palette --force")
    for finding in findings:
        assert finding.position is not None
        finding.position.asset, finding.position.stage = run.asset_id, "palette"
    return findings + _check_against_fit(run)


def _check_against_fit(run: StageRun) -> list[Finding]:
    """The palette image against the `fit` image it came from, when `fit` is an input and the sizes agree."""
    fit = run.upstream.get("fit")
    if fit is None or not (fit / "fit.png").is_file():
        return []
    source, mapped = read_rgba(fit / "fit.png"), read_rgba(run.output_dir / "palette.png")
    if source.shape != mapped.shape or has_partial_alpha(mapped):
        return []
    return check_mapping(run, source, mapped, fit / "fit.png")


def check_mapping(run: StageRun, source: np.ndarray, mapped: np.ndarray, fit_image: Path) -> list[Finding]:
    """Warn when `mapped` is far from `source` in OKLab, with the `palette-suggest` that grows the palette from
    `fit_image` (a file of the Asset's `fit` output; its path is given from the Project's root)."""
    try:
        shown = fit_image.relative_to(run.asset_dir.parent.parent.parent).as_posix()
    except ValueError:
        shown = fit_image.as_posix()
    fix = f"kiripix op palette-suggest {shown} --add 16 --scale 1"
    findings = check_mapping_error(mapping_error(source, mapped), "palette.png", fix=fix)
    for finding in findings:
        assert finding.position is not None
        finding.position.asset, finding.position.stage = run.asset_id, "palette"
    return findings


# Images a Decision names by hash (a painted Mask for `masks`, a Plate image for `layers`): stored once by core, never
# changed after.

IMPORT_DIR = ("decisions", "imports")  # under the Asset folder; each image is `<sha256>.png`


def stored_image(run: StageRun, png_hash: str) -> Path:
    return run.asset_dir.joinpath(*IMPORT_DIR, f"{png_hash}.png")


def check_unchanged(path: Path, png_hash: str) -> None:
    """Fail the run if a stored image no longer has the hash that names it."""
    if hashlib.sha256(path.read_bytes()).hexdigest() != png_hash:
        raise StageFailure(f"{path.name} was changed after it was imported; images named by hash are immutable")


# click to segment: shared by the masks and layers Stages. A `click`, positive or negative, segments the object under it:
# one Runner call each, with the same params. A positive click adds the segment to its target (a Mask for `masks`, a
# Layer for `layers`), a negative click takes it away from the target at its place in the replay. The Runner works on the Source, capped; the clicks map to it through the Grid
# transform, and its Mask maps back through the same transform (ADR 0004).

RUNNER_MAX_SIZE = 1536  # px on the longer side, to fit 8 GB of VRAM (ADR 0004)


def click_groups(decisions: tuple[CurrentDecision, ...]) -> list[list[CurrentDecision]]:
    """The Decisions in order, each in a list of its own. A negative `click` is not joined to the click before it: it is
    its own call, the same as a positive click at that point, and its segment is taken away at its place in the replay
    (ticket 0070)."""
    return [[decision] for decision in decisions]


def click_params(clicks: list[ClickPoint], grid: Grid) -> dict[str, Any]:
    try:
        points = [[*target_centre(grid, x, y), positive] for x, y, positive in clicks]
    except ValueError:
        x, y = next((x, y) for x, y, _ in clicks if padded_click(grid, x, y))
        raise StageFailure(f"the click at ({x}, {y}) is in the padded strip of the fit image (the right "
                           f"{grid.pad_right} and bottom {grid.pad_bottom} px), which has no Source pixels") from None
    return {"points": points, "max_size": RUNNER_MAX_SIZE}


def click_call(group: list[CurrentDecision], grid: Grid, source: Path) -> RunnerCall:
    """The SEGMENTER call of a click. A negative click is segmented as a positive click at that point would be, so both
    make the same call and share one pinned result and one Probe embedding; the sign is the replay's, not the Runner's.
    Its `decisions` leave out which Mask or Layer, so the same clicks in `masks` and in `layers` are one pinned result."""
    clicks = [(int(d.data["x"]), int(d.data["y"]), True) for d in group]
    return RunnerCall(
        runner=SEGMENTER,
        image=source,
        params=click_params(clicks, grid),
        decisions=[{"x": d.data["x"], "y": d.data["y"], "positive": True} for d in group],
    )


# A `box` segments the object a rough box holds: one call like a click's, with `box` in place of `points`, in Source pixels
# (the box's outer edges through the Grid transform). Its sign is the replay's, as a click's is (ticket 0079).


def box_of(decision: CurrentDecision) -> BoxCorners:
    data = decision.data
    return int(data["x0"]), int(data["y0"]), int(data["x1"]), int(data["y1"])


def box_problem(box: BoxCorners, width: int, height: int, pad_right: int = 0, pad_bottom: int = 0) -> str | None:
    """Why a box can't be used on a `width` x `height` target, or None. A box that only overlaps the padded strip is
    clipped to the cells with Source pixels; one that starts in it has none."""
    x0, y0, x1, y1 = box
    if x1 < x0 or y1 < y0:
        return "runs backwards: x1 and y1 are not below x0 and y0"
    if x1 >= width or y1 >= height:
        return f"is outside the {width}x{height} Plate"
    if x0 >= width - pad_right or y0 >= height - pad_bottom:
        return (f"starts in the padded strip (the right {pad_right} and bottom {pad_bottom} px), "
                "which has no Source pixels")
    return None


def padded_click(grid: Grid, x: int, y: int) -> bool:
    """Whether target pixel (x, y) is in the padded strip."""
    return x >= grid.cells_x or y >= grid.cells_y


def box_params(box: BoxCorners, grid: Grid) -> dict[str, Any]:
    x0, y0, x1, y1 = box
    edges_x, edges_y = grid.edges_x(), grid.edges_y()
    return {"box": [int(edges_x[x0]), int(edges_y[y0]), int(edges_x[x1 + 1]), int(edges_y[y1 + 1])],
            "max_size": RUNNER_MAX_SIZE}


def box_call(box: BoxCorners, grid: Grid, source: Path) -> RunnerCall:
    """The SEGMENTER call of a box, positive or negative alike, as `click_call` does for a click."""
    return RunnerCall(runner=SEGMENTER, image=source, params=box_params(box, grid),
                      decisions=[{"box": list(box), "positive": True}])


def lift_call(group: list[CurrentDecision], grid: Grid, source: Path) -> RunnerCall:
    """The SEGMENTER call of a `click` or a `box` group."""
    return box_call(box_of(group[0]), grid, source) if group[0].name == "box" else click_call(group, grid, source)


def runner_mask_to_target(mask: Image.Image, read: tuple[Grid, dict[str, Any]]) -> np.ndarray:
    grid, record = read
    source_width, source_height = record["source"]
    on_source = mask.convert("1").resize((int(source_width), int(source_height)), Image.Resampling.NEAREST)
    return mask_to_target(np.asarray(on_source, dtype=np.bool_), grid)


def runner_mask_on_source(mask: Image.Image, read: tuple[Grid, dict[str, Any]]) -> np.ndarray:
    """A Runner's Mask at the Source's size, before it goes to the target grid."""
    _, record = read
    source_width, source_height = record["source"]
    on_source = mask.convert("1").resize((int(source_width), int(source_height)), Image.Resampling.NEAREST)
    return np.asarray(on_source, dtype=np.bool_)
