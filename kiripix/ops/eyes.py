"""Ops for a character's eyes at sprite size (spec §6.3, §7; ticket 0203).

A render samples each pixel's centre, so an eye two pixels wide changes shape with every sub-pixel move of the head. These
Ops replace the rendered eyes with a small fixed pattern, as a pixel artist draws them: the pattern is chosen once for a clip
and a direction, sits on whole pixels, and moves only when the head has moved most of a pixel.

Pure numpy: arrays in, arrays out.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from statistics import median
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt
else:
    np = lazy_module("numpy")
    npt = lazy_module("numpy.typing")

if TYPE_CHECKING:
    U8 = npt.NDArray[np.uint8]
    Bool = npt.NDArray[np.bool_]
else:
    U8 = Any  # the array types are for the type checker; numpy loads late
    Bool = Any

# An eye is drawn in a clip and direction when its middle facing is above this (1 faces the camera) and it is seen in at
# least half the frames. Low, because an eye that wraps round the side of the face still shows in profile, where its mean
# normal leans mostly forward; the eye on the far side of the head is the one that isn't seen.
SHOWN_FACING = 0.1
HIDDEN_FACING = 0.0  # and left out of a frame where it faces away
WIDE = 1.5  # an eye at least this many px wide gets a white beside its pupil
TURNED = 0.25  # the face's normal leans this far to a side: both pupils sit on that side
STICK = 0.75  # px the pattern's ideal place must be from where it is before it moves
MAX_ROWS = 3


@dataclass(frozen=True)
class EyeAnchor:
    """One eye in one frame, as the Model puts it on screen: its centre and extent in px (x right, y down, a pixel's centre at
    its index + 0.5), how far it leans to the screen's right (`turn`, -1 to 1) and toward the camera (`facing`, -1 to 1), and
    whether it is in view (`seen`: false behind an arm)."""

    x: float
    y: float
    width: float
    height: float
    turn: float
    facing: float
    seen: bool = True


@dataclass(frozen=True)
class EyeStamp:
    """An eye's pattern in one frame: `columns` by `rows` px with its top left pixel at (`left`, `top`); the pupil is the
    column `pupil` (from 0), any other column the white."""

    left: int
    top: int
    columns: int
    rows: int
    pupil: int


def _snap(ideal: float, held: int | None) -> int:
    """The whole pixel for an ideal place, staying on `held` until the ideal is `STICK` px from it."""
    if held is not None and abs(ideal - held) < STICK:
        return held
    return int(np.floor(ideal + 0.5))


def plan_eyes(frames: Sequence[Sequence[EyeAnchor]], whites: bool = True, gap: int = 0) -> list[list[EyeStamp | None]]:
    """The pattern of each eye in each frame of one clip in one direction; None where an eye isn't drawn. `frames` has one
    list per frame, the same eyes in the same order in each.

    What is decided once for all the frames, from their middle values: which eyes are drawn at all, each one's columns (2
    with `whites` when it is `WIDE`, else 1; on a face turned to a side, the eye that faces the camera less is 1), the rows,
    the gap between two eyes, and which column is the pupil (toward the other eye when the face looks at the camera, on the
    side it is turned to otherwise). `gap` px are added to the Model's gap between two eyes (it stays at least 1), and the
    pattern stays centred on the eyes' middle; not on a face turned to a side, where the eyes are foreshortened. Per frame, only the place: the
    middle of the eyes that are drawn, on whole pixels, held until it has moved `STICK` px; and an eye is left out of a frame
    where it faces away or wasn't seen."""
    if not frames or not frames[0]:
        return [[] for _ in frames]
    count = len(frames[0])
    if any(len(f) != count for f in frames):
        raise ValueError("every frame must list the same eyes")
    shown = [median(f[i].facing for f in frames) > SHOWN_FACING and 2 * sum(f[i].seen for f in frames) >= len(frames)
             for i in range(count)]
    columns = [2 if whites and median(f[i].width for f in frames) >= WIDE else 1 for i in range(count)]
    drawn = [i for i in range(count) if shown[i]]
    if not drawn:
        return [[None] * count for _ in frames]
    rows = max(1, min(MAX_ROWS, int(np.floor(median(f[i].height for f in frames for i in drawn) + 0.5))))
    turn = median(f[i].turn for f in frames for i in drawn)
    if len(drawn) > 1 and abs(turn) > TURNED:
        far = min(drawn, key=lambda i: median(f[i].facing for f in frames))
        columns[far] = 1
    order = sorted(drawn, key=lambda i: median(f[i].x for f in frames))  # screen left to right
    # where each drawn eye's block starts, from the pattern's left edge, for every set of eyes a frame can show
    centres = {i: median(f[i].x for f in frames) for i in order}
    if abs(turn) > TURNED:
        gap = 0  # a turned face's outer eye sits at the silhouette's edge: a wider gap would push it onto the outline

    def blocks(present: tuple[int, ...]) -> tuple[dict[int, int], int]:
        offsets: dict[int, int] = {}
        at = 0
        for n, i in enumerate(present):
            if n:
                before = present[n - 1]
                apart = centres[i] - centres[before] - (columns[i] + columns[before]) / 2
                at += max(1, int(np.floor(apart + 0.5)) + gap)
            offsets[i] = at
            at += columns[i]
        return offsets, at

    def pupil(i: int, present: tuple[int, ...]) -> int:
        if columns[i] == 1:
            return 0
        if turn > TURNED:
            return columns[i] - 1
        if turn < -TURNED:
            return 0
        if len(present) == 1:
            return 0
        return columns[i] - 1 if i == present[0] else 0  # toward the other eye

    plans: list[list[EyeStamp | None]] = []
    held: dict[tuple[int, ...], tuple[int, int]] = {}
    for frame in frames:
        present = tuple(i for i in order if frame[i].seen and frame[i].facing > HIDDEN_FACING)
        stamps: list[EyeStamp | None] = [None] * count
        if present:
            offsets, width = blocks(present)
            middle_x = sum(frame[i].x for i in present) / len(present)
            middle_y = sum(frame[i].y for i in present) / len(present)
            if len(present) > 1:  # the middle of the blocks, not of the eyes, sits at the eyes' middle
                span = [offsets[i] + columns[i] / 2 for i in present]
                ideal_x = middle_x - sum(span) / len(span)
            else:
                ideal_x = middle_x - width / 2
            before = held.get(present)
            left = _snap(ideal_x, before[0] if before else None)
            top = _snap(middle_y - rows / 2, before[1] if before else None)
            held = {present: (left, top)}  # another set of eyes starts afresh
            for i in present:
                stamps[i] = EyeStamp(left + offsets[i], top, columns[i], rows, pupil(i, present))
        else:
            held = {}
        plans.append(stamps)
    return plans


