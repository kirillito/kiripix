"""Chroma key (spec §6.2, §7): remove a flat background colour exactly. Pure numpy; deterministic."""

from __future__ import annotations

from typing import TYPE_CHECKING
from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.ops.colour import U8, srgb_to_oklab
from kiripix.ops.resample import BoolMask


def _check_rgba(rgba: U8) -> None:
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise ValueError("expected an (H, W, 4) uint8 RGBA image")


def chroma_key(rgba: U8, key: tuple[int, int, int]) -> U8:
    """`rgba` with every pixel whose colour is exactly `key` cleared to (0, 0, 0, 0).

    Exact: a pixel one level off the key stays. Pixels that were already fully transparent are cleared too, so equal
    transparent pixels are equal. Alpha of the other pixels is untouched, partial or not. The input is not modified.
    """
    _check_rgba(rgba)
    if len(key) != 3 or any(not 0 <= value <= 255 for value in key):
        raise ValueError(f"the key is three numbers from 0 to 255, got {key}")
    out = rgba.copy()
    background = (rgba[..., :3] == np.array(key, dtype=np.uint8)).all(axis=2) | (rgba[..., 3] == 0)
    out[background] = 0
    return out


def key_fringe(rgba: U8, key: tuple[int, int, int], distance: float) -> BoolMask:
    """The pixels a chroma key left that look like leftover background: opaque, not exactly the key, within `distance`
    of it in OKLab, and touching (along an edge) a cleared pixel. Run it on the keyed image."""
    _check_rgba(rgba)
    if distance < 0:
        raise ValueError(f"the distance can't be negative, got {distance}")
    opaque = rgba[..., 3] != 0
    key_lab = srgb_to_oklab(np.array(key, dtype=np.uint8))
    near = np.sqrt(((srgb_to_oklab(rgba[..., :3]) - key_lab) ** 2).sum(axis=2)) <= distance
    cleared = ~opaque
    touching = np.zeros_like(cleared)
    touching[1:, :] |= cleared[:-1, :]
    touching[:-1, :] |= cleared[1:, :]
    touching[:, 1:] |= cleared[:, :-1]
    touching[:, :-1] |= cleared[:, 1:]
    result: BoolMask = opaque & near & touching
    return result


# A flat background that a lossy codec has made uneven (ticket 0243): a key with a tolerance, then what the codec and the
# image model leave round the figure.


def border_colour(rgba: U8, margin: int = 30) -> tuple[int, int, int]:
    """The flat background's colour as the border shows it: the median of each channel over the top `margin` rows and the
    `margin` columns at each side, down to two thirds of the height (the figure may stand on the bottom edge). Pixels that
    are fully transparent don't count; an image with none left is an error."""
    _check_rgba(rgba)
    if margin < 1:
        raise ValueError(f"the margin is at least 1, got {margin}")
    height = rgba.shape[0]
    side = max(height * 2 // 3, 1)
    parts = [rgba[:margin], rgba[:side, :margin], rgba[:side, -margin:]]
    border = np.concatenate([part.reshape(-1, 4) for part in parts])
    border = border[border[:, 3] != 0]
    if len(border) == 0:
        raise ValueError("the border has no opaque pixel to read the background from")
    r, g, b = (int(v) for v in np.median(border[:, :3], axis=0))
    return r, g, b


def chroma_key_tolerant(rgba: U8, key: tuple[int, int, int], tolerance: float) -> U8:
    """`rgba` with every pixel within `tolerance` of `key` in OKLab (distance, 0 is exact) cleared to (0, 0, 0, 0), and every
    pixel that was already transparent. With 0 it is `chroma_key`. The input is not modified."""
    _check_rgba(rgba)
    if tolerance < 0:
        raise ValueError(f"the tolerance can't be negative, got {tolerance}")
    if tolerance == 0:
        return chroma_key(rgba, key)
    if len(key) != 3 or any(not 0 <= value <= 255 for value in key):
        raise ValueError(f"the key is three numbers from 0 to 255, got {key}")
    distance = np.sqrt(((srgb_to_oklab(rgba[..., :3]) - srgb_to_oklab(np.array(key, dtype=np.uint8))) ** 2).sum(axis=2))
    out = rgba.copy()
    out[(distance <= tolerance) | (rgba[..., 3] == 0)] = 0
    return out


def _grow_into(cleared: BoolMask, candidates: BoolMask, reach: int) -> BoolMask:
    """`cleared` grown, one 8-neighbour step at a time for up to `reach` steps, through `candidates` only."""
    gone = cleared.copy()
    for _ in range(reach):
        padded = np.pad(gone, 1)
        near = np.zeros_like(gone)
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                near |= padded[dy:dy + gone.shape[0], dx:dx + gone.shape[1]]
        grown = gone | (candidates & near)
        if (grown == gone).all():
            break
        gone = grown
    result: BoolMask = gone
    return result


def remove_key_spill(rgba: U8, key: tuple[int, int, int], reach: int = 3, excess: float = 20.0) -> U8:
    """Clear the key's spill on the edge: opaque pixels within `reach` pixels (8-connected steps) of a cleared pixel,
    reaching it only through such pixels, whose colour leans toward the key's. The lean is how far the pixel's colour, with its
    mean grey taken off, lies along the key's own (the same taking-off), in 0..255 levels: over `excess` is spill. A key
    that is grey has no lean, so nothing is cleared. 0 reach clears nothing. The input is not modified."""
    _check_rgba(rgba)
    if reach < 0 or excess < 0:
        raise ValueError("the reach and the excess can't be negative")
    out = rgba.copy()
    key_rgb = np.array(key, dtype=np.float64)
    axis = key_rgb - key_rgb.mean()
    length = float(np.sqrt((axis**2).sum()))
    if reach == 0 or length == 0:
        return out
    rgb = rgba[..., :3].astype(np.float64)
    lean = ((rgb - rgb.mean(axis=2, keepdims=True)) * (axis / length)).sum(axis=2)
    cleared = rgba[..., 3] == 0
    gone = _grow_into(cleared, (lean > excess) & ~cleared, reach)
    out[gone & ~cleared] = 0
    return out


def remove_light_rim(rgba: U8, reach: int = 10, lightness: float = 0.8, chroma: float = 0.09) -> U8:
    """Clear a light rim round the figure, the sticker edge an image model draws: opaque pixels lighter than `lightness`
    (OKLab L) and less coloured than `chroma` (OKLab a, b length) that join a cleared pixel through such pixels within
    `reach` pixels (8-connected steps). The figure's own white (an eye's highlight) is safe unless it is within that reach
    of the cleared background. 0 reach clears nothing. The input is not modified."""
    _check_rgba(rgba)
    if reach < 0:
        raise ValueError("the reach can't be negative")
    out = rgba.copy()
    if reach == 0:
        return out
    lab = srgb_to_oklab(rgba[..., :3])
    cleared = rgba[..., 3] == 0
    light = (lab[..., 0] > lightness) & (np.hypot(lab[..., 1], lab[..., 2]) < chroma) & ~cleared
    gone = _grow_into(cleared, light, reach)
    out[gone & ~cleared] = 0
    return out
