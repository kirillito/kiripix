"""OKLab conversion, nearest-colour mapping, ordered dithering and the conformance report.

Pure numpy: arrays in, arrays out. Results are deterministic: squared distances are rounded before comparison, so a
last-bit difference between platforms' maths libraries can't flip a choice, and ties go to the earlier palette colour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
if TYPE_CHECKING:
    import numpy.typing as npt
else:
    npt = lazy_module("numpy.typing")

U8 = npt.NDArray[np.uint8]
F64 = npt.NDArray[np.float64]

BayerSize = Literal[0, 2, 4, 8]

_DISTANCE_DECIMALS = 12
_CHUNK = 1 << 16

_M1 = np.array(
    [
        [0.4122214708, 0.5363325363, 0.0514459929],
        [0.2119034982, 0.6806995451, 0.1073969566],
        [0.0883024619, 0.2817188376, 0.6299787005],
    ]
)
_M2 = np.array(
    [
        [0.2104542553, 0.7936177850, -0.0040720468],
        [1.9779984951, -2.4285922050, 0.4505937099],
        [0.0259040371, 0.7827717662, -0.8086757660],
    ]
)


def _srgb_to_linear_table() -> F64:
    c = np.arange(256, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


_LINEAR = _srgb_to_linear_table()


def srgb_to_oklab(rgb: U8) -> F64:
    """Convert (..., 3) uint8 sRGB to (..., 3) float64 OKLab (L, a, b)."""
    linear = _LINEAR[rgb]
    lms = np.cbrt(linear @ _M1.T)
    result: F64 = lms @ _M2.T
    return result


def bayer_matrix(size: int) -> npt.NDArray[np.int64]:
    """The ordered-dither index matrix of side `size` (a power of two), values 0 to size² - 1."""
    matrix = np.zeros((1, 1), dtype=np.int64)
    while matrix.shape[0] < size:
        m = 4 * matrix
        matrix = np.block([[m, m + 2], [m + 3, m + 1]])
    return matrix


def bayer_thresholds(size: int) -> F64:
    """Thresholds in (-0.5, 0.5), centred on zero, for a Bayer matrix of side `size`."""
    n = size * size
    result: F64 = (bayer_matrix(size).astype(np.float64) + 0.5) / n - 0.5
    return result


def palette_spread(palette_lab: F64) -> float:
    """The mean OKLab distance from each palette colour to its nearest other colour; 0 for one colour."""
    if len(palette_lab) < 2:
        return 0.0
    d = np.sqrt(((palette_lab[:, None, :] - palette_lab[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(d, np.inf)
    return float(d.min(axis=1).mean())


def nearest_index(lab: F64, palette_lab: F64) -> npt.NDArray[np.intp]:
    """For (N, 3) OKLab colours, the index of the nearest palette colour; ties go to the lowest index."""
    out = np.empty(len(lab), dtype=np.intp)
    for start in range(0, len(lab), _CHUNK):
        chunk = lab[start : start + _CHUNK]
        d2 = ((chunk[:, None, :] - palette_lab[None, :, :]) ** 2).sum(axis=2)
        out[start : start + _CHUNK] = np.round(d2, _DISTANCE_DECIMALS).argmin(axis=1)
    return out


def has_partial_alpha(rgba: U8) -> bool:
    alpha = rgba[..., 3]
    return bool(((alpha != 0) & (alpha != 255)).any())


def quantize(rgba: U8, palette_rgb: U8, dither: BayerSize = 0, strength: float = 1.0) -> U8:
    """Map an (H, W, 4) RGBA image onto the palette in OKLab.

    With `dither` 2, 4 or 8, an ordered Bayer offset of `strength` times the palette's spread is added to lightness
    before mapping. Alpha 0 becomes (0, 0, 0, 0); alpha 255 is mapped; any other alpha is refused.
    """
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("expected an (H, W, 4) RGBA image")
    if len(palette_rgb) == 0:
        raise ValueError("the palette has no colours")
    if has_partial_alpha(rgba):
        raise ValueError("the image has partially transparent pixels")
    height, width = rgba.shape[:2]
    palette_lab = srgb_to_oklab(palette_rgb)
    lab = srgb_to_oklab(rgba[..., :3])
    if dither:
        thresholds = bayer_thresholds(dither)
        tiled = np.tile(thresholds, (height // dither + 1, width // dither + 1))[:height, :width]
        lab = lab.copy()
        lab[..., 0] += tiled * (strength * palette_spread(palette_lab))
    index = nearest_index(lab.reshape(-1, 3), palette_lab).reshape(height, width)
    out = np.zeros_like(rgba)
    opaque = rgba[..., 3] == 255
    out[..., :3] = np.where(opaque[..., None], palette_rgb[index], 0)
    out[..., 3] = np.where(opaque, 255, 0)
    return out


def mapping_error(before: U8, after: U8) -> float:
    """The mean OKLab distance between two same-sized RGBA images, over the pixels opaque in both; 0.0 when none are."""
    if before.shape != after.shape:
        raise ValueError("the images differ in size")
    both = (before[..., 3] == 255) & (after[..., 3] == 255)
    if not both.any():
        return 0.0
    delta = srgb_to_oklab(before[..., :3][both]) - srgb_to_oklab(after[..., :3][both])
    return float(np.sqrt((delta**2).sum(axis=-1)).mean())


@dataclass(frozen=True)
class ConformanceReport:
    """How well an image keeps to a palette. Positions are (x, y), in row-major order."""

    width: int
    height: int
    opaque: int
    transparent: int
    partial_alpha: int
    off_palette: int
    first_off_palette: list[tuple[int, int]] = field(default_factory=list)
    first_partial_alpha: list[tuple[int, int]] = field(default_factory=list)


def _positions(mask: npt.NDArray[np.bool_], limit: int) -> list[tuple[int, int]]:
    ys, xs = np.nonzero(mask)
    return [(int(x), int(y)) for y, x in zip(ys[:limit], xs[:limit], strict=True)]


def conformance(rgba: U8, palette_rgb: U8, limit: int = 10) -> ConformanceReport:
    """Count the opaque pixels whose colour isn't in the palette, and the partially transparent pixels."""
    alpha = rgba[..., 3]
    opaque = alpha == 255
    partial = (alpha != 0) & ~opaque
    packed = rgba[..., :3].astype(np.uint32) @ np.array([1 << 16, 1 << 8, 1], dtype=np.uint32)
    packed_palette = palette_rgb.astype(np.uint32) @ np.array([1 << 16, 1 << 8, 1], dtype=np.uint32)
    off = opaque & ~np.isin(packed, packed_palette)
    return ConformanceReport(
        width=int(rgba.shape[1]),
        height=int(rgba.shape[0]),
        opaque=int(opaque.sum()),
        transparent=int((alpha == 0).sum()),
        partial_alpha=int(partial.sum()),
        off_palette=int(off.sum()),
        first_off_palette=_positions(off, limit),
        first_partial_alpha=_positions(partial, limit),
    )
