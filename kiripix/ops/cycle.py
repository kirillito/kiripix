"""Colour cycle Ops and the flicker sequence (ticket 0188, route (b) of 0183).

A loop's frames are baked: `cycle_rotate` steps chosen colours round a list, `cycle_pulse` moves each pixel up and down
its own ramp of the palette. `flicker_sequence` and `even_sequence` give the timing, `flash_count` and `seam_ratio` the
measures behind the `loop.flash` and seam findings. Pure: arrays in, arrays out. Images are (H, W, 4) RGBA uint8, a
region is an (H, W) bool mask, colours and palettes are (N, 3) uint8 RGB. Every output pixel is a colour the input had
or a colour of the palette; alpha is copied. Ties are broken by palette order, then index.

The defaults were checked by trial 0184 (the kitchen's TV): "confirmed by 0184" or set from it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from kiripix.ops.colour import F64, U8, _oklab_matrices, srgb_to_oklab
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

PULSE_DEPTH = 2  # places along the ramp (confirmed by 0184: 4 reached a ramp's end on a 283-colour palette)
PULSE_STEPS = 4  # frames in a pulse (confirmed by 0184)
FLICKER_MEAN_TICKS = 6  # (confirmed by 0184)
FLICKER_SPREAD = 0.6  # a hold is the mean plus or minus this share of it (confirmed by 0184)
FLICKER_LENGTH_TICKS = 600  # (confirmed by 0184)
EVEN_TICKS = 8  # (confirmed by 0184 for cycles; the Owner wants a sway slower, see 0192)
RAMP_HUE_WINDOW = math.radians(25)  # a colour's ramp holds colours this close to its hue (trial 0184)
RAMP_NEUTRAL_CHROMA = 0.03  # OKLab chroma below which a colour is grey and has no hue (confirmed by 0184)

TICKS_PER_SECOND = 60
FLASH_STEP = 0.10  # WCAG 2.3.1: a change of at least 10 % of the maximum relative luminance (confirmed by 0184)
FLASH_DARK_BELOW = 0.80  # ... where the darker state is below this (confirmed by 0184)
FLASH_AREA_FRACTION = 0.25 * (341 * 256) / (1024 * 768)  # a quarter of 341 x 256 at 1024 x 768, as a share of the screen
FLASH_PER_SECOND = 3  # more than this is the finding (the caller's rule), kept here with the measure (0184)

_DECIMALS = 12


def _pack(rgb: U8) -> npt.NDArray[np.uint32]:
    packed: npt.NDArray[np.uint32] = rgb[..., :3].astype(np.uint32) @ np.array([1 << 16, 1 << 8, 1], dtype=np.uint32)
    return packed


def _check_image(image: U8, region: BoolMask) -> None:
    if image.ndim != 3 or image.shape[2] != 4:
        raise ValueError("expected an (H, W, 4) RGBA image")
    if region.shape != image.shape[:2]:
        raise ValueError("the region differs in size from the image")


def _check_colours(colours: U8) -> None:
    if colours.ndim != 2 or colours.shape[1] != 3 or len(colours) == 0:
        raise ValueError("expected a list of (R, G, B) colours")


def cycle_index(image: U8, region: BoolMask, colours: U8) -> U8:
    """An 8-bit image: 0 outside the region or where the colour isn't in `colours`, else 1 + its position in the list."""
    _check_image(image, region)
    _check_colours(colours)
    if len(colours) > 255:
        raise ValueError("a cycle has at most 255 colours")
    packed_colours = _pack(colours)
    if len(np.unique(packed_colours)) != len(packed_colours):
        raise ValueError("a colour is listed twice")
    packed = _pack(image)
    index = np.zeros(image.shape[:2], dtype=np.uint8)
    for position, value in enumerate(packed_colours):
        index[region & (packed == value) & (image[..., 3] == 255)] = position + 1
    return index


def cycle_rotate(image: U8, index: U8, colours: U8, steps: int | None = None) -> U8:
    """(steps, H, W, 4) frames: frame k gives each indexed pixel `colours[(i + k) % len]`. Frame 0 is the input."""
    _check_colours(colours)
    if index.shape != image.shape[:2]:
        raise ValueError("the index differs in size from the image")
    count = len(colours)
    steps = count if steps is None else steps
    if steps < 1:
        raise ValueError("a cycle needs at least one frame")
    indexed = index > 0
    position = index.astype(np.int64) - 1
    frames = np.repeat(image[None], steps, axis=0)
    for k in range(1, steps):
        shifted = colours[(position[indexed] + k) % count]
        frames[k][indexed, :3] = shifted
    return frames


