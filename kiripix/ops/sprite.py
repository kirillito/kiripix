"""The sprite Kind's Ops (spec §7, ticket 0177): slice a sheet, find the feet, normals from a height, and colour regions as
parts (ticket 0319)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from kiripix.ops.colour import srgb_to_oklab
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


# The hue words that name a sprite's colour regions (ticket 0319), each at its OKLab hue in degrees.
HUE_WORDS = (("red", 25.0), ("orange", 60.0), ("yellow", 100.0), ("green", 140.0), ("cyan", 195.0), ("blue", 255.0),
             ("purple", 305.0), ("pink", 350.0))
NEUTRAL = "grey"


@dataclass(frozen=True)
class ColourRegions:
    """A sprite's colours grouped into regions, its parts when it has no material pass (ticket 0319).

    `names[i]` is region i + 1's name, `pixels[i]` its pixel count over every frame. `colours` (N, 3) is every opaque colour
    of the frames, and `region` (N,) the region of each, from 1.
    """

    names: list[str]
    pixels: list[int]
    colours: U8
    region: npt.NDArray[np.int64]


def _hue_word(degrees: float) -> str:
    def apart(centre: float) -> float:
        d = abs(degrees - centre) % 360.0
        return min(d, 360.0 - d)

    return min(HUE_WORDS, key=lambda w: (apart(w[1]), w[1]))[0]


def colour_regions(frames: Sequence[U8], hue_gap: float = 8.0, neutral_chroma: float = 0.025) -> ColourRegions:
    """The opaque colours of every frame together grouped by OKLab hue and chroma, so one part keeps one region in every frame.

    A colour of chroma (the OKLab a, b length) under `neutral_chroma` is neutral: every one of them is one region, `grey`. The
    others are sorted round the hue circle and cut wherever two neighbouring hues are more than `hue_gap` degrees apart; each
    run between cuts is a region (with no such gap, all of them are one). A region is named after the hue word (`HUE_WORDS`)
    nearest its mean hue (weighted by pixels and chroma); regions with the same word are numbered by pixel count, the largest
    plain, then `_2`, `_3` (a tie to the lower mean hue). Regions are in order of mean hue, `grey` last. Lightness plays no
    part: a part's shades, dark to light, stay in one region. Alpha must be 0 or 255; only 255 counts.
    """
    if hue_gap <= 0:
        raise ValueError("hue_gap must be above 0")
    pixels = [f[..., :3][f[..., 3] == 255] for f in frames]
    opaque = np.concatenate(pixels) if pixels else np.zeros((0, 3), dtype=np.uint8)
    if len(opaque) == 0:
        return ColourRegions([], [], np.zeros((0, 3), dtype=np.uint8), np.zeros(0, dtype=np.int64))
    colours, counts = np.unique(opaque, axis=0, return_counts=True)
    lab = srgb_to_oklab(colours)
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    hue = np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360.0
    neutral = chroma < neutral_chroma
    groups: list[list[int]] = []
    chromatic = np.flatnonzero(~neutral)
    if len(chromatic):
        ordered = chromatic[np.argsort(hue[chromatic], kind="stable")]
        values = hue[ordered]
        gaps = np.diff(np.concatenate([values, [values[0] + 360.0]]))  # gaps[i]: from i to the next, the last wrapping round
        cuts = np.flatnonzero(gaps > hue_gap)
        if len(cuts) == 0:
            groups.append([int(i) for i in ordered])
        else:
            for k, cut in enumerate(cuts):
                end = cuts[(k + 1) % len(cuts)]
                run = [(cut + 1 + j) % len(ordered) for j in range((end - cut) % len(ordered) or len(ordered))]
                groups.append([int(ordered[j]) for j in run])
    means: list[float] = []
    for members in groups:
        weight = counts[members] * chroma[members]
        angle = np.radians(hue[members])
        means.append(float(np.degrees(np.arctan2((weight * np.sin(angle)).sum(), (weight * np.cos(angle)).sum())) % 360.0))
    order = sorted(range(len(groups)), key=lambda g: means[g])
    groups = [groups[g] for g in order]
    means = [means[g] for g in order]
    words = [_hue_word(m) for m in means]
    if neutral.any():
        groups.append([int(i) for i in np.flatnonzero(neutral)])
        means.append(float("inf"))
        words.append(NEUTRAL)
    sizes = [int(counts[members].sum()) for members in groups]
    names = list(words)
    for word in set(words):
        same = sorted((g for g, w in enumerate(words) if w == word), key=lambda g: (-sizes[g], means[g]))
        for rank, g in enumerate(same[1:], start=2):
            names[g] = f"{word}_{rank}"
    region = np.zeros(len(colours), dtype=np.int64)
    for number, members in enumerate(groups, start=1):
        region[members] = number
    return ColourRegions(names, sizes, colours, region)


def region_labels(frame: U8, regions: ColourRegions) -> U8:
    """Frame's (H, W) region labels: 0 where transparent, else the region (from 1) of the pixel's colour, or, for a colour
    `regions` didn't see, the region of the nearest colour it did (OKLab)."""
    out = np.zeros(frame.shape[:2], dtype=np.uint8)
    opaque = frame[..., 3] == 255
    if not opaque.any() or len(regions.colours) == 0:
        return out
    colours, inverse = np.unique(frame[..., :3][opaque], axis=0, return_inverse=True)
    known = srgb_to_oklab(regions.colours)
    lab = srgb_to_oklab(colours)
    nearest = np.sqrt(((lab[:, None, :] - known[None, :, :]) ** 2).sum(axis=2)).argmin(axis=1)
    out[opaque] = regions.region[nearest][inverse.ravel()].astype(np.uint8)
    return out
