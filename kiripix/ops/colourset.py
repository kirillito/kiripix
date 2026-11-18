"""One set of colours for several images (spec §7): chosen once over all of them, then each image mapped to it.

Pure numpy. The set is found by k-means in OKLab over the opaque pixels of every image together, each image weighted
equally. The result doesn't depend on the order of the images: colours and weights are merged in a canonical order.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kiripix.ops.colour import BayerSize, has_partial_alpha, quantize, srgb_to_oklab
from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt
else:
    np = lazy_module("numpy")
    npt = lazy_module("numpy.typing")

_LLOYD_ROUNDS = 24
_ROUND = 12



@dataclass(frozen=True)
class SetReport:
    """How well the set serves one image: OKLab distance, mean and 95th percentile, and the colours it uses."""

    mean_error: float
    p95_error: float
    colours: "npt.NDArray[np.uint8]"  # (K, 3), in palette order


def _opaque(image: "npt.NDArray[np.uint8]", alpha: "npt.NDArray[np.generic] | None") -> "npt.NDArray[np.bool_]":
    if image.ndim != 3 or image.shape[2] not in (3, 4):
        raise ValueError("expected an (H, W, 3) or (H, W, 4) image")
    if alpha is None:
        if image.shape[2] == 3:
            return np.ones(image.shape[:2], dtype=np.bool_)
        alpha = image[..., 3]
    if alpha.shape != image.shape[:2]:
        raise ValueError("an alpha differs in size from its image")
    if ((alpha != 0) & (alpha != 255) & (alpha != 1)).any():
        raise ValueError("the image has partially transparent pixels")
    out: npt.NDArray[np.bool_] = alpha != 0
    return out


def set_colours(
    images: "Sequence[npt.NDArray[np.uint8]]",
    alphas: "Sequence[npt.NDArray[np.generic]] | None",
    n: int,
    keep: "npt.NDArray[np.uint8] | Sequence[Sequence[int]]" = (),
) -> "npt.NDArray[np.uint8]":
    """Up to `n` sRGB colours, an (K, 3) uint8 array, that serve every image's opaque pixels together.

    `alphas` gives each image's opaque mask (non-zero is opaque); None reads the image's own alpha channel. Each image
    counts equally, however many opaque pixels it has. The `keep` colours come first and stay exactly as given. The rest
    are k-means clusters in OKLab, seeded where the weighted pixels are worst served (ties go to the smaller colour)
    and refined by fixed Lloyd rounds. Exactly `n` come back when the opaque pixels have at least `n` distinct colours (a centre that rounds onto another
    colour is replaced by the worst-served pixel colour); fewer come back only when they have fewer.
    """
    if n < 1:
        raise ValueError("n must be at least 1")
    keep_rgb = np.asarray(keep, dtype=np.uint8).reshape(-1, 3)
    kept = np.unique(keep_rgb, axis=0, return_index=True)[1]
    keep_rgb = keep_rgb[np.sort(kept)]
    if len(keep_rgb) > n:
        raise ValueError("more keep colours than n")
    if alphas is not None and len(alphas) != len(images):
        raise ValueError("alphas and images differ in number")

    colour_parts: list[npt.NDArray[np.uint8]] = []
    weight_parts: list[npt.NDArray[np.float64]] = []
    for i, image in enumerate(images):
        mask = _opaque(image, None if alphas is None else alphas[i])
        pixels = image[..., :3][mask]
        if len(pixels) == 0:
            continue
        colours, counts = np.unique(pixels, axis=0, return_counts=True)
        colour_parts.append(colours)
        weight_parts.append(counts.astype(np.float64) / len(pixels))
    if not colour_parts:
        return keep_rgb
    allc = np.concatenate(colour_parts)
    allw = np.concatenate(weight_parts)
    order = np.lexsort((allw, allc[:, 2], allc[:, 1], allc[:, 0]))
    allc, allw = allc[order], allw[order]
    colours, start = np.unique(allc, axis=0, return_index=True)  # sorted by colour; `start` ascending
    w = np.add.reduceat(allw, start)
    lab = srgb_to_oklab(colours)
    fixed = srgb_to_oklab(keep_rgb) if len(keep_rgb) else np.zeros((0, 3))

    want = min(n - len(keep_rgb), len(colours))
    nearest = (
        np.sqrt(((lab[:, None, :] - fixed[None, :, :]) ** 2).sum(axis=2).min(axis=1))
        if len(fixed)
        else np.full(len(lab), np.inf)
    )
    seeds: list[int] = []
    for _ in range(want):
        score = np.round(w * np.where(np.isinf(nearest), 1.0, nearest**2), _ROUND)
        pick = int(score.argmax())  # ties go to the smaller colour: `colours` is sorted
        if score[pick] <= 0.0:
            break
        seeds.append(pick)
        nearest = np.minimum(nearest, np.sqrt(((lab - lab[pick]) ** 2).sum(axis=1)))
    if not seeds:
        return keep_rgb

    new = lab[seeds].copy()
    owner = np.zeros(len(lab), dtype=np.intp)
    for _ in range(_LLOYD_ROUNDS):
        both = np.concatenate([fixed, new])
        d2 = np.round(((lab[:, None, :] - both[None, :, :]) ** 2).sum(axis=2), _ROUND)
        owner = d2.argmin(axis=1)
        moved = False
        for k in range(len(new)):
            members = owner == len(fixed) + k
            if members.any():
                centre = (lab[members] * w[members, None]).sum(axis=0) / w[members].sum()
                if not np.array_equal(centre, new[k]):
                    new[k] = centre
                    moved = True
        if not moved:
            break

    rgb_f = colours.astype(np.float64)
    found: list[tuple[float, tuple[int, int, int]]] = []
    for k in range(len(new)):
        members = owner == len(fixed) + k
        if not members.any():
            continue
        mean = (rgb_f[members] * w[members, None]).sum(axis=0) / w[members].sum()
        rgb = (int(np.round(mean[0])), int(np.round(mean[1])), int(np.round(mean[2])))
        found.append((float(w[members].sum()), rgb))
    found.sort(key=lambda item: (-round(item[0], _ROUND), item[1]))
    result = [tuple(int(v) for v in c) for c in keep_rgb]
    for _, rgb in found:
        if rgb not in result:
            result.append(rgb)
    # A mean that rounded onto an earlier colour, or an empty cluster, leaves a gap: fill it with the colour the set
    # serves worst (largest weight times squared distance; ties go to the smaller colour).
    while len(result) < min(n, len(colours)):
        have = srgb_to_oklab(np.array(result, dtype=np.uint8).reshape(-1, 3))
        d2 = ((lab[:, None, :] - have[None, :, :]) ** 2).sum(axis=2).min(axis=1)
        score = np.round(w * d2, _ROUND)
        pick = int(score.argmax())
        if score[pick] <= 0.0 or tuple(int(v) for v in colours[pick]) in result:
            break
        result.append(tuple(int(v) for v in colours[pick]))
    return np.array(result, dtype=np.uint8).reshape(-1, 3)


def map_set(
    images: "Sequence[npt.NDArray[np.uint8]]", palette: "npt.NDArray[np.uint8]", dither: BayerSize = 0
) -> "list[npt.NDArray[np.uint8]]":
    """Each (H, W, 4) RGBA image mapped to the set's colours by `quantize`: nearest in OKLab, with ordered dither.

    Alpha 0 stays (0, 0, 0, 0); partial alpha is refused.
    """
    out = []
    for image in images:
        if image.ndim != 3 or image.shape[2] != 4:
            raise ValueError("expected an (H, W, 4) RGBA image")
        if has_partial_alpha(image):
            raise ValueError("the image has partially transparent pixels")
        out.append(quantize(image, palette, dither))
    return out


def set_report(
    before: "Sequence[npt.NDArray[np.uint8]]", after: "Sequence[npt.NDArray[np.uint8]]"
) -> list[SetReport]:
    """Per image, the mean and 95th-percentile OKLab error of the mapping, and the colours it uses."""
    if len(before) != len(after):
        raise ValueError("before and after differ in number")
    reports = []
    for a, b in zip(before, after, strict=True):
        if a.shape != b.shape:
            raise ValueError("an image differs in size from its mapped image")
        both = (a[..., 3] == 255) & (b[..., 3] == 255)
        if not both.any():
            reports.append(SetReport(0.0, 0.0, np.zeros((0, 3), dtype=np.uint8)))
            continue
        delta = srgb_to_oklab(a[..., :3][both]) - srgb_to_oklab(b[..., :3][both])
        dist = np.sqrt((delta**2).sum(axis=-1))
        used = np.unique(b[..., :3][both], axis=0)
        reports.append(SetReport(float(dist.mean()), float(np.percentile(dist, 95)), used))
    return reports