def ramps(palette: U8) -> list[tuple[int, ...]]:
    """For each palette colour, its ramp: the palette indices of the colours like it, darkest first.

    Greys (OKLab chroma below `RAMP_NEUTRAL_CHROMA`) share one ramp. A coloured colour's ramp holds every coloured
    colour within `RAMP_HUE_WINDOW` of its own hue, itself included. It is the colour's own neighbourhood, not a
    partition: on a large palette every hue has neighbours, so any grouping by gaps would join the whole hue circle
    (trial 0184: a navy screen pulsed through brown and green). Ordered by lightness, ties by palette index, so a
    colour's neighbours in its ramp are its next darker and lighter colour.
    """
    _check_colours(palette)
    lab = srgb_to_oklab(palette)
    lightness = np.round(lab[:, 0], _DECIMALS)
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    hue = np.arctan2(lab[:, 2], lab[:, 1])
    neutral = chroma < RAMP_NEUTRAL_CHROMA
    greys = tuple(sorted(np.nonzero(neutral)[0].tolist(), key=lambda i: (float(lightness[i]), i)))
    result: list[tuple[int, ...]] = []
    for i in range(len(palette)):
        if neutral[i]:
            result.append(greys)
            continue
        apart = np.abs((hue - hue[i] + math.pi) % math.tau - math.pi)
        near = ~neutral & (np.round(apart, _DECIMALS) <= round(RAMP_HUE_WINDOW, _DECIMALS))
        result.append(tuple(sorted(np.nonzero(near)[0].tolist(), key=lambda j: (float(lightness[j]), j))))
    return result


