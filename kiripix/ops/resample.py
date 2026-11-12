"""Resampling between a painted Source and the target pixel grid (spec §7), and the Grid transform that records it.

A Grid transform cuts the Source into cells: cell k of an axis starts at `offset + floor(k * scale)` and ends where
cell k + 1 starts, so the cells partition the Source with no gaps and no overlaps, and `scale` may be a whole number
(detected pixel art) or a ratio (a downscale). Everything here is exact integer or Fraction arithmetic.

Ties are broken explicitly: a thin line that straddles two cells goes to the cell with the larger dark share, then to
the right or lower one; a cell's alpha is opaque when at least half its pixels are; a Mask cell is set when at least half its
pixels are; an even-sized cell is sampled at the upper of its two middle pixels; the grid offset goes to the smallest
offset among equally good ones, and the scale to the largest consistent one.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
if TYPE_CHECKING:
    import numpy.typing as npt
else:
    npt = lazy_module("numpy.typing")

from kiripix.ops.colour import U8, srgb_to_oklab

if TYPE_CHECKING:
    BoolMask = npt.NDArray[np.bool_]
else:
    BoolMask = Any  # the array types are for the type checker; numpy loads late
if TYPE_CHECKING:
    IntArray = npt.NDArray[np.int64]
else:
    IntArray = Any  # the array types are for the type checker; numpy loads late

OPAQUE_FROM = 128  # an alpha at or above this counts as opaque when alpha is binarised


@dataclass(frozen=True)
class Grid:
    """The recorded Source-to-target transform: per-axis scale (Source pixels per target pixel), the Source offset of
    the first cell, and the target size in cells."""

    scale_x: Fraction
    scale_y: Fraction
    offset_x: int
    offset_y: int
    width: int
    height: int
    pad_right: int = 0  # target columns at the right with no Source pixels (transparent), counted in `width`
    pad_bottom: int = 0  # the same at the bottom, counted in `height`

    @property
    def cells_x(self) -> int:
        """The columns that have Source pixels: `width` less the padding."""
        return self.width - self.pad_right

    @property
    def cells_y(self) -> int:
        return self.height - self.pad_bottom

    def padded_to(self, width: int, height: int) -> "Grid":
        """The same grid padded on the right and bottom up to width x height cells (never smaller than it is now)."""
        if width < self.width or height < self.height:
            raise ValueError(f"can't pad a {self.width}x{self.height} grid down to {width}x{height}")
        return Grid(self.scale_x, self.scale_y, self.offset_x, self.offset_y, width, height,
                    self.pad_right + width - self.width, self.pad_bottom + height - self.height)

    @staticmethod
    def uniform(scale: int, offset_x: int, offset_y: int, source_width: int, source_height: int) -> "Grid":
        """A whole-number grid over a Source: as many whole cells as fit after the offsets."""
        if scale < 1:
            raise ValueError(f"the scale must be at least 1, got {scale}")
        if offset_x < 0 or offset_y < 0:
            raise ValueError("the offsets can't be negative")
        width, height = (source_width - offset_x) // scale, (source_height - offset_y) // scale
        if width < 1 or height < 1:
            raise ValueError(f"a {scale}x grid at offset {offset_x},{offset_y} holds no whole cell of a "
                             f"{source_width}x{source_height} Source")
        return Grid(Fraction(scale), Fraction(scale), offset_x, offset_y, width, height)

    @staticmethod
    def to_size(source_width: int, source_height: int, width: int, height: int) -> "Grid":
        """The grid that splits a Source into exactly width x height cells, with no offset."""
        if width < 1 or height < 1 or width > source_width or height > source_height:
            raise ValueError(f"can't downscale {source_width}x{source_height} to {width}x{height}")
        return Grid(Fraction(source_width, width), Fraction(source_height, height), 0, 0, width, height)

    @staticmethod
    def cover(source_width: int, source_height: int, width: int, height: int, offset_x: int = 0,
              offset_y: int = 0) -> "Grid":
        """The grid that fills width x height cells with one scale on both axes: the largest that still fills them,
        `min(source_width / width, source_height / height)`. The Source left over on the other axis is cropped; the
        offsets place the crop, in Source pixels from the top left. An offset that leaves less than the grid's size
        raises a ValueError that names the largest allowed."""
        if width < 1 or height < 1 or width > source_width or height > source_height:
            raise ValueError(f"can't downscale {source_width}x{source_height} to {width}x{height}")
        scale = min(Fraction(source_width, width), Fraction(source_height, height))
        grid = Grid(scale, scale, 0, 0, width, height)
        largest_x = source_width - int(grid.edges_x()[-1])
        largest_y = source_height - int(grid.edges_y()[-1])
        for axis, offset, largest in (("offset_x", offset_x, largest_x), ("offset_y", offset_y, largest_y)):
            if offset < 0 or offset > largest:
                raise ValueError(f"{axis} {offset} leaves less than the {width}x{height} the brief asks for: "
                                 f"the largest {axis} is {largest}")
        return Grid(scale, scale, offset_x, offset_y, width, height)

    def edges_x(self) -> IntArray:
        """The Source columns where each cell starts, plus where the last one ends: `width + 1` values. A padded cell
        has no Source pixels: it starts and ends where the last real cell ends."""
        return _edges(self.scale_x, self.offset_x, self.cells_x, self.pad_right)

    def edges_y(self) -> IntArray:
        return _edges(self.scale_y, self.offset_y, self.cells_y, self.pad_bottom)

    def to_json(self) -> dict[str, Any]:
        """A whole scale is a number; a ratio is the string "numerator/denominator"."""
        return {"scale_x": _scale_json(self.scale_x), "scale_y": _scale_json(self.scale_y),
                "offset_x": self.offset_x, "offset_y": self.offset_y, "width": self.width, "height": self.height,
                "pad_right": self.pad_right, "pad_bottom": self.pad_bottom}

    @staticmethod
    def from_json(data: dict[str, Any]) -> "Grid":
        return Grid(Fraction(data["scale_x"]), Fraction(data["scale_y"]), int(data["offset_x"]),
                    int(data["offset_y"]), int(data["width"]), int(data["height"]),
                    int(data.get("pad_right", 0)), int(data.get("pad_bottom", 0)))


def _scale_json(scale: Fraction) -> int | str:
    return scale.numerator if scale.denominator == 1 else f"{scale.numerator}/{scale.denominator}"


def _edges(scale: Fraction, offset: int, count: int, pad: int = 0) -> IntArray:
    k = np.arange(count + 1, dtype=np.int64)
    edges: IntArray = offset + (k * scale.numerator) // scale.denominator
    return np.concatenate([edges, np.full(pad, edges[-1], dtype=np.int64)]) if pad else edges


def _cell_index(edges: IntArray, length: int) -> IntArray:
    """For each Source pixel along an axis, its cell, or -1 outside the grid."""
    index = np.searchsorted(edges, np.arange(length), side="right") - 1
    index[(np.arange(length) < edges[0]) | (np.arange(length) >= edges[-1])] = -1
    result: IntArray = index.astype(np.int64)
    return result


# detection


def detect_grid(image: U8, max_scale: int = 64, tolerance: float = 0.02) -> Grid:
    """The pixel grid of upscaled pixel art: the largest whole scale (2 up to `max_scale`) and the offsets at which
    the colour changes of `image` sit on cell boundaries, with at most `tolerance` of them off the boundaries.

    Each axis gets its own offset (the one explaining most changes; ties to the smallest). An image with no grid, or
    with no colour changes at all, returns the 1x grid: every pixel is a cell.
    """
    height, width = image.shape[:2]
    changes_x = (image[:, 1:] != image[:, :-1]).any(axis=2).sum(axis=0)  # between columns c - 1 and c, at c = i + 1
    changes_y = (image[1:] != image[:-1]).any(axis=2).sum(axis=1)
    total = int(changes_x.sum() + changes_y.sum())
    if total > 0:
        columns, rows = np.arange(1, width), np.arange(1, height)
        for scale in range(min(max_scale, width, height), 1, -1):
            by_x = np.bincount(columns % scale, weights=changes_x, minlength=scale)
            by_y = np.bincount(rows % scale, weights=changes_y, minlength=scale)
            offset_x, offset_y = int(np.argmax(by_x)), int(np.argmax(by_y))  # argmax: the first, so the smallest
            off_grid = total - by_x[offset_x] - by_y[offset_y]
            if off_grid <= tolerance * total:
                try:
                    return Grid.uniform(scale, offset_x, offset_y, width, height)
                except ValueError:
                    continue
    return Grid.uniform(1, 0, 0, width, height)


# points


def point_to_target(grid: Grid, x: float, y: float) -> tuple[int, int]:
    """The target pixel a Source point falls in, clamped to the grid (a point outside it snaps to the nearest cell)."""
    tx = int(np.searchsorted(grid.edges_x(), x, side="right")) - 1  # the cells' own edges, so cells and points agree
    ty = int(np.searchsorted(grid.edges_y(), y, side="right")) - 1
    return min(max(tx, 0), grid.cells_x - 1), min(max(ty, 0), grid.cells_y - 1)


def target_centre(grid: Grid, tx: int, ty: int) -> tuple[float, float]:
    """The Source point at the centre of target pixel (tx, ty): where a click on that pixel lands in the Source. A padded
    cell has no Source pixels, so it raises a ValueError."""
    if tx >= grid.cells_x or ty >= grid.cells_y:
        raise ValueError(f"the pixel ({tx}, {ty}) is in the padded strip, which has no Source pixels")
    edges_x, edges_y = grid.edges_x(), grid.edges_y()
    return float(edges_x[tx] + edges_x[tx + 1]) / 2, float(edges_y[ty] + edges_y[ty + 1]) / 2


# images


def sample_nearest(image: U8, grid: Grid) -> U8:
    """One pixel per cell: the one at the cell's centre. Alpha is binarised: opaque from 128 up, else cleared."""
    _check_size(image, grid)
    edges_x, edges_y = grid.edges_x(), grid.edges_y()
    columns, rows = (edges_x[:-1] + edges_x[1:]) // 2, (edges_y[:-1] + edges_y[1:]) // 2
    sampled = image[np.minimum(rows, image.shape[0] - 1)[:, None], np.minimum(columns, image.shape[1] - 1)[None, :]]
    result = _binarise(sampled)
    result[grid.cells_y:, :] = 0  # padding is transparent: alpha 0, RGB 0
    result[:, grid.cells_x:] = 0
    return result


