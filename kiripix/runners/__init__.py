"""Local ML Runners (spec §8): lazy load, one at a time, unload after use. Uses only `checks` and `ops`."""

from kiripix.runners.base import (
    CheckCancel, Device, EmbeddingRunner, Runner, RunnerError, WeightFile, register_runner, runners,
)
from kiripix.runners.birefnet import BiRefNet
from kiripix.runners.lama import Lama
from kiripix.runners.sam2 import Sam2
from kiripix.runners.weights import RECORD, missing_weights, pull, remove, weights_dir

SEGMENTER = Sam2.id  # the Runner behind `click` Decisions
MATTER = BiRefNet.id  # the Runner behind matting: an RGBA image in, the same image with the matte as alpha out
INPAINTER = Lama.id
"""The Runner behind inpainting. Its contract: the call's image is a whole RGBA image, and `params` hold a hole as
`crop` [top, left, bottom, right] and `runs` [[y, x, length], ...] (rows relative to the crop's corner, as
`ops.mask_runs` makes them). It returns the crop as an RGBA image with the hole filled (filled pixels opaque, every other
pixel the input's). Nothing outside the Runner knows its engine or input size."""

register_runner(Sam2())
register_runner(Lama())
register_runner(BiRefNet())

__all__ = [
    "CheckCancel",
    "Device",
    "EmbeddingRunner",
    "INPAINTER",
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
