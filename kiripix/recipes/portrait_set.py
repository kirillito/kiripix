"""The portrait's image Stages (ticket 0243, spec §6.7): cutout, register, fit, palette, finish.

Every Stage works on the whole set: the neutral image and each declared emotion. A Stage's output folder holds the neutral
image as `<image>` (`cutout.png`, `register.png`, `fit.png`, `palette.png`, `finish.png`) and each emotion as
`emotions/<id>.png`, plus a record (`cutout.json`, `register.json`, `grid.json`, `palette.json`, `finish.json`) that lists the
emotions in declaration order, so the next Stage reads the set from it.

- **cutout:** the Prop's, on every image. The chroma key has a tolerance and a key read from each image's border (a lossy
  image model's green differs by image), and the key's spill, a light rim and small islands go. Matting is one pinned call
  per image.
- **register:** off by default (ticket 0321): the game's rules free the pose, the arms and the head's turn between emotions, so
  every emotion passes through as it is. `figure` lays each emotion on the neutral over the whole figure, `outside_face`
  outside the `face` region (a polygon or a brush, drawn in the neutral cutout's pixels), with the Looks' registration. Writes
  each emotion's Alignment and its residual in target pixels.
- **fit:** one Grid transform for the set, from the neutral: one scale that puts the figure's top row `head_top` px below the
  canvas top and its lowest row on the anchor's row, and the crop that centres it on the anchor's column; where the source
  has no pixels the canvas is transparent. `head_top` -1 is `Grid.cover`'s fill. Applied to every emotion; the alpha goes to
  the grid by vote.
- **palette:** the set's own colours (`set`, over every image together), the Project's (`project`) or none (`off`).
- **finish:** the pale grey specks the cutout left on the edge cleared (`clear_light_edge`, ticket 0322), the outline, then, if
  switched on, `lock_outside_face`: outside the `face` region every emotion takes the neutral's pixels.
  `portrait.out_of_canvas` flags a figure within `SPARE` px of the top, left or right edge.
"""

from __future__ import annotations

import hashlib
import json
import re
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

from kiripix.checks import Finding, Position, check_alpha, check_chroma_cutout, check_conformance
from kiripix.ops import (
    Grid,
    border_colour,
    chroma_key_tolerant,
    clear_light_edge,
    conformance,
    connected_regions,
    downscale,
    fill_polygon,
    has_partial_alpha,
    light_edge,
    map_set,
    mask_touching_target,
    outline_mask,
    paint_outline,
    paint_stroke,
    register,
    remove_key_spill,
    remove_light_rim,
    remove_orphans,
    remove_small_islands,
    resize_nearest,
    set_colours,
    set_report,
    srgb_to_oklab,
    warp_nearest,
)
from kiripix.recipes.base import (
    CheckSpec,
    DecisionSpec,
    ParamSpec,
    RunnerCall,
    StageFailure,
    StageInputs,
    StageRun,
    StageSpec,
)
from kiripix.recipes.common import BAYER, palette_rgb, read_rgba, write_rgba
from kiripix.recipes.regions import (
    MISALIGNED_RESIDUAL,
    SCALE_LIMIT,
    SHIFT_LIMIT,
    read_mask,
    write_mask,
)
from kiripix.runners import MATTER

NEUTRAL = "neutral"  # the picked Source's ID in the set, and the default fallback emotion
EMOTIONS_OUT = "emotions"  # in a Stage's output folder: `emotions/<id>.png`
RECORD_SCHEMA_VERSION = 1  # of cutout.json, register.json, grid.json, palette.json and finish.json

BRIEF = "brief"
SOURCE = "source"
CUTOUT = "cutout"
REGISTER = "register"
FIT = "fit"
PALETTE = "palette"
FINISH = "finish"

IMAGE = {CUTOUT: "cutout.png", REGISTER: "register.png", FIT: "fit.png", PALETTE: "palette.png", FINISH: "finish.png"}
RECORD = {CUTOUT: "cutout.json", REGISTER: "register.json", FIT: "grid.json", PALETTE: "palette.json", FINISH: "finish.json"}
FACE_FILE = "face.png"  # register: the face region in the neutral cutout's pixels; fit: in target pixels
_RUNNER_MAX_SIZE = 1536  # px on the longer side, to fit 8 GB of VRAM (ADR 0004)
_CODE_VERSION = 2  # of the reuse keys below: bump with a Stage's `version` (2: register's `mode`, 0321)
SHIMMER_VISIBLE = 0.03  # OKLab distance from which a pixel that differs from the neutral's shows (trial 0241)
SHIMMER_BOXES = 8  # the boxes a `portrait.shimmer` lists, the largest first
SPARE = 2  # px every gesture keeps from the canvas's top, left and right edges; the bottom edge is the waist cut (0321)
HEAD_TOP = 40  # px from the canvas top to the neutral figure's top row (the game's portrait rule, 0240)
REGISTER_MODES = ["off", "figure", "outside_face"]
_HEX = re.compile("#[0-9A-Fa-f]{6}")


# the set's images


def ids_of(folder: Path, stage: str) -> list[str]:
    """The emotions a built Stage lists in its record, in declaration order."""
    record = json.loads((folder / RECORD[stage]).read_text(encoding="utf-8"))
    return [str(e) for e in record["emotions"]]


def image_file(folder: Path, stage: str, emotion: str) -> Path:
    return folder / IMAGE[stage] if emotion == NEUTRAL else folder / EMOTIONS_OUT / f"{emotion}.png"


def read_set(folder: Path, stage: str, ids: list[str]) -> dict[str, Any]:
    """The neutral and each emotion's image of a built Stage, neutral first."""
    return {name: read_rgba(image_file(folder, stage, name)) for name in (NEUTRAL, *ids)}


def write_one(folder: Path, stage: str, emotion: str, rgba: Any) -> None:
    if emotion != NEUTRAL:
        (folder / EMOTIONS_OUT).mkdir(exist_ok=True)
    write_rgba(image_file(folder, stage, emotion), rgba)


def write_record(folder: Path, stage: str, record: dict[str, Any]) -> None:
    text = json.dumps({"schema_version": RECORD_SCHEMA_VERSION, **record}, indent=2) + "\n"
    (folder / RECORD[stage]).write_text(text, encoding="utf-8")


def read_record(folder: Path, stage: str, asset: str) -> dict[str, Any]:
    """A built Stage's record. An older one is refused, naming the rebuild."""
    record: dict[str, Any] = json.loads((folder / RECORD[stage]).read_text(encoding="utf-8"))
    if record.get("schema_version") != RECORD_SCHEMA_VERSION:
        raise StageFailure(f"{RECORD[stage]} has schema_version {record.get('schema_version')}; this Kiripix reads "
                           f"{RECORD_SCHEMA_VERSION}. Rebuild it: kiripix run {asset} {stage} --force")
    return record