SEPARATION = 0.05  # OKLab lightness gap between a cell's dark and light groups, from which it holds an edge or a line
DARK_SHARE = 0.4  # the share of a cell's pixels the dark group needs to win the cell


def downscale(image: U8, grid: Grid) -> U8:
    """One pixel per cell, keeping the Source's thin dark lines continuous and its flat areas even.

    A cell's opaque pixels are split at the cell's mean OKLab lightness into a dark and a light group. When the groups
    differ clearly (`SEPARATION`), the cell holds a line or an edge: it takes the dark group's mean colour if the dark
    group covers at least `DARK_SHARE` of the cell, else the light group's. Otherwise it takes the plain mean colour.
    A line two Source pixels wide that straddles two cells would be dark in both; only the cell with the larger dark
    share keeps it (ties go to the right or lower cell), so a line stays one pixel wide. A line runs along the axis where its run of
    cells is longer; where the runs are equal, as at a crossing, nothing is thinned. A cell is opaque when at least
    half its pixels are (alpha from 128 up); a clear cell is (0, 0, 0, 0).
    """
    _check_size(image, grid)
    index_x, index_y = _cell_index(grid.edges_x(), image.shape[1]), _cell_index(grid.edges_y(), image.shape[0])
    cell = index_y[:, None] * grid.width + index_x[None, :]
    inside = (index_y[:, None] >= 0) & (index_x[None, :] >= 0)
    opaque = image[..., 3] >= OPAQUE_FROM
    cells = grid.width * grid.height
    votes = np.bincount(cell[inside & opaque], minlength=cells)
    sizes = np.bincount(cell[inside], minlength=cells)
    chosen = (inside & opaque)
    where = cell[chosen]
    rgb = image[..., :3][chosen]
    lightness = srgb_to_oklab(rgb)[:, 0]

    def sums(weight: npt.NDArray[np.float64] | None = None) -> tuple[npt.NDArray[np.float64], ...]:
        w = np.ones(len(where)) if weight is None else weight
        return (np.bincount(where, weights=w, minlength=cells),
                np.bincount(where, weights=w * lightness, minlength=cells),
                *(np.bincount(where, weights=w * rgb[:, c], minlength=cells) for c in range(3)))

    count, light_sum, *rgb_sum = sums()
    mean_light = light_sum / np.maximum(count, 1)
    dark = (lightness < mean_light[where]).astype(np.float64)
    dark_count, dark_light, *dark_rgb = sums(dark)
    bright_count = count - dark_count
    gap = (light_sum - dark_light) / np.maximum(bright_count, 1) - dark_light / np.maximum(dark_count, 1)
    holds_edge = (gap > SEPARATION) & (dark_count > 0) & (bright_count > 0)
    share = np.where(count > 0, dark_count / np.maximum(count, 1), 0.0)
    is_line = (holds_edge & (share >= DARK_SHARE)).reshape(grid.height, grid.width)
    line_share = np.where(is_line, share.reshape(grid.height, grid.width), 0.0)
    padded = np.pad(line_share, 1)
    across_x = (line_share >= padded[1:-1, :-2]) & (line_share > padded[1:-1, 2:])  # wins against its x neighbours
    across_y = (line_share >= padded[:-2, 1:-1]) & (line_share > padded[2:, 1:-1])
    along_y, along_x = _run_lengths(is_line.T).T, _run_lengths(is_line)
    # A line runs along the axis where its run of cells is longer, and is thinned across the other; where the runs are
    # equal (a crossing, a lone cell) every cell is kept.
    is_line &= np.where(along_y > along_x, across_x, np.where(along_x > along_y, across_y, True))
    line_cell = is_line.reshape(-1)
    result = np.zeros((cells, 4), dtype=np.uint8)
    for c in range(3):
        mean = rgb_sum[c] / np.maximum(count, 1)
        dark_mean = dark_rgb[c] / np.maximum(dark_count, 1)
        bright_mean = (rgb_sum[c] - dark_rgb[c]) / np.maximum(bright_count, 1)
        value = np.where(holds_edge, np.where(line_cell, dark_mean, bright_mean), mean)
        result[:, c] = np.clip(np.rint(value), 0, 255).astype(np.uint8)
    result[:, 3] = 255
    result[votes * 2 < sizes] = 0
    result[count == 0] = 0
    shaped: U8 = result.reshape(grid.height, grid.width, 4)
    return shaped


