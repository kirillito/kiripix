"""Sound Ops (spec §7, ADR 0016): pure numpy over decoded samples. Decoding, resampling and encoding are ffmpeg's and live
in `kiripix/recipes/ffmpeg.py`; nothing here reads or writes a file.

Samples are float arrays in [-1, 1], shaped (frames,) for one channel or (frames, channels). Levels are dBFS (20 log10 of a
sample, 10 log10 of a mean square), floored at `FLOOR_DBFS` so no number is infinite. Times are samples; the caller converts.

`find_takes` cuts a recording into Takes by onset: the level rising fast (an energy rise, or new spectral content over a
ringing tail, which a spectral flux sees), `threshold` dB over a few frames. Both are measured in dB, so one threshold fits
both. A Take starts `pre_roll` before its onset, and ends where its level falls `floor` dB under its own early peak (or
within 6 dB of the recording's background), at the latest `tail` after the onset and at the latest where the next Take
starts; a Take that was cut short by the next one `overlaps_next`.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt
else:
    np = lazy_module("numpy")
    npt = lazy_module("numpy.typing")

FLOOR_DBFS = -120.0
CLIP_DBFS = -0.1  # a Take whose peak reaches this is clipped
WINDOW = 512  # samples of one analysis frame (11.6 ms at 44.1 kHz)
HOP = 128  # samples between frames (2.9 ms)
MIN_ONSET_DBFS = -60.0  # an onset whose frames never reach this level is not a sound
BACKGROUND_MARGIN_DB = 6.0
_CHUNK = 8192  # frames analysed at a time, so a long recording needs no more memory than a short one
_LOOKBACK = 3  # frames an onset is compared with
_EARLY_PEAK_S = 0.03
_BANDS = 24

Tick = Callable[[], None]


def _db_power(value: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    return np.maximum(10.0 * np.log10(np.maximum(value, 1e-30)), FLOOR_DBFS)


def to_mono(samples: npt.NDArray[np.floating]) -> npt.NDArray[np.float32]:
    """One channel: the mean of the channels."""
    if samples.ndim == 1:
        return samples.astype(np.float32, copy=False)
    return samples.mean(axis=1, dtype=np.float64).astype(np.float32)


def peak_dbfs(samples: npt.NDArray[np.floating]) -> float:
    """The highest absolute sample over every channel, in dBFS."""
    if samples.size == 0:
        return FLOOR_DBFS
    return float(max(FLOOR_DBFS, 20.0 * math.log10(max(float(np.abs(samples).max()), 1e-6))))


def rms_dbfs(samples: npt.NDArray[np.floating]) -> float:
    """The root mean square over every channel, in dBFS."""
    if samples.size == 0:
        return FLOOR_DBFS
    return float(_db_power(np.asarray(np.mean(samples.astype(np.float64) ** 2))))


def frame_levels(x: npt.NDArray[np.floating], tick: Tick | None = None) -> npt.NDArray[np.float64]:
    """The level (dBFS, mean square) of each analysis frame: `WINDOW` samples every `HOP`. At least one frame."""
    if len(x) < WINDOW:
        x = np.concatenate([x, np.zeros(WINDOW - len(x), dtype=x.dtype)])
    count = 1 + (len(x) - WINDOW) // HOP
    levels = np.empty(count, dtype=np.float64)
    for first in range(0, count, _CHUNK):
        last = min(count, first + _CHUNK)
        piece = x[first * HOP:(last - 1) * HOP + WINDOW]
        frames = np.lib.stride_tricks.sliding_window_view(piece, WINDOW)[::HOP].astype(np.float64)
        levels[first:last] = _db_power(np.mean(frames * frames, axis=1))
        if tick is not None:
            tick()
    return levels


def _rise(values: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """How far each value is over the highest of the `_LOOKBACK` before it along axis 0 (0 where it isn't): the first
    frames compare with the first one."""
    head = np.repeat(values[:1], _LOOKBACK, axis=0)
    ext = np.concatenate([head, values], axis=0)
    count = len(values)
    reference = np.maximum.reduce([ext[k:k + count] for k in range(_LOOKBACK)])
    return np.maximum(values - reference, 0.0)


def spectral_flux(x: npt.NDArray[np.floating], tick: Tick | None = None) -> npt.NDArray[np.float64]:
    """The spectral flux of each analysis frame, in dB: the mean over frequency of how far each bin's level rose over its
    highest in the `_LOOKBACK` frames before (a broadband attack of 30 dB gives 30; a steady noise gives about 1). Bins under
    -90 dBFS count as -90, so digital silence makes none."""
    if len(x) < WINDOW:
        x = np.concatenate([x, np.zeros(WINDOW - len(x), dtype=x.dtype)])
    count = 1 + (len(x) - WINDOW) // HOP
    window = np.hanning(WINDOW)
    norm = float(window.sum()) / 2.0
    flux = np.empty(count, dtype=np.float64)
    carry: npt.NDArray[np.float64] | None = None
    for first in range(0, count, _CHUNK):
        last = min(count, first + _CHUNK)
        piece = x[first * HOP:(last - 1) * HOP + WINDOW]
        frames = np.lib.stride_tricks.sliding_window_view(piece, WINDOW)[::HOP].astype(np.float64)
        magnitude = np.abs(np.fft.rfft(frames * window, axis=1)) / norm
        levels = np.maximum(20.0 * np.log10(magnitude + 1e-9), -90.0)[:, 1:]
        head = np.repeat(levels[:1], _LOOKBACK, axis=0) if carry is None else carry
        ext = np.concatenate([head, levels], axis=0)
        size = len(levels)
        reference = np.maximum.reduce([ext[k:k + size] for k in range(_LOOKBACK)])
        flux[first:last] = np.maximum(levels - reference, 0.0).mean(axis=1)
        carry = ext[-_LOOKBACK:]
        if tick is not None:
            tick()
    return flux


@dataclass(frozen=True)
class Span:
    """One Take's cut, in samples: `start` (the onset less the pre-roll), the `onset` itself and `end` (exclusive)."""

    start: int
    onset: int
    end: int
    overlaps_next: bool  # the next Take began before this one's level fell to the floor


def _first_onset_sample(x: npt.NDArray[np.floating], frame: int, rate: int) -> int:
    """The sample where the sound that made `frame` the first to rise begins: the first one in its neighbourhood of at
    least a tenth of the neighbourhood's peak (and over three times the level just before)."""
    a = max(0, frame * HOP - 2 * HOP)
    b = min(len(x), frame * HOP + WINDOW + int(0.02 * rate))
    segment = np.abs(x[a:b].astype(np.float64))
    peak = float(segment.max())
    before = x[max(0, a - WINDOW):a].astype(np.float64)
    noise = float(np.sqrt(np.mean(before * before))) if len(before) else 0.0
    over = np.flatnonzero(segment >= max(0.1 * peak, 3.0 * noise))
    return a + (int(over[0]) if len(over) else int(np.argmax(segment)))


def find_takes(x: npt.NDArray[np.floating], rate: int, *, threshold: float, min_gap_ms: float, pre_roll_ms: float,
               tail_ms: float, floor_db: float, tick: Tick | None = None) -> list[Span]:
    """The Takes of a mono recording, in time order, by their onsets; none when nothing rises by `threshold` dB.

    `min_gap_ms` is the least time between two onsets. A Take never overlaps the next in samples: it is cut where the next
    one starts (`overlaps_next` then says its level hadn't fallen)."""
    levels = frame_levels(x, tick)
    flux = spectral_flux(x, tick)
    strength = np.maximum(_rise(levels), flux)
    count = len(levels)
    ahead = int(0.025 * rate / HOP) + 1
    padded = np.concatenate([levels, np.full(ahead, FLOOR_DBFS)])
    loudest = np.maximum.reduce([padded[k:k + count] for k in range(ahead)])
    candidates = np.flatnonzero((strength >= threshold) & (loudest >= MIN_ONSET_DBFS))
    gap = max(1, math.ceil(min_gap_ms / 1000.0 * rate / HOP))
    onsets: list[int] = []
    frames: list[int] = []
    last = -gap
    for frame in candidates:
        if int(frame) - last < gap:
            continue
        onset = _first_onset_sample(x, int(frame), rate)
        if onsets and onset <= onsets[-1]:
            continue
        onsets.append(onset)
        frames.append(int(frame))
        last = int(frame)
    if not onsets:
        return []
    pre_roll = int(round(pre_roll_ms / 1000.0 * rate))
    tail = int(round(tail_ms / 1000.0 * rate))
    background = float(np.percentile(levels, 10))
    spans: list[Span] = []
    previous_end = 0
    for k, onset in enumerate(onsets):
        start = max(previous_end, onset - pre_roll)
        following = max(onset + 1, onsets[k + 1] - pre_roll) if k + 1 < len(onsets) else None
        first = max(0, math.ceil((onset - WINDOW + 1) / HOP))
        early = levels[first:min(count, first + int(_EARLY_PEAK_S * rate / HOP) + 1)]
        peak_frame = first + int(np.argmax(early))
        end_level = max(float(levels[peak_frame]) - floor_db, background + BACKGROUND_MARGIN_DB)
        limit_tail = onset + tail
        limit_next = following if following is not None else len(x)
        limit = min(limit_tail, limit_next, len(x))
        last_frame = min(count - 1, max(peak_frame, (limit - WINDOW // 2) // HOP))
        below = np.flatnonzero(levels[peak_frame + 1:last_frame + 1] < end_level)
        overlaps = False
        if len(below):
            end = (peak_frame + 1 + int(below[0])) * HOP + WINDOW // 2
        else:
            end = limit
            overlaps = following is not None and limit_next <= limit_tail
        end = min(max(end, onset + 1), limit, len(x))
        spans.append(Span(start=start, onset=onset, end=end, overlaps_next=overlaps))
        previous_end = end
    return spans


def find_whole(x: npt.NDArray[np.floating], rate: int, *, floor_db: float, tick: Tick | None = None) -> list[Span]:
    """One Take: the recording less its silent head and tail, where the level is `floor_db` under the recording's own
    (95th percentile) level. None when the recording holds nothing over -90 dBFS."""
    levels = frame_levels(x, tick)
    loud = float(np.percentile(levels, 95))
    if loud < -90.0:
        return []
    active = np.flatnonzero(levels >= loud - floor_db)
    start = int(active[0]) * HOP
    end = min(len(x), int(active[-1]) * HOP + WINDOW)
    return [Span(start=start, onset=start, end=end, overlaps_next=False)]


# loudness: ITU-R BS.1770-4

_K_LENGTH = 16384  # samples of the K-weighting's impulse response kept: its tail is under -100 dB by then
_k_cache: dict[int, npt.NDArray[np.float64]] = {}


def _biquad(b: tuple[float, float, float], a: tuple[float, float], size: int) -> npt.NDArray[np.float64]:
    """The impulse response of a biquad (a1 and a2 given; a0 is 1), `size` samples."""
    out = np.zeros(size, dtype=np.float64)
    x1 = x2 = y1 = y2 = 0.0
    for n in range(size):
        x0 = 1.0 if n == 0 else 0.0
        y0 = b[0] * x0 + b[1] * x1 + b[2] * x2 - a[0] * y1 - a[1] * y2
        out[n] = y0
        x2, x1, y2, y1 = x1, x0, y1, y0
    return out


def _k_weighting(rate: int) -> npt.NDArray[np.float64]:
    """The impulse response of the K-weighting filter at `rate`: the high shelf, then the high-pass, from BS.1770's
    analogue prototypes by the bilinear transform."""
    if rate not in _k_cache:
        f0, gain, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
        k = math.tan(math.pi * f0 / rate)
        vh = 10.0 ** (gain / 20.0)
        vb = vh ** 0.4996667741545416
        a0 = 1.0 + k / q + k * k
        shelf_b = ((vh + vb * k / q + k * k) / a0, 2.0 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0)
        shelf_a = (2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0)
        f0, q = 38.13547087602444, 0.5003270373238773
        k = math.tan(math.pi * f0 / rate)
        a0 = 1.0 + k / q + k * k
        high_a = (2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0)
        first = _biquad(shelf_b, shelf_a, _K_LENGTH)
        # the cascade's impulse response: the high-pass's, run over the shelf's
        out = np.zeros(_K_LENGTH, dtype=np.float64)
        x1 = x2 = y1 = y2 = 0.0
        for n in range(_K_LENGTH):
            x0 = float(first[n])
            y0 = x0 - 2.0 * x1 + x2 - high_a[0] * y1 - high_a[1] * y2
            out[n] = y0
            x2, x1, y2, y1 = x1, x0, y1, y0
        _k_cache[rate] = out
    return _k_cache[rate]


def _filtered(x: npt.NDArray[np.float64], impulse: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """`x` filtered by `impulse` (FFT overlap-add, in blocks), as long as `x`."""
    block = 1 << 17
    size = 1 << (block + len(impulse) - 1 - 1).bit_length()
    spectrum = np.fft.rfft(impulse, size)
    out = np.zeros(len(x) + len(impulse), dtype=np.float64)
    for first in range(0, len(x), block):
        piece = x[first:first + block]
        out[first:first + len(piece) + len(impulse) - 1] += np.fft.irfft(np.fft.rfft(piece, size) * spectrum, size)[
            :len(piece) + len(impulse) - 1]
    return out[:len(x)]


def _channel_weights(channels: int) -> list[float]:
    return [[1.0, 1.0, 1.0, 0.0, 1.41, 1.41][c] if c < 6 else 1.0 for c in range(channels)]


def lufs(samples: npt.NDArray[np.floating], rate: int, tick: Tick | None = None) -> float:
    """The integrated loudness in LUFS (BS.1770-4: K-weighting, 400 ms blocks every 100 ms, the -70 LUFS gate, then the
    gate 10 LU under what remains). A signal shorter than one block, such as a footstep, has no blocks to gate: its loudness
    is its mean square over the whole signal. Silence is `FLOOR_DBFS`."""
    data = samples.reshape(len(samples), -1).astype(np.float64)
    if data.shape[0] == 0:
        return FLOOR_DBFS
    impulse = _k_weighting(rate)
    segment = max(1, rate // 10)
    segments = data.shape[0] // segment
    weights = _channel_weights(data.shape[1])
    total = np.zeros(max(segments, 1), dtype=np.float64)  # the weighted mean square of each 100 ms
    whole = 0.0
    for channel in range(data.shape[1]):
        if weights[channel] == 0.0:
            continue
        filtered = _filtered(data[:, channel], impulse)
        whole += weights[channel] * float(np.mean(filtered * filtered))
        if segments:
            squares = filtered[:segments * segment] ** 2
            total += weights[channel] * squares.reshape(segments, segment).mean(axis=1)
        if tick is not None:
            tick()
    if segments < 4:
        return max(FLOOR_DBFS, -0.691 + float(_db_power(np.asarray(whole))))
    blocks = np.convolve(total, np.ones(4) / 4.0, mode="valid")
    block_loudness = -0.691 + _db_power(blocks)
    kept = blocks[block_loudness > -70.0]
    if len(kept) == 0:
        return FLOOR_DBFS
    relative = -0.691 + float(_db_power(np.asarray(kept.mean()))) - 10.0
    kept = blocks[block_loudness > max(-70.0, relative)]
    if len(kept) == 0:
        return FLOOR_DBFS
    return float(-0.691 + _db_power(np.asarray(kept.mean())))


# spectrum


def _spectrum(mono: npt.NDArray[np.floating], rate: int) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """The frequencies and power of the Hann-windowed signal; zero-padded to 4096 samples at least, so a short one still has
    bins in every band."""
    data = mono.astype(np.float64)
    size = max(4096, 1 << (len(data) - 1).bit_length()) if len(data) else 4096
    power = np.abs(np.fft.rfft(data * np.hanning(len(data)) if len(data) > 1 else data, size)) ** 2
    return np.fft.rfftfreq(size, 1.0 / rate), power


def spectral_centroid(mono: npt.NDArray[np.floating], rate: int) -> float:
    """The power-weighted mean frequency in Hz; 0 for silence."""
    frequencies, power = _spectrum(mono, rate)
    total = float(power.sum())
    return float((frequencies * power).sum() / total) if total > 0.0 else 0.0


def band_profile(mono: npt.NDArray[np.floating], rate: int) -> npt.NDArray[np.float64]:
    """The signal's level in `_BANDS` bands from 50 Hz up (equal ratios), in dB with their mean taken off: its colour,
    whatever its loudness."""
    frequencies, power = _spectrum(mono, rate)
    edges = np.geomspace(50.0, min(16000.0, rate / 2.0), _BANDS + 1)
    bands = np.array([power[(frequencies >= low) & (frequencies < high)].sum()
                      for low, high in zip(edges[:-1], edges[1:], strict=True)])
    profile = _db_power(bands + 1e-12)
    return profile - float(profile.mean())


def similarity_to_median(profiles: list[npt.NDArray[np.float64]], lengths: list[int]) -> list[float]:
    """How like the typical Take each one is, 0 to 1: the correlation of its band profile with the median profile (the
    median of each band over the Takes), mapped to 0..1, times the square root of how near its length is to the median's.
    A scrape among steps is longer and a different colour, so it scores low. One Take is 1."""
    if len(profiles) < 2:
        return [1.0] * len(profiles)
    stack = np.stack(profiles)
    median = np.median(stack, axis=0)
    median_length = float(np.median(np.asarray(lengths, dtype=np.float64)))
    scores: list[float] = []
    for profile, length in zip(profiles, lengths, strict=True):
        denominator = float(np.linalg.norm(profile) * np.linalg.norm(median))
        correlation = float(np.dot(profile, median)) / denominator if denominator > 0.0 else 1.0
        ratio = min(length, median_length) / max(length, median_length, 1.0)
        scores.append(round(0.5 * (correlation + 1.0) * math.sqrt(ratio), 4))
    return scores


@dataclass(frozen=True)
class TakeMeasures:
    peak_dbfs: float
    rms_dbfs: float
    lufs: float
    centroid_hz: float
    tail_dbfs: float  # the level of the Take's last 10 ms
    clipped: bool
    profile: npt.NDArray[np.float64]


def measure_take(samples: npt.NDArray[np.floating], rate: int, tick: Tick | None = None) -> TakeMeasures:
    """What `slice` says of one Take: peak, RMS, integrated loudness, spectral centroid, the level of its tail, whether it
    clips, and its band profile (for `similarity_to_median`)."""
    mono = to_mono(samples)
    peak = peak_dbfs(samples)
    tail = rms_dbfs(mono[-max(1, rate // 100):])
    return TakeMeasures(peak_dbfs=round(peak, 2), rms_dbfs=round(rms_dbfs(samples), 2), lufs=round(lufs(samples, rate, tick), 2),
                        centroid_hz=round(spectral_centroid(mono, rate), 1), tail_dbfs=round(tail, 2),
                        clipped=peak >= CLIP_DBFS, profile=band_profile(mono, rate))


def clean_ranks(clipped: list[bool], overlaps: list[bool], tails_dbfs: list[float], similarity: list[float]) -> list[int]:
    """Each Take's rank by how clean it is, 1 the cleanest: no clipping, then no overlap with the next Take, then the
    quieter tail (in steps of 3 dB), then the likeness to the typical Take; ties by position."""
    order = sorted(range(len(clipped)), key=lambda i: (clipped[i], overlaps[i], round(tails_dbfs[i] / 3.0), -similarity[i], i))
    ranks = [0] * len(clipped)
    for rank, index in enumerate(order, 1):
        ranks[index] = rank
    return ranks


# processing (ticket 0397)


def fade(samples: npt.NDArray[np.floating], rate: int, in_ms: float, out_ms: float) -> npt.NDArray[np.float32]:
    """`samples` (frames, channels) with a linear fade in over the first `in_ms` and out over the last `out_ms`; each is cut
    to half the length, so the two never overlap."""
    out = samples.astype(np.float32, copy=True)
    half = len(out) // 2
    fade_in = min(int(round(in_ms * rate / 1000.0)), half)
    fade_out = min(int(round(out_ms * rate / 1000.0)), half)
    if fade_in > 0:
        out[:fade_in] *= (np.arange(fade_in, dtype=np.float32) / fade_in).reshape(-1, *([1] * (out.ndim - 1)))
    if fade_out > 0:
        out[len(out) - fade_out:] *= (np.arange(fade_out, 0, -1, dtype=np.float32) / fade_out).reshape(-1, *([1] * (out.ndim - 1)))
    return out


def peak_normalise(samples: npt.NDArray[np.floating], target_dbfs: float) -> tuple[npt.NDArray[np.float32], float]:
    """`samples` scaled so the highest absolute sample is `target_dbfs`, and the gain in dB. Silence is left alone (gain 0)."""
    peak = float(np.abs(samples).max()) if samples.size else 0.0
    if peak < 1e-6:
        return samples.astype(np.float32, copy=True), 0.0
    gain = 10.0 ** (target_dbfs / 20.0) / peak
    return (samples.astype(np.float64) * gain).astype(np.float32), round(20.0 * math.log10(gain), 4)


def find_loop_end(samples: npt.NDArray[np.floating], start: int, end: int, crossfade: int, search: int,
                  tick: Tick | None = None) -> tuple[int, float]:
    """Where a loop that begins at sample `start` should end, near `end` (up to `search` samples before it): the end whose
    last `crossfade` samples best match the `crossfade` samples before `start`, which are what the seam is faded into.
    Normalised cross-correlation (FFT) over the mono mix. Returns the end and the match, -1 to 1 (1: the same sound).
    Needs `start >= crossfade` and `end - search - crossfade > start`; the first best match wins a tie."""
    mono = to_mono(samples).astype(np.float64)
    if start < crossfade:
        raise ValueError("a loop needs the crossfade's length of sound before its start")
    low = max(start + 2 * crossfade, end - search)
    if low > end:
        return end, 0.0
    reference = mono[start - crossfade:start]
    region = mono[low - crossfade:end]
    size = 1 << (len(region) + crossfade - 1).bit_length()
    numerator = np.fft.irfft(np.fft.rfft(region, size) * np.conj(np.fft.rfft(reference, size)), size)[:len(region) - crossfade + 1]
    squares = np.concatenate(([0.0], np.cumsum(region * region)))
    energy = squares[crossfade:] - squares[:len(squares) - crossfade]
    energy = energy[:len(numerator)]
    score = numerator / (np.sqrt(np.maximum(energy, 1e-18) * max(float(reference @ reference), 1e-18)))
    if tick is not None:
        tick()
    best = int(np.argmax(score))
    return low + best, round(float(score[best]), 4)


def crossfade_loop(samples: npt.NDArray[np.floating], start: int, end: int, crossfade: int,
                   match: float) -> npt.NDArray[np.float32]:
    """The loop `samples[start:end]` with its last `crossfade` samples crossfaded into the `crossfade` samples before `start`,
    so that the sample after its last is the one that follows them: the first. Equal-power for sounds that don't match (noise),
    linear for ones that do (`match` 0.5 or more), which keeps the level."""
    out = samples[start:end].astype(np.float64)
    t = (np.arange(crossfade, dtype=np.float64) + 0.5) / crossfade
    if match >= 0.5:
        w_out, w_in = 1.0 - t, t
    else:
        w_out, w_in = np.cos(0.5 * math.pi * t), np.sin(0.5 * math.pi * t)
    shape = (-1,) + (1,) * (out.ndim - 1)
    out[-crossfade:] = (samples[end - crossfade:end] * w_out.reshape(shape) + samples[start - crossfade:start] * w_in.reshape(shape))
    return out.astype(np.float32)


def seam_step(loop: npt.NDArray[np.floating]) -> float:
    """How big the jump from a loop's last sample to its first is, against the ordinary step between its neighbouring samples
    (the mean mix's RMS of the differences, over the 20 ms around the seam's two sides): near 1 is no click, 5 or more is one."""
    mono = to_mono(loop).astype(np.float64)
    ordinary = float(np.sqrt(0.5 * (np.mean(np.diff(mono[-441:]) ** 2) + np.mean(np.diff(mono[:441]) ** 2))))
    return round(abs(float(mono[0] - mono[-1])) / max(ordinary, 1e-9), 3)
