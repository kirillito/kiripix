"""BiRefNet for matting: the image's foreground as a soft matte, on ONNX Runtime with CUDA, falling back to the CPU.

The model takes the image stretched to 1024 x 1024 and returns the matte's logits at that size. The matte (a sigmoid of
them) is scaled to the result's size, capped at `max_size` px on the longer side, and becomes the alpha of the input's
colours, so partial alpha survives until `fit`. ONNX Runtime is imported only when the Runner loads.
"""

from __future__ import annotations

import gc
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
if TYPE_CHECKING:
    from PIL import Image
else:
    Image = lazy_module("PIL.Image")

from kiripix.runners import ort
from kiripix.runners.base import CheckCancel, Device, Runner, RunnerError, WeightFile

_SIZE = 1024
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_MODEL = "model.onnx"
# onnx-community/BiRefNet-ONNX, the fp32 export of ZhengPeng7/BiRefNet, pinned at one commit.
_URL = "https://huggingface.co/onnx-community/BiRefNet-ONNX/resolve/534d3c82d3bb8b2f0867db6dfbc3a525b8e42f67/onnx/model.onnx"


class BiRefNet(Runner):
    id = "birefnet"
    description = "BiRefNet (fp32, 1024 px): matting, the foreground as a soft alpha."
    licence = "MIT"
    weights = (WeightFile(_MODEL, _URL, "58f621f00f5d756097615970a88a791584600dcf7c45b18a0a6267535a1ebd3c", 972666916),)

    def __init__(self) -> None:
        self._session: Any = None

    def load(self, directory: Path, device: Device) -> None:
        try:
            import onnxruntime

            self._session = onnxruntime.InferenceSession(str(directory / _MODEL), providers=ort.providers(device))
        except Exception as error:  # noqa: BLE001 - ONNX Runtime's own errors derive directly from Exception
            self.unload()
            raise RunnerError(f"can't load BiRefNet from {directory}: {error}") from None

    @property
    def device_used(self) -> str:
        return "cuda" if self._session is not None and ort.CUDA in self._session.get_providers() else "cpu"

    def call(self, image: np.ndarray, params: dict[str, Any], check_cancel: CheckCancel) -> np.ndarray:
        """`params`: `max_size`, the cap on the result's longer side. Returns an (H, W, 4) RGBA image."""
        height, width = image.shape[:2]
        scale = min(1.0, int(params["max_size"]) / max(width, height))
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        colour = Image.fromarray(image[..., :3], "RGB")
        squared = colour.resize((_SIZE, _SIZE), Image.Resampling.BILINEAR)
        pixels = (np.asarray(squared, dtype=np.float32) / 255 - _MEAN) / _STD
        feeds = {self._session.get_inputs()[0].name: pixels.transpose(2, 0, 1)[None]}
        [logits, *_] = ort.run(self._session, feeds, check_cancel, "BiRefNet")
        matte = 1 / (1 + np.exp(-np.asarray(logits, dtype=np.float32).reshape(logits.shape[-2:])))
        scaled = Image.fromarray(matte, "F").resize(size, Image.Resampling.BILINEAR)
        alpha = np.clip(np.rint(np.asarray(scaled) * 255), 0, 255).astype(np.uint8)
        result = np.empty((size[1], size[0], 4), dtype=np.uint8)
        result[..., :3] = np.asarray(colour if size == colour.size else colour.resize(size, Image.Resampling.LANCZOS))
        result[..., 3] = alpha
        return result

    def unload(self) -> None:
        self._session = None
        gc.collect()