def _run_lengths(mask: BoolMask) -> IntArray:
    """For each set cell, the length of the run of set cells along its row it belongs to; 0 for a clear cell."""
    starts = mask & ~np.pad(mask, ((0, 0), (1, 0)))[:, :-1]
    label = np.cumsum(starts.ravel()).reshape(mask.shape)
    label[~mask] = 0
    lengths = np.bincount(label.ravel())
    lengths[0] = 0
    result: IntArray = lengths[label].astype(np.int64)
    return result


def alpha_by_vote(fitted: U8, source: U8, grid: Grid) -> U8:
    """`fitted` (one pixel per cell, as `sample_nearest` gives) with its alpha decided by majority vote of the cell.

    A cell is opaque when at least half its Source pixels are (alpha from 128 up), as in `downscale`; the result's
    alpha is 0 or 255. Where the vote is opaque but the sampled pixel is clear, the colour is the cell's most common
    one, as `downscale` gives; where the vote is clear, the pixel is (0, 0, 0, 0).
    """
    _check_size(source, grid)
    if fitted.shape != (grid.height, grid.width, 4):
        raise ValueError(f"the fitted image is {fitted.shape[1]}x{fitted.shape[0]}, the grid {grid.width}x{grid.height}")
    opaque = mask_to_target(source[..., 3] >= OPAQUE_FROM, grid)
    result = _binarise(fitted)
    refill = opaque & (result[..., 3] == 0)
    if refill.any():
        result[refill] = downscale(source, grid)[refill]
    result[~opaque] = 0
    return result


