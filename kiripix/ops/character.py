"""Ops for a character's palette and its normal map (spec §6.3, §7; ADR 0004).

Pure numpy: arrays in, arrays out. Mapping and orphan cleanup are the room's Ops (`quantize`, `remove_orphans`); this
module adds the one choice a character needs on top, which palette colours all its frames share, and the normal pass,
which is never palette-mapped.
"""

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from kiripix.ops.colour import srgb_to_oklab

U8 = npt.NDArray[np.uint8]
F64 = npt.NDArray[np.float64]

_DECIMALS = 9


def palette_subset(frames: Sequence[U8], palette_rgb: U8, n: int) -> U8:
    """The `n` palette colours that best fit every opaque pixel of all the frames together, in palette order.

    "Best" is the smallest total OKLab distance from each opaque pixel to its nearest chosen colour. Colours are added
    greedily, each the one that lowers the total most; a tie in the (rounded) total goes to the earlier palette colour.
    The result is one subset for the whole character, so mapping every frame onto it can't give a frame a colour that
    another frame lacks. With `n` at or above the palette's size, the whole palette comes back. With no opaque pixel
    at all, the first `n` palette colours do. Only opaque (alpha 255) pixels count; the frames may differ in size.
    """
    if n < 1:
        raise ValueError("n must be at least 1")
    if palette_rgb.ndim != 2 or palette_rgb.shape[1] != 3 or len(palette_rgb) == 0:
        raise ValueError("expected a non-empty (N, 3) palette")
    size = len(palette_rgb)
    if n >= size:
        return palette_rgb.copy()
    pixels = [f[..., :3][f[..., 3] == 255].reshape(-1, 3) for f in frames]
    opaque = np.concatenate(pixels) if pixels else np.zeros((0, 3), dtype=np.uint8)
    if len(opaque) == 0:
        return palette_rgb[:n].copy()
    colours, counts = np.unique(opaque, axis=0, return_counts=True)
    lab = srgb_to_oklab(colours)
    palette_lab = srgb_to_oklab(palette_rgb)
    distance = np.sqrt(((lab[:, None, :] - palette_lab[None, :, :]) ** 2).sum(axis=2))
    weight = counts.astype(np.float64)
    nearest = np.full(len(colours), np.inf)
    chosen: list[int] = []
    for _ in range(n):
        total = (weight[:, None] * np.minimum(nearest[:, None], distance)).sum(axis=0)
        total = np.round(total / weight.sum(), _DECIMALS)
        total[chosen] = np.inf
        pick = int(total.argmin())
        chosen.append(pick)
        nearest = np.minimum(nearest, distance[:, pick])
    return palette_rgb[np.array(sorted(chosen), dtype=np.intp)].copy()


def _decode(normal: U8) -> F64:
    return normal[..., :3].astype(np.float64) / 255.0 * 2.0 - 1.0


def _unit(vectors: F64) -> F64:
    """Scale to length 1; a zero vector becomes (0, 0, 1), a normal facing the viewer."""
    length = np.sqrt((vectors**2).sum(axis=-1, keepdims=True))
    flat = length < 1e-9
    out: F64 = np.where(flat, np.array([0.0, 0.0, 1.0]), vectors / np.where(flat, 1.0, length))
    return out


def _to_bytes(vectors: F64) -> U8:
    scaled = np.round((vectors * 0.5 + 0.5) * 255.0, 6)
    out: U8 = np.clip(np.floor(scaled + 0.5), 0, 255).astype(np.uint8)
    return out


def _check_normal(normal: U8) -> None:
    if normal.ndim != 3 or normal.shape[2] != 4 or normal.dtype != np.uint8:
        raise ValueError("expected an (H, W, 4) uint8 RGBA normal pass")
    alpha = normal[..., 3]
    if ((alpha != 0) & (alpha != 255)).any():
        raise ValueError("the normal pass has partially transparent pixels")


def quantise_normals(normal: U8, levels: int) -> U8:
    """Quantise a normal pass to `levels` values per axis, then renormalise. Never palette-mapped.

    `normal` is an (H, W, 4) uint8 RGBA pass in the view-space encoding of `encode_normals`' docstring: R, G, B are
    X, Y, Z as (v + 1) / 2 * 255. Each axis is rounded (half up) to one of `levels` evenly spaced values over [-1, 1],
    the vector is scaled back to length 1, and the result is encoded the same way. One level puts every axis at 0, a
    zero vector, which becomes (0, 0, 1): a flat map facing the viewer. Alpha 0 pixels stay (0, 0, 0, 0); alpha 255
    pixels keep alpha 255; any other alpha is refused. `levels` is 1 to 256.
    """
    if not 1 <= levels <= 256:
        raise ValueError("levels must be from 1 to 256")
    _check_normal(normal)
    vectors = _decode(normal)
    if levels == 1:
        vectors = np.zeros_like(vectors)
    else:
        steps = levels - 1
        vectors = np.floor(np.round((vectors + 1.0) / 2.0 * steps, _DECIMALS) + 0.5) / steps * 2.0 - 1.0
    out = np.zeros_like(normal)
    opaque = normal[..., 3] == 255
    out[..., :3] = np.where(opaque[..., None], _to_bytes(_unit(vectors)), 0)
    out[..., 3] = np.where(opaque, 255, 0)
    return out


def encode_normals(normal: U8) -> U8:
    """The normal pass as Godot 4.7 expects it in a `CanvasTexture`'s normal map.

    Input and output are (H, W, 4) uint8 RGBA, alpha 0 or 255. The input is Blender's camera-space normal pass
    (X right, Y up, Z toward the camera, each as (v + 1) / 2 * 255). The output follows the OpenGL convention that
    Godot's normal maps use (Godot docs, "Using 2D lights and shadows", normal maps): red is X, +X to the right; green
    is Y, +Y up in the image; blue is Z, +Z toward the viewer; a flat normal is (128, 128, 255). Both conventions have
    the same axes, so no channel is flipped. What the encoding does do: a normal facing away from the camera (Z below
    0) can't be stored, so its Z is set to 0 before the vector is renormalised; the length is 1 within the byte's
    rounding. Alpha 0 pixels stay (0, 0, 0, 0). NOTE: the Y direction is the one thing to confirm in Godot 4.7 under a
    `PointLight2D` (ticket 0113, the gate); if it lights from the wrong side, flip G here and in the goldens.
    """
    _check_normal(normal)
    vectors = _decode(normal)
    vectors[..., 2] = np.maximum(vectors[..., 2], 0.0)
    out = np.zeros_like(normal)
    opaque = normal[..., 3] == 255
    out[..., :3] = np.where(opaque[..., None], _to_bytes(_unit(vectors)), 0)
    out[..., 3] = np.where(opaque, 255, 0)
    return out
