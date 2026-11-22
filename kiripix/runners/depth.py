"""Depth Anything V2 Small for relative depth, on ONNX Runtime with CUDA, falling back to the CPU (ticket 0340, ADR 0014).

The model takes the image stretched to `size` px on its longer side, both sides a multiple of 14, and returns its relative
inverse depth (nearer is bigger) at that size. The Runner returns it as float32, scaled so the image's own range is 0 to 1,
at that size: the Stage maps it through the Grid. The input size is a parameter of the call and so part of its key
(ADR 0002, ADR 0014): it is never lowered from the machine's free VRAM, so a pin doesn't depend on the machine. When the GPU
has no room for the size asked, the call fails and says which parameter to lower.

A pinned depth result is a 16-bit greyscale PNG (`encode`, `decode`), which keeps the depth's gradients smooth for a Sobel
filter, where 8 bits would stair-step them. ONNX Runtime is imported only when the Runner loads.
"""

from __future__ import annotations

import gc
import shutil
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

from kiripix.ops.depth import u16_to_unit, unit_to_u16
from kiripix.runners import ort
from kiripix.runners.base import CheckCancel, Device, Runner, RunnerError, WeightFile

SIZES = (1036, 518)  # the long side: 74 and 37 patches of 14 px
_PATCH = 14
_MEAN = (0.485, 0.456, 0.406)  # arrays are built where used: numpy loads late
_STD = (0.229, 0.224, 0.225)
_MODEL = "model.onnx"
# onnx-community/depth-anything-v2-small, the fp32 export of depth-anything/Depth-Anything-V2-Small, pinned at one commit.
_URL = "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/" \
       "4472b7362082ad9968fee890ca0f1e5aca36b93d/onnx/model.onnx"
_OUT_OF_MEMORY = ("out of memory", "failed to allocate", "bfcarena", "cudaerrormemoryallocation")


def input_size(width: int, height: int, long_side: int) -> tuple[int, int]:
    """The model's input (width, height) for an image of this size: its longer side near `long_side`, both a multiple of 14."""
    scale = long_side / max(width, height)
    return (max(_PATCH, round(width * scale / _PATCH) * _PATCH), max(_PATCH, round(height * scale / _PATCH) * _PATCH))


# A pinned depth's pixels: `encode` as it is pinned, `decode` as a Stage reads it back (the pure Ops).
encode = unit_to_u16
decode = u16_to_unit


class DepthAnythingV2Small(Runner):
    id = "depth-anything-v2-small"
    description = "Depth Anything V2 Small (fp32, ONNX): relative depth of an image."
    licence = "Apache-2.0"
    weights = (WeightFile(_MODEL, _URL, "afb6a5c28f3b6bf1618c6e43f02073ef9dfdc70e937502d51603e57b0a1df10c", 99060839),)

    def __init__(self) -> None:
        self._session: Any = None
        self._gpu_unused = False

    def load(self, directory: Path, device: Device) -> None:
        try:
            import onnxruntime

            self._session = onnxruntime.InferenceSession(str(directory / _MODEL), providers=ort.providers(device))
        except Exception as error:  # noqa: BLE001 - ONNX Runtime's own errors derive directly from Exception
            self.unload()
            raise RunnerError(f"can't load Depth Anything from {directory}: {error}") from None
        self._gpu_unused = device != "cpu" and self.device_used == "cpu" and shutil.which("nvidia-smi") is not None

    @property
    def device_used(self) -> str:
        return "cuda" if self._session is not None and ort.CUDA in self._session.get_providers() else "cpu"

    @property
    def gpu_unused(self) -> str | None:
        if not self._gpu_unused:
            return None
        return "Depth Anything ran on the CPU, though this machine has an NVIDIA GPU: ONNX Runtime can't load its CUDA libraries"

    def call(self, image: np.ndarray, params: dict[str, Any], check_cancel: CheckCancel) -> np.ndarray:
        """`params`: `size`, the long side of the model's input: 1036, or 518 where VRAM is short. Returns a float32
        (H, W) depth in 0 to 1 at the model's input size, nearer bigger."""
        size = params.get("size")
        if size not in SIZES:
            raise RunnerError(f"Depth Anything's `size` is one of {', '.join(map(str, SIZES))}, not {size!r}")
        height, width = image.shape[:2]
        new_width, new_height = input_size(width, height, size)
        resized = Image.fromarray(image[..., :3], "RGB").resize((new_width, new_height), Image.Resampling.BICUBIC)
        pixels = (np.asarray(resized, dtype=np.float32) / 255 - np.array(_MEAN, dtype=np.float32)) / np.array(_STD, dtype=np.float32)
        feeds = {self._session.get_inputs()[0].name: np.ascontiguousarray(pixels.transpose(2, 0, 1)[None])}
        try:
            [output, *_] = ort.run(self._session, feeds, check_cancel, "Depth Anything")
        except RunnerError as error:
            if self.device_used == "cuda" and any(text in str(error).lower() for text in _OUT_OF_MEMORY):
                if size == SIZES[-1]:
                    raise RunnerError(f"the GPU has no room for Depth Anything even at size {size}: run with --cpu") from None
                raise RunnerError(
                    f"the GPU has no room for Depth Anything at size {size}: set the call's `size` to {SIZES[-1]}, "
                    "or run with --cpu", set_param=("size", SIZES[-1])) from None
            raise
        depth = np.asarray(output, dtype=np.float32).reshape(output.shape[-2:])
        low, high = float(depth.min()), float(depth.max())
        scaled: np.ndarray = ((depth - low) / (high - low) if high > low else np.zeros_like(depth)).astype(np.float32)
        return scaled

    def unload(self) -> None:
        self._session = None
        gc.collect()
