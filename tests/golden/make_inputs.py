"""Writes the golden input images. Run once: `uv run python tests/golden/make_inputs.py`; the PNGs are committed (LFS).

Expected outputs are written by `uv run pytest tests/golden --update-golden`, then reviewed by eye before committing.
"""

from pathlib import Path

import numpy as np
from PIL import Image

INPUTS = Path(__file__).parent / "inputs"


def gradient() -> np.ndarray:
    """64 x 32: hue across, lightness down. Exercises every palette region and the dithering thresholds."""
    x = np.linspace(0, 1, 64)[None, :]
    y = np.linspace(0, 1, 32)[:, None]
    hue = x * 6
    r = np.clip(np.abs(hue - 3) - 1, 0, 1)
    g = np.clip(2 - np.abs(hue - 2), 0, 1)
    b = np.clip(2 - np.abs(hue - 4), 0, 1)
    rgb = np.stack([r, g, b], axis=2) * (1 - y[..., None]) + y[..., None] * 0.5 * (1 - y[..., None])
    rgba = np.full((32, 64, 4), 255, dtype=np.uint8)
    rgba[..., :3] = np.round(np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    return rgba


def main() -> None:
    INPUTS.mkdir(exist_ok=True)
    image = gradient()
    Image.fromarray(image, "RGBA").save(INPUTS / "gradient.png")

    transparent = image.copy()
    checker = (np.indices((32, 64)).sum(axis=0) // 4) % 2 == 0
    transparent[checker] = (123, 45, 67, 0)
    Image.fromarray(transparent, "RGBA").save(INPUTS / "transparent.png")

    partial = image.copy()
    partial[5, 7, 3] = 128
    Image.fromarray(partial, "RGBA").save(INPUTS / "partial_alpha.png")


if __name__ == "__main__":
    main()