def cycle_pulse(
    image: U8,
    region: BoolMask,
    palette: U8,
    depth: int = PULSE_DEPTH,
    steps: int = PULSE_STEPS,
) -> U8:
    """(steps, H, W, 4) frames: each opaque region pixel moves up to `depth` places lighter along its own ramp and back.

    The offset follows a triangle over the frames (0 at frame 0, `depth` at the middle, whole places, halves rounded up).
    A pixel at its ramp's end stays, one near it stops at the end. Pixels whose colour isn't in the palette stay.
    """
    _check_image(image, region)
    _check_colours(palette)
    if steps < 1 or depth < 0:
        raise ValueError("a pulse needs at least one frame and a depth of 0 or more")
    packed_palette = _pack(palette)
    packed = _pack(image)
    # the first palette entry of a colour is its identity, so a palette listing a colour twice stays deterministic
    first = {int(v): i for i, v in reversed(list(enumerate(packed_palette)))}
    ramp_of = ramps(palette)
    pixel_index = np.full(image.shape[:2], -1, dtype=np.int64)
    candidates = region & (image[..., 3] == 255)
    for value, i in first.items():
        pixel_index[candidates & (packed == value)] = i
    frames = np.repeat(image[None], steps, axis=0)
    ys, xs = np.nonzero(pixel_index >= 0)
    for k in range(1, steps):
        a = steps - abs(2 * k - steps)
        offset = (depth * a + steps // 2) // steps
        if offset == 0:
            continue
        for y, x in zip(ys.tolist(), xs.tolist(), strict=True):
            i = int(pixel_index[y, x])
            ramp = ramp_of[i]
            place = ramp.index(i)
            frames[k, y, x, :3] = palette[ramp[min(place + offset, len(ramp) - 1)]]
    return frames


def flicker_sequence(
    seed: int,
    frames: Sequence[int],
    mean_ticks: int = FLICKER_MEAN_TICKS,
    spread: float = FLICKER_SPREAD,
    length_ticks: int = FLICKER_LENGTH_TICKS,
) -> list[tuple[int, int]]:
    """A fixed, seeded list of (frame, ticks) over the distinct `frames` (ids), starting on `frames[0]`, summing to `length_ticks`.

    Each hold is the mean plus or minus up to `spread` of it (whole ticks, at least 1); the next frame is any other one,
    drawn uniformly. The last hold is cut to fit. Uses its own PCG64 generator: the same seed gives the same list on
    every platform.
    """
    if len(frames) == 0 or len(set(frames)) != len(frames):
        raise ValueError("flicker needs at least one frame, each listed once")
    if mean_ticks < 1 or length_ticks < 1 or not 0 <= spread <= 1:
        raise ValueError("mean and length are at least 1 tick; spread is between 0 and 1")
    rng = np.random.Generator(np.random.PCG64(seed))
    reach = int(math.floor(mean_ticks * spread + 1e-9))
    low, high = max(1, mean_ticks - reach), mean_ticks + reach
    sequence: list[tuple[int, int]] = []
    current, total = 0, 0
    while total < length_ticks:
        hold = min(int(rng.integers(low, high + 1)), length_ticks - total)
        sequence.append((frames[current], hold))
        total += hold
        if len(frames) > 1:
            pick = int(rng.integers(0, len(frames) - 1))
            current = pick if pick < current else pick + 1
    return sequence


def even_sequence(frames: Sequence[int], ticks: int = EVEN_TICKS, pingpong: bool = False) -> list[tuple[int, int]]:
    """Each of `frames` (ids) for `ticks`; with `pingpong`, 0 1 ... n-1 ... 1, so the loop's wrap repeats no frame."""
    if len(frames) == 0 or ticks < 1:
        raise ValueError("a sequence needs at least one frame and 1 tick")
    order = list(range(len(frames)))
    if pingpong and len(order) > 2:
        order += list(range(len(order) - 2, 0, -1))
    return [(frames[i], ticks) for i in order]


def _luminance(rgb: U8) -> F64:
    """WCAG relative luminance of (..., 3) uint8 sRGB, 0 to 1."""
    table = _oklab_matrices()[0]
    linear = table[rgb]
    result: F64 = linear @ np.array([0.2126, 0.7152, 0.0722])
    return result


def flash_count(
    frames: U8,
    sequence: Sequence[tuple[int, int]],
    region_area: int,
    screen_area: int,
) -> float:
    """The most flashes in any one second of the looping sequence, by the WCAG 2.3.1 general flash measure.

    A flash is a pair of opposing changes in relative luminance of at least `FLASH_STEP`, the darker state below
    `FLASH_DARK_BELOW`. It counts only where the changing pixels cover at least `FLASH_AREA_FRACTION` of the screen
    (a quarter of 341 x 256 at 1024 x 768, scaled to `screen_area`); a region smaller than that never counts. Ticks run
    at `TICKS_PER_SECOND`. `frames` are the (N, H, W, 4) images the sequence's frame ids index.
    """
    entries = list(sequence)
    if len(entries) < 2:
        return 0.0
    min_area = FLASH_AREA_FRACTION * screen_area
    if region_area < min_area:
        return 0.0
    cache: dict[int, F64] = {}
    opaque = frames[..., 3] == 255

    def lum(f: int) -> F64:
        if f not in cache:
            cache[f] = _luminance(frames[f][..., :3])
        return cache[f]

    # each transition between shown frames (the last one wraps to the first): (tick it happens at, direction or 0)
    events: list[tuple[int, int]] = []
    at = 0
    for n, (frame, ticks) in enumerate(entries):
        at += ticks
        nxt = entries[(n + 1) % len(entries)][0]
        if nxt == frame:
            continue
        a, b = lum(frame), lum(nxt)
        delta = b - a
        both = opaque[frame] & opaque[nxt]
        big = both & (np.abs(delta) >= FLASH_STEP - 1e-9) & (np.minimum(a, b) < FLASH_DARK_BELOW)
        if big.sum() >= min_area:
            net = float(delta[big].sum())
            events.append((at, 1 if net > 0 else -1))
    if len(events) < 2:
        return 0.0
    period = at
    copies = math.ceil(TICKS_PER_SECOND / period) + 1
    unrolled = [(t + c * period, d) for c in range(copies) for t, d in events]
    best = 0
    for i, (start, _) in enumerate(unrolled[: len(events)]):
        window = [d for t, d in unrolled[i:] if t < start + TICKS_PER_SECOND]
        best = max(best, min(window.count(1), window.count(-1)))
    return float(best)


def _changed(a: U8, b: U8) -> int:
    return int((a != b).any(axis=-1).sum())


def seam_ratio(frames: U8, sequence: Sequence[tuple[int, int]]) -> float:
    """The change from the last shown frame back to the first, over the median change between consecutive shown frames.

    Change is the number of pixels that differ. 1.0 is a seam as smooth as the rest; 0.0 when the loop wraps onto the
    frame it ends on; infinity when the frames never change between shown frames but the seam does.
    """
    shown = [f for f, _ in sequence]
    if len(shown) < 2:
        return 1.0
    steps = [_changed(frames[a], frames[b]) for a, b in zip(shown, shown[1:], strict=False)]
    seam = _changed(frames[shown[-1]], frames[shown[0]])
    median = float(np.median(steps))
    if median == 0:
        return 1.0 if seam == 0 else math.inf
    return seam / median


def cycle_seam_ratio(colours: U8, pingpong: bool = False) -> float:
    """For a colour cycle, the largest OKLab step between neighbours in the cycle, wrap included, over the median step.

    A pingpong cycle has no wrap step, so it is 1.0.
    """
    _check_colours(colours)
    if len(colours) < 3 or pingpong:
        return 1.0
    lab = srgb_to_oklab(colours)
    steps = np.sqrt(((np.roll(lab, -1, axis=0) - lab) ** 2).sum(axis=1))
    median = float(np.median(steps))
    if median == 0:
        return 1.0 if float(steps.max()) == 0 else math.inf
    return float(steps.max()) / median
