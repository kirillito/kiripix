"""Join Ops (spec §14 M4, ticket 0135): put a piece an image model painted onto a Source, past its edge.

A join takes three steps, and all three are needed (trial 0063): `register_piece` undoes the model's small rescale and
shift, `match_tone` removes a brightness step, and `seam_join` cuts through the overlap along the least difference and
blends. `resample_piece` carries a piece onto the base's pixel grid between the first and the second step.

All of them work on painted Sources before `fit`, so they are float-valued and smooth where an Op on a target image
must not be. Pure: arrays in, arrays out. Alpha is binary on the way in (a pixel counts as present at 255).

Conventions. Pixel (x, y) has its centre at integer coordinates. A piece is laid on the base by an `Overlap`: the
`side` of the base it lies on, how many px (`width`) of the base's edge it covers, and `offset`, the shift along the
edge (the piece's top edge against the base's top edge for east and west, left edges for north and south). That is
only the first guess; `register_piece` refines it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt
else:
    np = lazy_module("numpy")
    npt = lazy_module("numpy.typing")

if TYPE_CHECKING:
    U8 = npt.NDArray[np.uint8]
    F64 = npt.NDArray[np.float64]
else:
    U8 = Any  # the array types are for the type checker; numpy loads late
    F64 = Any

Side = Literal["east", "west", "north", "south"]
JOIN_SIDES: tuple[str, ...] = ("east", "west", "north", "south")

_PATCH = 24  # side of an edge patch, px
_SEARCH = (16, 4, 2)  # the reach of each registration pass, px; the first is the most the first guess may be off
_MIN_SCORE = 0.6  # normalised correlation below which a patch is not trusted
_MIN_STD = 2.0  # a patch flatter than this (0..255) carries no position
_MIN_SPAN = 64.0  # an axis' scale needs samples at least this far apart
_MIN_PATCHES = 4
_BIG = 3 * 255 * 4  # a seam pixel where only one image has colour costs more than any difference


@dataclass(frozen=True)
class Overlap:
    """A piece laid on a base: on which `side`, covering `width` px of the base's edge, `offset` px along it."""

    side: Side
    width: int
    offset: int = 0

    def origin(self, base_shape: tuple[int, ...], piece_shape: tuple[int, ...]) -> tuple[int, int]:
        """Where the piece's top-left pixel lands in the base's coordinates (may be negative)."""
        bh, bw = int(base_shape[0]), int(base_shape[1])
        ph, pw = int(piece_shape[0]), int(piece_shape[1])
        if self.side == "east":
            return bw - self.width, self.offset
        if self.side == "west":
            return self.width - pw, self.offset
        if self.side == "south":
            return self.offset, bh - self.width
        return self.offset, self.width - ph

    @classmethod
    def placed(
        cls, side: Side, base_shape: tuple[int, ...], piece_shape: tuple[int, ...], origin: tuple[int, int]
    ) -> "Overlap":
        """The Overlap that puts a piece of `piece_shape` at `origin`: the inverse of `origin`."""
        bh, bw = int(base_shape[0]), int(base_shape[1])
        ph, pw = int(piece_shape[0]), int(piece_shape[1])
        x, y = origin
        if side == "east":
            return cls(side, bw - x, y)
        if side == "west":
            return cls(side, x + pw, y)
        if side == "south":
            return cls(side, bh - y, x)
        return cls(side, y + ph, x)


@dataclass(frozen=True)
class Registration:
    """Where a piece lands on the base: `base_x = scale_x * piece_x + shift_x`, and the same for y.

    `residual` is the root-mean-square distance in px between each edge patch's measured place and the fit's.
    `patches` is how many edge patches the last pass used.
    """

    scale_x: float
    scale_y: float
    shift_x: float
    shift_y: float
    residual: float
    patches: int

    def to_base(self, x: float, y: float) -> tuple[float, float]:
        return self.scale_x * x + self.shift_x, self.scale_y * y + self.shift_y


@dataclass(frozen=True)
class GainRange:
    """The lowest and highest gain `match_tone` applied."""

    low: float
    high: float


@dataclass(frozen=True, eq=False)
class Seam:
    """The cut `seam_join` made, in the joined image's coordinates.

    `points` is (n, 2) of (x, y), one per row (east and west joins) or column (north and south) where both images have
    colour, in order along the seam. For a join on an east or west side a point is the first pixel taken from the piece
    (east) or from the base (west) at that row; on a north or south side, the same by column. `length` is the path's
    length in px, `mean_difference` the mean absolute RGB difference (0..255) of the pixels it cuts.
    """

    points: Any
    length: float
    mean_difference: float
    base_origin: tuple[int, int]
    piece_origin: tuple[int, int]


