"""The character's `palette` Stage (spec §6.3, ADR 0004, ticket 0110).

It means what a room's `palette` means (a strict OKLab mapping, optional ordered dithering, orphan cleanup), with one
choice on top: the character shares one subset of the Project palette across every frame of every clip and direction,
chosen by `palette_subset`, so a colour never flickers between frames. Only the colour pass is mapped. The normal, depth
and mask passes stay in `render`'s folder, untouched; `render.json` is copied here, so the frame list goes on to `finish`.

Output in `work/palette/`: `color/<clip>/<dir>/<NNN>.png` (as in `render`), `palette.json` and `render.json`.
"""

from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks import Finding, Position
from kiripix.ops import conformance, palette_subset, quantize, remove_orphans
from kiripix.recipes.base import StageFailure, StageRun
from kiripix.recipes.common import BAYER, palette_rgb, read_rgba, write_rgba

PALETTE_SCHEMA_VERSION = 1
RENDER_FILE = "render.json"
PALETTE_FILE = "palette.json"


def _render(run: StageRun) -> dict[str, Any]:
    path = run.upstream["render"] / RENDER_FILE
    try:
        document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StageFailure("render has no render.json; run it again") from None
    return document


def _colour_files(document: dict[str, Any]) -> list[tuple[str, str, int, str]]:
    """Every colour frame, as (clip, direction, index, file relative to the pass folder's parent)."""
    found = []
    for entry in document["clips"]:
        for direction, frames in entry["directions"].items():
            for frame in frames:
                found.append((entry["name"], direction, int(frame["index"]), str(frame["files"]["color"])))
    return found


def _indexes(subset: np.ndarray, palette: np.ndarray) -> list[int]:
    """The Project palette's index of each subset colour (the first, when the palette repeats a colour)."""
    taken: list[int] = []
    for colour in subset:
        matches = np.nonzero((palette == colour).all(axis=1))[0]
        free = [int(i) for i in matches if int(i) not in taken]
        if not free:
            raise StageFailure(f"the palette subset holds {tuple(int(c) for c in colour)}, which the Project palette "
                               f"doesn't hold {'that many times' if len(matches) else 'at all'}",
                               code="palette.subset_unknown")
        taken.append(free[0])
    return taken


def run_character_palette(run: StageRun) -> None:
    render = run.upstream["render"]
    document = _render(run)
    files = _colour_files(document)
    palette = palette_rgb(run)
    count = int(run.params["colors"])
    frames: list[np.ndarray] = []
    for number, (_clip, _direction, _index, name) in enumerate(files):
        run.check_cancel()
        run.progress(number, len(files) * 2, "reading frames")
        frames.append(read_rgba(render / name))
    run.check_cancel()
    try:
        subset = palette_subset(frames, palette, count)
    except ValueError as error:
        raise StageFailure(f"can't choose the character's colours: {error}") from None
    dither, strength, orphans = BAYER[str(run.params["dither"])], float(run.params["strength"]), int(run.params["orphan_size"])
    for number, ((clip, direction, index, name), frame) in enumerate(zip(files, frames, strict=True)):
        run.check_cancel()
        run.progress(len(files) + number, len(files) * 2, f"mapping {clip}/{direction}/{index:03d}")
        try:
            mapped = quantize(frame, subset, dither, strength)
        except ValueError as error:
            raise StageFailure(f"{clip}/{direction} frame {index} can't be mapped: {error}") from None
        target = run.output_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        write_rgba(target, remove_orphans(mapped, orphans))
    shutil.copyfile(render / RENDER_FILE, run.output_dir / RENDER_FILE)
    colours = [{"index": i, "rgb": [int(c) for c in rgb], "hex": "#%02x%02x%02x" % tuple(int(c) for c in rgb)}
               for i, rgb in zip(_indexes(subset, palette), subset, strict=True)]
    (run.output_dir / PALETTE_FILE).write_text(
        json.dumps({"schema_version": PALETTE_SCHEMA_VERSION, "colors": colours}, indent=2) + "\n", encoding="utf-8")


def check_character_palette(run: StageRun) -> list[Finding]:
    """`palette.off_palette` on every colour frame, against the character's own subset; the finding names the frame."""
    out = run.output_dir
    try:
        chosen = json.loads((out / PALETTE_FILE).read_text(encoding="utf-8"))["colors"]
        document = json.loads((out / RENDER_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError):
        return []  # nothing built to check
    subset = np.array([c["rgb"] for c in chosen], dtype=np.uint8).reshape(-1, 3)
    findings = []
    for clip, direction, index, name in _colour_files(document):
        path = out / name
        if not path.is_file():
            findings.append(Finding(code="palette.off_palette", message=f"{name} ({clip}, {direction}, frame {index}) is "
                                    f"missing", position=Position(asset=run.asset_id, stage="palette", file=name),
                                    fix=f"kiripix run {run.asset_id} palette --force"))
            continue
        report = conformance(read_rgba(path), subset)
        if report.off_palette:
            x, y = report.first_off_palette[0]
            findings.append(Finding(
                code="palette.off_palette",
                message=f"clip {clip}, direction {direction}, frame {index} has {report.off_palette} pixels off the "
                        f"character's palette, the first at ({x}, {y})",
                position=Position(asset=run.asset_id, stage="palette", file=name, x=x, y=y),
                fix=f"kiripix run {run.asset_id} palette --force"))
    return findings
