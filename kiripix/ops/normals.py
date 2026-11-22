"""A room's normal map from a depth image (ticket 0341, ADR 0014), as pure Ops: a depth to the target grid, a height in target
pixels, the masked fill, Sobel to a tilt, the quantise to levels, the Layers' front-most normals, and `lit`, the Plate lit
from a corner. The encoding is Godot's: red is X (+X right), green is Y (+Y up in the image), blue is Z (toward the viewer),
each as (v + 1) / 2 * 255, so a flat normal is (128, 128, 255). A normal is never palette-mapped. Arrays in, arrays out."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt
else:
    np = lazy_module("numpy")
    npt = lazy_module("numpy.typing")

MAX_TILT = 0.75  # the largest tilt component kept (about 49 degrees), the trial's
FLAT = (128, 128, 255)  # a normal facing the viewer, as encoded
_FILL_RADII = (1, 2, 4, 8, 16, 32, 64, 128, 400)
_LIGHT = (-0.5, 0.5, 0.7)  # `lit`: from the upper left, in front of the room; +Y is up in the image
_AMBIENT = 0.35


def cell_means(values: npt.NDArray[np.floating], edges_x: npt.NDArray[np.integer], edges_y: npt.NDArray[np.integer]
               ) -> npt.NDArray[np.float64]:
    """The mean of `values` over each Grid cell: cell (i, j) covers rows `edges_y[j]` to `edges_y[j + 1]` and columns
    `edges_x[i]` to `edges_x[i + 1]` (the Grid's `edges_x()` and `edges_y()`). A padded cell, which has no pixels, takes the
    last cell that has some, so the padding is flat. The sums come from one table in float64, so they are exact in order."""
    if values.ndim != 2:
        raise ValueError("cell_means needs a 2D array")
    table = np.zeros((values.shape[0] + 1, values.shape[1] + 1), dtype=np.float64)
    table[1:, 1:] = values.astype(np.float64).cumsum(axis=0).cumsum(axis=1)
    x0, x1, y0, y1 = edges_x[:-1], edges_x[1:], edges_y[:-1], edges_y[1:]
    sums = table[y1][:, x1] - table[y0][:, x1] - table[y1][:, x0] + table[y0][:, x0]
    area = (y1 - y0)[:, None] * (x1 - x0)[None, :]
    real_x, real_y = int((x1 > x0).sum()), int((y1 > y0).sum())
    if real_x == 0 or real_y == 0:
        raise ValueError("the Grid has no cell with pixels")
    means = np.where(area > 0, sums / np.maximum(area, 1), 0.0)
    columns = np.minimum(np.arange(len(x0)), real_x - 1)
    rows = np.minimum(np.arange(len(y0)), real_y - 1)
    result: npt.NDArray[np.float64] = means[rows][:, columns]
    return result


def heights(depth: npt.NDArray[np.floating], strength: float) -> npt.NDArray[np.float32]:
    """A relative depth (nearer is bigger) as a height in target pixels: the 1st to the 99th percentile spans 0 to
    `strength`, and the rest is clipped. A flat depth gives a flat height."""
    low, high = np.percentile(depth, [1, 99])
    if not high > low:
        return np.zeros(depth.shape, dtype=np.float32)
    scaled = np.clip((depth - low) / (high - low), 0, 1) * strength
    return scaled.astype(np.float32)


def _box_mean(values: npt.NDArray[np.float64], radius: int) -> npt.NDArray[np.float64]:
    padded = np.pad(values, radius, mode="edge")
    table = np.pad(padded.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    size = 2 * radius + 1
    result: npt.NDArray[np.float64] = (table[size:, size:] - table[:-size, size:] - table[size:, :-size]
                                       + table[:-size, :-size]) / (size * size)
    return result


def masked_fill(values: npt.NDArray[np.floating], inside: npt.NDArray[np.bool_]) -> npt.NDArray[np.float32]:
    """`values` with every pixel outside `inside` replaced by the mean of nearby pixels inside it (the window grows
    1, 2, 4 ... px until it holds one), so a Sobel filter finds no step at the edge of `inside`. Pixels inside are
    unchanged. With nothing inside, `values` as they are."""
    if values.shape != inside.shape:
        raise ValueError("values and the mask must be the same size")
    out = np.where(inside, values, 0.0).astype(np.float64)
    known = inside.astype(np.float64)
    have = inside.copy()
    if not have.any():
        return values.astype(np.float32)
    for radius in _FILL_RADII:
        if have.all():
            break
        weight = _box_mean(known, radius)
        reached = (weight > 1e-4) & ~have
        out[reached] = _box_mean(out * known, radius)[reached] / weight[reached]
        known[reached] = 1.0
        have |= reached
    return np.where(have, out, values).astype(np.float32)


def _sobel(height: npt.NDArray[np.float32]) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.float32]]:
    p = np.pad(height, 1, mode="edge")
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:] - p[:-2, :-2] - 2 * p[1:-1, :-2] - p[2:, :-2]) / np.float32(8)
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:] - p[:-2, :-2] - 2 * p[:-2, 1:-1] - p[:-2, 2:]) / np.float32(8)
    return gx.astype(np.float32), gy.astype(np.float32)  # gy points down the image


def _quantise(g: npt.NDArray[np.float32], deadzone: float, levels: int) -> npt.NDArray[np.float32]:
    """A tilt component in -1 to 1: flat within the deadzone, else `levels` steps per side up to `MAX_TILT`."""
    a = np.abs(g)
    t = np.clip((a - deadzone) / (MAX_TILT - deadzone), 0, 1)
    q = np.ceil(t * levels - 1e-6) / levels
    q = np.where(a <= deadzone, 0.0, np.maximum(q, 1.0 / levels))
    return (np.sign(g) * q * MAX_TILT).astype(np.float32)


def tilts(height: npt.NDArray[np.float32], deadzone: float, levels: int) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.float32]]:
    """The quantised tilt (x, y) of a height image: the slope from Sobel, the deadzone stays flat, then `levels` steps per side.
    A height that rises to the right tilts the normal left (-x); one that rises down the image tilts it up (+y, as Godot's
    Y is up while the image's is down)."""
    if not 0 <= deadzone < MAX_TILT:
        raise ValueError(f"the deadzone is from 0 up to {MAX_TILT}")
    if levels < 1:
        raise ValueError("levels is at least 1")
    gx, gy = _sobel(height)
    return _quantise(-gx, deadzone, levels), _quantise(gy, deadzone, levels)


def encode(nx: npt.NDArray[np.float32], ny: npt.NDArray[np.float32]) -> npt.NDArray[np.uint8]:
    """Tilts as an (H, W, 4) normal map in Godot's encoding, alpha 255: Z is what makes the vector one long."""
    nz = np.sqrt(np.clip(1 - nx.astype(np.float64) ** 2 - ny.astype(np.float64) ** 2, 0, 1))
    rgb = np.stack([nx, ny, nz], axis=-1) * 0.5 + 0.5
    out = np.full(nx.shape + (4,), 255, dtype=np.uint8)
    out[..., :3] = np.rint(rgb * 255).astype(np.uint8)
    return out


def front_normals(height: npt.NDArray[np.float32], alphas: Sequence[npt.NDArray[np.bool_]], deadzone: float, levels: int,
                  between: Callable[[], None] = lambda: None) -> npt.NDArray[np.uint8]:
    """The room's normal map as seen: the whole room's `height` gives the Plate's normals, and each Layer, in order (a later
    one in front), takes the normals of the height refilled outside its alpha (`masked_fill`), over the pixels of its alpha.
    `alphas` are the Layers' (H, W) boolean alphas. `between` is called before each Layer (a cancel check)."""
    nx, ny = tilts(height, deadzone, levels)
    for alpha in alphas:
        between()
        if not alpha.any():
            continue
        lx, ly = tilts(masked_fill(height, alpha), deadzone, levels)
        nx, ny = np.where(alpha, lx, nx), np.where(alpha, ly, ny)
    return encode(nx, ny)


def flatten(normal: npt.NDArray[np.uint8], where: npt.NDArray[np.bool_]) -> npt.NDArray[np.uint8]:
    """`normal` with the normals at `where` facing the viewer, alpha 255."""
    out = normal.copy()
    out[where] = (*FLAT, 255)
    return out


def tilt_of(normal: npt.NDArray[np.uint8]) -> npt.NDArray[np.float32]:
    """How far each normal leans from the viewer, as the length of its (x, y): 0 is flat, 1 is edge on."""
    x = normal[..., 0].astype(np.float32) / 255 * 2 - 1
    y = normal[..., 1].astype(np.float32) / 255 * 2 - 1
    return np.hypot(x - (FLAT[0] / 255 * 2 - 1), y - (FLAT[1] / 255 * 2 - 1)).astype(np.float32)


def lit(image: npt.NDArray[np.uint8], normal: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
    """`image` lit by a fixed light from its upper left over `normal`, to judge a normal map without Godot. A flat pixel
    keeps its colour; one facing the light is brighter, one facing away darker, never below `_AMBIENT` of its colour. Alpha is
    never changed. Both are (H, W, 4) uint8 of one size."""
    if image.shape != normal.shape or image.ndim != 3:
        raise ValueError(f"lit needs (H, W, 4) images of one size, got {image.shape} and {normal.shape}")
    vectors = normal[..., :3].astype(np.float64) / 255 * 2 - 1
    vectors /= np.maximum(np.linalg.norm(vectors, axis=-1, keepdims=True), 1e-9)
    light = np.array(_LIGHT, dtype=np.float64)
    light /= np.linalg.norm(light)
    flat = np.array([FLAT[0] / 255 * 2 - 1, FLAT[1] / 255 * 2 - 1, 1.0])
    flat /= np.linalg.norm(flat)
    facing = np.clip((vectors @ light) / float(flat @ light), 0, 2)
    gain = _AMBIENT + (1 - _AMBIENT) * facing
    out = image.copy()
    out[..., :3] = np.clip(np.rint(image[..., :3].astype(np.float64) * gain[..., None]), 0, 255).astype(np.uint8)
    return out