# --- geometry ---------------------------------------------------------------------------------------------------


def _check(base: U8, piece: U8) -> None:
    for name, image in (("base", base), ("piece", piece)):
        if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
            raise ValueError(f"the {name} must be an RGBA uint8 image, got shape {image.shape} and {image.dtype}")


def _check_overlap(base: U8, piece: U8, overlap: Overlap) -> None:
    if overlap.side not in JOIN_SIDES:
        raise ValueError(f"unknown side {overlap.side!r}; use one of {', '.join(JOIN_SIDES)}")
    along = 1 if overlap.side in ("east", "west") else 0
    most = min(base.shape[along], piece.shape[along])
    if not 1 <= overlap.width <= most:
        raise ValueError(f"an overlap of {overlap.width} px doesn't fit images {most} px across the join")


def _normal(side: str, array: Any) -> Any:
    """The array turned so that the piece lies east of the base (a copy only where it has to be)."""
    if side == "west":
        return array[:, ::-1]
    if side == "south":
        return array.swapaxes(0, 1)
    if side == "north":
        return array[::-1].swapaxes(0, 1)
    return array


def _unnormal(side: str, array: Any) -> Any:
    if side == "west":
        return array[:, ::-1]
    if side == "south":
        return array.swapaxes(0, 1)
    if side == "north":
        return array.swapaxes(0, 1)[::-1]
    return array


def _natural_point(side: str, x: int, y: int, normal_width: int) -> tuple[int, int]:
    """A pixel of the normalised canvas, as the joined image's (x, y). `normal_width` is the canvas' width."""
    if side == "west":
        return normal_width - 1 - x, y
    if side == "south":
        return y, x
    if side == "north":
        return y, normal_width - 1 - x
    return x, y


def _luma(rgba: U8) -> F64:
    rgb = rgba[..., :3].astype(np.float64)
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


# --- register_piece ---------------------------------------------------------------------------------------------


def _warp(image: F64, scale_x: float, scale_y: float, shift_x: float, shift_y: float, box: tuple[int, int, int, int]) -> tuple[F64, Any]:
    """Bilinear samples of `image` (H, W, C) laid on the base grid: the pixels of `box` (x0, y0, x1, y1, half-open)
    and a boolean (rows, columns) of those that fall inside the image."""
    x0, y0, x1, y1 = box
    height, width = image.shape[:2]
    px = (np.arange(x0, x1, dtype=np.float64) - shift_x) / scale_x
    py = (np.arange(y0, y1, dtype=np.float64) - shift_y) / scale_y
    inside = (py[:, None] >= 0) & (py[:, None] <= height - 1) & (px[None, :] >= 0) & (px[None, :] <= width - 1)
    px = np.clip(px, 0, width - 1)
    py = np.clip(py, 0, height - 1)
    ix = np.minimum(np.floor(px).astype(np.int64), max(width - 2, 0))
    iy = np.minimum(np.floor(py).astype(np.int64), max(height - 2, 0))
    fx = (px - ix)[None, :, None]
    fy = (py - iy)[:, None, None]
    ix1 = np.minimum(ix + 1, width - 1)
    iy1 = np.minimum(iy + 1, height - 1)
    top = image[iy][:, ix] * (1 - fx) + image[iy][:, ix1] * fx
    bottom = image[iy1][:, ix] * (1 - fx) + image[iy1][:, ix1] * fx
    return top * (1 - fy) + bottom * fy, inside


