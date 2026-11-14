"""Frame Ops (ticket 0192, route (c) of 0183): `sway`, `shimmer` and `scroll`.

Each makes the frames of a Loop from one image by moving whole pixels, so every output pixel is a copy of an input
pixel and the frames are on the palette by construction. Pure: arrays in, arrays out. Images are (H, W, 4) RGBA uint8,
a region is an (H, W) bool mask; the result is (frames, H, W, 4). Frame 0 is the input. Alpha moves with the pixels
(`sway`) or stays where the region is (`shimmer`, `scroll`: a whole pixel, alpha included, is copied).

The defaults marked "set by 0184" are placeholders until the trial reports.
"""

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
    BoolMask = npt.NDArray[np.bool_]
else:
    U8 = Any
    BoolMask = Any

SWAY_AMPLITUDE = 1  # px at the far end (set by 0184)
SWAY_FRAMES = 4  # (set by 0184)
SHIMMER_AMPLITUDE = 1  # px (set by 0184)
SHIMMER_WAVELENGTH = 6  # rows (set by 0184)
SHIMMER_FRAMES = 6  # (set by 0184)


def _check(image: U8, region: BoolMask | None = None) -> None:
    if image.ndim != 3 or image.shape[2] != 4:
        raise ValueError("expected an (H, W, 4) RGBA image")
    if region is not None and region.shape != image.shape[:2]:
        raise ValueError("the region differs in size from the image")


def _whole(values: Any) -> Any:
    """Round to whole pixels, halves away from zero, so a wave is symmetric and no tie is left to the platform."""
    return (np.sign(values) * np.floor(np.abs(values) + 0.5)).astype(np.int64)


def _shift_rows(image: U8, shifts: Any, keep: BoolMask | None = None) -> U8:
    """Each row r moved right by `shifts[r]` px; what leaves the image is dropped, what is uncovered is (0, 0, 0, 0).
    With `keep`, a pixel only comes from a `keep` pixel of its row and only lands on a `keep` pixel; else it stays."""
    height, width = image.shape[:2]
    out = np.zeros_like(image) if keep is None else image.copy()
    columns = np.arange(width)
    for row in range(height):
        shift = int(shifts[row])
        if shift == 0:
            out[row] = image[row]
            continue
        source = columns - shift
        inside = (source >= 0) & (source < width)
        if keep is not None:
            inside &= keep[row]
            inside[inside] = keep[row][source[inside]]
        out[row, columns[inside]] = image[row, source[inside]]
    return out


def sway(image: U8, anchor_row: int, amplitude: float = SWAY_AMPLITUDE, frames: int = SWAY_FRAMES) -> U8:
    """The frames of an object swaying from `anchor_row`: row r moves by `round(amplitude * sin(2 pi k / frames) * d(r))`
    px, where d is 0 at the anchor and 1 at the image's row farthest from it. The alpha moves with the pixels, so where the
    object uncovers pixels the frame is transparent (and whatever is under it shows). Frame 0 is the input."""
    _check(image)
    if frames < 2:
        raise ValueError("a sway needs at least two frames")
    height = image.shape[0]
    if not 0 <= anchor_row < height:
        raise ValueError(f"the anchor row {anchor_row} is outside the image's {height} rows")
    reach = max(anchor_row, height - 1 - anchor_row)
    depth = np.abs(np.arange(height) - anchor_row) / reach if reach else np.zeros(height)
    out = np.zeros((frames, *image.shape), dtype=np.uint8)
    for k in range(frames):
        wave = math.sin(2 * math.pi * k / frames) * amplitude
        out[k] = image if k == 0 else _shift_rows(image, _whole(wave * depth))
    return out


def shimmer(image: U8, region: BoolMask, amplitude: float = SHIMMER_AMPLITUDE, wavelength: float = SHIMMER_WAVELENGTH,
            frames: int = SHIMMER_FRAMES) -> U8:
    """The frames of water shimmering: each row inside `region` moves sideways by
    `round(amplitude * sin(2 pi (row / wavelength + k / frames)))` px, taking pixels from inside the region only. To make
    frame 0 the input, the wave is taken relative to frame 0's (its shift is subtracted), so the shift is at most twice
    `amplitude`. A pixel with no region pixel to take stays as it is. Periodic in `frames`."""
    _check(image, region)
    if frames < 2 or wavelength <= 0:
        raise ValueError("a shimmer needs at least two frames and a wavelength over zero")
    rows = np.arange(image.shape[0])
    base = np.sin(2 * math.pi * rows / wavelength)
    out = np.zeros((frames, *image.shape), dtype=np.uint8)
    for k in range(frames):
        wave = np.sin(2 * math.pi * (rows / wavelength + k / frames)) - base
        out[k] = image if k == 0 else _shift_rows(image, _whole(amplitude * wave), region)
    return out


def scroll_period(width: int, height: int, dx: int, dy: int) -> int:
    """The number of frames after which a scroll of (dx, dy) per frame in a `width` x `height` box is back at frame 0."""
    if dx == 0 and dy == 0:
        raise ValueError("a scroll needs a dx or a dy")
    across = width // math.gcd(width, abs(dx)) if dx else 1
    down = height // math.gcd(height, abs(dy)) if dy else 1
    return across * down // math.gcd(across, down)


def scroll(image: U8, region: BoolMask, dx: int, dy: int, frames: int | None = None) -> U8:
    """The frames of the region's pixels moving by (`dx`, `dy`) per frame, wrapping within the region's bounding box and
    masked to the region: only region pixels change, taking what the box held `k` steps before. `frames` defaults to the
    period of the wrap. Frame 0 is the input."""
    _check(image, region)
    if not region.any():
        raise ValueError("a scroll needs a region")
    count = scroll_period(*_box_size(region), dx, dy) if frames is None else frames
    if count < 1:
        raise ValueError("a scroll needs at least one frame")
    ys, xs = np.nonzero(region)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1
    box = image[y0:y1, x0:x1]
    inside = region[y0:y1, x0:x1]
    out = np.zeros((count, *image.shape), dtype=np.uint8)
    for k in range(count):
        out[k] = image
        moved = np.roll(box, shift=(dy * k, dx * k), axis=(0, 1))
        out[k, y0:y1, x0:x1][inside] = moved[inside]
    return out


def _box_size(region: BoolMask) -> tuple[int, int]:
    ys, xs = np.nonzero(region)
    return int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
