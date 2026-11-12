"""The character's `finish` Stage (spec §6.3, ADR 0004, ticket 0111).

Two things, both after `palette`:

- the outline: a 1 px silhouette of each colour frame's alpha, painted in the palette colour `outline_colour` (an index into the
  Project palette) once the colours are mapped, so it is a palette colour and never dithered or mapped. `outline=false` skips it.
  `placement` is `outside` (the line is the transparent pixels around the silhouette, so the silhouette keeps its pixels and a
  Prop's outline matches; where the character touches the frame's edge the line has nowhere to go) or `edge` (the line is the
  silhouette's own edge pixels). `render`'s cell leaves the character at least `ceil(0.1 * height)` px under its feet and more
  elsewhere, so `outside` has room.
- the normal pass, from `render`: quantised to `normal_levels` values per axis, encoded for Godot, and cut by the final colour
  frame's alpha, so an outline pixel gets a normal that faces the camera and the two images line up pixel for pixel. It is
  never palette-mapped.

Output in `work/finish/`, in `render`'s layout: `color/<clip>/<dir>/<NNN>.png` and `normal/<clip>/<dir>/<NNN>.png` for every
frame, `render.json` (copied, so the frame list and pivots go on to `sheet`) and `finish.json` (what was drawn).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks import Finding, PartCounts, Position, check_conformance, check_part_vanishes
from kiripix.checks.sheet import SheetFrame, check_normal_size
from kiripix.ops import (
    Placement,
    add_outline,
    conformance,
    encode_normals,
    height_from_alpha,
    normals_from_height,
    quantise_normals,
)
from kiripix.recipes.base import CheckFunction, ParamSpec, StageFailure, StageFunction, StageRun
from kiripix.recipes.character_palette import RENDER_FILE, _colour_files
from kiripix.recipes.common import palette_rgb, read_rgba, write_rgba

FINISH_SCHEMA_VERSION = 1
FINISH_FILE = "finish.json"
FLAT = (128, 128, 255, 255)  # a normal facing the camera, as `encode_normals` writes it


def normals_params(default: str = "pass") -> tuple[ParamSpec, ParamSpec]:
    """The `normals` and `relief` parameters, for a Recipe that declares them (the sprite's `finish`, ticket 0176, which has no
    normal pass and defaults to `height`). The character doesn't: a new parameter would change its hashes, and it reads `pass`
    when `normals` isn't declared, which is also what they default to here."""
    return (
        ParamSpec(name="normals", type="choice", choices=["pass", "height", "flat"], default=default,
                  description="pass: the normal pass of the frame Stage; height: normals from a rounded height of the "
                              "silhouette; flat: every opaque pixel faces the camera."),
        ParamSpec(name="relief", type="float", minimum=0.0, maximum=1.0, default=0.0,
                  description="With normals=height, the share of the colour frame's lightness in the height, 0 to 1."),
    )