def upscale(image: npt.NDArray[Any], factor: int) -> npt.NDArray[Any]:
    """Each pixel repeated `factor` times along both axes: nearest neighbour, whole factors only."""
    if factor < 1:
        raise ValueError(f"the factor must be a whole number of at least 1, got {factor}")
    return np.repeat(np.repeat(image, factor, axis=0), factor, axis=1)


# masks


def mask_to_target(mask: BoolMask, grid: Grid) -> BoolMask:
    """A Source-resolution Mask as a target-resolution one: a cell is set when at least half its pixels are."""
    if mask.dtype != np.bool_ or mask.ndim != 2:
        raise ValueError("a Mask is a 2-D boolean array")
    index_x, index_y = _cell_index(grid.edges_x(), mask.shape[1]), _cell_index(grid.edges_y(), mask.shape[0])
    rows, columns = np.nonzero(mask)  # a room replays this for every click, so it never touches the clear pixels
    cell_x, cell_y = index_x[columns], index_y[rows]
    inside = (cell_x >= 0) & (cell_y >= 0)
    set_pixels = np.bincount(cell_y[inside] * grid.width + cell_x[inside],
                             minlength=grid.width * grid.height).reshape(grid.height, grid.width)
    sizes = np.outer(np.bincount(index_y[index_y >= 0], minlength=grid.height),
                     np.bincount(index_x[index_x >= 0], minlength=grid.width))
    result: BoolMask = (set_pixels * 2 >= sizes) & (sizes > 0)
    return result


