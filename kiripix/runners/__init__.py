"""Local ML Runners (spec §8): lazy load, one at a time, unload after use. Uses only `checks` and `ops`."""

from kiripix.runners.base import CheckCancel, Device, Runner, RunnerError, WeightFile, register_runner, runners
from kiripix.runners.sam2 import Sam2
from kiripix.runners.weights import RECORD, missing_weights, pull, remove, weights_dir

SEGMENTER = Sam2.id  # the Runner behind `click` Decisions

register_runner(Sam2())

__all__ = [
    "CheckCancel",
    "Device",
    "RECORD",
    "Runner",
    "RunnerError",
    "SEGMENTER",
    "WeightFile",
    "missing_weights",
    "pull",
    "register_runner",
    "remove",
    "runners",
    "weights_dir",
]