def brief_of(run: StageRun) -> dict[str, Any]:
    brief: dict[str, Any] = json.loads((run.upstream[BRIEF] / "brief.json").read_text(encoding="utf-8"))
    return brief


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reuse_key(*parts: Any) -> str:
    return hashlib.sha256(json.dumps([_CODE_VERSION, *parts], sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _kept(run: StageRun, stage: str, emotion: str, key: str) -> dict[str, Any] | None:
    """An image's entry in this Stage's previous record, when its inputs are the same (so its file is copied, not made again);
    the file is copied into the new output here. Nothing is reused after `--force`."""
    previous = run.previous
    if previous is None or run.forced or not (previous / RECORD[stage]).is_file():
        return None
    try:
        entries = json.loads((previous / RECORD[stage]).read_text(encoding="utf-8"))["images"]
        entry = entries[emotion]
        old = image_file(previous, stage, emotion)
        if entry.get("key") != key or not old.is_file():
            return None
    except (KeyError, ValueError, TypeError):
        return None
    if emotion != NEUTRAL:
        (run.output_dir / EMOTIONS_OUT).mkdir(exist_ok=True)
    shutil.copyfile(old, image_file(run.output_dir, stage, emotion))
    kept: dict[str, Any] = entry
    return kept


def _placed(found: list[Finding], asset: str, stage: str) -> list[Finding]:
    """A shared Check's findings, placed on this Asset's Stage."""
    for finding in found:
        assert finding.position is not None
        finding.position.asset, finding.position.stage = asset, stage
    return found


# cutout


def _chroma(run: StageRun) -> tuple[int, int, int] | None:
    """The fixed key, or None for `auto`: each image's border says."""
    colour = str(run.params["chroma"])
    if colour == "auto":
        return None
    if not _HEX.fullmatch(colour):
        raise StageFailure(f"the chroma colour {colour!r} isn't #RRGGBB or auto; "
                           f"kiripix set {run.asset_id} cutout chroma=auto", fix=f"kiripix set {run.asset_id} cutout chroma=auto")
    return int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)


def _source_images(run: StageRun) -> dict[str, Path]:
    folder = run.upstream[SOURCE]
    record = json.loads((folder / "emotions.json").read_text(encoding="utf-8"))
    found = {NEUTRAL: folder / "source.png"}
    for emotion in record["emotions"]:
        found[str(emotion)] = folder / EMOTIONS_OUT / f"{emotion}.png"
    return found


def _cutout_calls(run: StageRun) -> list[RunnerCall]:
    """One matting call for each image of the set that is built."""
    if run.params["method"] != "matting" or not (run.upstream[SOURCE] / "emotions.json").is_file():
        return []
    return [RunnerCall(runner=MATTER, image=path, params={"max_size": _RUNNER_MAX_SIZE}, decisions=[])
            for path in _source_images(run).values() if path.is_file()]


def _matted(run: StageRun, source: Any, path: Path) -> Any:
    height, width = source.shape[:2]
    [call] = [c for c in _cutout_calls(run) if c.image == path]
    with Image.open(run.pinned(call)) as opened:
        matte = opened.convert("RGBA").getchannel("A")
        if matte.size != (width, height):  # the call was capped: nearest, so the matte's own alpha values stay
            matte = matte.resize((width, height), Image.Resampling.NEAREST)
        alpha = np.asarray(matte, dtype=np.uint8)
    cut = source.copy()
    cut[..., 3] = np.minimum(source[..., 3], alpha)
    cut[cut[..., 3] == 0] = 0
    return cut


def _keyed(run: StageRun, source: Any) -> tuple[Any, dict[str, Any]]:
    """A chroma cutout: the tolerant key, the key's spill and the light rim at the edge, then the islands."""
    key = _chroma(run) or border_colour(source)
    tolerance = float(run.params["tolerance"])
    cut = chroma_key_tolerant(source, key, tolerance)
    keyed = int((cut[..., 3] == 0).sum())
    cut = remove_key_spill(cut, key, int(run.params["spill_reach"]))
    spill = int((cut[..., 3] == 0).sum()) - keyed
    cut = remove_light_rim(cut, int(run.params["rim_reach"]))
    rim = int((cut[..., 3] == 0).sum()) - keyed - spill
    opaque = cut[..., 3] != 0
    kept = remove_small_islands(opaque, int(run.params["islands"]))
    cut[opaque & ~kept] = 0
    return cut, {"chroma": list(key), "keyed": keyed, "spill": spill, "rim": rim, "islands": int((opaque & ~kept).sum())}


def _cutout(run: StageRun) -> None:
    images = _source_images(run)
    parameters = {k: v for k, v in run.params.items()}
    records: dict[str, Any] = {}
    reused = 0
    for index, (name, path) in enumerate(images.items()):
        run.check_cancel()
        run.progress(index, len(images), f"cutout of {name}")
        pinned = None
        if run.params["method"] == "matting":
            [call] = [c for c in _cutout_calls(run) if c.image == path]
            pinned = _digest(run.pinned(call))
        key = _reuse_key(parameters, _digest(path), pinned)
        entry = _kept(run, CUTOUT, name, key)
        if entry is None:
            source = read_rgba(path)
            if run.params["method"] == "matting":
                cut, info = _matted(run, source, path), {"chroma": None, "keyed": 0, "spill": 0, "rim": 0, "islands": 0}
            else:
                cut, info = _keyed(run, source)
            write_one(run.output_dir, CUTOUT, name, cut)
            entry = {"key": key, **info}
        else:
            reused += 1
        records[name] = entry
    if reused:
        run.notes.append(f"{reused} of {len(images)} images unchanged, not cut again")
    write_record(run.output_dir, CUTOUT, {"emotions": [e for e in images if e != NEUTRAL], "images": records})


def _check_cutout(run: StageRun) -> list[Finding]:
    if run.params["method"] != "chroma":
        return []
    record = read_record(run.output_dir, CUTOUT, run.asset_id)
    findings: list[Finding] = []
    for name in (NEUTRAL, *record["emotions"]):
        key = record["images"][name].get("chroma")
        if key is None:
            continue
        found = check_chroma_cutout(read_rgba(image_file(run.output_dir, CUTOUT, name)), (key[0], key[1], key[2]),
                                    f"{name}.png", fix=f"kiripix set {run.asset_id} cutout method=matting")
        findings += _placed(found, run.asset_id, CUTOUT)
    return findings


# register

FACE = DecisionSpec(
    name="face",
    description="Draw the face region, in the neutral cutout's pixels: where the emotions are meant to differ from the neutral "
                "image. Registration is estimated outside it, and `finish` takes the neutral's pixels outside it "
                "(`lock_outside_face`), so it must hold everything meant to change, a raised hand included. A polygon "
                "(`points`, at least three corners) or, with a `radius`, a brush stroke along `points`; `erase` clears. "
                "Decisions replay in order. Made on the neutral cutout: a new neutral Source puts it in needs-review.",
    entry_schema={
        "type": "object",
        "properties": {
            "points": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                       "minItems": 1},
            "radius": {"type": "integer", "minimum": 0},
            "erase": {"type": "boolean"},
        },
        "required": ["points"],
        "additionalProperties": False,
    },
    on_image=True,
    problem=lambda data: (f"a polygon needs at least three points, got {len(data['points'])}; give a `radius` for a brush "
                          "stroke" if "radius" not in data and len(data["points"]) < 3 else None),
)


