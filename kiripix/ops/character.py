"""Ops for a character's palette and its normal map (spec §6.3, §7; ADR 0004).

Pure numpy: arrays in, arrays out. Mapping and orphan cleanup are the room's Ops (`quantize`, `remove_orphans`); this
module adds the one choice a character needs on top, which palette colours all its frames share, and the normal pass,
which is never palette-mapped.
"""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Collection, Mapping, Sequence

from typing import TYPE_CHECKING, Any
from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
if TYPE_CHECKING:
    import numpy.typing as npt
else:
    npt = lazy_module("numpy.typing")

from kiripix.ops.colour import BayerSize, has_partial_alpha, quantize, srgb_to_oklab

if TYPE_CHECKING:
    U8 = npt.NDArray[np.uint8]
else:
    U8 = Any  # the array types are for the type checker; numpy loads late
if TYPE_CHECKING:
    F64 = npt.NDArray[np.float64]
else:
    F64 = Any  # the array types are for the type checker; numpy loads late

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


def _check_parts(parts: Mapping[str, Collection[int]]) -> None:
    owner: dict[int, str] = {}
    for name, materials in parts.items():
        for material in materials:
            if material in owner:
                raise ValueError(f"material {material} is in both part {owner[material]!r} and part {name!r}")
            owner[material] = name


def _part_mask(frame: U8, labels: npt.NDArray[np.integer[Any]], materials: Collection[int]) -> npt.NDArray[np.bool_]:
    mask: npt.NDArray[np.bool_] = (frame[..., 3] == 255) & np.isin(labels, np.array(sorted(materials), dtype=np.int64))
    return mask


def part_ramps(
    frames: Sequence[U8],
    labels: Sequence[npt.NDArray[np.integer[Any]]],
    parts: Mapping[str, Collection[int]],
    palette: U8,
    steps: Mapping[str, int],
    reserved: U8,
) -> dict[str, U8]:
    """For each part, the `steps[part]` palette colours that best fit its opaque pixels, dark to light.

    `labels[i]` is frame i's (H, W) image of material indexes; a part owns a set of materials. Fit is as in
    `palette_subset`: the smallest total OKLab distance from the part's opaque pixels (all frames together) to their
    nearest ramp colour, colours added greedily, a tie in the rounded total going to the earlier palette colour. No
    colour is in two ramps, nor equal to a `reserved` colour (an (N, 3) array; every palette entry of that colour is
    out). When parts want the same colour, the part that loses least by being denied it (in total distance, not
    mean, so a big part outweighs a small one; a tie goes to the earlier part in `parts`) takes its next-best colour,
    colour by colour from the lowest palette index, until nobody clashes. Each ramp is in order of OKLab lightness,
    ties by palette index. A part that can't get `steps` free colours raises ValueError naming it.
    """
    if palette.ndim != 2 or palette.shape[1] != 3 or len(palette) == 0:
        raise ValueError("expected a non-empty (N, 3) palette")
    if len(frames) != len(labels):
        raise ValueError("every frame needs a label image")
    _check_parts(parts)
    names = list(parts)
    for name in names:
        if steps.get(name, 0) < 1:
            raise ValueError(f"part {name!r} needs at least 1 step")
    size = len(palette)
    blocked = np.zeros(size, dtype=bool)
    if len(reserved):
        blocked = (palette[:, None, :] == reserved.reshape(-1, 3)[None, :, :]).all(axis=2).any(axis=1)
    palette_lab = srgb_to_oklab(palette)
    distance: dict[str, F64] = {}
    weight: dict[str, F64] = {}
    for name in names:
        pixels = [f[..., :3][_part_mask(f, lab, parts[name])] for f, lab in zip(frames, labels, strict=True)]
        opaque = np.concatenate(pixels) if pixels else np.zeros((0, 3), dtype=np.uint8)
        if len(opaque):
            colours, counts = np.unique(opaque, axis=0, return_counts=True)
            lab = srgb_to_oklab(colours)
            distance[name] = np.sqrt(((lab[:, None, :] - palette_lab[None, :, :]) ** 2).sum(axis=2))
            weight[name] = counts.astype(np.float64)
        else:
            distance[name] = np.zeros((0, size))
            weight[name] = np.zeros(0)

    def select(name: str, banned: set[int]) -> tuple[list[int], float]:
        out_of_play = blocked.copy()
        out_of_play[sorted(banned)] = True
        free = int((~out_of_play).sum())
        if free < steps[name]:
            raise ValueError(f"part {name!r} needs {steps[name]} colours, and the palette has only {free} left for it")
        nearest = np.full(len(weight[name]), np.inf)
        chosen: list[int] = []
        for _ in range(steps[name]):
            total = (weight[name][:, None] * np.minimum(nearest[:, None], distance[name])).sum(axis=0)
            total = np.round(total, _DECIMALS)
            total[out_of_play] = np.inf
            total[chosen] = np.inf
            pick = int(total.argmin())
            chosen.append(pick)
            nearest = np.minimum(nearest, distance[name][:, pick])
        cost = float(np.round((weight[name] * nearest).sum(), _DECIMALS)) if len(nearest) else 0.0
        return chosen, cost

    banned: dict[str, set[int]] = {name: set() for name in names}
    picks = {name: select(name, banned[name]) for name in names}
    while True:
        wanted: dict[int, list[str]] = {}
        for name in names:
            for colour in picks[name][0]:
                wanted.setdefault(colour, []).append(name)
        clash = sorted(c for c, who in wanted.items() if len(who) > 1)
        if not clash:
            break
        colour = clash[0]
        losses = {name: select(name, banned[name] | {colour})[1] - picks[name][1] for name in wanted[colour]}
        loser = min(wanted[colour], key=lambda name: (round(losses[name], _DECIMALS), names.index(name)))
        banned[loser].add(colour)
        picks[loser] = select(loser, banned[loser])
    ramps: dict[str, U8] = {}
    for name in names:
        order = sorted(picks[name][0], key=lambda i: (round(float(palette_lab[i, 0]), _DECIMALS), i))
        ramps[name] = palette[np.array(order, dtype=np.intp)].copy()
    return ramps


