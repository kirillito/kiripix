"""Look Ops (ticket 0130, ADR 0009, trial 0128): what the `looks` Stage does to an image model's edit of a room.

An edit comes back from the model as a picture of the Source with some of it redrawn, a little rescaled or shifted, and
every pixel re-rendered by about 1 ΔE. So the Stage registers it on the Source (`register`, `warp_nearest`), may match
its light to the room's (`regrade`), and then works out, on the fitted images before the palette, where it really differs
(`difference_region`, `drift_boxes`). Before the palette, because the palette's steps are about 3 ΔE apart: a count of
changed mapped pixels would find redraw nowhere and noise everywhere.

ΔE is the OKLab distance times 100. Pure: arrays in, arrays out. Pixel (x, y) has its centre at integer coordinates.
Nothing here smooths an image the Stage keeps: `warp_nearest` and `resize_nearest` pick pixels, and `regrade` returns
colours the palette then maps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from kiripix.ops.colour import F64, U8, _oklab_matrices, srgb_to_oklab
from kiripix.ops.layers import connected_regions, remove_small_pieces
from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt
else:
    np = lazy_module("numpy")
    npt = lazy_module("numpy.typing")

if TYPE_CHECKING:
    BoolMask = npt.NDArray[np.bool_]
else:
    BoolMask = Any

TILE = 96  # Source px: the side of a registration tile (0128 had over 300 of them outside a region)
MIN_STD = 2.0  # a tile flatter than this (0..255 luma) carries no position
MIN_PEAK = 0.08  # the phase correlation's peak, as a share of the tile's energy, below which a tile isn't trusted
MIN_TILES = 6  # fewer textured tiles than this and the edit is left as it is
NEGLIGIBLE = 0.25  # Source px: a registration that moves no pixel further than this isn't applied
_PASSES = 5


@dataclass(frozen=True)
class Alignment:
    """Where the edit's content is: `edit_x = scale_x * room_x + shift_x`, and the same for y (Source px).

    `residual` is the median distance in Source px between each tile's measured displacement and the fit's, `tiles` how
    many textured tiles the last pass used (0 when there were too few to estimate: the identity).
    """

    scale_x: float = 1.0
    scale_y: float = 1.0
    shift_x: float = 0.0
    shift_y: float = 0.0
    residual: float = 0.0
    tiles: int = 0

    def displacement(self, width: int, height: int) -> float:
        """The furthest any pixel of a `width` x `height` image moves, in px (the corners move most)."""
        worst = 0.0
        for x in (0, width - 1):
            for y in (0, height - 1):
                worst = max(worst, math.hypot((self.scale_x - 1) * x + self.shift_x,
                                              (self.scale_y - 1) * y + self.shift_y))
        return worst

    def negligible(self, width: int, height: int) -> bool:
        return self.displacement(width, height) < NEGLIGIBLE


@dataclass(frozen=True)
class Drift:
    """A component of redraw outside a Look's region: its box (x, y, width, height) and how many pixels are in it."""

    x: int
    y: int
    width: int
    height: int
    pixels: int


def _luma(rgba: U8) -> F64:
    rgb = rgba[..., :3].astype(np.float64)
    result: F64 = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114
    return result


def _check_pair(room: U8, edit: U8) -> None:
    for name, image in (("room", room), ("edit", edit)):
        if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
            raise ValueError(f"the {name} must be an RGBA uint8 image, got shape {image.shape} and {image.dtype}")
    if room.shape != edit.shape:
        raise ValueError(f"the room is {room.shape[1]}x{room.shape[0]} and the edit {edit.shape[1]}x{edit.shape[0]}")