def mask_to_source(mask: BoolMask, grid: Grid, source_width: int, source_height: int) -> BoolMask:
    """A target-resolution Mask at Source resolution: each cell's pixels take its value; outside the grid is clear."""
    if mask.shape != (grid.height, grid.width):
        raise ValueError(f"the Mask is {mask.shape[1]}x{mask.shape[0]}, the grid {grid.width}x{grid.height}")
    index_x, index_y = _cell_index(grid.edges_x(), source_width), _cell_index(grid.edges_y(), source_height)
    inside = (index_y[:, None] >= 0) & (index_x[None, :] >= 0)
    result: BoolMask = mask[np.maximum(index_y, 0)[:, None], np.maximum(index_x, 0)[None, :]] & inside
    return result


# helpers


def _check_size(image: U8, grid: Grid) -> None:
    height, width = image.shape[:2]
    edges_x, edges_y = grid.edges_x(), grid.edges_y()
    if edges_x[-1] > width or edges_y[-1] > height:
        raise ValueError(f"the grid reaches {edges_x[-1]}x{edges_y[-1]}, past the {width}x{height} image")


def _binarise(image: U8) -> U8:
    """Opaque pixels at alpha 255, the rest fully cleared (RGB zeroed, so equal transparent pixels are equal)."""
    result = image.copy()
    clear = result[..., 3] < OPAQUE_FROM
    result[clear] = 0
    result[~clear, 3] = 255
    return result


def _pack(image: U8) -> npt.NDArray[np.uint32]:
    wide = image.astype(np.uint32)
    packed: npt.NDArray[np.uint32] = (
        (wide[..., 0] << 24) | (wide[..., 1] << 16) | (wide[..., 2] << 8) | wide[..., 3]  # type: ignore[assignment]
    )
    return packed


def _unpack(packed: npt.NDArray[np.uint32]) -> U8:
    shifts = np.array([24, 16, 8, 0], dtype=np.uint32)
    result: U8 = ((packed[..., None] >> shifts) & 255).astype(np.uint8)
    return result
