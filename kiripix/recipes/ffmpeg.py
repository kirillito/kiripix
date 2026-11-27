"""The one place that runs ffmpeg (ADR 0016, ticket 0395), as `blender_launcher.py` is the one place that runs Blender.

ffmpeg is the binary of the `imageio-ffmpeg` wheel locked in `uv.lock` (spec §5), never a system ffmpeg, which differs from
machine to machine. This module finds it, refuses another wheel version or another binary (`ffmpeg.wrong_version`, fix
`uv sync`), declares the computed Stage input `ffmpeg.version` (the first line of `ffmpeg -version`, so a lock update makes
every Stage that runs ffmpeg stale), decodes a recording to float PCM, and probes one. A cancel kills the process; the output
goes into a folder core swaps into place whole, so nothing is left half-made.

Analysis is not here: it is the sound Ops over the decoded samples. Core (which sits on `recipes`) uses `probe` for
`import`. `export`, `commands`, `cli` and `server` never run ffmpeg.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING

from kiripix.ops.lazy import lazy_module
from kiripix.recipes.base import StageFailure, computed_setting
from kiripix.recipes.wav import read_wav

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt
else:
    np = lazy_module("numpy")
    npt = lazy_module("numpy.typing")

WHEEL = "imageio-ffmpeg"
WHEEL_VERSION = "0.8.1"
VERSION_SETTING = "ffmpeg.version"  # a computed Stage input: the first line of `ffmpeg -version`
RATE = 44100  # the rate a recording is decoded to
SUFFIXES = (".wav", ".flac", ".mp3", ".ogg")  # the recordings `import` takes
_POLL = 0.1  # seconds between looks at the cancel token while ffmpeg runs

CheckCancel = Callable[[], None]


def _wrong(message: str) -> StageFailure:
    return StageFailure(message, code="ffmpeg.wrong_version", fix="uv sync")


@lru_cache(maxsize=1)
def executable() -> str:
    """The ffmpeg the locked wheel bundles. Raises StageFailure (`ffmpeg.wrong_version`, fix `uv sync`) for another wheel
    version, an `IMAGEIO_FFMPEG_EXE` or system ffmpeg, or a wheel without a binary."""
    try:
        import imageio_ffmpeg
        found = metadata.version(WHEEL)
    except (ImportError, metadata.PackageNotFoundError):
        raise _wrong(f"{WHEEL} {WHEEL_VERSION} is not installed, so there is no ffmpeg") from None
    if found != WHEEL_VERSION:
        raise _wrong(f"{WHEEL} is {found}, and Kiripix pins {WHEEL_VERSION} (uv.lock)")
    try:
        path = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
    except (RuntimeError, OSError) as error:
        raise _wrong(f"the {WHEEL} wheel has no ffmpeg binary: {error}") from None
    if not path.is_relative_to(Path(imageio_ffmpeg.__file__).resolve().parent):
        raise _wrong(f"ffmpeg is {path}, not the binary of the {WHEEL} wheel (is IMAGEIO_FFMPEG_EXE set?)")
    return str(path)


@lru_cache(maxsize=1)
def version_line() -> str:
    """The first line of `ffmpeg -version`; `ffmpeg unavailable` when it can't run (a Stage then fails with the reason)."""
    try:
        done = subprocess.run([executable(), "-version"], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError, StageFailure):
        return "ffmpeg unavailable"
    lines = done.stdout.splitlines()
    return lines[0].strip() if lines else "ffmpeg unavailable"


computed_setting(VERSION_SETTING, version_line)


