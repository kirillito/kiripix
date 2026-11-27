"""Sound contact-sheet Ops (spec §7, ticket 0396): the pictures an agent reads in place of hearing a sound. Pure numpy; text,
layout and the PNG are core's (`kiripix.core.sound_sheet`).

Every image is uint8 RGB shaped (height, width, 3). A waveform is drawn at absolute level (full scale is the picture's whole
height), so a louder file looks taller; a spectrogram is in absolute dBFS, so it looks brighter. Sample positions map to
columns by `span_columns`, which is also how a Take's box is placed, so a box and the picture under it never disagree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt
else:
    np = lazy_module("numpy")
    npt = lazy_module("numpy.typing")

Rgb = tuple[int, int, int]

BACKGROUND: Rgb = (22, 22, 28)
WAVE_COLOUR: Rgb = (120, 200, 255)
CLIP_COLOUR: Rgb = (255, 70, 70)
GUIDE_COLOUR: Rgb = (50, 50, 64)
CENTRE_COLOUR: Rgb = (70, 70, 90)
FRAME = 1024  # samples of one spectrogram column's window
FLOOR_DB = -90.0  # the spectrogram's black
_CLIPPED = 0.999
_RAMP = ((0.0, (8, 8, 20)), (0.25, (40, 20, 110)), (0.5, (150, 30, 120)), (0.75, (235, 120, 40)), (1.0, (255, 245, 200)))


def span_columns(start: int, end: int, total: int, width: int) -> tuple[int, int]:
    """The column a span of samples `start` to `end` (exclusive) begins at and how many columns it covers (at least 1), in a
    picture `width` columns wide that shows `total` samples. Round to nearest, ties to even (numpy's rule)."""
    first = int(np.rint(start * width / max(total, 1)))
    last = int(np.rint(end * width / max(total, 1)))
    first = min(max(first, 0), max(width - 1, 0))
    return first, max(1, min(last, width) - first)


def _mono(samples: npt.NDArray[np.floating]) -> npt.NDArray[np.float64]:
    if samples.ndim == 1:
        return samples.astype(np.float64)
    return samples.mean(axis=1, dtype=np.float64)


def waveform_image(samples: npt.NDArray[np.floating], width: int, height: int, *, colour: Rgb = WAVE_COLOUR,
                   background: Rgb = BACKGROUND) -> npt.NDArray[np.uint8]:
    """The waveform of `samples` (frames,) or (frames, channels), mixed to mono: for each column the lowest to the highest
    sample under it, at absolute level (full scale reaches the top and bottom). A faint guide marks half scale (-6 dBFS) and
    the centre line; a column that reaches full scale is red. Nothing but the guides for no samples."""
    image = np.empty((height, width, 3), dtype=np.uint8)
    image[:] = background
    middle = (height - 1) / 2.0
    rows = np.arange(height)[:, None]
    for guide in (0.5, -0.5):
        image[int(np.rint(middle - guide * middle)), :] = GUIDE_COLOUR
    image[int(np.rint(middle)), :] = CENTRE_COLOUR
    data = _mono(samples)
    count = len(data)
    if count == 0:
        return image
    edges = np.arange(width + 1) * count // width
    starts = np.minimum(edges[:-1], count - 1)
    low = np.minimum.reduceat(data, starts)
    high = np.maximum.reduceat(data, starts)
    top = np.rint(middle - np.clip(high, -1.0, 1.0) * middle).astype(np.int64)
    bottom = np.rint(middle - np.clip(low, -1.0, 1.0) * middle).astype(np.int64)
    bottom = np.maximum(bottom, top)
    inside = (rows >= top[None, :]) & (rows <= bottom[None, :])
    loud = np.maximum(np.abs(low), np.abs(high)) >= _CLIPPED
    for column_colour, columns in ((colour, ~loud), (CLIP_COLOUR, loud)):
        picked = inside & columns[None, :]
        image[picked] = column_colour
    return image


def _colour_ramp(level: npt.NDArray[np.float64]) -> npt.NDArray[np.uint8]:
    """0 to 1 as black, blue, magenta, orange, pale yellow."""
    stops = np.array([stop for stop, _ in _RAMP])
    out = np.empty(level.shape + (3,), dtype=np.uint8)
    for channel in range(3):
        values = np.array([rgb[channel] for _, rgb in _RAMP], dtype=np.float64)
        out[..., channel] = np.rint(np.interp(level, stops, values)).astype(np.uint8)
    return out


def spectrogram_image(samples: npt.NDArray[np.floating], rate: int, width: int, height: int, *, low_hz: float = 50.0,
                      high_hz: float = 16000.0) -> npt.NDArray[np.uint8]:
    """A spectrogram of `samples` (mixed to mono): `width` columns across its length, `height` rows from `high_hz` (top) down to
    `low_hz` on a log frequency axis, level in absolute dBFS (a full-scale sine is 0 dB) from `FLOOR_DB` (black) to 0 (pale).
    Each column is a Hann-windowed `FRAME`-sample FFT centred on it, zero-padded off the ends; a row interpolates its two
    nearest bins in dB."""
    data = _mono(samples)
    count = len(data)
    high_hz = min(high_hz, rate / 2.0)
    window = np.hanning(FRAME)
    padded = np.concatenate([np.zeros(FRAME, dtype=np.float64), data, np.zeros(FRAME, dtype=np.float64)])
    centres = ((np.arange(width) + 0.5) * count / width).astype(np.int64)
    index = centres[:, None] + np.arange(FRAME)[None, :] - FRAME // 2 + FRAME
    frames = padded[index] * window[None, :]
    magnitude = np.abs(np.fft.rfft(frames, axis=1)) / (window.sum() / 2.0)
    decibels = 20.0 * np.log10(np.maximum(magnitude, 1e-9))  # (width, bins)
    positions = np.geomspace(low_hz, high_hz, height)[::-1] * FRAME / rate
    below = np.minimum(np.floor(positions).astype(np.int64), decibels.shape[1] - 2)
    fraction = positions - below
    rows = decibels[:, below] * (1.0 - fraction)[None, :] + decibels[:, below + 1] * fraction[None, :]  # (width, height)
    level = np.clip((rows.T - FLOOR_DB) / -FLOOR_DB, 0.0, 1.0)
    return _colour_ramp(level)


def draw_box(image: npt.NDArray[np.uint8], left: int, top: int, right: int, bottom: int, colour: Rgb,
             thickness: int = 1) -> npt.NDArray[np.uint8]:
    """A copy of `image` with the outline of the rectangle from (`left`, `top`) to (`right`, `bottom`), both inclusive, drawn
    inside those bounds, clipped to the picture."""
    out = image.copy()
    height, width = out.shape[:2]
    left, right = max(left, 0), min(right, width - 1)
    top, bottom = max(top, 0), min(bottom, height - 1)
    if left > right or top > bottom:
        return out
    t = max(1, thickness)
    out[top:top + t, left:right + 1] = colour
    out[max(bottom - t + 1, top):bottom + 1, left:right + 1] = colour
    out[top:bottom + 1, left:left + t] = colour
    out[top:bottom + 1, max(right - t + 1, left):right + 1] = colour
    return out


def draw_column(image: npt.NDArray[np.uint8], x: int, colour: Rgb) -> npt.NDArray[np.uint8]:
    """A copy of `image` with the column `x` drawn in `colour`; unchanged when `x` is off the picture."""
    out = image.copy()
    if 0 <= x < out.shape[1]:
        out[:, x] = colour
    return out
