"""Making an image easier to look at: a tint over each Mask. For previews, never for game art."""

from collections.abc import Mapping

import numpy as np
import numpy.typing as npt

from kiripix.ops.colour import U8

# Distinct from each other and from a typical palette's mid-tones; `solid` is red like its colour in `[masks.*]`.
TINTS: tuple[tuple[int, int, int], ...] = (
    (255, 0, 0), (0, 255, 255), (0, 255, 0), (255, 0, 255), (255, 255, 0), (255, 128, 0), (0, 128, 255), (128, 0, 255),
)


def tint_masks(image: U8, masks: Mapping[str, npt.NDArray[np.bool_]], strength: float = 0.5) -> U8:
    """`image` with each Mask's pixels blended towards that Mask's tint, in name order.

    A Mask is an (H, W) boolean array of the image's size; Mask `i` of the sorted names gets `TINTS[i % len(TINTS)]`.
    The tint changes colour, never alpha.
    """
    result = image.copy()
    for index, name in enumerate(sorted(masks)):
        mask = masks[name]
        if mask.shape != image.shape[:2]:
            raise ValueError(f"mask '{name}' is {mask.shape[1]}x{mask.shape[0]} but the image is "
                             f"{image.shape[1]}x{image.shape[0]}")
        tint = np.array(TINTS[index % len(TINTS)], dtype=np.float64)
        blended = result[mask][:, :3] * (1 - strength) + tint * strength
        result[mask, :3] = np.round(blended).astype(np.uint8)
    return result
