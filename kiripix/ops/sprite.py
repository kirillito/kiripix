"""The sprite Kind's Ops (spec §7, ticket 0177): slice a sheet, find the feet, normals from a height."""

from __future__ import annotations

import math
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
    F64 = npt.NDArray[np.float64]
else:
    U8 = Any  # the array types are for the type checker; numpy loads late
    F64 = Any

_DIAGONAL = math.sqrt(2.0)
_FAR = 1e9


def slice_grid(sheet: U8, columns: int, rows: int) -> list[list[U8]]:
    """Cut an RGBA `sheet` into `rows` x `columns` equal cells; the result is a list of rows of cells, row by row.

    A sheet whose width isn't a multiple of `columns`, or whose height isn't a multiple of `rows`, raises a
    ValueError that gives both the sheet's size and the counts. Each cell is a copy.
    """
    if columns < 1 or rows < 1:
        raise ValueError("columns and rows must be at least 1")
    height, width = sheet.shape[:2]
    if width % columns or height % rows:
        raise ValueError(
            f"the sheet is {width} x {height} px, which {columns} columns x {rows} rows don't divide into equal cells"
        )
    cw, ch = width // columns, height // rows
    return [[sheet[r * ch : (r + 1) * ch, c * cw : (c + 1) * cw].copy() for c in range(columns)] for r in range(rows)]


def feet_point(alpha: U8) -> tuple[int, int] | None:
    """The figure's feet in a binary `alpha` (H, W): (x, y), or None for an empty frame.

    `y` is the lowest opaque row. `x` is the mean column of the opaque pixels in the lowest two rows (that row and the
    one above it), rounded half down. Specks are not this Op's job: `fit` runs after the alpha vote, which leaves
    none. A shadow or a tail at the lowest row moves the point; the `pivot` Decision is the cure.
    """
    opaque = alpha > 0
    rows = np.flatnonzero(opaque.any(axis=1))
    if rows.size == 0:
        return None
    y = int(rows[-1])
    xs = np.nonzero(opaque[max(y - 1, 0) : y + 1])[1]
    n = int(xs.size)
    total = int(xs.sum())
    # round half down of total / n, in integers: ceil((2 * total - n) / (2 * n))
    x = -((n - 2 * total) // (2 * n))
    return int(x), y


def _chamfer(inside: Any) -> F64:
    """Distance in px from each inside pixel to the nearest outside pixel (1 and sqrt 2 steps); outside the image counts
    as outside. Two row-wise passes: a row's left-to-right (then right-to-left) chain is a running minimum."""
    h, w = inside.shape
    d = np.pad(np.where(inside, _FAR, 0.0), 1, constant_values=0.0)
    x = np.arange(w + 2, dtype=np.float64)
    for y in range(1, h + 1):
        up = d[y - 1]
        cand = np.minimum(up + 1.0, np.minimum(np.roll(up, 1), np.roll(up, -1)) + _DIAGONAL)
        row = np.minimum(d[y], cand)
        row = np.minimum.accumulate(row - x) + x
        d[y] = np.where(d[y] == 0.0, 0.0, row)
    for y in range(h, 0, -1):
        down = d[y + 1]
        cand = np.minimum(down + 1.0, np.minimum(np.roll(down, 1), np.roll(down, -1)) + _DIAGONAL)
        row = np.minimum(d[y], cand)
        row = (np.minimum.accumulate((row + x)[::-1])[::-1]) - x
        d[y] = np.where(d[y] == 0.0, 0.0, row)
    return d[1:-1, 1:-1]


def height_from_alpha(alpha: U8, saturate: float = 4.0) -> F64:
    """A rounded "pillow" height (H, W) from a binary `alpha`: 0 outside, rising to 1 at `saturate` px in from the edge.

    The height is the square root of the chamfer distance to the nearest transparent pixel (steps of 1 and sqrt 2,
    outside the image counting as transparent), divided by `saturate` and clamped to 0..1. Any alpha above 0 is inside.
    """
    if saturate <= 0:
        raise ValueError("saturate must be above 0")
    distance = _chamfer(alpha > 0)
    return np.sqrt(np.clip(distance / saturate, 0.0, 1.0))


def normals_from_height(height: F64, alpha: U8, strength: float = 1.6) -> U8:
    """Tangent-space normals (H, W, 4) uint8 RGBA from a `height` (H, W) by a Sobel filter.

    normal = normalise(-dx * strength, dy * strength, 1), with +Y up in the image (the OpenGL convention of Godot's
    `CanvasTexture`; image rows run down, so dy is the row difference as it is), each axis encoded (v + 1) / 2 * 255.
    Outside the image the height is 0. Alpha 0 pixels are (0, 0, 0, 0), the others have alpha 255. The result takes
    `quantise_normals` and `encode_normals` as they are.
    """
    if height.shape != alpha.shape:
        raise ValueError("height and alpha must have the same shape")
    hp = np.pad(height.astype(np.float64), 1, mode="constant", constant_values=0.0)
    gx = (hp[:-2, 2:] + 2 * hp[1:-1, 2:] + hp[2:, 2:]) - (hp[:-2, :-2] + 2 * hp[1:-1, :-2] + hp[2:, :-2])
    gy = (hp[2:, :-2] + 2 * hp[2:, 1:-1] + hp[2:, 2:]) - (hp[:-2, :-2] + 2 * hp[:-2, 1:-1] + hp[:-2, 2:])
    nx = -gx * strength
    ny = gy * strength
    nz = np.ones_like(nx)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    unit = np.stack([nx / length, ny / length, nz / length], axis=-1)
    encoded = np.floor((unit * 0.5 + 0.5) * 255.0 + 0.5).astype(np.uint8)
    opaque = alpha > 0
    out = np.zeros((*alpha.shape, 4), dtype=np.uint8)
    out[..., :3] = np.where(opaque[..., None], encoded, 0)
    out[..., 3] = np.where(opaque, 255, 0)
    return out
