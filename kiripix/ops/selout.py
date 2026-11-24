"""Sel-out lines (ticket 0382, spec §6.3): a line pixel takes the colour of the part it borders, the darker one where it borders two,
in place of one colour for every line. Pure: arrays in, an array out.

A frame's `labels` is its material pass (0 the background, else the part's index) and `colours` maps a label to the colour of its
line, normally the darkest colour of its part's ramp. The candidates of a pixel are its own label and those of its four
neighbours (so an outline pixel outside the silhouette, which has no label of its own, has the parts it touches, and an inner
line has its own part and the one across the border). The darkest candidate wins: the lowest luma, a tie going to the lower
label, so the result doesn't depend on which side of a border is looked at."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from kiripix.ops.cleanup import Placement, outline_mask
from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt
else:
    np = lazy_module("numpy")
    npt = lazy_module("numpy.typing")

_LUMA = (0.2126, 0.7152, 0.0722)
_LABELS = 256


def _table(colours: Mapping[int, tuple[int, int, int]]) -> tuple[npt.NDArray[np.uint8], npt.NDArray[np.float64]]:
    """The colour of each label (256 x 3) and its rank, luma plus a tie-break by label, infinite for a label with no colour."""
    rgb = np.zeros((_LABELS, 3), dtype=np.uint8)
    rank = np.full(_LABELS, np.inf)
    for label, colour in colours.items():
        if not 0 < int(label) < _LABELS:
            raise ValueError(f"a label is 1 to {_LABELS - 1}, not {label}")
        rgb[int(label)] = colour
        rank[int(label)] = round(float(np.array(colour, dtype=np.float64) @ np.array(_LUMA)), 6) + int(label) * 1e-9
    return rgb, rank


def sel_out_paint(
    rgba: npt.NDArray[np.uint8],
    labels: npt.NDArray[np.integer[Any]],
    target: npt.NDArray[np.bool_],
    colours: Mapping[int, tuple[int, int, int]],
    fallback: tuple[int, int, int] | None = None,
) -> npt.NDArray[np.uint8]:
    """`rgba` with the pixels of the Mask `target` painted, opaque, in the darkest line colour among their own label and their four
    neighbours' (see the module). A target pixel with no label that has a colour gets `fallback`, or stays as it is with none.
    The input is not changed."""
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("expected an (H, W, 4) RGBA image")
    if labels.shape != rgba.shape[:2] or target.shape != labels.shape:
        raise ValueError("the frame, its label image and the target Mask differ in size")
    rgb, rank = _table(colours)
    padded = np.pad(labels.astype(np.int64), 1)
    around = np.stack([padded[1:-1, 1:-1], padded[:-2, 1:-1], padded[2:, 1:-1], padded[1:-1, :-2], padded[1:-1, 2:]])
    ranks = rank[np.clip(around, 0, _LABELS - 1)]
    ranks = np.where(around > 0, ranks, np.inf)
    best = np.take_along_axis(around, ranks.argmin(axis=0)[None], axis=0)[0]
    known = np.isfinite(ranks.min(axis=0))
    out = rgba.copy()
    chosen = target & known
    out[chosen] = np.concatenate([rgb[best[chosen]], np.full((int(chosen.sum()), 1), 255, dtype=np.uint8)], axis=1)
    if fallback is not None:
        out[target & ~known] = (*fallback, 255)
    return out


def sel_out_outline(
    rgba: npt.NDArray[np.uint8],
    labels: npt.NDArray[np.integer[Any]],
    colours: Mapping[int, tuple[int, int, int]],
    fallback: tuple[int, int, int],
    placement: Placement = "outside",
) -> npt.NDArray[np.uint8]:
    """The silhouette's outline (`outline_mask` of the alpha) painted by `sel_out_paint`: each outline pixel in the darkest line
    colour of the part or parts it borders. `fallback` is for a pixel whose parts have no colour."""
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("expected an (H, W, 4) RGBA image")
    return sel_out_paint(rgba, labels, outline_mask(rgba[..., 3] > 0, placement), colours, fallback)
