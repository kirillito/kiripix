"""Making an image easier to look at: a tint over each Mask. For previews, never for game art."""

from __future__ import annotations

from collections.abc import Mapping

from typing import TYPE_CHECKING
from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
if TYPE_CHECKING:
    import numpy.typing as npt
else:
    npt = lazy_module("numpy.typing")

from kiripix.ops.colour import U8

# Distinct from each other and from a typical palette's mid-tones; `solid` is red like its colour in `[masks.*]`.
TINTS: tuple[tuple[int, int, int], ...] = (
    (255, 0, 0), (0, 255, 255), (0, 255, 0), (255, 0, 255), (255, 255, 0), (255, 128, 0), (0, 128, 255), (128, 0, 255),
)


def tint_masks(image: U8, masks: Mapping[str, npt.NDArray[np.bool_]], strength: float = 0.5) -> U8:
    """`image` with each Mask's pixels blended towards that Mask's tint, `solid` first and then in name order.

    A Mask is an (H, W) boolean array of the image's size; Mask `i` in that order gets `TINTS[i % len(TINTS)]`. The tint
    changes colour, never alpha.
    """
    result = image.copy()
    for index, name in enumerate(sorted(masks, key=lambda name: (name != "solid", name))):
        mask = masks[name]
        if mask.shape != image.shape[:2]:
            raise ValueError(f"mask '{name}' is {mask.shape[1]}x{mask.shape[0]} but the image is "
                             f"{image.shape[1]}x{image.shape[0]}")
        tint = np.array(TINTS[index % len(TINTS)], dtype=np.float64)
        blended = result[mask][:, :3] * (1 - strength) + tint * strength
        result[mask, :3] = np.round(blended).astype(np.uint8)
    return result


def tint_mask(image: U8, mask: npt.NDArray[np.bool_], colour: tuple[int, int, int], strength: float = 0.5) -> U8:
    """`image` with one Mask's pixels blended towards `colour`; alpha is never changed."""
    if mask.shape != image.shape[:2]:
        raise ValueError(f"the mask is {mask.shape[1]}x{mask.shape[0]} but the image is {image.shape[1]}x{image.shape[0]}")
    result = image.copy()
    blended = result[mask][:, :3] * (1 - strength) + np.array(colour, dtype=np.float64) * strength
    result[mask, :3] = np.round(blended).astype(np.uint8)
    return result


def brighten(image: U8, factor: float) -> U8:
    """`image` with its colour channels multiplied by `factor` and clipped to 255; alpha is never changed.

    For looking at a dark room only. A factor of 1 returns the image unchanged.
    """
    if factor <= 0:
        raise ValueError(f"the factor must be above 0, not {factor}")
    result = image.copy()
    if factor != 1:
        scaled = np.round(image[..., :3].astype(np.float64) * factor)
        result[..., :3] = np.clip(scaled, 0, 255).astype(np.uint8)
    return result


def draw_grid(image: U8, step: int, zoom: int, origin: tuple[int, int] = (0, 0), every: int = 5) -> U8:
    """A line on each boundary between target pixels whose coordinate is a multiple of `step`, on an image already zoomed.

    `image` shows the target pixels from `origin` (x, y) on, each `zoom` pixels wide. The lines are measured from the
    room's origin, not the image's, so a crop that starts off a multiple of `step` still lines up. A line is one pixel
    of the zoomed image, on the left or top edge of its target pixel; every `every`th line (counting from 0) is
    stronger. A line lightens a dark pixel and darkens a light one, and is opaque.
    """
    if step < 1 or zoom < 1 or every < 1:
        raise ValueError("step, zoom and every must be at least 1")
    height, width = image.shape[:2]
    weight = np.zeros((height, width), dtype=np.float64)  # the strongest line over each pixel

    def lines(first: int, size: int) -> list[tuple[int, float]]:
        found = []
        for target in range(-(-first // step) * step, first + -(-size // zoom) + 1, step):
            position = (target - first) * zoom
            if 0 <= position < size:
                found.append((position, 0.6 if (target // step) % every == 0 else 0.3))
        return found

    for x, strength in lines(origin[0], width):
        weight[:, x] = np.maximum(weight[:, x], strength)
    for y, strength in lines(origin[1], height):
        weight[y, :] = np.maximum(weight[y, :], strength)
    drawn = weight > 0
    rgb = image[..., :3].astype(np.float64)
    luma = rgb @ np.array([0.299, 0.587, 0.114])
    towards = np.where(luma < 128, 255.0, 0.0)[..., None]
    blended = rgb * (1 - weight[..., None]) + towards * weight[..., None]
    result = image.copy()
    result[drawn, :3] = np.round(blended[drawn]).astype(np.uint8)
    result[drawn, 3] = 255
    return result
