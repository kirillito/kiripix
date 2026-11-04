"""What a Runner is (spec §8): a local ML model behind one interface, with its weights, licence and registry.

A Runner is loaded lazily, one at a time, and unloaded after use; core does that around its calls, holding the GPU lock.
Its weights' hash is declared here, never read from the files, because it is part of every pinned call's key, and a
fresh clone with no weights must still find its pinned results. In names Kiripix controls, a Runner's files are its
weights.
"""

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

Device = Literal["auto", "cpu"]  # auto: the GPU if ONNX Runtime can use it, else the CPU
CheckCancel = Callable[[], None]


class RunnerError(Exception):
    """A Runner couldn't load or finish: bad weights, no network, an engine error. Its message says why."""


@dataclass(frozen=True)
class WeightFile:
    """One file of a Runner's weights, as it is downloaded."""

    name: str
    url: str
    sha256: str
    size: int


class Runner(ABC):
    """A local ML model. `call` takes the input image and JSON parameters, and returns an image or a Mask."""

    id: str
    description: str
    licence: str
    weights: tuple[WeightFile, ...] = ()

    @property
    def weights_hash(self) -> str:
        """A hash of the Runner's weights: the part of a pinned call's key that says which weights made the result."""
        lines = sorted(f"{weight.name} {weight.sha256}" for weight in self.weights)
        return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    @abstractmethod
    def load(self, directory: Path, device: Device) -> None:
        """Load the weights from `directory`, where they have been pulled. Returns once the Runner can be called."""

    @abstractmethod
    def call(self, image: np.ndarray, params: dict[str, Any], check_cancel: CheckCancel) -> np.ndarray:
        """One inference on an (H, W, 4) RGBA image. Raises what `check_cancel` raises, as soon as it can."""

    @abstractmethod
    def unload(self) -> None:
        """Let go of everything `load` took, so the next Runner has the memory."""

    @property
    def device_used(self) -> str:
        """Where the loaded Runner runs, for the history. Never part of a pinned call's key (ADR 0002)."""
        return "cpu"


_RUNNERS: dict[str, Runner] = {}


def register_runner(runner: Runner) -> None:
    """Add a Runner. The built-in Runners register here; the test harness replaces them with a fake."""
    _RUNNERS[runner.id] = runner


def runners() -> dict[str, Runner]:
    return dict(_RUNNERS)
