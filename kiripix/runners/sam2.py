"""SAM 2.1 (small) for click-to-segment, on ONNX Runtime with CUDA, falling back to the CPU.

The encoder takes the image stretched to 1024 x 1024 and the decoder takes the clicks in those coordinates; it returns
three candidate masks as 256 x 256 logits with a score each. The best one is scaled to the input image, capped at
`max_size` px on its longer side, and thresholded at 0. ONNX Runtime is imported only when the Runner loads, so nothing
else pays for it.
"""

import contextlib
import gc
import io
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from kiripix.runners.base import CheckCancel, Device, EmbeddingRunner, RunnerError, WeightFile

_SIZE = 1024
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_FILES = "https://huggingface.co/onnx-community/sam2.1-hiera-small-ONNX/resolve/" \
         "a7df49d8de14b9d2e4504d1687b0d568f905fd8d/onnx/"
_ENCODER = "vision_encoder.onnx"
_DECODER = "prompt_encoder_mask_decoder.onnx"
CUDA = "CUDAExecutionProvider"
CPU = "CPUExecutionProvider"
_ERRORS_ONLY = 3  # ONNX Runtime warns about how this export places and scatters on every load


def _weight(name: str, sha256: str, size: int) -> WeightFile:
    return WeightFile(name, _FILES + name, sha256, size)


def _run(session: Any, feeds: dict[str, np.ndarray], check_cancel: CheckCancel) -> Sequence[np.ndarray]:
    """One inference that a cancel can stop. It runs on a thread of its own, because Python delivers Ctrl+C only to a
    main thread that is running bytecode. On a cancel, `RunOptions.terminate` stops the inference, and what
    `check_cancel` raised carries on from here once it has."""
    import onnxruntime

    options = onnxruntime.RunOptions()
    outcome: dict[str, Any] = {}

    def work() -> None:
        try:
            outcome["result"] = session.run(None, feeds, options)
        except Exception as error:  # noqa: BLE001 - handed to the waiting thread
            outcome["error"] = error

    thread = threading.Thread(target=work, name="runner-inference", daemon=True)
    thread.start()
    try:
        while thread.is_alive():
            thread.join(0.05)
            check_cancel()
    except BaseException:
        options.terminate = True
        thread.join()
        raise
    if "error" in outcome:
        raise RunnerError(f"SAM 2 failed: {outcome['error']}")
    result: Sequence[np.ndarray] = outcome["result"]
    return result


class Sam2(EmbeddingRunner):
    id = "sam2.1-small"
    description = "SAM 2.1 (hiera small): click-to-segment."
    licence = "Apache-2.0"
    weights = (
        _weight(_ENCODER, "aacf1f7137bb6fffcf6bf166abcfabe28f57a76059254f3fb611c4a64a208119", 467440),
        _weight(f"{_ENCODER}_data", "260fd1f0a34e72a3dc79a739e563b4facc0ba75504818b433a1f808e66637456", 162476288),
        _weight(_DECODER, "079c59b261f723ff5c6a125e69b0170a957b21c58738c28d2b0394ecd0587d7f", 213114),
        _weight(f"{_DECODER}_data", "f9e59a584ab8ced21fa812c211bc01084204db1c9e92a5ef4fb3a49972b4e864", 20958208),
    )

    def __init__(self) -> None:
        self._encoder: Any = None
        self._decoder: Any = None
        self._embedded: tuple[bytes, dict[str, np.ndarray]] | None = None  # the last image, so more clicks don't re-encode

    def load(self, directory: Path, device: Device) -> None:
        try:
            import onnxruntime

            if device != "cpu" and hasattr(onnxruntime, "preload_dlls"):
                with contextlib.redirect_stdout(io.StringIO()):  # it prints what it can't find, and stdout is the JSON
                    onnxruntime.preload_dlls()
            usable = onnxruntime.get_available_providers()
            providers = [CUDA, CPU] if device != "cpu" and CUDA in usable else [CPU]
            onnxruntime.set_default_logger_severity(_ERRORS_ONLY)
            self._encoder = onnxruntime.InferenceSession(str(directory / _ENCODER), providers=providers)
            self._decoder = onnxruntime.InferenceSession(str(directory / _DECODER), providers=providers)
        except Exception as error:  # noqa: BLE001 - ONNX Runtime's own errors derive directly from Exception
            self.unload()
            raise RunnerError(f"can't load SAM 2 from {directory}: {error}") from None

    @property
    def device_used(self) -> str:
        return "cuda" if self._encoder is not None and CUDA in self._encoder.get_providers() else "cpu"

    def embed(self, image: np.ndarray, check_cancel: CheckCancel) -> dict[str, np.ndarray]:
        key = image.tobytes()
        if self._embedded is not None and self._embedded[0] == key:
            return self._embedded[1]
        squared = Image.fromarray(image[..., :3], "RGB").resize((_SIZE, _SIZE), Image.Resampling.BILINEAR)
        pixels = (np.asarray(squared, dtype=np.float32) / 255 - _MEAN) / _STD
        outputs = _run(self._encoder, {"pixel_values": pixels.transpose(2, 0, 1)[None]}, check_cancel)
        names = [output.name for output in self._encoder.get_outputs()]
        embeddings = dict(zip(names, outputs))
        self._embedded = (key, embeddings)
        return embeddings

    def decode(self, embedding: dict[str, np.ndarray], size: tuple[int, int], params: dict[str, Any],
               check_cancel: CheckCancel) -> np.ndarray:
        """`params`: `points`, each [x, y, positive] in the image's pixels; `max_size`, the cap on the Mask's size."""
        height, width = size
        points = params["points"]
        coordinates = np.array([[x * _SIZE / width, y * _SIZE / height] for x, y, _ in points], dtype=np.float32)
        labels = np.array([1 if positive else 0 for _, _, positive in points], dtype=np.int64)
        feeds = {
            **embedding,
            "input_points": coordinates[None, None],
            "input_labels": labels[None, None],
            "input_boxes": np.zeros((1, 0, 4), dtype=np.float32),
        }
        names = [output.name for output in self._decoder.get_outputs()]
        outputs = dict(zip(names, _run(self._decoder, feeds, check_cancel)))
        best = int(np.argmax(outputs["iou_scores"][0, 0]))
        logits = outputs["pred_masks"][0, 0, best]
        scale = min(1.0, int(params["max_size"]) / max(width, height))
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        scaled = Image.fromarray(logits, "F").resize(size, Image.Resampling.BILINEAR)
        result: np.ndarray = np.asarray(scaled) > 0
        return result

    def unload(self) -> None:
        self._encoder = self._decoder = self._embedded = None
        gc.collect()
