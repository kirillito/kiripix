"""Local ML Runners (spec §8): lazy load, one at a time, unload after use. Uses only `checks` and `ops`."""

from kiripix.runners.base import (
    CheckCancel, Device, EmbeddingRunner, Runner, RunnerError, WeightFile, register_runner, runners,
)
from kiripix.runners.birefnet import BiRefNet
from kiripix.runners.sam2 import Sam2
from kiripix.runners.weights import RECORD, missing_weights, pull, remove, weights_dir

SEGMENTER = Sam2.id  # the Runner behind `click` Decisions
MATTER = BiRefNet.id  # the Runner behind matting: an RGBA image in, the same image with the matte as alpha out

register_runner(Sam2())
register_runner(BiRefNet())

__all__ = [
    "CheckCancel",
    "Device",
    "EmbeddingRunner",
    "MATTER",
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