def face_region(run: StageRun, shape: tuple[int, int]) -> Any:
    """The face region's Mask in the neutral cutout's pixels: the `face` Decisions replayed in order."""
    region = np.zeros(shape, dtype=np.bool_)
    for decision in run.decisions:
        if decision.name != FACE.name:
            continue
        data = decision.data
        points = [(int(x), int(y)) for x, y in data["points"]]
        erase = bool(data.get("erase", False))
        region = (paint_stroke(region, points, int(data["radius"]), erase=erase) if "radius" in data
                  else fill_polygon(region, points, erase=erase))
    return region


def _on_grey(rgba: Any, grey: int = 128) -> Any:
    """A cutout laid on one grey: registration reads a figure's texture, not the black of the cleared pixels."""
    out = rgba.copy()
    out[rgba[..., 3] == 0] = (grey, grey, grey, 255)
    out[..., 3] = 255
    return out


def _problems(alignment: Any, scale: float, residual: float) -> list[str]:
    problems = []
    for axis, value in (("x", alignment.scale_x), ("y", alignment.scale_y)):
        if abs(value - 1) > SCALE_LIMIT:
            problems.append(f"the edit's scale on {axis} is {value:.4f}, outside {1 - SCALE_LIMIT:.3f} to {1 + SCALE_LIMIT:.3f}")
    for axis, shift in (("x", alignment.shift_x), ("y", alignment.shift_y)):
        if abs(shift) / scale > SHIFT_LIMIT:
            problems.append(f"the edit is shifted {abs(shift) / scale:.1f} target px on {axis}, over {SHIFT_LIMIT:g}")
    if alignment.tiles and residual > MISALIGNED_RESIDUAL:
        problems.append(f"the edit's tiles still miss the neutral by {residual:.2f} target px (median) after registration, "
                        f"over {MISALIGNED_RESIDUAL:g}: it isn't a rescaled or shifted copy of it")
    return problems


def _register(run: StageRun) -> None:
    cut = run.upstream[CUTOUT]
    ids = ids_of(cut, CUTOUT)
    neutral = read_rgba(cut / IMAGE[CUTOUT])
    height, width = neutral.shape[:2]
    brief = brief_of(run)
    mode = str(run.params["mode"])
    scale = 1.0  # source px per target px, for the limits in target px: `Grid.cover`'s, near enough to `fit`'s
    if mode != "off":
        try:
            scale = float(Grid.cover(width, height, int(brief["width"]), int(brief["height"])).scale_x)
        except ValueError:
            raise StageFailure(f"the neutral image is {width}x{height}, smaller than the {brief['width']}x{brief['height']} "
                               "canvas; make it larger or the canvas smaller (kiripix set <asset> brief width=.. height=..)") from None
    face = face_region(run, (height, width))
    exclude = face if face.any() and mode == "outside_face" else None
    reference = _on_grey(neutral)
    face_hash = hashlib.sha256(face.tobytes()).hexdigest()
    neutral_hash = _digest(cut / IMAGE[CUTOUT])
    shutil.copyfile(cut / IMAGE[CUTOUT], run.output_dir / IMAGE[REGISTER])
    if face.any():  # `finish`'s shimmer and lock read it, whatever the mode
        write_mask(run.output_dir / FACE_FILE, face)
    records: dict[str, Any] = {}
    reused = 0
    for index, name in enumerate(ids):
        run.check_cancel()
        run.progress(index, len(ids), f"register {name}")
        path = image_file(cut, CUTOUT, name)
        key = _reuse_key(neutral_hash, _digest(path), face_hash, scale, mode)
        entry = _kept(run, REGISTER, name, key)
        if entry is not None:
            records[name] = entry
            reused += 1
            continue
        edit = resize_nearest(read_rgba(path), width, height)
        if mode == "off":  # the identity: the emotion as its image put it
            write_one(run.output_dir, REGISTER, name, edit)
            records[name] = {"key": key, "scale": [1.0, 1.0], "shift": [0.0, 0.0], "residual": 0.0, "residual_target": 0.0,
                             "tiles": 0, "applied": False, "problems": []}
            continue
        alignment = register(reference, _on_grey(edit), exclude)
        residual = alignment.residual / scale
        problems = _problems(alignment, scale, residual)
        applied = alignment.tiles > 0 and not problems and not alignment.negligible(width, height)
        write_one(run.output_dir, REGISTER, name, warp_nearest(edit, alignment) if applied else edit)
        records[name] = {"key": key, "scale": [alignment.scale_x, alignment.scale_y],
                         "shift": [alignment.shift_x, alignment.shift_y], "residual": alignment.residual,
                         "residual_target": residual, "tiles": alignment.tiles, "applied": applied, "problems": problems}
    if reused:
        run.notes.append(f"{reused} of {len(ids)} emotions unchanged, not registered again")
    if mode == "off":
        run.notes.append(f"registration is off: every emotion is used as its image put it (kiripix set {run.asset_id} "
                         f"{REGISTER} mode=figure lays them on the neutral)")
    elif ids and not any(r["applied"] for r in records.values()):
        run.notes.append("registration moved nothing: every emotion already lies on the neutral image")
    write_record(run.output_dir, REGISTER, {"emotions": ids, "mode": mode, "face": exclude is not None,
                                            "target_scale": scale, "images": records})


