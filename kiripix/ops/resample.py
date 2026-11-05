"""Resampling between a painted Source and the target pixel grid (spec §7), and the Grid transform that records it.

A Grid transform cuts the Source into cells: cell k of an axis starts at `offset + floor(k * scale)` and ends where
cell k + 1 starts, so the cells partition the Source with no gaps and no overlaps, and `scale` may be a whole number
(detected pixel art) or a ratio (a mode-filter downscale). Everything here is exact integer or Fraction arithmetic.

Ties are broken explicitly: the colour mode of a cell goes to the smallest packed RGBA value among equally common
colours; a cell's alpha is opaque when at least half its pixels are; a Mask cell is set when at least half its
pixels are; an even-sized cell is sampled at the upper of its two middle pixels; the grid offset goes to the smallest
offset among equally good ones, and the scale to the largest consistent one.
"""

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import numpy as np
import numpy.typing as npt

from kiripix.ops.colour import U8

BoolMask = npt.NDArray[np.bool_]
IntArray = npt.NDArray[np.int64]

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

    def edges_x(self) -> IntArray:
        """The Source columns where each cell starts, plus where the last one ends: `width + 1` values."""
        return _edges(self.scale_x, self.offset_x, self.width)

    def edges_y(self) -> IntArray:
        return _edges(self.scale_y, self.offset_y, self.height)

    def to_json(self) -> dict[str, Any]:
        """A whole scale is a number; a ratio is the string "numerator/denominator"."""
        return {"scale_x": _scale_json(self.scale_x), "scale_y": _scale_json(self.scale_y),
                "offset_x": self.offset_x, "offset_y": self.offset_y, "width": self.width, "height": self.height}

    @staticmethod
    def from_json(data: dict[str, Any]) -> "Grid":
        return Grid(Fraction(data["scale_x"]), Fraction(data["scale_y"]), int(data["offset_x"]),
                    int(data["offset_y"]), int(data["width"]), int(data["height"]))


def _scale_json(scale: Fraction) -> int | str:
    return scale.numerator if scale.denominator == 1 else f"{scale.numerator}/{scale.denominator}"


def _edges(scale: Fraction, offset: int, count: int) -> IntArray:
    k = np.arange(count + 1, dtype=np.int64)
    return offset + (k * scale.numerator) // scale.denominator


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
    return min(max(tx, 0), grid.width - 1), min(max(ty, 0), grid.height - 1)


def target_centre(grid: Grid, tx: int, ty: int) -> tuple[float, float]:
    """The Source point at the centre of target pixel (tx, ty): where a click on that pixel lands in the Source."""
    edges_x, edges_y = grid.edges_x(), grid.edges_y()
    return float(edges_x[tx] + edges_x[tx + 1]) / 2, float(edges_y[ty] + edges_y[ty + 1]) / 2


# images


def sample_nearest(image: U8, grid: Grid) -> U8:
    """One pixel per cell: the one at the cell's centre. Alpha is binarised: opaque from 128 up, else cleared."""
    _check_size(image, grid)
    edges_x, edges_y = grid.edges_x(), grid.edges_y()
    columns, rows = (edges_x[:-1] + edges_x[1:]) // 2, (edges_y[:-1] + edges_y[1:]) // 2
    sampled = image[rows[:, None], columns[None, :]]
    return _binarise(sampled)


def downscale_mode(image: U8, grid: Grid) -> U8:
    """One pixel per cell: the most common colour among the cell's opaque pixels. A cell is opaque when at least half
    its pixels are (alpha from 128 up); ties between colours go to the smallest packed RGBA value."""
    _check_size(image, grid)
    index_x, index_y = _cell_index(grid.edges_x(), image.shape[1]), _cell_index(grid.edges_y(), image.shape[0])
    cell = index_y[:, None] * grid.width + index_x[None, :]
    inside = (index_y[:, None] >= 0) & (index_x[None, :] >= 0)
    opaque = image[..., 3] >= OPAQUE_FROM
    cells = grid.width * grid.height
    votes = np.bincount(cell[inside & opaque], minlength=cells)
    sizes = np.bincount(cell[inside], minlength=cells)
    packed = _pack(_binarise(image))
    colours, colour_of = np.unique(packed[inside & opaque], return_inverse=True)
    result = np.zeros((cells, 4), dtype=np.uint8)
    if len(colours):
        key = cell[inside & opaque] * len(colours) + colour_of
        keys, counts = np.unique(key, return_counts=True)  # keys ascend: cell, then colour (packed order)
        owner = keys // len(colours)
        order = np.lexsort((keys, -counts, owner))  # per cell: most common first, then the smallest colour
        first = np.ones(len(order), dtype=bool)
        first[1:] = owner[order][1:] != owner[order][:-1]
        winners = order[first]
        result[owner[winners]] = _unpack(colours[keys[winners] % len(colours)])
    result[votes * 2 < sizes] = 0
    shaped: U8 = result.reshape(grid.height, grid.width, 4)
    return shaped


def alpha_by_vote(fitted: U8, source: U8, grid: Grid) -> U8:
    """`fitted` (one pixel per cell, as `sample_nearest` gives) with its alpha decided by majority vote of the cell.

    A cell is opaque when at least half its Source pixels are (alpha from 128 up), as in `downscale_mode`; the result's
    alpha is 0 or 255. Where the vote is opaque but the sampled pixel is clear, the colour is the cell's most common
    one, as `downscale_mode` gives; where the vote is clear, the pixel is (0, 0, 0, 0).
    """
    _check_size(source, grid)
    if fitted.shape != (grid.height, grid.width, 4):
        raise ValueError(f"the fitted image is {fitted.shape[1]}x{fitted.shape[0]}, the grid {grid.width}x{grid.height}")
    opaque = mask_to_target(source[..., 3] >= OPAQUE_FROM, grid)
    result = _binarise(fitted)
    refill = opaque & (result[..., 3] == 0)
    if refill.any():
        result[refill] = downscale_mode(source, grid)[refill]
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
