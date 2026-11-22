"""The style measures (ticket 0333, trial 0332): numbers read off a painted RGBA image, to compare an Asset with the
Project's others. Pure: arrays in, frozen dataclasses of numbers out.

Two measures were kept by the Owner: the outline's density on a figure's edge, and the pixel scale (a run-length gcd that
reads 2 or more when an image was upscaled). Palette use, value range, saturation range and light direction were dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

    RGBAImage = NDArray[np.uint8]
else:
    np = lazy_module("numpy")


@dataclass(frozen=True)
class OutlineMeasure:
    outline_px: int
    """Opaque pixels of exactly the outline colour."""
    edge_px: int
    """Opaque pixels with a transparent (or out-of-image) 4-neighbour: the silhouette's edge."""
    density: float
    """`outline_px / edge_px`; 0.0 when there is no edge. Near 1 or above: drawn with an outline; near 0: without."""


@dataclass(frozen=True)
class ScaleMeasure:
    runs: int
    """Runs of one colour among opaque pixels, along every row and every column."""
    gcd: int
    """The greatest common divisor of all run lengths: 2 or more means the image was upscaled by that factor. 0 if no runs."""
    median: float
    """The median run length; 0.0 if no runs."""
    run1_share: float
    """The share of runs of length 1."""


def outline_density(image: RGBAImage, outline_rgb: tuple[int, int, int]) -> OutlineMeasure:
    """How much of the silhouette's edge is the outline colour. Opaque is alpha > 0; the edge is an opaque pixel with a
    non-opaque 4-neighbour, the image border counting as non-opaque."""
    opaque = image[..., 3] > 0
    padded = np.pad(opaque, 1)
    inside = padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
    edge = opaque & ~inside
    ink = opaque & np.all(image[..., :3] == np.array(outline_rgb, dtype=np.uint8), axis=-1)
    edge_px, outline_px = int(edge.sum()), int(ink.sum())
    return OutlineMeasure(outline_px, edge_px, outline_px / edge_px if edge_px else 0.0)


def _run_lengths(key: NDArray[np.int64]) -> NDArray[np.int64]:
    """Lengths of the runs of equal non-negative values along axis 1 of `key`; negative values are gaps and end a run."""
    padded = np.full((key.shape[0], key.shape[1] + 2), -1, dtype=np.int64)
    padded[:, 1:-1] = key
    flat = padded.ravel()
    changes = np.flatnonzero(flat[1:] != flat[:-1]) + 1  # every place the value changes (the -1 columns separate rows)
    edges = np.concatenate(([0], changes, [flat.size]))
    return np.diff(edges)[flat[edges[:-1]] >= 0]


def pixel_scale(image: RGBAImage) -> ScaleMeasure:
    """The run-length gcd of an image: runs of one RGB colour among opaque pixels, along rows and columns. Pass the
    image cut to its opaque box, so the border does not matter."""
    opaque = image[..., 3] > 0
    rgb = image[..., :3].astype(np.int64)
    key = np.where(opaque, (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2], -1)
    runs = np.concatenate((_run_lengths(key), _run_lengths(np.ascontiguousarray(key.T))))
    if runs.size == 0:
        return ScaleMeasure(0, 0, 0.0, 0.0)
    return ScaleMeasure(int(runs.size), int(np.gcd.reduce(runs)), float(np.median(runs)), float((runs == 1).mean()))