def _check_register(run: StageRun) -> list[Finding]:
    record = read_record(run.output_dir, REGISTER, run.asset_id)
    findings: list[Finding] = []
    if record.get("mode") == "off":
        return findings
    for name in record["emotions"]:
        entry = record["images"][name]
        findings.append(Finding(
            code="portrait.residual", severity="info",
            message=f"the emotion {name} lies on the neutral image to {entry['residual_target']:.2f} target px (median of "
                    f"{entry['tiles']} tiles); scale {entry['scale'][0]:.4f}, {entry['scale'][1]:.4f}, shift "
                    f"{entry['shift'][0]:+.2f}, {entry['shift'][1]:+.2f} source px"
                    + ("" if entry["applied"] else ", not applied"),
            position=Position(asset=run.asset_id, stage=REGISTER),
            owner_action="Nothing is needed.",
            data={"emotion": name, "scale": entry["scale"], "shift": entry["shift"], "residual": entry["residual_target"],
                  "tiles": entry["tiles"], "applied": entry["applied"]}))
        if not entry["tiles"]:
            findings.append(Finding(
                code="portrait.misaligned", severity="warning",
                message=f"the emotion {name} can't be measured against the neutral image: no textured tile lies outside the "
                        "face region (flat colours), so it is used as it is, unregistered",
                position=Position(asset=run.asset_id, stage=REGISTER),
                owner_action=f"Flip the emotion over the neutral image and check that nothing outside the face moved; if it "
                             f"did, make the edit again (kiripix import {run.asset_id} <png> --emotion {name}).",
                data={"emotion": name, "problems": [], "residual": None}))
        if entry["problems"]:
            findings.append(Finding(
                code="portrait.misaligned",
                message=f"the emotion {name} doesn't lie on the neutral image: " + "; ".join(entry["problems"]),
                position=Position(asset=run.asset_id, stage=REGISTER),
                owner_action=f"Make the edit again so it keeps the neutral image's size and framing (kiripix import "
                             f"{run.asset_id} <png> --emotion {name}, then kiripix pick {run.asset_id} <variant> --emotion "
                             f"{name}), or draw the face region so the changed face doesn't pull the estimate (kiripix decide "
                             f"{run.asset_id} {REGISTER} --help).",
                data={"emotion": name, "problems": entry["problems"], "residual": entry["residual_target"]}))
    return findings


# fit