def run(arguments: Sequence[str | Path], check_cancel: CheckCancel) -> tuple[int, str]:
    """Run ffmpeg with `arguments` (after `-nostdin -hide_banner`) and return its exit code and what it wrote on stderr. It is
    killed, and Cancelled raised, as soon as `check_cancel` says so."""
    command = [executable(), "-nostdin", "-hide_banner", *[str(a) for a in arguments]]
    try:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except OSError as error:
        raise StageFailure(f"ffmpeg could not run: {error}", code="ffmpeg.wrong_version", fix="uv sync") from None
    chunks: list[bytes] = []

    def read() -> None:
        assert process.stderr is not None
        chunks.append(process.stderr.read())

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        while True:
            check_cancel()
            try:
                code = process.wait(timeout=_POLL)
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        if process.poll() is None:  # a cancel: ffmpeg goes with it
            process.kill()
            process.wait()
    reader.join()
    return code, b"".join(chunks).decode("utf-8", errors="replace")


@dataclass(frozen=True)
class AudioInfo:
    """What `probe` read of a recording. `channels` is None for a layout it doesn't name."""

    codec: str
    rate: int
    channels: int | None
    duration_s: float | None


_LAYOUTS = {"mono": 1, "stereo": 2, "2.1": 3, "3.0": 3, "quad": 4, "4.0": 4, "5.0": 5, "5.1": 6, "7.1": 8}


def _channels(layout: str) -> int | None:
    name = layout.strip().split("(")[0]
    if name in _LAYOUTS:
        return _LAYOUTS[name]
    match = re.match(r"(\d+) channels", name)
    return int(match.group(1)) if match else None


def probe(path: Path, check_cancel: CheckCancel) -> AudioInfo | None:
    """The first audio stream of the file, after decoding the whole file (so a truncated or corrupt one is refused too);
    None when ffmpeg can't read it as audio."""
    code, text = run(["-v", "info", "-i", path, "-vn", "-f", "null", "-"], check_cancel)
    stream = re.search(r"Stream #\d+:\d+[^:]*: Audio: ([^\s,(]+)[^,]*, (\d+) Hz, ([^,\n]+)", text)
    if code != 0 or stream is None:
        return None
    length = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", text)
    seconds = (int(length.group(1)) * 3600 + int(length.group(2)) * 60 + float(length.group(3))) if length else None
    return AudioInfo(codec=stream.group(1), rate=int(stream.group(2)), channels=_channels(stream.group(3)),
                     duration_s=seconds)


def decode_to_wav(source: Path, target: Path, check_cancel: CheckCancel, rate: int = RATE) -> None:
    """Decode the first audio stream of `source` to a float32 WAV at `rate`, keeping its channels. Raises StageFailure
    (`ffmpeg.decode_failed`) when ffmpeg can't."""
    code, text = run(["-v", "error", "-y", "-i", source, "-vn", "-map", "0:a:0", "-map_metadata", "-1", "-ar", str(rate),
                      "-c:a", "pcm_f32le", "-fflags", "+bitexact", "-flags:a", "+bitexact", "-f", "wav", target],
                     check_cancel)
    if code != 0 or not target.is_file():
        last = [line for line in text.splitlines() if line.strip()][-1:] or ["no message"]
        raise StageFailure(f"ffmpeg could not decode {source.name}: {last[0]}", code="ffmpeg.decode_failed",
                           owner_action=f"Re-export {source.name} as a WAV or FLAC and import it as a new Variant.")


_BITEXACT = ["-fflags", "+bitexact", "-flags:a", "+bitexact", "-map_metadata", "-1", "-threads", "1", "-filter_threads", "1"]


def _failed(what: str, text: str) -> StageFailure:
    last = [line for line in text.splitlines() if line.strip()][-1:] or ["no message"]
    return StageFailure(f"ffmpeg could not {what}: {last[0]}", code="ffmpeg.failed", fix="uv sync")


def filter_wav(source: Path, target: Path, filters: str, channels: int, check_cancel: CheckCancel, rate: int = RATE) -> None:
    """Run the audio filter chain `filters` over the float WAV `source`, mix it to `channels`, and write a float32 WAV at
    `rate` (ticket 0397). The flags are fixed (bitexact, one thread), so the same input gives the same bytes. Raises
    StageFailure (`ffmpeg.failed`) when ffmpeg can't."""
    chain = f"{filters}," if filters else ""
    code, text = run(["-v", "error", "-y", "-i", source, "-vn", "-af", f"{chain}aresample={rate}", "-ac", str(channels),
                      "-c:a", "pcm_f32le", *_BITEXACT, "-f", "wav", target], check_cancel)
    if code != 0 or not target.is_file():
        raise _failed(f"filter {source.name}", text)


