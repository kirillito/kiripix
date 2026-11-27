"""Reading and writing WAV files as float arrays (ADR 0016): what `ffmpeg.py` leaves in a Stage's output folder (float32 PCM)
and what a test or the contact sheet reads. Stdlib and numpy only: the `wave` module can't do float."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import TYPE_CHECKING

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt
else:
    np = lazy_module("numpy")
    npt = lazy_module("numpy.typing")

_PCM, _FLOAT, _EXTENSIBLE = 1, 3, 0xFFFE


class WavError(ValueError):
    """A file that isn't a WAV this module reads (PCM 16, 24 or 32 bit, or float 32 or 64 bit)."""


def read_wav(path: Path) -> tuple[int, npt.NDArray[np.float32]]:
    """The sample rate and the samples, float32 in [-1, 1], shaped (frames, channels)."""
    data = path.read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise WavError(f"{path.name} is not a WAV file")
    position = 12
    fmt: tuple[int, int, int, int] | None = None  # tag, channels, rate, bits
    body: tuple[int, int] | None = None
    while position + 8 <= len(data):
        name, size = data[position:position + 4], struct.unpack("<I", data[position + 4:position + 8])[0]
        start = position + 8
        if name == b"fmt ":
            tag, channels, rate, _, _, bits = struct.unpack("<HHIIHH", data[start:start + 16])
            if tag == _EXTENSIBLE and size >= 26:
                tag = struct.unpack("<H", data[start + 24:start + 26])[0]
            fmt = (tag, channels, rate, bits)
        elif name == b"data":
            body = (start, min(size, len(data) - start))
            break
        position = start + size + (size & 1)
    if fmt is None or body is None:
        raise WavError(f"{path.name} has no fmt or data chunk")
    tag, channels, rate, bits = fmt
    raw = data[body[0]:body[0] + body[1]]
    samples: npt.NDArray[np.float32]
    if tag == _FLOAT and bits == 32:
        samples = np.frombuffer(raw[:len(raw) // 4 * 4], dtype="<f4").astype(np.float32)
    elif tag == _FLOAT and bits == 64:
        samples = np.frombuffer(raw[:len(raw) // 8 * 8], dtype="<f8").astype(np.float32)
    elif tag == _PCM and bits == 16:
        samples = (np.frombuffer(raw[:len(raw) // 2 * 2], dtype="<i2").astype(np.float32) / 32768.0)
    elif tag == _PCM and bits == 32:
        samples = (np.frombuffer(raw[:len(raw) // 4 * 4], dtype="<i4").astype(np.float64) / 2147483648.0).astype(np.float32)
    elif tag == _PCM and bits == 24:
        packed = np.frombuffer(raw[:len(raw) // 3 * 3], dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        value = packed[:, 0] | (packed[:, 1] << 8) | (packed[:, 2] << 16)
        samples = (np.where(value >= 1 << 23, value - (1 << 24), value) / 8388608.0).astype(np.float32)
    else:
        raise WavError(f"{path.name} is a WAV of format {tag} at {bits} bits, which this reads only as PCM 16, 24, 32 or float")
    frames = len(samples) // channels
    return rate, samples[:frames * channels].reshape(frames, channels)


def write_wav(path: Path, rate: int, samples: npt.NDArray[np.floating]) -> None:
    """A float32 WAV of `samples` (frames,) or (frames, channels). Not atomic: a Stage writes into the folder core swaps in."""
    data = np.ascontiguousarray(samples.reshape(len(samples), -1), dtype="<f4")
    channels = data.shape[1]
    payload = data.tobytes()
    header = (b"RIFF" + struct.pack("<I", 36 + len(payload)) + b"WAVE" + b"fmt " + struct.pack(
        "<IHHIIHH", 16, _FLOAT, channels, rate, rate * channels * 4, channels * 4, 32) + b"data" + struct.pack("<I", len(payload)))
    path.write_bytes(header + payload)