def resize_nearest(image: U8, width: int, height: int) -> U8:
    """`image` at another size, each pixel taken from the source pixel under its centre. No smoothing."""
    if width < 1 or height < 1:
        raise ValueError(f"can't resize to {width}x{height}")
    source_height, source_width = image.shape[:2]
    if (source_width, source_height) == (width, height):
        return image
    xs = np.minimum((np.arange(width) * 2 + 1) * source_width // (2 * width), source_width - 1)
    ys = np.minimum((np.arange(height) * 2 + 1) * source_height // (2 * height), source_height - 1)
    result: U8 = image[ys][:, xs]
    return result


def dilate(mask: BoolMask, radius: int) -> BoolMask:
    """`mask` grown by `radius` px in every direction (a square reach)."""
    if mask.dtype != np.bool_ or mask.ndim != 2:
        raise ValueError("a Mask is a 2-D boolean array")
    if radius < 0:
        raise ValueError(f"the radius can't be negative, got {radius}")
    if radius == 0 or not mask.any():
        return mask.copy()
    padded = np.pad(mask.astype(np.int64), radius)
    total = padded.cumsum(axis=0).cumsum(axis=1)
    total = np.pad(total, ((1, 0), (1, 0)))
    size = 2 * radius + 1
    height, width = mask.shape
    counts = (total[size:size + height, size:size + width] - total[:height, size:size + width]
              - total[size:size + height, :width] + total[:height, :width])
    result: BoolMask = counts > 0
    return result


# --- register ---------------------------------------------------------------------------------------------------


def _warp_luma(luma: F64, alignment: Alignment) -> F64:
    """The edit's luma laid on the room: bilinear samples at `scale * p + shift`, for the estimate only."""
    height, width = luma.shape
    px = np.clip(alignment.scale_x * np.arange(width) + alignment.shift_x, 0, width - 1)
    py = np.clip(alignment.scale_y * np.arange(height) + alignment.shift_y, 0, height - 1)
    ix = np.minimum(np.floor(px).astype(np.int64), max(width - 2, 0))
    iy = np.minimum(np.floor(py).astype(np.int64), max(height - 2, 0))
    ix1, iy1 = np.minimum(ix + 1, width - 1), np.minimum(iy + 1, height - 1)
    fx, fy = (px - ix)[None, :], (py - iy)[:, None]
    top = luma[iy][:, ix] * (1 - fx) + luma[iy][:, ix1] * fx
    bottom = luma[iy1][:, ix] * (1 - fx) + luma[iy1][:, ix1] * fx
    result: F64 = top * (1 - fy) + bottom * fy
    return result


def _parabola(left: float, centre: float, right: float) -> float:
    bend = left - 2 * centre + right
    if bend >= -1e-12:
        return 0.0
    return float(max(-0.5, min(0.5, 0.5 * (left - right) / bend)))


def _tile_window(tile: int) -> F64:
    taper = np.minimum(1.0, np.minimum(np.arange(tile) + 0.5, tile - np.arange(tile) - 0.5) / (tile / 8))
    window: F64 = np.outer(taper, taper)  # flat over the middle, so a shifted tile loses little of its content
    return window


def _displacements(room: F64, edit: F64, exclude: BoolMask | None, tile: int,
                   refine: bool) -> list[tuple[float, float, float, float]]:
    """Where each textured tile of the edit sits against the room's: (x, y, dx, dy), the tile's centre and the shift of
    its content. The first look is a normalised cross-correlation of the tile (a peak, to a parabola's sub-pixel); once
    the edit is laid close (`refine`), a Lucas-Kanade step on the room's gradient, which is exact for a small shift and
    doesn't lock to whole pixels as a peak does on a smooth picture. Tiles are laid from the top left in a grid."""
    height, width = room.shape
    window = _tile_window(tile)
    found: list[tuple[float, float, float, float]] = []
    for y in range(0, height - tile + 1, tile):
        for x in range(0, width - tile + 1, tile):
            if exclude is not None and exclude[y:y + tile, x:x + tile].any():
                continue
            a = room[y:y + tile, x:x + tile]
            b = edit[y:y + tile, x:x + tile]
            if a.std() < MIN_STD:
                continue
            if refine:
                step = _lucas_kanade(a, b, window)
                if step is None:
                    continue
                dx, dy = step
            else:
                peak = _correlation_peak(a, b, window)
                if peak is None:
                    continue
                dx, dy = peak
            found.append((x + (tile - 1) / 2, y + (tile - 1) / 2, dx, dy))
    return found


def _correlation_peak(a: F64, b: F64, window: F64) -> tuple[float, float] | None:
    tile = a.shape[0]
    wa, wb = (a - a.mean()) * window, (b - b.mean()) * window
    norm = float(np.sqrt((wa**2).sum() * (wb**2).sum()))
    surface = np.fft.ifft2(np.fft.fft2(wb) * np.conj(np.fft.fft2(wa))).real / max(norm, 1e-9)
    iy, ix = (int(v) for v in np.unravel_index(int(np.argmax(surface)), surface.shape))
    if surface[iy, ix] < MIN_PEAK:
        return None
    dx = ix + _parabola(surface[iy, ix - 1], surface[iy, ix], surface[iy, (ix + 1) % tile])
    dy = iy + _parabola(surface[iy - 1, ix], surface[iy, ix], surface[(iy + 1) % tile, ix])
    return (dx - tile if dx > tile / 2 else dx), (dy - tile if dy > tile / 2 else dy)


def _lucas_kanade(a: F64, b: F64, window: F64) -> tuple[float, float] | None:
    """The small shift (dx, dy) with b(p) = a(p - d): least squares of b - a = -grad(a) . d under the window. None when
    the tile has texture in one direction only (the shift along an edge can't be told)."""
    gradient = np.gradient(a)
    w = window[1:-1, 1:-1]
    gy, gx = gradient[0][1:-1, 1:-1], gradient[1][1:-1, 1:-1]
    diff = (b - a)[1:-1, 1:-1]
    sxx, sxy, syy = float((w * gx * gx).sum()), float((w * gx * gy).sum()), float((w * gy * gy).sum())
    det = sxx * syy - sxy * sxy
    if det <= 1e-6 * max(sxx * syy, 1e-12) or min(sxx, syy) < 1e-3 * w.sum():
        return None
    rx, ry = -float((w * gx * diff).sum()), -float((w * gy * diff).sum())
    dx, dy = (syy * rx - sxy * ry) / det, (sxx * ry - sxy * rx) / det
    if abs(dx) > 8.0 or abs(dy) > 8.0:
        return None  # beyond what the linearisation holds: the correlation pass should have got it closer
    return dx, dy


def _line(q: F64, d: F64) -> tuple[float, float]:
    """The least-squares d = slope * q + intercept."""
    centre = float(q.mean())
    spread = float(((q - centre) ** 2).sum())
    slope = float(((q - centre) * (d - d.mean())).sum() / spread) if spread > 0 else 0.0
    return slope, float(d.mean()) - slope * centre


def _fit(samples: list[tuple[float, float, float, float]]) -> tuple[tuple[float, float, float, float], float, int]:
    """Fit displacement = slope * position + intercept on each axis, dropping outliers (a tile the edit redrew) until
    none is further than three times the median miss and a quarter pixel. Returns (ax, bx, ay, by), the median miss
    and the tiles kept."""
    data = np.array(samples, dtype=np.float64)
    keep = np.ones(len(data), dtype=bool)
    while True:
        ax, bx = _line(data[keep, 0], data[keep, 2])
        ay, by = _line(data[keep, 1], data[keep, 3])
        miss = np.hypot(data[:, 2] - (ax * data[:, 0] + bx), data[:, 3] - (ay * data[:, 1] + by))
        trimmed = keep & (miss <= 3.0 * float(np.median(miss[keep])) + 0.25)
        if trimmed.sum() == keep.sum() or trimmed.sum() < MIN_TILES:
            break
        keep = trimmed
    return (ax, bx, ay, by), float(np.median(miss[keep])), int(keep.sum())


def register(room: U8, edit: U8, exclude: BoolMask | None = None, tile: int = TILE) -> Alignment:
    """Estimate the scale (per axis) and shift, no rotation, that lay `edit` on `room`, both at the Source's size.

    Phase correlation on luminance tiles that have texture and lie wholly outside `exclude` (where the edit is meant to
    differ), fitted robustly, in two passes (the second measures what the first left). Fewer than `MIN_TILES` such tiles
    give the identity with `tiles` 0. Nothing here bounds the answer: the caller judges it against its limits.
    """
    _check_pair(room, edit)
    if exclude is not None and exclude.shape != room.shape[:2]:
        raise ValueError("exclude must be a Mask of the images' size")
    room_luma, edit_luma = _luma(room), _luma(edit)
    current = Alignment()
    for index in range(_PASSES):
        samples = _displacements(room_luma, _warp_luma(edit_luma, current), exclude, tile, refine=index > 0)
        if len(samples) < MIN_TILES:
            return current if current.tiles else Alignment()
        (ax, bx, ay, by), residual, used = _fit(samples)
        current = Alignment(current.scale_x * (1 + ax), current.scale_y * (1 + ay),
                            current.shift_x + current.scale_x * bx, current.shift_y + current.scale_y * by,
                            residual, used)
        if math.hypot(ax * room.shape[1], ay * room.shape[0]) + math.hypot(bx, by) < 0.02:
            break  # what the pass measured is already below what a pixel can show
    return current


def warp_nearest(edit: U8, alignment: Alignment) -> U8:
    """`edit` laid on the room's grid: each pixel taken from the edit at `scale * p + shift`, rounded to the nearest
    pixel (a border pixel repeats outside the edit). The identity returns the edit as it is."""
    height, width = edit.shape[:2]
    if alignment == Alignment() or alignment.negligible(width, height):
        return edit
    ix = np.clip(np.floor(alignment.scale_x * np.arange(width) + alignment.shift_x + 0.5).astype(np.int64), 0, width - 1)
    iy = np.clip(np.floor(alignment.scale_y * np.arange(height) + alignment.shift_y + 0.5).astype(np.int64), 0,
                 height - 1)
    result: U8 = edit[iy][:, ix]
    return result


# --- regrade ----------------------------------------------------------------------------------------------------


def _oklab_to_srgb(lab: F64) -> U8:
    table, m1, m2 = _oklab_matrices()
    lms = (lab @ np.linalg.inv(m2).T) ** 3
    linear = np.clip(lms @ np.linalg.inv(m1).T, 0.0, 1.0)
    encoded = np.where(linear <= 0.0031308, linear * 12.92, 1.055 * np.power(linear, 1 / 2.4) - 0.055)
    result: U8 = np.floor(np.clip(encoded, 0.0, 1.0) * 255 + 0.5).astype(np.uint8)
    return result


def regrade(room: U8, edit: U8, exclude: BoolMask | None = None) -> U8:
    """`edit` with its light matched to `room`'s: a gain and an offset on each OKLab channel, least squares over the
    opaque pixels outside `exclude`, applied to the whole edit. Too few pixels (under 64), or none unlike, change nothing."""
    _check_pair(room, edit)
    usable = (room[..., 3] == 255) & (edit[..., 3] == 255)
    if exclude is not None:
        usable &= ~exclude
    if int(usable.sum()) < 64:
        return edit
    want, have = srgb_to_oklab(room[..., :3][usable]), srgb_to_oklab(edit[..., :3][usable])
    everything = srgb_to_oklab(edit[..., :3])
    graded = everything.copy()
    for channel in range(3):
        slope, intercept = _line(have[:, channel], want[:, channel])
        slope = min(max(slope, 0.5), 2.0)
        intercept = float(want[:, channel].mean()) - slope * float(have[:, channel].mean())
        graded[..., channel] = everything[..., channel] * slope + intercept
    result = edit.copy()
    opaque = edit[..., 3] == 255
    result[..., :3] = np.where(opaque[..., None], _oklab_to_srgb(graded), edit[..., :3])
    return result


# --- difference and drift ---------------------------------------------------------------------------------------


def difference_map(room: U8, edit: U8) -> F64:
    """The OKLab distance between two same-sized images times 100, as the mean over each pixel's 3x3 neighbourhood
    (edges repeated). A pixel transparent in either image has no difference."""
    _check_pair(room, edit)
    both = (room[..., 3] > 0) & (edit[..., 3] > 0)
    distance = np.linalg.norm(srgb_to_oklab(room[..., :3]) - srgb_to_oklab(edit[..., :3]), axis=2) * 100.0
    distance = np.where(both, distance, 0.0)
    height, width = distance.shape
    padded = np.pad(distance, 1, mode="edge")
    total = np.zeros((height, width), dtype=np.float64)
    for dy in range(3):
        for dx in range(3):
            total += padded[dy:dy + height, dx:dx + width]
    result: F64 = total / 9.0
    return result


def difference_region(room: U8, edit: U8, box: tuple[int, int, int, int], tolerance: float, specks: int) -> BoolMask:
    """Where `edit` differs from `room` by at least `tolerance` ΔE (3x3 mean) inside `box` (x0, y0, x1, y1, both
    corners included), with 8-connected pieces of fewer than `specks` pixels removed."""
    if tolerance < 0:
        raise ValueError(f"the tolerance can't be negative, got {tolerance}")
    x0, y0, x1, y1 = box
    if x1 < x0 or y1 < y0:
        raise ValueError(f"the box ({x0}, {y0}) to ({x1}, {y1}) runs backwards")
    inside = np.zeros(room.shape[:2], dtype=np.bool_)
    inside[y0:y1 + 1, x0:x1 + 1] = True
    region: BoolMask = (difference_map(room, edit) >= tolerance) & inside
    return remove_small_pieces(region, specks)


def drift_boxes(room: U8, edit: U8, region: BoolMask, tolerance: float, min_size: int) -> list[Drift]:
    """The 8-connected pieces of at least `min_size` pixels where `edit` differs from `room` by `tolerance` ΔE (3x3
    mean) outside `region`: the redraw the edit made that the Look doesn't cover. Largest first; ties go to the top,
    then the left."""
    if region.shape != room.shape[:2]:
        raise ValueError("region must be a Mask of the images' size")
    drifted = (difference_map(room, edit) >= tolerance) & ~region
    found = []
    for piece in connected_regions(drifted, eight=True):
        if len(piece) < min_size:
            continue
        y0, x0 = (int(v) for v in piece.min(axis=0))
        y1, x1 = (int(v) for v in piece.max(axis=0))
        found.append(Drift(x0, y0, x1 - x0 + 1, y1 - y0 + 1, int(len(piece))))
    found.sort(key=lambda d: (-d.pixels, d.y, d.x))
    return found


def mask_box(mask: BoolMask) -> tuple[int, int, int, int] | None:
    """The smallest box (x, y, width, height) holding every set pixel of a Mask, or None when none is set."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