def _document(run: StageRun) -> dict[str, Any]:
    try:
        document: dict[str, Any] = json.loads((run.upstream["palette"] / RENDER_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StageFailure("palette has no render.json; run it again") from None
    return document


def _normal_name(colour_name: str) -> str:
    return "normal/" + colour_name.partition("/")[2]


def _outline_colour(run: StageRun, palette: np.ndarray) -> tuple[int, tuple[int, int, int]] | None:
    """The outline's index and colour, or None for `outline=false`; StageFailure when the index isn't in the palette."""
    if not run.params["outline"]:
        return None
    index = int(run.params["outline_colour"])
    if not 0 <= index < len(palette):
        raise StageFailure(f"the outline colour {index} is not in the palette, which has {len(palette)} colours "
                           f"(indexes 0 to {len(palette) - 1}); kiripix set {run.asset_id} finish outline_colour=0",
                           code="finish.outline_colour_unknown",
                           fix=f"kiripix set {run.asset_id} finish outline_colour=0")
    r, g, b = (int(v) for v in palette[index])
    _refuse_a_ramp_colour(run, palette, index, (r, g, b))
    return index, (r, g, b)


def _refuse_a_ramp_colour(run: StageRun, palette: np.ndarray, index: int, rgb: tuple[int, int, int]) -> None:
    """An outline in a part's ramp would be recoloured with the part by the game's swap: `finish.outline_in_ramp`, with the first
    palette colour that no ramp and no fixed colour of the character has as the fix (ticket 0150)."""
    try:
        document = json.loads((run.upstream["palette"] / "palette.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    parts = document.get("parts", [])
    if parts:  # the Project's ramp table reserves its colours for every character with a part of it (ticket 0168)
        parts = parts + [r for r in document.get("table", []) if r.get("rgb") is not None
                         and all(p["name"] != r["name"] for p in parts)]
    owner = next((p["name"] for p in parts if list(rgb) in p["rgb"]), None)
    if owner is None:
        return
    used = {tuple(rgb_) for p in parts for rgb_ in p["rgb"]} | {tuple(c["rgb"]) for c in document.get("colors", [])}
    free = next((i for i, colour in enumerate(palette) if tuple(int(v) for v in colour) not in used), None)
    if free is None:
        raise StageFailure(f"the outline colour {index} is in the ramp of part {owner!r}, and the character's ramps and colours "
                           f"use the whole palette, so no colour is free for the outline",
                           code="finish.outline_in_ramp",
                           owner_action="Give the character fewer colours or a shorter ramp (palette colors, parts), or add a "
                                        "colour to the Project palette for the outline.")
    raise StageFailure(f"the outline colour {index} is in the ramp of part {owner!r}, so swapping that part would recolour the "
                       f"outline; palette colour {free} is free", code="finish.outline_in_ramp",
                       fix=f"kiripix set {run.asset_id} finish outline_colour={free}")


def _normals_mode(run: StageRun) -> str:
    mode = str(run.params.get("normals", "pass"))
    if mode not in ("pass", "height", "flat"):
        raise StageFailure(f"normals must be pass, height or flat, not {mode!r}", fix=f"kiripix set {run.asset_id} finish normals=pass")
    return mode


def _lightness(colour: np.ndarray) -> np.ndarray:
    """Each pixel's luma, 0 to 1."""
    rgb = colour[..., :3].astype(np.float64)
    return np.asarray((rgb @ np.array([0.2126, 0.7152, 0.0722])) / 255.0)


def _flat_frame(colour: np.ndarray) -> np.ndarray:
    """`normals=flat`: every opaque pixel of the final colour frame faces the camera. Already quantised and encoded."""
    out = np.zeros(colour.shape, dtype=np.uint8)
    out[colour[..., 3] > 0] = np.array(FLAT, dtype=np.uint8)
    return out


def _height_pass(mapped: np.ndarray, relief: float) -> np.ndarray:
    """`normals=height`: a raw normal pass from the mapped colour frame's silhouette (before the outline), for
    `_normal_frame` to quantise, encode and cut."""
    alpha = np.where(mapped[..., 3] > 0, 255, 0).astype(np.uint8)
    height = height_from_alpha(alpha)
    if relief > 0:
        height = (1.0 - relief) * height + relief * _lightness(mapped) * (alpha > 0)
    return cast("np.ndarray", normals_from_height(height, alpha))


def _normal_frame(normal: np.ndarray, colour: np.ndarray, levels: int) -> np.ndarray:
    """The quantised, encoded normal pass cut by the colour frame's alpha: an opaque colour pixel with no normal under it (the
    outline) faces the camera."""
    encoded = encode_normals(quantise_normals(normal, levels))
    opaque = colour[..., 3] > 0
    out = np.zeros_like(encoded)
    out[opaque] = np.where((encoded[..., 3] > 0)[opaque][:, None], encoded[opaque], np.array(FLAT, dtype=np.uint8))
    return out


def _run_finish(run: StageRun, source: str) -> None:
    document = _document(run)
    mode, relief = _normals_mode(run), float(run.params.get("relief", 0.0))
    palette = palette_rgb(run)
    outline = _outline_colour(run, palette)
    levels, placement = int(run.params["normal_levels"]), str(run.params["placement"])
    files = _colour_files(document)
    for number, (clip, direction, index, name) in enumerate(files):
        run.check_cancel()
        run.progress(number, len(files), f"finishing {clip}/{direction}/{index:03d}")
        colour = read_rgba(run.upstream["palette"] / name)
        mapped = colour
        if outline is not None:
            colour = add_outline(colour, outline[1], cast(Placement, placement))
        try:
            if mode == "flat":
                finished = _flat_frame(colour)
            else:
                normal = _height_pass(mapped, relief) if mode == "height" else read_rgba(run.upstream[source] / _normal_name(name))
                if normal.shape != colour.shape:
                    finished = normal  # not the colour frame's size: `normal.size_mismatch` says so, there is no cut to make
                else:
                    finished = _normal_frame(normal, colour, levels)
        except ValueError as error:
            raise StageFailure(f"{clip}/{direction} frame {index}: can't quantise the normal pass: {error}") from None
        except OSError:
            raise StageFailure(f"{source} has no normal pass for {clip}/{direction} frame {index}; "
                               f"run {source} again") from None
        for target, image in ((run.output_dir / name, colour), (run.output_dir / _normal_name(name), finished)):
            target.parent.mkdir(parents=True, exist_ok=True)
            write_rgba(target, image)
    shutil.copyfile(run.upstream["palette"] / RENDER_FILE, run.output_dir / RENDER_FILE)
    drawn = {"schema_version": FINISH_SCHEMA_VERSION, "normal_levels": levels,
             **({} if mode == "pass" else {"normals": mode}),
             "outline": None if outline is None else {"colour": outline[0], "rgb": list(outline[1]), "placement": placement}}
    (run.output_dir / FINISH_FILE).write_text(json.dumps(drawn, indent=2) + "\n", encoding="utf-8")


def _read_labels(path: Path) -> np.ndarray:
    """A material frame: mode L, each pixel's material index."""
    from PIL import Image

    with Image.open(path) as image:
        return np.asarray(image.convert("L"), dtype=np.uint8).copy()


def _vanishing_parts(run: StageRun, source: str, document: dict[str, Any], frames: list[SheetFrame]) -> list[Finding]:
    """`sheet.part_vanishes` (ticket 0159): each material's pixels per finished frame, counted where the final colour frame is
    opaque, from the material pass `render` wrote. Nothing when the pass isn't there to read."""
    names = {int(m["index"]): str(m["name"]) for m in document.get("materials", [])}
    render = run.upstream.get(source)
    if not names or render is None:
        return []
    watch = [w.strip() for w in str(run.params.get("watch_parts", "")).split(",") if w.strip()]
    by_name = {(f.clip, f.direction, f.index): f for f in frames}
    counted: list[PartCounts] = []
    for entry in document["clips"]:
        for direction, listed in entry["directions"].items():
            for frame in listed:
                found = by_name.get((entry["name"], direction, int(frame["index"])))
                path = render / str(frame["files"].get("material", ""))
                if found is None or not path.is_file():
                    continue
                labels = _read_labels(path)
                if labels.shape != found.image.shape[:2]:
                    continue
                inside = labels[found.image[..., 3] > 0]
                counted.append(PartCounts(entry["name"], direction, int(frame["index"]),
                                          {name: int((inside == index).sum()) for index, name in sorted(names.items())}))
    findings = check_part_vanishes(counted, watch, int(run.params.get("part_min_pixels", 1)))
    for finding in findings:
        finding.position = Position(asset=run.asset_id, stage="finish", field=finding.position.field if finding.position else None)
    return findings


def _check_finish(run: StageRun, source: str) -> list[Finding]:
    """`normal.size_mismatch` on every frame, and `palette.off_palette` on the colour frames against the Project palette."""
    out = run.output_dir
    try:
        document = json.loads((out / RENDER_FILE).read_text(encoding="utf-8"))
        palette = palette_rgb(run)
    except (OSError, ValueError, StageFailure):
        return []  # nothing built to check
    fix = f"kiripix run {run.asset_id} finish --force"
    frames: list[SheetFrame] = []
    findings: list[Finding] = []
    for clip, direction, index, name in _colour_files(document):
        colour_path, normal_path = out / name, out / _normal_name(name)
        if not colour_path.is_file() or not normal_path.is_file():
            missing = name if not colour_path.is_file() else _normal_name(name)
            findings.append(Finding(code="normal.size_mismatch", message=f"{missing} ({clip}, {direction}, frame {index}) is "
                                    f"missing", position=Position(asset=run.asset_id, stage="finish", file=missing), fix=fix))
            continue
        colour = read_rgba(colour_path)
        frames.append(SheetFrame(clip, direction, index, colour, (0, 0), read_rgba(normal_path)))
        findings += check_conformance(conformance(colour, palette), name, fix=fix)
    findings += check_normal_size(frames, fix)
    findings += _vanishing_parts(run, source, document, frames)
    for finding in findings:
        if finding.position is None:
            finding.position = Position()
        finding.position.asset, finding.position.stage = run.asset_id, "finish"
    return findings


def finish_stage(frames: str = "render") -> tuple[StageFunction, CheckFunction]:
    """The Stage's `run` and `check` for a Recipe whose frame list, normal frames and material frames are in the Stage named
    `frames` (the character's `render`, a sprite's `fit`; ticket 0176). The Stage must list it and `palette` upstream."""
    return (lambda run: _run_finish(run, frames)), (lambda run: _check_finish(run, frames))


run_character_finish, check_character_finish = finish_stage("render")