def set_grid(neutral: Any, width: int, height: int, anchor: tuple[int, int], offset_x: int = -1, offset_y: int = -1) -> Grid:
    """The set's Grid transform: `Grid.cover`'s scale for the canvas from the neutral, and the crop that puts the figure's
    centre column on the anchor's column and its lowest row on the anchor's row (clamped to the image). A crop offset
    of 0 or more is the Owner's and is used as given."""
    source_height, source_width = neutral.shape[:2]
    try:
        probe = Grid.cover(source_width, source_height, width, height)
    except ValueError:
        raise StageFailure(f"the neutral image is {source_width}x{source_height}, smaller than the {width}x{height} canvas; "
                           "make it larger or the canvas smaller") from None
    ys, xs = np.nonzero(neutral[..., 3])
    if len(xs) == 0:
        raise StageFailure("the neutral cutout is empty: the figure was keyed out; check the cutout")
    scale = probe.scale_x
    largest_x = source_width - int(probe.edges_x()[-1])
    largest_y = source_height - int(probe.edges_y()[-1])
    centre = Fraction(int(xs.min()) + int(xs.max()) + 1, 2)
    foot = int(ys.max()) + 1
    wanted_x = centre - (anchor[0] + Fraction(1, 2)) * scale
    wanted_y = foot - (anchor[1] + 1) * scale
    if offset_x < 0:
        offset_x = min(max(int((wanted_x * 2 + 1) // 2), 0), largest_x)
    if offset_y < 0:
        offset_y = min(max(int((wanted_y * 2 + 1) // 2), 0), largest_y)
    try:
        return Grid.cover(source_width, source_height, width, height, offset_x, offset_y)
    except ValueError as error:
        raise StageFailure(str(error)) from None


def head_top_grid(neutral: Any, width: int, height: int, anchor: tuple[int, int], head_top: int, offset_x: int = -1,
                  offset_y: int = -1) -> tuple[Grid, tuple[int, int, int, int]]:
    """The set's Grid transform from the neutral (ticket 0321): one scale that puts the figure's top row `head_top` px below
    the canvas top and its lowest row on the anchor's row, and the crop that puts its centre column on the anchor's column.
    Where the crop reaches past the source the source is padded with transparent pixels: the padding (left, top, right,
    bottom) is returned with the Grid, which is over the padded source. A crop offset of 0 or more is the Owner's, in the
    source's pixels, and is used as given."""
    source_height, source_width = neutral.shape[:2]
    ys, xs = np.nonzero(neutral[..., 3])
    if len(xs) == 0:
        raise StageFailure("the neutral cutout is empty: the figure was keyed out; check the cutout")
    rows = anchor[1] + 1 - head_top
    if rows < 1:
        raise StageFailure(f"head_top {head_top} isn't above the anchor's row {anchor[1]}; kiripix set <asset> fit "
                           f"head_top={HEAD_TOP}")
    top, foot = int(ys.min()), int(ys.max()) + 1
    scale = Fraction(foot - top, rows)
    if scale < 1:
        raise StageFailure(f"the neutral figure is {foot - top} px tall, fewer than the {rows} canvas rows from head_top "
                           f"{head_top} to the anchor; make the image larger or head_top larger")
    centre = Fraction(int(xs.min()) + int(xs.max()) + 1, 2)
    if offset_x < 0:
        wanted = centre - (anchor[0] + Fraction(1, 2)) * scale
        offset_x = int((wanted * 2 + 1) // 2)
    if offset_y < 0:
        offset_y = top - int(head_top * scale)  # row `head_top`'s cell starts on the figure's top row
    left, upper = max(-offset_x, 0), max(-offset_y, 0)
    grid = Grid(scale, scale, offset_x + left, offset_y + upper, width, height)
    right = max(int(grid.edges_x()[-1]) - (source_width + left), 0)
    bottom = max(int(grid.edges_y()[-1]) - (source_height + upper), 0)
    return grid, (left, upper, right, bottom)


def padded(image: Any, padding: tuple[int, int, int, int]) -> Any:
    """An image or a Mask with transparent (False) pixels added: left, top, right, bottom."""
    left, top, right, bottom = padding
    width = ((top, bottom), (left, right)) + (((0, 0),) if image.ndim == 3 else ())
    return np.pad(image, width)


def _fit(run: StageRun) -> None:
    reg = run.upstream[REGISTER]
    ids = ids_of(reg, REGISTER)
    images = read_set(reg, REGISTER, ids)
    brief = brief_of(run)
    width, height, anchor = int(brief["width"]), int(brief["height"]), (int(brief["anchor"][0]), int(brief["anchor"][1]))
    head_top, offset_x, offset_y = int(run.params["head_top"]), int(run.params["offset_x"]), int(run.params["offset_y"])
    padding = (0, 0, 0, 0)
    if head_top < 0:
        grid = set_grid(images[NEUTRAL], width, height, anchor, offset_x, offset_y)
    else:
        grid, padding = head_top_grid(images[NEUTRAL], width, height, anchor, head_top, offset_x, offset_y)
    figure: dict[str, Any] = {}
    for index, (name, image) in enumerate(images.items()):
        run.check_cancel()
        run.progress(index, len(images), f"fit {name}")
        fitted = downscale(padded(image, padding), grid)
        write_one(run.output_dir, FIT, name, fitted)
        if name == NEUTRAL:
            figure = figure_place(fitted)
    face_file = reg / FACE_FILE
    if face_file.is_file():
        write_mask(run.output_dir / FACE_FILE, mask_touching_target(padded(read_mask(face_file), padding), grid))
    source = images[NEUTRAL].shape
    write_record(run.output_dir, FIT, {"mode": "downscale", "source": [source[1], source[0]], "anchor": list(anchor),
                                       "head_top": head_top, "padding": list(padding), "figure": figure, "emotions": ids,
                                       "face": face_file.is_file(), **grid.to_json()})


def figure_place(fitted: Any) -> dict[str, Any]:
    """Where the fitted neutral figure stands on the canvas: its centre column (a half pixel when its width is even), its
    top row and its lowest opaque row. Empty for an empty figure."""
    ys, xs = np.nonzero(fitted[..., 3])
    if len(xs) == 0:
        return {}
    return {"centre_x": (int(xs.min()) + int(xs.max())) / 2, "top_y": int(ys.min()), "foot_y": int(ys.max())}


def _check_fit(run: StageRun) -> list[Finding]:
    record = read_record(run.output_dir, FIT, run.asset_id)
    brief = brief_of(run)
    want = (int(brief["width"]), int(brief["height"]))
    findings: list[Finding] = []
    for name in (NEUTRAL, *record["emotions"]):
        file = f"{name}.png"
        image = read_rgba(image_file(run.output_dir, FIT, name))
        if (image.shape[1], image.shape[0]) != want:
            findings.append(Finding(
                code="fit.size_mismatch",
                message=f"the fit image of {name} is {image.shape[1]}x{image.shape[0]}, the brief asks for "
                        f"{want[0]}x{want[1]}",
                position=Position(asset=run.asset_id, stage=FIT, file=file), fix=f"kiripix run {run.asset_id} fit --force"))
        found = check_alpha(conformance(image, np.zeros((0, 3), dtype=np.uint8)), file)
        findings += _placed(found, run.asset_id, FIT)
    return findings


# palette


def outline_rgb(run: StageRun) -> tuple[int, int, int]:
    """The outline's colour: the Project palette's colour at `outline_colour`."""
    palette = palette_rgb(run)
    index = int(run.params["outline_colour"])
    if not 0 <= index < len(palette):
        raise StageFailure(f"the outline colour {index} is not in the palette, which has {len(palette)} colours (indexes 0 "
                           f"to {len(palette) - 1}); kiripix set {run.asset_id} palette outline_colour=0",
                           fix=f"kiripix set {run.asset_id} palette outline_colour=0")
    r, g, b = (int(v) for v in palette[index])
    return r, g, b


def _keep(run: StageRun) -> list[tuple[int, int, int]]:
    found: list[tuple[int, int, int]] = []
    for word in str(run.params["keep"]).replace(",", " ").split():
        if not _HEX.fullmatch(word):
            raise StageFailure(f"the keep colour {word!r} isn't #RRGGBB; kiripix set {run.asset_id} palette keep=''",
                               fix=f"kiripix set {run.asset_id} palette keep=''")
        found.append((int(word[1:3], 16), int(word[3:5], 16), int(word[5:7], 16)))
    return found


def _palette(run: StageRun) -> None:
    fit = run.upstream[FIT]
    ids = ids_of(fit, FIT)
    images = read_set(fit, FIT, ids)
    names, fitted = list(images), list(images.values())
    mode = str(run.params["mode"])
    outline = outline_rgb(run)
    for name, image in images.items():
        if has_partial_alpha(image):
            raise StageFailure(f"the fit image of {name} has partially transparent pixels; "
                               f"kiripix run {run.asset_id} fit --force", fix=f"kiripix run {run.asset_id} fit --force")
    run.check_cancel()
    if mode == "off":
        mapped = [image.copy() for image in fitted]
        used = np.unique(np.concatenate([i[..., :3][i[..., 3] == 255] for i in fitted]), axis=0)
        colours = np.unique(np.concatenate([used, np.array([outline], dtype=np.uint8)]), axis=0)
    else:
        if mode == "set":
            keep = [outline, *(c for c in _keep(run) if c != outline)]
            if len(keep) > int(run.params["n"]):
                raise StageFailure(f"n is {run.params['n']}, fewer than the {len(keep)} colours to keep (the outline's and "
                                   f"the keep list); kiripix set {run.asset_id} palette n={len(keep)}",
                                   fix=f"kiripix set {run.asset_id} palette n={len(keep)}")
            colours = set_colours(fitted, None, int(run.params["n"]), keep)
        else:
            colours = palette_rgb(run)
        run.check_cancel()
        mapped = map_set(fitted, colours, BAYER[str(run.params["dither"])])
        size = int(run.params["orphan_size"])
        mapped = [remove_orphans(image, size) for image in mapped]
    report = set_report(fitted, mapped)
    for name, image in zip(names, mapped, strict=True):
        write_one(run.output_dir, PALETTE, name, image)
    errors = {name: {"mean_error": r.mean_error, "p95_error": r.p95_error, "colours": len(r.colours)}
              for name, r in zip(names, report, strict=True)}
    write_record(run.output_dir, PALETTE, {
        "emotions": ids, "mode": mode, "n": int(run.params["n"]),
        "colours": [[int(v) for v in c] for c in colours], "outline": list(outline), "images": errors})


def _set_colours(folder: Path, asset: str) -> Any:
    record = read_record(folder, PALETTE, asset)
    return np.array(record["colours"], dtype=np.uint8).reshape(-1, 3)


def _check_on_colours(run: StageRun, stage: str, colours: Any) -> list[Finding]:
    record = read_record(run.output_dir, stage, run.asset_id)
    findings: list[Finding] = []
    for name in (NEUTRAL, *record["emotions"]):
        file = f"{name}.png"
        report = conformance(read_rgba(image_file(run.output_dir, stage, name)), colours)
        found = check_alpha(report, file) + check_conformance(report, file, fix=f"kiripix run {run.asset_id} {stage} --force")
        findings += _placed(found, run.asset_id, stage)
    return findings


def _check_palette(run: StageRun) -> list[Finding]:
    findings = _check_on_colours(run, PALETTE, _set_colours(run.output_dir, run.asset_id))
    record = read_record(run.output_dir, PALETTE, run.asset_id)
    if record["mode"] != "off":
        said = ", ".join(f"{n} {e['mean_error']:.4f} / {e['p95_error']:.4f}" for n, e in record["images"].items())
        findings.append(Finding(
            code="palette.set_error", severity="info",
            message=f"the set's {len(record['colours'])} colours map each image with this OKLab mean / 95th percentile "
                    f"error: {said}",
            position=Position(asset=run.asset_id, stage=PALETTE),
            owner_action=f"Nothing is needed. If the gradients band, give the set more colours: kiripix set {run.asset_id} "
                         f"palette n={min(int(record['n']) * 2, 256)}.",
            data={"mode": record["mode"], "colours": len(record["colours"]), "images": record["images"]}))
    return findings


# finish


def outline_line(rgba: Any, placement: str) -> Any:
    """The outline's line Mask. The canvas's edge counts as figure, not as empty: where the portrait is cut by the canvas (the
    waist-up crop), there is no line along the cut."""
    alpha = np.pad(rgba[..., 3] > 0, 1, mode="edge")
    line = outline_mask(alpha, placement)[1:-1, 1:-1]  # type: ignore[arg-type]
    return line


def differing(image: Any, reference: Any, outside: Any) -> tuple[Any, Any]:
    """The pixels of `image` outside the face that differ from the neutral's, and those of them that show (an OKLab distance
    over `SHIMMER_VISIBLE`, or one opaque and the other clear)."""
    differ = (image != reference).any(axis=2) & outside
    both = (image[..., 3] == 255) & (reference[..., 3] == 255)
    distance = np.zeros(differ.shape)
    near = differ & both
    if near.any():
        distance[near] = np.sqrt(((srgb_to_oklab(image[..., :3][near]) - srgb_to_oklab(reference[..., :3][near])) ** 2).sum(axis=1))
    return differ, differ & (~both | (distance > SHIMMER_VISIBLE))


def boxes_of(mask: Any) -> list[dict[str, int]]:
    """The 8-connected pieces of a Mask as boxes, the largest first: x, y, width, height, pixels."""
    found = []
    for piece in connected_regions(mask, eight=True):
        y0, x0 = (int(v) for v in piece.min(axis=0))
        y1, x1 = (int(v) for v in piece.max(axis=0))
        found.append({"x": x0, "y": y0, "width": x1 - x0 + 1, "height": y1 - y0 + 1, "pixels": len(piece)})
    found.sort(key=lambda b: (-b["pixels"], b["y"], b["x"]))
    return found[:SHIMMER_BOXES]


def _finish(run: StageRun) -> None:
    pal = run.upstream[PALETTE]
    ids = ids_of(pal, PALETTE)
    images = read_set(pal, PALETTE, ids)
    record = read_record(pal, PALETTE, run.asset_id)
    colour = (int(record["outline"][0]), int(record["outline"][1]), int(record["outline"][2]))
    placement = str(run.params["placement"])
    clearing = bool(run.params["clear_light_edge"])
    light: dict[str, Any] = {}
    for name in list(images):
        before = images[name]
        if clearing:
            images[name] = clear_light_edge(before)
        left = light_edge(images[name])
        light[name] = {"cleared": int(((before[..., 3] > 0) & (images[name][..., 3] == 0)).sum()), "pixels": int(left.sum()),
                       "boxes": boxes_of(left)}
    if run.params["outline"]:
        images = {n: paint_outline(i, outline_line(i, placement), colour) for n, i in images.items()}
    face_file = run.upstream[FIT] / FACE_FILE
    face = read_mask(face_file) if face_file.is_file() else None
    outside = ~face if face is not None else np.ones(images[NEUTRAL].shape[:2], dtype=np.bool_)
    lock = bool(run.params["lock_outside_face"]) and face is not None
    reference = images[NEUTRAL]
    shimmer: dict[str, Any] = {}
    for name in ids:
        run.check_cancel()
        differ, shows = differing(images[name], reference, outside)
        shimmer[name] = {"exact": int(differ.sum()), "visible": int(shows.sum()), "boxes": boxes_of(differ)}
        if lock:
            locked = images[name].copy()
            locked[outside] = reference[outside]
            images[name] = locked
    for name, image in images.items():
        write_one(run.output_dir, FINISH, name, image)
    write_record(run.output_dir, FINISH, {
        "emotions": ids, "outline": {"drawn": bool(run.params["outline"]), "colour": list(colour), "placement": placement},
        "face": face is not None, "locked": lock, "shimmer": shimmer,
        "light_edge": {"cleared": clearing, "images": light}})


def near_edge(rgba: Any, spare: int = SPARE) -> Any:
    """The opaque pixels within `spare` px of the top, left or right edge (the bottom edge is the waist cut)."""
    band = np.zeros(rgba.shape[:2], dtype=np.bool_)
    band[:spare] = True
    band[:, :spare] = True
    band[:, -spare:] = True
    near: Any = band & (rgba[..., 3] > 0)
    return near


def _out_of_canvas(run: StageRun, ids: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    asset = run.asset_id
    for name in (NEUTRAL, *ids):
        near = near_edge(read_rgba(image_file(run.output_dir, FINISH, name)))
        if not near.any():
            continue
        ys, xs = np.nonzero(near)
        x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
        edges = {"top": int(near[:SPARE].sum()), "left": int(near[:, :SPARE].sum()), "right": int(near[:, -SPARE:].sum())}
        said = ", ".join(f"{n} px at the {edge} edge" for edge, n in edges.items() if n)
        image = "the neutral image" if name == NEUTRAL else f"the emotion {name}"
        remake = (f"kiripix import {asset} <png> --emotion {name}, then kiripix pick {asset} <variant> --emotion {name}"
                  if name != NEUTRAL else f"kiripix import {asset} <png>, then kiripix pick {asset} <variant>")
        findings.append(Finding(
            code="portrait.out_of_canvas", severity="warning",
            message=f"{image} reaches within {SPARE} px of the canvas's edge: {said} (a gesture leaves the frame, or "
                    f"comes too close to it)",
            position=Position(asset=asset, stage=FINISH, file=f"{name}.png", x=x0, y=y0, width=x1 - x0 + 1,
                              height=y1 - y0 + 1),
            owner_action=f"Make the image again with the gesture inside the frame ({remake}); the image's crop is the "
                         f"image model's, Kiripix doesn't move a figure.",
            data={"emotion": name, "spare": SPARE, "edges": edges, "box": {"x": x0, "y": y0, "width": x1 - x0 + 1,
                                                                             "height": y1 - y0 + 1}}))
    return findings


def _light_rim(asset: str, record: dict[str, Any]) -> list[Finding]:
    """`portrait.light_rim`: the pale grey edge pixels left before the outline was drawn, per image."""
    findings: list[Finding] = []
    light = record.get("light_edge")
    if not light:
        return findings
    for name, entry in light["images"].items():
        if not entry["pixels"]:
            continue
        first = entry["boxes"][0]
        image = "the neutral image" if name == NEUTRAL else f"the emotion {name}"
        if light["cleared"]:
            how: dict[str, str] = {"owner_action": f"Flip the emotions and judge the specks by eye; if they flicker, take a "
                                                   f"wider rim off in the cutout: kiripix set {asset} cutout rim_reach=16."}
        else:
            how = {"fix": f"kiripix set {asset} finish clear_light_edge=true"}
        findings.append(Finding(
            code="portrait.light_rim", severity="warning",
            message=f"{image} has {entry['pixels']} pixels of pale grey specks on its edge, the image model's white rim the "
                    f"cutout left; they differ from image to image, so they flicker when the expression changes",
            position=Position(asset=asset, stage=FINISH, file=f"{name}.png", x=first["x"], y=first["y"],
                              width=first["width"], height=first["height"]),
            data={"emotion": name, "pixels": entry["pixels"], "boxes": entry["boxes"], "cleared": light["cleared"]},
            **how))
    return findings


def _check_finish(run: StageRun) -> list[Finding]:
    asset = run.asset_id
    findings = _check_on_colours(run, FINISH, _set_colours(run.upstream[PALETTE], asset))
    record = read_record(run.output_dir, FINISH, asset)
    findings += _out_of_canvas(run, record["emotions"])
    findings += _light_rim(asset, record)
    for name in record["emotions"]:
        entry = record["shimmer"][name]
        if not entry["exact"]:
            continue
        boxes = entry["boxes"]
        first = boxes[0] if boxes else None
        where = "outside the face" if record["face"] else "in the whole picture (no face region is drawn)"
        if record["locked"]:
            tail = "the lock set them to the neutral's pixels"
            action = (f"Nothing is needed. If something outside the face region should change (a raised hand), grow the "
                      f"region over it: kiripix decide {asset} {REGISTER} --help.")
        elif record["face"]:
            tail = "the lock is off"
            action = (f"Nothing is needed: the body may change between emotions; judge the flicker by eye. For a set whose "
                      f"body should stay still, switch the lock on: kiripix set {asset} finish lock_outside_face=true.")
        else:
            tail = "without a face region there is nothing to lock"
            action = (f"Nothing is needed: the body may change between emotions; judge the flicker by eye. For a set whose "
                      f"body should stay still, draw the face region and switch the lock on: kiripix decide {asset} "
                      f"{REGISTER} --help.")
        findings.append(Finding(
            code="portrait.shimmer", severity="info",
            message=f"the emotion {name} differs from the neutral image in {entry['exact']} pixels {where}, {entry['visible']} "
                    f"of them visibly (over {SHIMMER_VISIBLE:g} OKLab); {tail}",
            position=Position(asset=asset, stage=FINISH, x=first["x"], y=first["y"], width=first["width"],
                              height=first["height"]) if first else Position(asset=asset, stage=FINISH),
            owner_action=action,
            data={"emotion": name, "exact": entry["exact"], "visible": entry["visible"], "boxes": boxes,
                  "face": record["face"], "locked": record["locked"]}))
    return findings


# the Stages

_CHECK_SHIMMER = CheckSpec(code="portrait.shimmer", description="Per emotion, the pixels outside the face region (or all of "
                           "them, without one) that differ from the neutral's, with boxes (info). `data`: `emotion`, `exact`, "
                           "`visible`, `boxes`, `face`, `locked`.")


def _stages() -> tuple[StageSpec, ...]:
    return (
        StageSpec(
            name=CUTOUT,
            description="Chroma key or matting on the neutral and on every emotion: a key with a tolerance read from each "
                        "image's border, then the key's spill, a light rim and small islands taken off.",
            params=(
                ParamSpec(name="method", type="choice", description="Chroma key (with a tolerance), or matting.",
                          default="chroma", choices=["chroma", "matting"]),
                ParamSpec(name="chroma", type="str", default="auto",
                          description="The background colour, #RRGGBB, or `auto`: the median of each image's border (a lossy "
                                      "image model's green differs from image to image)."),
                ParamSpec(name="tolerance", type="float", default=0.06, minimum=0, maximum=0.3,
                          description="How far a pixel may be from the key and still be background, an OKLab distance."),
                ParamSpec(name="spill_reach", type="int", default=3, minimum=0, maximum=32,
                          description="Pixels from the cleared background within which the key's colour cast is cleared."),
                ParamSpec(name="rim_reach", type="int", default=10, minimum=0, maximum=64,
                          description="Pixels from the cleared background within which a light, unsaturated rim (the image "
                                      "model's sticker edge) is cleared; 0 keeps it."),
                ParamSpec(name="islands", type="int", default=1500, minimum=0,
                          description="Opaque pieces under this many source pixels are cleared."),
            ),
            checks=(
                CheckSpec(code="cutout.chroma_keyed_nothing", description="The key cleared some of each image."),
                CheckSpec(code="cutout.chroma_keyed_everything", description="The key left some of each image."),
                CheckSpec(code="cutout.chroma_fringe", description="No near-key fringe along the edge (warning)."),
            ),
            available_from="M5", image=IMAGE[CUTOUT], run=_cutout, check=_check_cutout, runner_calls=_cutout_calls,
        ),
        StageSpec(
            name=REGISTER,
            description="Off by default: every emotion as its image put it (the body may move between emotions). Or each "
                        "emotion laid on the neutral image (scale and shift), over the whole figure or outside the `face` "
                        "region.",
            version=2,  # 0321: `mode`, off by default
            inputs=StageInputs(upstream=[CUTOUT, BRIEF]),
            params=(
                ParamSpec(name="mode", type="choice", default="off", choices=REGISTER_MODES,
                          description="`off`: no registration, every emotion used as it is (a new pose, a raised arm). "
                                      "`figure`: each emotion laid on the neutral over the whole figure. `outside_face`: "
                                      "outside the `face` region only. The last two are for a set whose edits keep the body "
                                      "still."),
            ),
            decisions=(FACE,),
            checks=(
                CheckSpec(code="portrait.misaligned", description="An emotion lies on the neutral within half a target "
                          "pixel after registration, and within its limits (scale 0.985 to 1.015, shift 4 target px)."),
                CheckSpec(code="portrait.residual", description="Per emotion, the scale, shift and residual (info). Neither "
                          "is raised with `mode` off."),
            ),
            owner_input="Draws the face region, only if needed.",
            available_from="M5", image=IMAGE[REGISTER], run=_register, check=_check_register,
        ),
        StageSpec(
            name=FIT,
            description="One Grid transform for the set, from the neutral: one scale that puts the figure's top row "
                        "`head_top` px below the canvas top and its lowest row on the anchor's row, and one crop centred on "
                        "the anchor, applied to every emotion; transparent where the source has no pixels; alpha by "
                        "majority vote.",
            version=2,  # 0321: `head_top`
            inputs=StageInputs(upstream=[REGISTER, BRIEF]),
            params=(
                ParamSpec(name="head_top", type="int", default=HEAD_TOP, minimum=-1,
                          description="Canvas px from the top to the neutral figure's top row (the game's rule is 40). -1 "
                                      "fills the canvas instead (`Grid.cover`), the figure's lowest row on the anchor's row."),
                ParamSpec(name="offset_x", type="int", default=-1, minimum=-1,
                          description="Source pixels from the left where the crop starts. -1 centres the figure on the "
                                      "anchor's column."),
                ParamSpec(name="offset_y", type="int", default=-1, minimum=-1,
                          description="Source pixels from the top where the crop starts. -1 puts the figure's top row at "
                                      "`head_top` (or, with `head_top` -1, its lowest row on the anchor's row)."),
            ),
            checks=(CheckSpec(code="fit.size_mismatch", description="Every image has the brief's exact size."),
                    CheckSpec(code="image.partial_alpha", description="Alpha is binary.")),
            owner_input="Tunes the crop.",
            available_from="M5", image=IMAGE[FIT], run=_fit, check=_check_fit,
        ),
        StageSpec(
            name=PALETTE,
            description="The set's own colours: `n` chosen once over every image, so a shade can't flip between emotions. "
                        "Or the Project's palette, or none.",
            inputs=StageInputs(upstream=[FIT], settings=["palette"]),
            params=(
                ParamSpec(name="mode", type="choice", default="set", choices=["set", "project", "off"],
                          description="`set`: the set's own colours. `project`: the Project palette, strictly, as a Prop. "
                                      "`off`: colours kept, only the alpha is binary."),
                ParamSpec(name="n", type="int", default=32, minimum=1, maximum=256,
                          description="The set's colours (mode `set`). 24 is the least that reads smoothly on the trial's set."),
                ParamSpec(name="dither", type="choice", default="none", choices=list(BAYER),
                          description="Ordered dithering before mapping (the trial found it adds a pattern the gradients "
                                      "don't need)."),
                ParamSpec(name="keep", type="str", default="",
                          description="Colours that must be in the set, #RRGGBB separated by commas (mode `set`). The "
                                      "outline's colour is always kept."),
                ParamSpec(name="outline_colour", type="int", default=0, minimum=0,
                          description="The outline's colour: an index into the Project palette. It is kept among the set's "
                                      "colours, and `finish` draws it."),
                ParamSpec(name="orphan_size", type="int", default=1, minimum=0, maximum=16,
                          description="Remove pixel islands up to this size, in each image."),
            ),
            checks=(
                CheckSpec(code="palette.off_palette", description="Every opaque pixel is one of the set's colours."),
                CheckSpec(code="palette.set_error", description="Per image, the mapping's mean and 95th percentile OKLab "
                          "error (info)."),
            ),
            available_from="M5", image=IMAGE[PALETTE], run=_palette, check=_check_palette,
        ),
        StageSpec(
            name=FINISH,
            description="The pale grey specks on the edge cleared, the outline, and, if switched on, the neutral's pixels "
                        "outside the face region in every emotion.",
            version=2,  # 0321: `lock_outside_face` off by default; 0322: `clear_light_edge` on by default
            inputs=StageInputs(upstream=[PALETTE, FIT]),
            params=(
                ParamSpec(name="clear_light_edge", type="bool", default=True,
                          description="Before the outline, clear the specks of pale grey on the figure's edge (pieces of "
                                      "up to 4 px, OKLab L over 0.7, a, b length under 0.08): the image model's white rim, "
                                      "which the cutout leaves and which flickers between emotions. A highlight inside the "
                                      "figure, or a white garment on its edge, stays."),
                ParamSpec(name="outline", type="bool", default=True, description="Draw the outline."),
                ParamSpec(name="placement", type="choice", default="edge", choices=["edge", "outside"],
                          description="edge: the figure's own border pixels are repainted (the image model already draws a "
                                      "dark outline). outside: a line around it, which doubles that outline. Where the "
                                      "canvas cuts the figure there is no line."),
                ParamSpec(name="lock_outside_face", type="bool", default=False,
                          description="Outside the `face` region (drawn on `register`) every emotion takes the neutral's "
                                      "pixels, for a set whose body never moves. Off: the game's rules let the pose, the "
                                      "arms and the lean change between emotions. Nothing to lock without a face region."),
            ),
            checks=(
                CheckSpec(code="palette.off_palette", description="Every opaque pixel is one of the set's colours."),
                _CHECK_SHIMMER,
                CheckSpec(code="portrait.out_of_canvas", description=f"Per image, no opaque pixel within {SPARE} px of the "
                          "top, left or right edge (warning; the bottom is the waist cut). `data`: `emotion`, `spare`, "
                          "`edges` (pixels per edge), `box`."),
                CheckSpec(code="portrait.light_rim", description="Per image, no speck of pale grey (up to 4 px) on the "
                          "figure's edge before the outline (warning): the white rim the cutout left. `data`: `emotion`, `pixels`, `boxes`, "
                          "`cleared`."),
            ),
            available_from="M5", image=IMAGE[FINISH], run=_finish, check=_check_finish,
        ),
    )


STAGES = _stages()