def fill_from_neighbours(colour: U8, mask: Bool) -> U8:
    """`colour` (h, w, 4) with each masked pixel given the colour of the nearest opaque pixel outside the mask, growing in
    from the mask's edge a ring at a time (up, left, right, down, in that order). A masked pixel that no such pixel reaches
    keeps its colour."""
    out = colour.copy()
    todo = mask & (colour[..., 3] > 0)
    known = (colour[..., 3] > 0) & ~mask
    height, width = todo.shape
    while todo.any():
        grown = np.zeros_like(todo)
        fresh = out.copy()
        for dy, dx in ((-1, 0), (0, -1), (0, 1), (1, 0)):
            source = np.zeros_like(known)
            ys = slice(max(0, dy), height + min(0, dy))
            xs = slice(max(0, dx), width + min(0, dx))
            ys_from = slice(max(0, -dy), height + min(0, -dy))
            xs_from = slice(max(0, -dx), width + min(0, -dx))
            source[ys_from, xs_from] = known[ys, xs]  # source[y, x]: the pixel at (y + dy, x + dx) is known
            take = todo & source & ~grown
            if take.any():
                shifted = np.zeros_like(out)
                shifted[ys_from, xs_from] = out[ys, xs]
                fresh[take] = shifted[take]
                grown |= take
        if not grown.any():
            break
        out = fresh
        known = known | grown
        todo = todo & ~grown
    return out


def paint_eyes(colour: U8, stamps: Sequence[EyeStamp | None], pupil_rgb: Sequence[int], white_rgb: Sequence[int] | None,
               closed: bool | Collection[int] = False) -> U8:
    """`colour` with each eye's pattern painted on its opaque pixels: the pupil column in `pupil_rgb`, the others in
    `white_rgb` (the pupil's colour when None). A closed eye is one line of the pupil's colour along its bottom row, and
    the rows above it are left as they are: the lid. `closed` is true for every eye (a blink), or the places in `stamps` of
    the eyes that are (a wink)."""
    out = colour.copy()
    height, width = out.shape[:2]
    for place, stamp in enumerate(stamps):
        if stamp is None:
            continue
        shut = closed if isinstance(closed, bool) else place in closed
        for row in range(stamp.rows):
            if shut and row < stamp.rows - 1:
                continue
            for column in range(stamp.columns):
                y, x = stamp.top + row, stamp.left + column
                if not (0 <= y < height and 0 <= x < width) or out[y, x, 3] == 0:
                    continue
                dark = shut or column == stamp.pupil or white_rgb is None
                out[y, x, :3] = np.asarray(pupil_rgb if dark else white_rgb, dtype=np.uint8)
    return out
