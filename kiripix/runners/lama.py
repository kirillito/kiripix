"""LaMa (big-lama) for inpainting: fills a hole in an image from what is around it, on ONNX Runtime with CUDA, falling
back to the CPU.

The ONNX conversion takes a fixed 512 x 512 image and Mask. The crop is fitted inside that square keeping its aspect
(the rest is padded with its own edge pixels, outside the hole), inpainted, and scaled back. Only the hole's pixels are
taken from the result, so what is outside the hole is the input's, bit for bit. ONNX Runtime is imported only when the
Runner loads.
"""

import gc
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from kiripix.runners import ort
from kiripix.runners.base import CheckCancel, Device, Runner, RunnerError, WeightFile

_SIZE = 512
_MODEL = "lama_fp32.onnx"
# Carve/LaMa-ONNX, the fp32 export of big-lama, pinned at one commit.
_URL = "https://huggingface.co/Carve/LaMa-ONNX/resolve/c3c0c9e468934d62e79c329e35d82dd09ff8c444/lama_fp32.onnx"


class Lama(Runner):
    id = "lama"
    description = "LaMa (big-lama, fp32, 512 px): inpainting, a hole filled from its surroundings."
    licence = "Apache-2.0"
    can_stay_warm = True  # about 0.5 GB of VRAM; it loads in 20 s, so a lift in `serve` shouldn't pay that each time
    weights = (WeightFile(_MODEL, _URL, "1faef5301d78db7dda502fe59966957ec4b79dd64e16f03ed96913c7a4eb68d6", 208044816),)

    def __init__(self) -> None:
        self._session: Any = None

    def load(self, directory: Path, device: Device) -> None:
        try:
            import onnxruntime

            self._session = onnxruntime.InferenceSession(str(directory / _MODEL), providers=ort.providers(device))
        except Exception as error:  # noqa: BLE001 - ONNX Runtime's own errors derive directly from Exception
            self.unload()
            raise RunnerError(f"can't load LaMa from {directory}: {error}") from None

    @property
    def device_used(self) -> str:
        return "cuda" if self._session is not None and ort.CUDA in self._session.get_providers() else "cpu"

    def call(self, image: np.ndarray, params: dict[str, Any], check_cancel: CheckCancel) -> np.ndarray:
        """`params`: `crop` [top, left, bottom, right] (bottom and right exclusive) and `runs` [[y, x, length], ...], the
        hole's rows relative to the crop's top-left corner. Returns the crop as an (h, w, 4) RGBA image with the hole
        filled: the filled pixels are opaque, and every other pixel is the input's."""
        top, left, bottom, right = (int(v) for v in params["crop"])
        crop = np.ascontiguousarray(image[top:bottom, left:right])
        height, width = crop.shape[:2]
        hole = np.zeros((height, width), dtype=np.bool_)
        for y, x, length in params["runs"]:
            hole[y, x:x + length] = True
        if not hole.any():
            return crop

        # Fit the crop inside the square, keeping its aspect, and pad with its edge pixels, outside the hole.
        scale = _SIZE / max(height, width)
        rows, columns = max(1, round(height * scale)), max(1, round(width * scale))
        colour = Image.fromarray(crop[..., :3], "RGB").resize((columns, rows), Image.Resampling.BICUBIC)
        flags = Image.fromarray(hole.astype(np.uint8) * 255, "L").resize((columns, rows), Image.Resampling.BILINEAR)
        pixels = np.pad(np.asarray(colour), ((0, _SIZE - rows), (0, _SIZE - columns), (0, 0)), mode="edge")
        squared = np.pad(np.asarray(flags) > 0, ((0, _SIZE - rows), (0, _SIZE - columns)))
        pixels = pixels.copy()
        pixels[squared] = 0
        feeds: dict[str, np.ndarray] = {
            self._session.get_inputs()[0].name: (pixels.astype(np.float32) / 255).transpose(2, 0, 1)[None],
            self._session.get_inputs()[1].name: squared.astype(np.float32)[None, None],
        }
        [output, *_] = ort.run(self._session, feeds, check_cancel, "LaMa")
        filled = np.clip(np.rint(np.asarray(output, dtype=np.float32)[0].transpose(1, 2, 0)), 0, 255).astype(np.uint8)
        filled = filled[:rows, :columns]
        if filled.shape[:2] != (height, width):
            filled = np.asarray(Image.fromarray(filled, "RGB").resize((width, height), Image.Resampling.BICUBIC))
        result = crop.copy()
        result[hole, :3] = filled[hole]
        result[hole, 3] = 255
        return result

    def unload(self) -> None:
        self._session = None
        gc.collect()