@dataclass(frozen=True)
class Loudness:
    """What the first `loudnorm` pass measured: integrated loudness (LUFS), true peak (dBTP), loudness range (LU), the gate's
    threshold (LUFS) and the offset it wants."""

    integrated: float
    true_peak: float
    lra: float
    threshold: float
    offset: float


def measure_loudness(source: Path, target_lufs: float, true_peak: float, lra: float, check_cancel: CheckCancel) -> Loudness:
    """`loudnorm`'s first pass over `source` (the JSON it prints). StageFailure (`ffmpeg.failed`) when it can't be read."""
    code, text = run(["-v", "info", "-i", source, "-af",
                      f"loudnorm=I={target_lufs:g}:TP={true_peak:g}:LRA={lra:g}:print_format=json", "-f", "null",
                      *_BITEXACT, "-"], check_cancel)
    start, end = text.rfind("{"), text.rfind("}")
    try:
        found = json.loads(text[start:end + 1])
        return Loudness(integrated=float(found["input_i"]), true_peak=float(found["input_tp"]),
                        lra=float(found["input_lra"]), threshold=float(found["input_thresh"]),
                        offset=float(found["target_offset"]))
    except (ValueError, KeyError):
        raise _failed(f"measure the loudness of {source.name}", text) from None


def apply_loudness(source: Path, target: Path, target_lufs: float, true_peak: float, lra: float, measured: Loudness,
                   check_cancel: CheckCancel, rate: int = RATE) -> None:
    """`loudnorm`'s second pass, linear: one gain from `measured`, back at `rate` (loudnorm itself works at 192 kHz)."""
    chain = (f"loudnorm=I={target_lufs:g}:TP={true_peak:g}:LRA={lra:g}:measured_I={measured.integrated}:"
             f"measured_TP={measured.true_peak}:measured_LRA={measured.lra}:measured_thresh={measured.threshold}:"
             f"offset={measured.offset}:linear=true,aresample={rate}")
    code, text = run(["-v", "error", "-y", "-i", source, "-af", chain, "-c:a", "pcm_f32le", *_BITEXACT, "-f", "wav", target],
                     check_cancel)
    if code != 0 or not target.is_file():
        raise _failed(f"normalise the loudness of {source.name}", text)


def encode_ogg(source: Path, target: Path, quality: float, rate: int, check_cancel: CheckCancel) -> None:
    """Encode the WAV `source` to OGG Vorbis (`-c:a libvorbis -q:a <quality> -ar <rate>`), keeping its channels (ticket 0400).
    The flags are fixed (`_BITEXACT`: `+bitexact` gives the Ogg stream a fixed serial in place of a random one, which is the
    one thing that made two encodes of the same input differ, and leaves out the encoder's version tag; no metadata; one
    thread), so the same input gives the same bytes on one platform. Raises StageFailure (`ffmpeg.failed`) when ffmpeg can't."""
    code, text = run(["-v", "error", "-y", "-i", source, "-vn", "-c:a", "libvorbis", "-q:a", f"{quality:g}", "-ar", str(rate),
                      *_BITEXACT, "-f", "ogg", target], check_cancel)
    if code != 0 or not target.is_file():
        raise _failed(f"encode {source.name} to OGG Vorbis", text)


def decode(source: Path, check_cancel: CheckCancel, rate: int = RATE) -> tuple[int, npt.NDArray[np.float32]]:
    """The recording's rate and float32 samples, (frames, channels), as `decode_to_wav` makes them (through a temporary
    file, which is removed)."""
    with tempfile.TemporaryDirectory(prefix="kiripix-ffmpeg-") as folder:
        target = Path(folder, "decoded.wav")
        decode_to_wav(source, target, check_cancel, rate)
        return read_wav(target)