def quantize_by_part(
    frame: U8,
    labels: npt.NDArray[np.integer[Any]],
    parts: Mapping[str, Collection[int]],
    ramps: Mapping[str, U8],
    fixed: U8,
    dither: BayerSize = 0,
    strength: float = 1.0,
) -> U8:
    """Map each opaque pixel onto its own part's ramp, or onto `fixed` when its material is in no part.

    Mapping is `quantize`'s, OKLab nearest, run once per part on that part's pixels only. An ordered dither
    (`dither` 2, 4 or 8) offsets lightness by `strength` times the spread of that ramp alone, with the Bayer cell
    taken from the pixel's position in the frame, so a dithered pixel never leaves its ramp. Alpha as in `quantize`:
    0 stays (0, 0, 0, 0), anything but 0 and 255 is refused.
    """
    if labels.shape != frame.shape[:2]:
        raise ValueError("the label image and the frame differ in size")
    if frame.ndim != 3 or frame.shape[2] != 4:
        raise ValueError("expected an (H, W, 4) RGBA image")
    if has_partial_alpha(frame):
        raise ValueError("the image has partially transparent pixels")
    _check_parts(parts)
    out = np.zeros_like(frame)
    opaque = frame[..., 3] == 255
    in_part = np.zeros(opaque.shape, dtype=bool)
    groups: list[tuple[npt.NDArray[np.bool_], U8]] = []
    for name, materials in parts.items():
        mask = _part_mask(frame, labels, materials)
        in_part |= mask
        groups.append((mask, ramps[name]))
    groups.append((opaque & ~in_part, fixed))
    for mask, colours in groups:
        if not mask.any():
            continue
        only = frame.copy()
        only[..., 3] = np.where(mask, 255, 0)
        mapped = quantize(only, colours, dither, strength)
        out[mask] = mapped[mask]
    return out


def remove_orphans_by_part(
    rgba: U8,
    labels: npt.NDArray[np.integer[Any]],
    parts: Mapping[str, Collection[int]],
    orphan_size: int,
) -> U8:
    """`remove_orphans` that keeps parts apart.

    An island is a 4-connected region of one colour and one material. One of at most `orphan_size` pixels takes the
    most common colour among the regions that touch it, but only regions larger than `orphan_size`, of its own part
    (a material in no part is a part of its own), and of another colour; a tie goes to the smaller (r, g, b). It
    keeps its colour when no such region touches it. An island that touches no pixel of its own material is kept:
    it is all of its material there, a detail such as an eye, not a speck of shading. Size 0 changes nothing.
    """
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("expected an (H, W, 4) RGBA image")
    if labels.shape != rgba.shape[:2]:
        raise ValueError("the label image and the frame differ in size")
    if orphan_size < 0:
        raise ValueError("orphan_size can't be negative")
    _check_parts(parts)
    out = rgba.copy()
    if orphan_size == 0:
        return out
    height, width = rgba.shape[:2]
    owner = {material: index for index, materials in enumerate(parts.values()) for material in materials}
    material = labels.astype(np.int64).ravel().tolist()
    group = [owner.get(m, -1 - m) for m in material]  # a material in no part is its own group
    packed = (
        (rgba[..., 0].astype(np.int64) << 16) | (rgba[..., 1].astype(np.int64) << 8) | rgba[..., 2].astype(np.int64)
    )
    flat = np.where(rgba[..., 3] == 255, packed, -1).ravel().tolist()
    label = [-1] * (height * width)
    regions: list[list[int]] = []

    def around(at: int) -> list[int]:
        y, x = divmod(at, width)
        return [to for ok, to in ((y > 0, at - width), (y < height - 1, at + width), (x > 0, at - 1),
                                  (x < width - 1, at + 1)) if ok]

    for start in range(height * width):
        if flat[start] < 0 or label[start] >= 0:
            continue
        found = len(regions)
        members = [start]
        label[start] = found
        queue = deque([start])
        while queue:
            at = queue.popleft()
            for to in around(at):
                if label[to] < 0 and flat[to] == flat[start] and material[to] == material[start]:
                    label[to] = found
                    members.append(to)
                    queue.append(to)
        regions.append(members)
    for members in regions:
        if len(members) > orphan_size:
            continue
        own = label[members[0]]
        mat = material[members[0]]
        touching = [to for at in members for to in around(at) if label[to] >= 0 and label[to] != own]
        if not any(material[to] == mat for to in touching):
            continue  # all of its material there: a detail, not a speck
        votes: Counter[int] = Counter()
        for to in touching:
            if len(regions[label[to]]) > orphan_size and group[to] == group[members[0]] and flat[to] != flat[members[0]]:
                votes[flat[to]] += 1
        if not votes:
            continue
        best = min(votes, key=lambda colour: (-votes[colour], colour))
        rgb = np.array([best >> 16, (best >> 8) & 255, best & 255], dtype=np.uint8)
        for at in members:
            out[divmod(at, width) + (slice(0, 3),)] = rgb
    return out


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
