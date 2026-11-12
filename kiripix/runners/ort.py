"""What the ONNX Runners share: choosing the providers, and one inference that a cancel can stop. ONNX Runtime is imported
only when a Runner loads or runs, so nothing else pays for it."""

from __future__ import annotations

import contextlib
import io
import threading
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.runners.base import CheckCancel, Device, RunnerError

CUDA = "CUDAExecutionProvider"
CPU = "CPUExecutionProvider"
_ERRORS_ONLY = 3  # ONNX Runtime warns about how some exports place and scatter, on every load


def providers(device: Device) -> list[str]:
    """The GPU first when asked for it and ONNX Runtime can use it, and the CPU always."""
    import onnxruntime

    if device != "cpu" and hasattr(onnxruntime, "preload_dlls"):
        with contextlib.redirect_stdout(io.StringIO()):  # it prints what it can't find, and stdout is the JSON
            onnxruntime.preload_dlls()
    onnxruntime.set_default_logger_severity(_ERRORS_ONLY)
    return [CUDA, CPU] if device != "cpu" and CUDA in onnxruntime.get_available_providers() else [CPU]


def run(session: Any, feeds: dict[str, np.ndarray], check_cancel: CheckCancel, name: str) -> Sequence[np.ndarray]:
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
        raise RunnerError(f"{name} failed: {outcome['error']}")
    result: Sequence[np.ndarray] = outcome["result"]
    return result
