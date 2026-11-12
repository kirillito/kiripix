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
from typing import TYPE_CHECKING, Any, cast

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks import Finding, Position, check_conformance
from kiripix.checks.sheet import SheetFrame, check_normal_size
from kiripix.ops import Placement, add_outline, conformance, encode_normals, quantise_normals
from kiripix.recipes.base import StageFailure, StageRun
from kiripix.recipes.character_palette import RENDER_FILE, _colour_files
from kiripix.recipes.common import palette_rgb, read_rgba, write_rgba

FINISH_SCHEMA_VERSION = 1
FINISH_FILE = "finish.json"
FLAT = (128, 128, 255, 255)  # a normal facing the camera, as `encode_normals` writes it


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
    return index, (r, g, b)


def _normal_frame(normal: np.ndarray, colour: np.ndarray, levels: int) -> np.ndarray:
    """The quantised, encoded normal pass cut by the colour frame's alpha: an opaque colour pixel with no normal under it (the
    outline) faces the camera."""
    encoded = encode_normals(quantise_normals(normal, levels))
    opaque = colour[..., 3] > 0
    out = np.zeros_like(encoded)
    out[opaque] = np.where((encoded[..., 3] > 0)[opaque][:, None], encoded[opaque], np.array(FLAT, dtype=np.uint8))
    return out


def run_character_finish(run: StageRun) -> None:
    document = _document(run)
    palette = palette_rgb(run)
    outline = _outline_colour(run, palette)
    levels, placement = int(run.params["normal_levels"]), str(run.params["placement"])
    files = _colour_files(document)
    for number, (clip, direction, index, name) in enumerate(files):
        run.check_cancel()
        run.progress(number, len(files), f"finishing {clip}/{direction}/{index:03d}")
        colour = read_rgba(run.upstream["palette"] / name)
        if outline is not None:
            colour = add_outline(colour, outline[1], cast(Placement, placement))
        try:
            normal = read_rgba(run.upstream["render"] / _normal_name(name))
            if normal.shape != colour.shape:
                finished = normal  # not the colour frame's size: `normal.size_mismatch` says so, there is no cut to make
            else:
                finished = _normal_frame(normal, colour, levels)
        except ValueError as error:
            raise StageFailure(f"{clip}/{direction} frame {index}: can't quantise the normal pass: {error}") from None
        except OSError:
            raise StageFailure(f"render has no normal pass for {clip}/{direction} frame {index}; "
                               f"run render again") from None
        for target, image in ((run.output_dir / name, colour), (run.output_dir / _normal_name(name), finished)):
            target.parent.mkdir(parents=True, exist_ok=True)
            write_rgba(target, image)
    shutil.copyfile(run.upstream["palette"] / RENDER_FILE, run.output_dir / RENDER_FILE)
    drawn = {"schema_version": FINISH_SCHEMA_VERSION, "normal_levels": levels,
             "outline": None if outline is None else {"colour": outline[0], "rgb": list(outline[1]), "placement": placement}}
    (run.output_dir / FINISH_FILE).write_text(json.dumps(drawn, indent=2) + "\n", encoding="utf-8")


def check_character_finish(run: StageRun) -> list[Finding]:
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
    for finding in findings:
        if finding.position is None:
            finding.position = Position()
        finding.position.asset, finding.position.stage = run.asset_id, "finish"
    return findings