def _positions(low: int, high: int, cap: int) -> list[int]:
    """Top-left coordinates of patches along [low, high], one patch apart, at most `cap` of them, spread evenly."""
    if high < low:
        return []
    count = min(cap, (high - low) // _PATCH + 1)
    if count == 1:
        return [(low + high) // 2]
    return sorted({int(round(low + (high - low) * i / (count - 1))) for i in range(count)})


def _strip_boxes(
    overlaps: list[Overlap], base_shape: tuple[int, ...], footprint: tuple[int, int, int, int]
) -> list[tuple[int, int, int, int]]:
    """The part of the base each overlap's strip covers: the piece's footprint cut to that side of the base."""
    bh, bw = base_shape[:2]
    fx0, fy0, fx1, fy1 = footprint
    boxes = []
    for overlap in overlaps:
        x0, y0, x1, y1 = max(fx0, 0), max(fy0, 0), min(fx1, bw), min(fy1, bh)
        if overlap.side == "east":
            x0 = max(x0, bw - overlap.width - _SEARCH[0])
        elif overlap.side == "west":
            x1 = min(x1, overlap.width + _SEARCH[0])
        elif overlap.side == "south":
            y0 = max(y0, bh - overlap.width - _SEARCH[0])
        else:
            y1 = min(y1, overlap.width + _SEARCH[0])
        boxes.append((x0, y0, x1, y1))
    return boxes


def _measure(
    base_luma: F64,
    base_valid: Any,
    warped_luma: F64,
    warped_valid: Any,
    box: tuple[int, int, int, int],
    boxes: list[tuple[int, int, int, int]],
    reach: int,
) -> list[tuple[float, float, float, float]]:
    """Where each edge patch of the warped piece (kept inside `boxes`) sits in the base: (x, y, dx, dy) with the
    patch's centre and its displacement, for the patches that correlate well. `box` is the warped array's place."""
    bx0, by0, _, _ = box
    bh, bw = base_luma.shape
    seen: set[tuple[int, int]] = set()
    found: list[tuple[float, float, float, float]] = []
    for x0, y0, x1, y1 in boxes:
        xs = _positions(max(x0, reach), min(x1 - _PATCH, bw - _PATCH - reach), 12 if x1 - x0 < y1 - y0 else 48)
        ys = _positions(max(y0, reach), min(y1 - _PATCH, bh - _PATCH - reach), 12 if y1 - y0 < x1 - x0 else 48)
        for y in ys:
            for x in xs:
                if (x, y) in seen:
                    continue
                seen.add((x, y))
                template_valid = warped_valid[y - by0 : y - by0 + _PATCH, x - bx0 : x - bx0 + _PATCH]
                window_valid = base_valid[y - reach : y + _PATCH + reach, x - reach : x + _PATCH + reach]
                if not template_valid.all() or not window_valid.all():
                    continue
                template = warped_luma[y - by0 : y - by0 + _PATCH, x - bx0 : x - bx0 + _PATCH]
                if template.std() < _MIN_STD:
                    continue
                score = _correlate(template, base_luma[y - reach : y + _PATCH + reach, x - reach : x + _PATCH + reach])
                iy, ix = (int(v) for v in np.unravel_index(int(np.argmax(score)), score.shape))
                if score[iy, ix] < _MIN_SCORE:
                    continue
                dx = ix - reach + _parabola(score[iy, ix - 1], score[iy, ix], score[iy, ix + 1]) if 0 < ix < 2 * reach else ix - reach
                dy = iy - reach + _parabola(score[iy - 1, ix], score[iy, ix], score[iy + 1, ix]) if 0 < iy < 2 * reach else iy - reach
                half = (_PATCH - 1) / 2
                found.append((x + half, y + half, float(dx), float(dy)))
    return found


def _correlate(template: F64, window: F64) -> F64:
    """Normalised correlation of `template` (P, P) at every position inside `window`: (2R + 1, 2R + 1)."""
    tz = template - template.mean()
    views = np.lib.stride_tricks.sliding_window_view(window, template.shape)
    sums = views.sum(axis=(2, 3))
    squares = (views * views).sum(axis=(2, 3))
    count = template.size
    variance = np.maximum(squares - sums * sums / count, 0.0)
    numerator = np.einsum("ijkl,kl->ij", views, tz)
    denominator = np.sqrt(variance * float(np.sum(tz * tz)))
    return np.where(denominator > 1e-9, numerator / np.maximum(denominator, 1e-9), -1.0)


def _parabola(left: float, centre: float, right: float) -> float:
    bend = left - 2 * centre + right
    if bend >= -1e-12:
        return 0.0
    return float(max(-0.5, min(0.5, 0.5 * (left - right) / bend)))


def _line(q: F64, d: F64, slope: float | None) -> tuple[float, float]:
    """The least-squares d = slope * q + intercept; the slope is fixed when given."""
    centre = float(q.mean())
    if slope is None:
        spread = float(((q - centre) ** 2).sum())
        slope = float(((q - centre) * (d - d.mean())).sum() / spread) if spread > 0 else 0.0
    return slope, float(d.mean()) - slope * centre


def _fit(samples: list[tuple[float, float, float, float]]) -> tuple[tuple[float, float, float, float], float, int]:
    """Fit displacement = a * position + b on each axis, dropping outliers. Returns (ax, bx, ay, by), the residual
    (rms px) and the patches kept. An axis whose samples are less than `_MIN_SPAN` apart takes the other axis' slope
    (or 0 if that is weak as well)."""
    data = np.array(samples, dtype=np.float64)
    keep = np.ones(len(data), dtype=bool)
    while True:
        qx, qy, dx, dy = (data[keep, i] for i in range(4))
        weak_x = float(qx.max() - qx.min()) < _MIN_SPAN
        weak_y = float(qy.max() - qy.min()) < _MIN_SPAN
        ax, bx = _line(qx, dx, 0.0 if weak_x else None)
        ay, by = _line(qy, dy, 0.0 if weak_y else None)
        if weak_x and not weak_y:
            ax, bx = _line(qx, dx, ay)
        elif weak_y and not weak_x:
            ay, by = _line(qy, dy, ax)
        miss = np.hypot(data[:, 2] - (ax * data[:, 0] + bx), data[:, 3] - (ay * data[:, 1] + by))
        limit = 3.0 * float(np.median(miss[keep])) + 0.25
        trimmed = keep & (miss <= limit)
        if trimmed.sum() == keep.sum() or trimmed.sum() < _MIN_PATCHES:
            break
        keep = trimmed
    return (ax, bx, ay, by), float(np.sqrt(np.mean(miss[keep] ** 2))), int(keep.sum())


def register_piece(base: U8, piece: U8, overlaps: list[Overlap]) -> Registration:
    """Estimate the scale and shift (no rotation) that put `piece` on `base`, from patches along each overlap.

    Each Overlap gives the first guess and says which edge of the base to look along; a corner piece has two (one east
    or west, one north or south), and the patches of both constrain the fit. Scale is per axis, because an image model
    rescales a piece by up to about 1.25 % and not always the same on both axes. Patches are matched by normalised
    correlation in luminance, so a tone step doesn't throw them off; pixels with no alpha are ignored. Three passes
    narrow the search (16, 4, 2 px), each on the piece resampled with the last pass' result.

    The first overlap with a side in each direction sets the first guess; with two on the same direction, the first.
    Raises ValueError when the overlap has too few textured patches (flat sky, a wall of one colour) to fit.
    """
    _check(base, piece)
    if not overlaps:
        raise ValueError("register_piece needs at least one overlap")
    for overlap in overlaps:
        _check_overlap(base, piece, overlap)
    ox = next((o.origin(base.shape, piece.shape)[0] for o in overlaps if o.side in ("east", "west")), None)
    oy = next((o.origin(base.shape, piece.shape)[1] for o in overlaps if o.side in ("north", "south")), None)
    first = overlaps[0].origin(base.shape, piece.shape)
    ox = first[0] if ox is None else ox
    oy = first[1] if oy is None else oy

    base_luma = _luma(base)
    base_valid = base[..., 3] == 255
    piece_luma = _luma(piece)[..., None]
    piece_valid = piece[..., 3] == 255
    sx, sy, tx, ty = 1.0, 1.0, float(ox), float(oy)
    bh, bw = base.shape[:2]
    ph, pw = piece.shape[:2]
    residual, used = 0.0, 0
    for reach in _SEARCH:
        footprint = (
            math.floor(tx),
            math.floor(ty),
            math.ceil(sx * (pw - 1) + tx) + 1,
            math.ceil(sy * (ph - 1) + ty) + 1,
        )
        box = (max(footprint[0], 0), max(footprint[1], 0), min(footprint[2], bw), min(footprint[3], bh))
        if box[2] <= box[0] or box[3] <= box[1]:
            raise ValueError("the piece doesn't overlap the base: check the overlap widths")
        warped, inside = _warp(piece_luma, sx, sy, tx, ty, box)
        valid_map, _ = _warp(piece_valid[..., None].astype(np.float64), sx, sy, tx, ty, box)
        warped_valid = inside & (valid_map[..., 0] > 0.999)
        samples = _measure(
            base_luma, base_valid, warped[..., 0], warped_valid, box, _strip_boxes(overlaps, base.shape, footprint), reach
        )
        if len(samples) < _MIN_PATCHES:
            raise ValueError(
                f"only {len(samples)} textured patches along the overlap (at least {_MIN_PATCHES} needed to register); "
                "widen the overlap or register by hand"
            )
        (ax, bx, ay, by), residual, used = _fit(samples)
        sx, sy = sx * (1 + ax), sy * (1 + ay)
        tx, ty = (1 + ax) * tx + bx, (1 + ay) * ty + by
    return Registration(sx, sy, tx, ty, residual, used)


def resample_piece(piece: U8, registration: Registration) -> tuple[U8, tuple[int, int]]:
    """Resample `piece` onto the base's pixel grid, bilinear. Returns the piece and the (x, y) of its top-left pixel in
    the base's coordinates; `Overlap.placed` turns that into the Overlap `match_tone` and `seam_join` take."""
    r = registration
    box = (
        math.floor(r.shift_x),
        math.floor(r.shift_y),
        math.ceil(r.scale_x * (piece.shape[1] - 1) + r.shift_x) + 1,
        math.ceil(r.scale_y * (piece.shape[0] - 1) + r.shift_y) + 1,
    )
    warped, inside = _warp(piece.astype(np.float64), r.scale_x, r.scale_y, r.shift_x, r.shift_y, box)
    present = inside & (warped[..., 3] >= 127.5)
    out = np.floor(np.clip(warped, 0, 255) + 0.5).astype(np.uint8)
    out[..., 3] = np.where(present, 255, 0)
    out[~present, :3] = 0
    return out, (box[0], box[1])


# --- match_tone -------------------------------------------------------------------------------------------------


def _smooth(values: F64, sigma: float) -> F64:
    radius = max(1, int(math.ceil(3 * sigma)))
    kernel = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    return np.convolve(values, kernel, mode="full")[radius : radius + len(values)]


def match_tone(base: U8, piece: U8, overlap: Overlap, sigma: float = 24.0) -> tuple[U8, GainRange]:
    """Scale the piece's brightness to the base's, with one gain per row for an east or west join (per column for north
    or south), taken from the overlap and smoothed along the join with a Gaussian of `sigma` px.

    The piece must already lie on the base's pixel grid (`resample_piece`) as `overlap` says. A gain is the base's
    summed RGB over the row's overlap pixels divided by the piece's, so a bright pixel counts for more than a dark one.
    Rows with no overlap take the nearest row's gain. Alpha is untouched. Returns the toned piece and the lowest and
    highest gain.
    """
    _check(base, piece)
    _check_overlap(base, piece, overlap)
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    side = overlap.side
    nb, np_ = _normal(side, base), _normal(side, piece)
    bh, bw = nb.shape[:2]
    ph, pw = np_.shape[:2]
    ox, oy = bw - overlap.width, overlap.offset
    numerator = np.zeros(ph)
    denominator = np.zeros(ph)
    rows = np.arange(ph)
    base_rows = rows + oy
    usable = (base_rows >= 0) & (base_rows < bh)
    for j in rows[usable]:
        b = nb[base_rows[j], ox:bw]
        p = np_[j, : bw - ox]
        both = (b[:, 3] == 255) & (p[:, 3] == 255)
        numerator[j] = float(b[both, :3].sum())
        denominator[j] = float(p[both, :3].sum())
    num_s, den_s = _smooth(numerator, sigma), _smooth(denominator, sigma)
    known = den_s > 1e-6
    if not known.any():
        raise ValueError("the overlap holds no pixel present in both images")
    gain = np.interp(rows, rows[known], num_s[known] / den_s[known])
    toned = np_.copy()
    scaled = np.floor(np.clip(np_[..., :3].astype(np.float64) * gain[:, None, None], 0, 255) + 0.5).astype(np.uint8)
    toned[..., :3] = np.where((np_[..., 3] == 255)[..., None], scaled, np_[..., :3])
    return np.ascontiguousarray(_unnormal(side, toned)), GainRange(float(gain.min()), float(gain.max()))


# --- seam_join --------------------------------------------------------------------------------------------------


def seam_join(base: U8, piece: U8, overlap: Overlap, blend: int = 6) -> tuple[U8, Seam]:
    """Join `piece` to `base` along the least-difference path through their overlap, blended over `blend` px.

    The piece must lie on the base's grid as `overlap` says. The path runs the length of the join (top to bottom for
    an east or west join, left to right for north or south), moves at most 1 px across per step, and avoids pixels
    where only one image has colour. Ties go to the straighter step, then to the lower coordinate. Base pixels before
    the path and piece pixels after it are blended over `blend` px (0 is a hard cut); where only one image has colour,
    that image shows. The canvas grows to hold both. Returns the joined RGBA image and the Seam.
    """
    _check(base, piece)
    _check_overlap(base, piece, overlap)
    if blend < 0:
        raise ValueError("blend can't be negative")
    side = overlap.side
    nb, np_ = _normal(side, base), _normal(side, piece)
    bh, bw = nb.shape[:2]
    ph, pw = np_.shape[:2]
    ox, oy = bw - overlap.width, overlap.offset
    ymin = min(0, oy)
    height = max(bh, oy + ph) - ymin
    width = max(bw, ox + pw)
    by, py = -ymin, oy - ymin
    cb = np.zeros((height, width, 4), dtype=np.uint8)
    cp = np.zeros((height, width, 4), dtype=np.uint8)
    cb[by : by + bh, :bw] = nb
    cp[py : py + ph, ox : ox + pw] = np_
    vb, vp = cb[..., 3] == 255, cp[..., 3] == 255
    both = vb & vp
    low, high = ox, min(bw, ox + pw)
    margin = max(1, (blend + 1) // 2)
    if low + margin > high - margin:
        margin = 1
    if low + margin > high - margin:
        raise ValueError("the overlap is too narrow to put a seam in")
    diff = np.abs(cb[:, low:high, :3].astype(np.int64) - cp[:, low:high, :3].astype(np.int64)).sum(axis=2)
    cost_pixel = np.where(both[:, low:high], diff, _BIG)
    first, last = low + margin, high - margin
    columns = np.arange(first, last + 1)
    cost = cost_pixel[:, columns - 1 - low] + cost_pixel[:, columns - low]  # twice the mean, kept integer
    count = len(columns)
    accumulated = np.empty((height, count), dtype=np.int64)
    step = np.zeros((height, count), dtype=np.int8)
    accumulated[0] = cost[0]
    infinity = np.iinfo(np.int64).max // 4
    for r in range(1, height):
        previous = accumulated[r - 1]
        candidates = np.stack(
            [
                previous,
                np.concatenate([[infinity], previous[:-1]]),
                np.concatenate([previous[1:], [infinity]]),
            ]
        )
        pick = np.argmin(candidates, axis=0)  # the first minimum: straight, then left, then right
        accumulated[r] = candidates[pick, np.arange(count)] + cost[r]
        step[r] = pick
    path = np.empty(height, dtype=np.int64)
    j = int(np.argmin(accumulated[-1]))
    for r in range(height - 1, -1, -1):
        path[r] = j
        if r > 0:
            j += (0, -1, 1)[int(step[r, j])]
    seam_x = columns[path]

    x = np.arange(width)[None, :]
    if blend > 0:
        weight = np.clip((x - seam_x[:, None] + 0.5) / blend + 0.5, 0.0, 1.0)
    else:
        weight = (x >= seam_x[:, None]).astype(np.float64)
    mixed = cb[..., :3].astype(np.float64) * (1 - weight[..., None]) + cp[..., :3].astype(np.float64) * weight[..., None]
    mixed = np.floor(mixed + 0.5).astype(np.uint8)
    rgb = np.where(both[..., None], mixed, np.where(vb[..., None], cb[..., :3], np.where(vp[..., None], cp[..., :3], 0)))
    joined = np.zeros((height, width, 4), dtype=np.uint8)
    joined[..., :3] = rgb
    joined[..., 3] = np.where(vb | vp, 255, 0)

    rows = np.flatnonzero(both[:, low:high].any(axis=1))
    points = np.array(
        [_natural_point(side, int(seam_x[r]), int(r), width) for r in rows], dtype=np.int64
    ).reshape(-1, 2)
    length = float(np.hypot(np.diff(seam_x[rows]), 1.0).sum() + 1.0) if len(rows) else 0.0
    cut = [float(diff[r, seam_x[r] - low]) for r in rows]
    mean_difference = sum(cut) / len(cut) / 3.0 if cut else 0.0
    corners = [_natural_point(side, cx, cy, width) for cx in (0, bw - 1) for cy in (by, by + bh - 1)]
    piece_corners = [_natural_point(side, cx, cy, width) for cx in (ox, ox + pw - 1) for cy in (py, py + ph - 1)]
    seam = Seam(
        points,
        round(length, 3),
        round(mean_difference, 3),
        (min(c[0] for c in corners), min(c[1] for c in corners)),
        (min(c[0] for c in piece_corners), min(c[1] for c in piece_corners)),
    )
    return np.ascontiguousarray(_unnormal(side, joined)), seam
