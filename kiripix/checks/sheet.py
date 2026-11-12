"""The sheet Checks (spec §6.3, ticket 0108): pivots, cells, frame counts, empty frames, normal sizes.

Every Check takes the frames as `SheetFrame` values and the `fix` command to name in its findings. Positions name the
clip, direction and frame in `field` as `clip/direction/frame`, and the pivot or pixel in `x`, `y` where there is one.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing import TYPE_CHECKING
from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks.finding import Finding, Position
from kiripix.ops.sheet import default_cell_pivot


@dataclass(frozen=True)
class SheetFrame:
    """One frame of a clip in one direction. `pivot` is the ground point under the root, in frame pixels."""

    clip: str
    direction: str
    index: int
    image: np.ndarray  # RGBA
    pivot: tuple[int, int]
    normal: np.ndarray | None = None


def _where(f: SheetFrame, x: int | None = None, y: int | None = None) -> Position:
    return Position(field=f"{f.clip}/{f.direction}/{f.index}", x=x, y=y)


def _name(f: SheetFrame) -> str:
    return f"clip {f.clip}, direction {f.direction}, frame {f.index}"


def check_pivot_drift(frames: list[SheetFrame], stationary: set[str], fix: str, tolerance: int = 0) -> list[Finding]:
    """In each stationary clip and direction, a frame whose pivot is further than `tolerance` px (on either axis)
    from the first frame's. Clips not in `stationary` are not checked."""
    findings: list[Finding] = []
    first: dict[tuple[str, str], SheetFrame] = {}
    for f in sorted(frames, key=lambda f: (f.clip, f.direction, f.index)):
        if f.clip not in stationary:
            continue
        ref = first.setdefault((f.clip, f.direction), f)
        if ref is f:
            continue
        dx, dy = f.pivot[0] - ref.pivot[0], f.pivot[1] - ref.pivot[1]
        if max(abs(dx), abs(dy)) > tolerance:
            findings.append(Finding(
                code="sheet.pivot_drift", position=_where(f, *f.pivot), fix=fix,
                message=f"{_name(f)}: the feet moved ({dx:+d}, {dy:+d}) px from frame {ref.index} in a stationary "
                        f"clip (tolerance {tolerance} px)"))
    return findings


def check_frame_overflow(frames: list[SheetFrame], cell: tuple[int, int], fix: str,
                         cell_pivot: tuple[int, int] | None = None) -> list[Finding]:
    """A frame whose opaque pixels, placed with the pivot on `cell_pivot`, don't fit the cell."""
    cw, ch = cell
    px, py = cell_pivot if cell_pivot is not None else default_cell_pivot(cell)
    findings: list[Finding] = []
    for f in frames:
        ys, xs = np.nonzero(f.image[..., 3] > 0)
        if len(xs) == 0:
            continue
        left, top = px - f.pivot[0], py - f.pivot[1]
        x0, x1, y0, y1 = int(xs.min()) + left, int(xs.max()) + left, int(ys.min()) + top, int(ys.max()) + top
        if x0 < 0 or y0 < 0 or x1 >= cw or y1 >= ch:
            findings.append(Finding(
                code="sheet.frame_overflow", position=Position(field=f"{f.clip}/{f.direction}/{f.index}",
                                                               x=x0, y=y0, width=x1 - x0 + 1, height=y1 - y0 + 1),
                fix=fix,
                message=f"{_name(f)}: opaque pixels span ({x0}, {y0}) to ({x1}, {y1}) around the pivot, outside the "
                        f"{cw} x {ch} cell"))
    return findings


def check_frame_count(frames: list[SheetFrame], expected: dict[str, int], fix: str,
                      directions: list[str] | None = None) -> list[Finding]:
    """A clip and direction with a different number of frames than its clip says (`expected`, by clip name). With
    `directions`, every expected clip must have frames in each of them, so a direction never rendered counts as 0."""
    counts: dict[tuple[str, str], int] = {(clip, d): 0 for clip in expected for d in directions or []}
    for f in frames:
        counts[(f.clip, f.direction)] = counts.get((f.clip, f.direction), 0) + 1
    findings: list[Finding] = []
    for (clip, direction), n in sorted(counts.items()):
        if clip in expected and n != expected[clip]:
            findings.append(Finding(
                code="sheet.frame_count", position=Position(field=f"{clip}/{direction}"), fix=fix,
                message=f"clip {clip}, direction {direction}: {n} frames, but the clip says {expected[clip]}"))
    return findings


def check_empty_frame(frames: list[SheetFrame], fix: str) -> list[Finding]:
    """A frame with no opaque pixel."""
    return [Finding(code="sheet.empty_frame", position=_where(f), fix=fix,
                    message=f"{_name(f)}: no opaque pixel")
            for f in frames if not (f.image[..., 3] > 0).any()]


def check_normal_size(frames: list[SheetFrame], fix: str) -> list[Finding]:
    """A normal map whose size isn't its colour frame's."""
    findings: list[Finding] = []
    for f in frames:
        if f.normal is not None and f.normal.shape[:2] != f.image.shape[:2]:
            nh, nw = f.normal.shape[:2]
            h, w = f.image.shape[:2]
            findings.append(Finding(
                code="normal.size_mismatch", position=_where(f), fix=fix,
                message=f"{_name(f)}: the normal map is {nw} x {nh}, the colour frame {w} x {h}"))
    return findings
