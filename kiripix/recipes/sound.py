"""The sound Recipe (spec §6.8, ADR 0016, ticket 0395): source, slice, keep, then process and export (0397, 0400).

`source` decodes the picked recording with ffmpeg to 44.1 kHz float PCM (`source.wav`, `source.json`). `slice` finds the
Takes with the sound Ops and measures each one (`takes.json`). `keep` is the Decision that names the kept Takes in order,
each by its span in the recording (`start_ms`, `end_ms`): a Take's number is only for typing, because a new threshold that
finds an extra Take renumbers the rest. On replay a recorded span matches the one current Take that starts within 15 ms of
it and covers at least half of it (ADR 0016, decision 4).
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from kiripix.checks import Finding, Position
from kiripix.ops.lazy import lazy_module
from kiripix.ops import sound as ops
from kiripix.recipes import ffmpeg, wav
from kiripix.recipes.base import (
    PICK,
    CheckSpec,
    CurrentDecision,
    DecisionSpec,
    KindSpec,
    NeedsInput,
    ParamSpec,
    StageFailure,
    StageInputs,
    StageRun,
    StageSpec,
    chain,
)
from kiripix.recipes.common import picked, source_needs_input, variants

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

SOUND = "sound"
PROCESS_STAGE, PROCESS_RECORD = "process", "process.json"
LOOP_USES = ("ambience", "music")  # the uses `process`'s `loop` = auto loops
LENGTH_RATIO = 2.0  # `process.odd_one_out`: a variation this many times longer or shorter than the median
LOUDNESS_LU = 6.0  # ... or this many LU from the median's loudness
MIN_ODD_VARIATIONS = 3
USES = ("sfx", "ui", "ambience", "music")
ONSET_USES = ("sfx", "ui")  # the uses `slice`'s `auto` mode cuts by onset; the others are one Take
SOURCE_STAGE, SLICE_STAGE, KEEP_STAGE = "source", "slice", "keep"
SOURCE_FILE, SOURCE_RECORD = "source.wav", "source.json"
TAKES_FILE, KEEP_FILE = "takes.json", "keep.json"
SCHEMA_VERSION = 1  # of source.json, takes.json and keep.json: 1 (ticket 0395)
START_TOLERANCE_MS = 15.0  # a recorded Take matches a current one that starts this close, and covers half of it
EXACT_MS = 1.0  # every bound within this: the replay is exact
SOUND_SUFFIXES = ffmpeg.SUFFIXES


def ms(sample: int, rate: int) -> float:
    """A sample position as milliseconds, to 3 decimals (a sample is 0.023 ms at 44.1 kHz)."""
    return round(sample * 1000.0 / rate, 3)


# the files the Stages write


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRecord(_Strict):
    """`source.json`: what the decoded recording is."""

    schema_version: int = SCHEMA_VERSION
    variant: str
    rate: int
    channels: int
    frames: int
    duration_ms: float


class TakeRecord(_Strict):
    """One Take in `takes.json`: its cut in samples and milliseconds, and its measures. `onset_ms` is where the sound begins;
    `start_ms` is `pre_roll` before it."""

    number: int = Field(ge=1, description="Its place in time order, from 1: what `decide keep --takes` types.")
    start_sample: int
    onset_sample: int
    end_sample: int
    start_ms: float
    onset_ms: float
    end_ms: float
    peak_dbfs: float
    rms_dbfs: float
    lufs: float
    centroid_hz: float
    similarity: float = Field(description="0 to 1: how like the typical Take it is (spectral colour and length).")
    clean_rank: int = Field(ge=1, description="1 is the cleanest: no clipping, no overlap with the next, a quiet tail.")
    tail_dbfs: float
    clipped: bool
    overlaps_next: bool


class TakesRecord(_Strict):
    """`takes.json`."""

    schema_version: int = SCHEMA_VERSION
    rate: int
    channels: int
    frames: int
    duration_ms: float
    mode: str
    settings: dict[str, float | str]
    takes: list[TakeRecord]


class KeptTake(_Strict):
    """One variation in `keep.json`: the kept Take as `slice` has it now."""

    variation: int = Field(ge=1)
    take: int
    start_sample: int
    end_sample: int
    start_ms: float
    end_ms: float


class KeepRecord(_Strict):
    """`keep.json`: the kept Takes, in the order of their variation numbers."""

    schema_version: int = SCHEMA_VERSION
    kept: list[KeptTake]


def read_takes(path: Path) -> TakesRecord:
    """`takes.json`; StageFailure (`stage.output_unreadable`, whose fix rebuilds the Stage) when it is not this version's."""
    try:
        return TakesRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as error:
        raise StageFailure(f"{path.name} can't be read: {error}") from None


# source


def _source(run: StageRun) -> None:
    chosen = picked(run)
    assert chosen is not None  # `source_needs_input` holds the Stage back until there is a Pick
    path = variants(run)[chosen]
    if not hashlib.sha256(path.read_bytes()).hexdigest().startswith(chosen):
        raise StageFailure(f"the Variant {path.name} was changed after it was imported, and Variants are immutable; "
                           "import the changed recording as a new Variant and pick that")
    target = run.output_dir / SOURCE_FILE
    ffmpeg.decode_to_wav(path, target, run.check_cancel)
    rate, samples = wav.read_wav(target)
    record = SourceRecord(variant=chosen, rate=rate, channels=samples.shape[1], frames=samples.shape[0],
                          duration_ms=ms(samples.shape[0], rate))
    (run.output_dir / SOURCE_RECORD).write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")


# slice


def resolved_mode(mode: str, use: object) -> str:
    """`onsets` or `whole`: what a `slice` mode of `auto` means for the Asset's use."""
    if mode != "auto":
        return mode
    return "onsets" if use in ONSET_USES else "whole"


def _slice(run: StageRun) -> None:
    record = SourceRecord.model_validate_json((run.upstream[SOURCE_STAGE] / SOURCE_RECORD).read_text(encoding="utf-8"))
    rate, samples = wav.read_wav(run.upstream[SOURCE_STAGE] / SOURCE_FILE)
    run.check_cancel()
    mode = resolved_mode(str(run.params["mode"]), run.asset_params.get("use"))
    mono = ops.to_mono(samples)
    if mode == "whole":
        spans = ops.find_whole(mono, rate, floor_db=float(run.params["floor"]), tick=run.check_cancel)
    else:
        spans = ops.find_takes(
            mono, rate, threshold=float(run.params["threshold"]), min_gap_ms=float(run.params["min_gap"]),
            pre_roll_ms=float(run.params["pre_roll"]), tail_ms=float(run.params["tail"]), floor_db=float(run.params["floor"]),
            tick=run.check_cancel)
    measures: list[ops.TakeMeasures] = []
    for number, span in enumerate(spans, 1):
        run.progress(number - 1, len(spans), f"measuring Take {number}")
        measures.append(ops.measure_take(samples[span.start:span.end], rate, run.check_cancel))
    similarity = ops.similarity_to_median([m.profile for m in measures], [s.end - s.start for s in spans])
    ranks = ops.clean_ranks([m.clipped for m in measures], [s.overlaps_next for s in spans],
                            [m.tail_dbfs for m in measures], similarity)
    takes = [TakeRecord(
        number=number, start_sample=span.start, onset_sample=span.onset, end_sample=span.end, start_ms=ms(span.start, rate),
        onset_ms=ms(span.onset, rate), end_ms=ms(span.end, rate), peak_dbfs=m.peak_dbfs, rms_dbfs=m.rms_dbfs, lufs=m.lufs,
        centroid_hz=m.centroid_hz, similarity=similarity[number - 1], clean_rank=ranks[number - 1], tail_dbfs=m.tail_dbfs,
        clipped=m.clipped, overlaps_next=span.overlaps_next)
        for number, (span, m) in enumerate(zip(spans, measures, strict=True), 1)]
    applied: dict[str, float | str] = {"mode": mode}
    if mode == "onsets":
        applied.update({name: float(run.params[name]) for name in ("threshold", "min_gap", "pre_roll", "tail", "floor")})
    else:
        applied["floor"] = float(run.params["floor"])
    out = TakesRecord(rate=rate, channels=record.channels, frames=record.frames, duration_ms=record.duration_ms, mode=mode,
                      settings=applied, takes=takes)
    (run.output_dir / TAKES_FILE).write_text(out.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _check_slice(run: StageRun) -> list[Finding]:
    record = read_takes(run.output_dir / TAKES_FILE)
    where = Position(asset=run.asset_id, stage=SLICE_STAGE)
    found: list[Finding] = []
    if not record.takes:
        if record.mode == "onsets":
            threshold = float(record.settings["threshold"])
            lower = max(3.0, threshold - 4.0)
            message = f"no sound rises by {record.settings['threshold']:g} dB in the recording"
            if lower < threshold:
                found.append(Finding(code="slice.none", message=message, position=where,
                                     fix=f"kiripix set {run.asset_id} slice threshold={lower:g}"))
            else:  # at the lowest threshold already: a lower one is no fix
                found.append(Finding(code="slice.none", message=message, position=where,
                                     owner_action=f"Import a louder recording, or take it whole: "
                                                  f"kiripix set {run.asset_id} slice mode=whole."))
        else:
            found.append(Finding(code="slice.none", message="the recording holds nothing over -90 dBFS", position=where,
                                 owner_action="Import a recording that has sound in it."))
    clipped = [t.number for t in record.takes if t.clipped]
    if clipped:
        found.append(Finding(
            code="slice.clipped", severity="warning", position=where, data={"takes": clipped},
            message=f"Take {', '.join(map(str, clipped))} reach{'es' if len(clipped) == 1 else ''} 0 dBFS: clipped",
            fix=f"kiripix sound-takes {run.asset_id}"))
    overlapping = [t.number for t in record.takes if t.overlaps_next]
    if overlapping:
        found.append(Finding(
            code="slice.overlap", severity="warning", position=where, data={"takes": overlapping},
            message=f"Take {', '.join(map(str, overlapping))} still sound{'s' if len(overlapping) == 1 else ''} when the next "
                    "Take begins: they run together",
            fix=f"kiripix sound-takes {run.asset_id}"))
    return found


# keep


def _keep_problem(data: dict[str, Any]) -> str | None:
    spans = [(float(t["start_ms"]), float(t["end_ms"])) for t in data["takes"]]
    for start, end in spans:
        if end <= start:
            return f"a Take's end_ms ({end:g}) is not after its start_ms ({start:g})"
    for i, (start, _) in enumerate(spans):
        if any(abs(start - other) <= EXACT_MS for other, _ in spans[:i]):
            return f"two kept Takes start at {start:g} ms: a Take is kept once"
    return None


KEEP = DecisionSpec(
    name="keep",
    description="The Takes to keep, in order: their spans in the recording. The order gives the variation numbers 1, 2, ... "
                "`kiripix decide <id> keep --takes 3,5,8` writes it from the numbers `sound-takes` shows. Latest counts.",
    entry_schema={
        "type": "object",
        "properties": {"takes": {"type": "array", "minItems": 1, "items": {
            "type": "object",
            "properties": {"start_ms": {"type": "number", "minimum": 0}, "end_ms": {"type": "number", "minimum": 0}},
            "required": ["start_ms", "end_ms"], "additionalProperties": False}}},
        "required": ["takes"],
        "additionalProperties": False,
    },
    problem=_keep_problem,
)


def kept_spans(decision: CurrentDecision) -> list[tuple[float, float]]:
    """A `keep` Decision's spans in order, as (start_ms, end_ms)."""
    return [(float(t["start_ms"]), float(t["end_ms"])) for t in decision.data["takes"]]


def latest_keep(decisions: tuple[CurrentDecision, ...]) -> CurrentDecision | None:
    kept = [d for d in decisions if d.name == KEEP.name]
    return kept[-1] if kept else None


@dataclass(frozen=True)
class Match:
    """One recorded span against the current Takes: `status` is `exact` (both bounds within 1 ms), `moved`, `missing` (no
    Take matches), `split` (two or more do) or `merged` (its Take is already another kept Take's). `take` is the one
    Take it matched, for `exact` and `moved`."""

    index: int  # its place in the Decision, from 0
    start_ms: float
    end_ms: float
    status: str
    take: TakeRecord | None = None
    candidates: tuple[int, ...] = ()  # the numbers of the Takes that matched, for `split`


def _covers(take: TakeRecord, start_ms: float, end_ms: float) -> bool:
    shared = min(take.end_ms, end_ms) - max(take.start_ms, start_ms)
    return shared >= 0.5 * (end_ms - start_ms)


def match_takes(spans: list[tuple[float, float]], takes: list[TakeRecord]) -> list[Match]:
    """Each recorded span against the current Takes (ADR 0016, decision 4): the one Take that starts within 15 ms of it
    and covers at least half of it. The Stage never drops a Take or picks a neighbour."""
    found: list[Match] = []
    used: dict[int, int] = {}
    for index, (start, end) in enumerate(spans):
        near = [t for t in takes if abs(t.start_ms - start) <= START_TOLERANCE_MS and _covers(t, start, end)]
        if not near:
            found.append(Match(index, start, end, "missing"))
        elif len(near) > 1:
            found.append(Match(index, start, end, "split", candidates=tuple(t.number for t in near)))
        elif near[0].number in used:
            found.append(Match(index, start, end, "merged", near[0], (near[0].number,)))
        else:
            take = near[0]
            used[take.number] = index
            exact = abs(take.start_ms - start) <= EXACT_MS and abs(take.end_ms - end) <= EXACT_MS
            found.append(Match(index, start, end, "exact" if exact else "moved", take))
    return found


def _span_text(start: float, end: float) -> str:
    return f"{start:g}-{end:g} ms"


def _current_takes(run: StageRun) -> list[TakeRecord] | None:
    path = run.upstream[SLICE_STAGE] / TAKES_FILE
    try:
        return read_takes(path).takes if path.is_file() else None
    except StageFailure:
        return None  # an older `slice` output: it is rebuilt first


def _keep_needs_input(run: StageRun) -> NeedsInput | None:
    decision = latest_keep(run.decisions)
    look = f"kiripix sound-takes {run.asset_id}"
    if decision is None:
        return NeedsInput("no Takes kept: choose them after looking at the Takes slice found", command=look)
    takes = _current_takes(run)
    if takes is None:
        return None  # `slice` isn't built: it comes first
    problems = [m for m in match_takes(kept_spans(decision), takes) if m.status in ("missing", "split", "merged")]
    if not problems:
        return None
    first = problems[0]
    place = f"kept Take {first.index + 1} ({_span_text(first.start_ms, first.end_ms)})"
    if first.status == "split":
        code = "keep.take_split"
        why = f"{place} is now {len(first.candidates)} Takes ({', '.join(map(str, first.candidates))})"
    elif first.status == "merged":
        code = "keep.take_missing"
        why = f"{place} is now run together with an earlier kept Take (Take {first.candidates[0]})"
    else:
        code = "keep.take_missing"
        why = f"{place} matches no Take now"
    more = f" (and {len(problems) - 1} more)" if len(problems) > 1 else ""
    return NeedsInput(why + more + ": decide the Takes to keep again", command=look, code=code,
                      data={"take": first.index + 1, "start_ms": first.start_ms, "end_ms": first.end_ms,
                            "problems": [{"take": m.index + 1, "status": m.status, "start_ms": m.start_ms, "end_ms": m.end_ms,
                                          "candidates": list(m.candidates)} for m in problems]})


def _keep(run: StageRun) -> None:
    decision = latest_keep(run.decisions)
    takes = _current_takes(run)
    assert decision is not None and takes is not None  # `needs_input` holds the Stage back
    kept: list[KeptTake] = []
    for match in match_takes(kept_spans(decision), takes):
        if match.take is None or match.status not in ("exact", "moved"):
            raise StageFailure(f"kept Take {match.index + 1} ({_span_text(match.start_ms, match.end_ms)}) matches no Take")
        take = match.take
        kept.append(KeptTake(variation=match.index + 1, take=take.number, start_sample=take.start_sample,
                             end_sample=take.end_sample, start_ms=take.start_ms, end_ms=take.end_ms))
    (run.output_dir / KEEP_FILE).write_text(KeepRecord(kept=kept).model_dump_json(indent=2) + "\n", encoding="utf-8")


def _keep_review(run: StageRun) -> list[tuple[CurrentDecision, dict[str, Any]]]:
    """A kept Take whose bound moved more than 1 ms (a changed `tail`) is needs-review: `accept` records the new spans."""
    decision = latest_keep(run.decisions)
    takes = _current_takes(run)
    if decision is None or takes is None:
        return []
    matches = match_takes(kept_spans(decision), takes)
    if any(m.take is None or m.status not in ("exact", "moved") for m in matches) or all(m.status == "exact" for m in matches):
        return []
    return [(decision, {"takes": [{"start_ms": m.take.start_ms, "end_ms": m.take.end_ms} for m in matches if m.take is not None]})]


# process


def _p(name: str, type_: Any, default: Any, minimum: float | None, maximum: float | None, description: str,
       choices: list[str] | None = None) -> ParamSpec:
    return ParamSpec(name=name, type=type_, default=default, minimum=minimum, maximum=maximum, choices=choices,
                     description=description)


PROCESS_PARAMS = (
    _p("trim_start", "float", 0.0, 0, 60000, "ms cut off the start of each kept Take."),
    _p("trim_end", "float", 0.0, 0, 60000, "ms cut off the end of each kept Take."),
    _p("fade_in", "float", 2.0, 0, 5000, "ms of fade in (not for a loop: its seam is crossfaded)."),
    _p("fade_out", "float", 10.0, 0, 10000, "ms of fade out (not for a loop)."),
    _p("speed", "float", 1.0, 0.25, 4, "Playback speed, pitch and length together (1.5: a third shorter and a fifth higher)."),
    _p("pitch", "float", 0.0, -24, 24, "Semitones to shift the pitch by, the length kept (rubberband)."),
    _p("highpass", "float", 0.0, 0, 20000, "Hz under which sound is cut; 0 is off."),
    _p("lowpass", "float", 0.0, 0, 22000, "Hz over which sound is cut; 0 is off."),
    _p("denoise", "float", 0.0, 0, 30, "dB of light noise reduction (afftdn); 0 is off."),
    _p("channels", "int", 0, 0, 2, "1 or 2 to mix to that many channels; 0 takes the use's row of `[sound.use.<use>]`."),
    _p("loop", "choice", "auto", None, None, "on, off, or auto (ambience and music loop, sfx and ui don't).",
       ["auto", "on", "off"]),
    _p("loop_start", "float", 0.0, 0, 3600000, "A loop: ms into the processed Take where it begins (at least the crossfade)."),
    _p("loop_end", "float", 0.0, 0, 3600000, "A loop: ms into the processed Take where its window ends; 0 is the Take's end."),
    _p("loop_crossfade", "float", 50.0, 5, 5000, "A loop: ms of crossfade at the seam."),
    _p("loop_search", "float", 1000.0, 0, 60000, "A loop: how many ms before `loop_end` its end may move to match the start."),
    _p("loop_min_match", "float", 0.2, 0, 1, "A loop: the least match (-1 to 1) of its end to its start before `process.loop_seam`."),
)


def _tune_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {"start_ms": {"type": "number", "minimum": 0}, "end_ms": {"type": "number", "minimum": 0}}
    for spec in PROCESS_PARAMS:
        if spec.type == "choice":
            properties[spec.name] = {"enum": spec.choices}
        else:
            properties[spec.name] = {"type": "integer" if spec.type == "int" else "number", "minimum": spec.minimum,
                                     "maximum": spec.maximum}
    return {"type": "object", "properties": properties, "required": ["start_ms", "end_ms"], "additionalProperties": False}


def _tune_problem(data: dict[str, Any]) -> str | None:
    if float(data["end_ms"]) <= float(data["start_ms"]):
        return f"end_ms ({data['end_ms']:g}) is not after start_ms ({data['start_ms']:g})"
    return None


TUNE = DecisionSpec(
    name="tune",
    description="Process parameters for one kept Take, named by its span in the recording (`start_ms`, `end_ms`, as `sound-takes` "
                "and `keep` give them) with any of the Stage's parameters: they replace the Asset's for that variation. "
                'For example {"start_ms": 500, "end_ms": 900, "speed": 1.5}. Several for one Take apply in order.',
    entry_schema=_tune_schema(),
    problem=_tune_problem,
)


class ProcessedTake(_Strict):
    """One variation in `process.json`. `loop_offset` is where the loop begins in the processed Take (ms; null when it isn't a
    loop), `loop_match` how well its end matched its start (-1 to 1)."""

    variation: int = Field(ge=1)
    take: int
    file: str
    start_ms: float
    end_ms: float
    length_ms: float
    peak_dbfs: float
    lufs: float
    loop: bool
    loop_offset: float | None
    loop_match: float | None
    settings: dict[str, float | str]
    overridden: bool = Field(description="A `tune` Decision changed some of its settings.")


class UnmatchedTune(_Strict):
    start_ms: float
    end_ms: float


class ProcessRecord(_Strict):
    """`process.json`."""

    schema_version: int = SCHEMA_VERSION
    use: str
    rate: int
    channels: int
    target: dict[str, float]
    variations: list[ProcessedTake]
    unmatched_tunes: list[UnmatchedTune] = []


def read_process(path: Path) -> ProcessRecord:
    """`process.json`; StageFailure (`stage.output_unreadable`) when it is not this version's."""
    try:
        return ProcessRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as error:
        raise StageFailure(f"{path.name} can't be read: {error}") from None


def _tunes(run: StageRun, takes: list[TakeRecord], kept: list[KeptTake]) -> tuple[dict[int, dict[str, Any]], list[UnmatchedTune]]:
    """Each variation's `tune` parameters, merged in order, and the `tune` Decisions that name no kept Take."""
    merged: dict[int, dict[str, Any]] = {}
    unmatched: list[UnmatchedTune] = []
    variation_of = {k.take: k.variation for k in kept}
    for decision in run.decisions:
        if decision.name != TUNE.name:
            continue
        start, end = float(decision.data["start_ms"]), float(decision.data["end_ms"])
        found = match_takes([(start, end)], takes)[0]
        if found.take is None or found.take.number not in variation_of:
            unmatched.append(UnmatchedTune(start_ms=start, end_ms=end))
            continue
        merged.setdefault(variation_of[found.take.number], {}).update(
            {k: v for k, v in decision.data.items() if k not in ("start_ms", "end_ms")})
    return merged, unmatched


def _filters(values: dict[str, Any], rate: int) -> str:
    """The ffmpeg chain for the denoise, speed, pitch and filter parameters, in that order (denoise on the recording's own
    noise; the filters on what is heard)."""
    chain: list[str] = []
    if float(values["denoise"]) > 0:
        chain.append(f"afftdn=nr={float(values['denoise']):g}:tn=1")
    if float(values["speed"]) != 1.0:
        chain.append(f"asetrate={round(rate * float(values['speed']))}")
    if float(values["pitch"]) != 0.0:
        chain.append(f"rubberband=pitch={2.0 ** (float(values['pitch']) / 12.0):.6f}")
    if float(values["highpass"]) > 0:
        chain.append(f"highpass=f={float(values['highpass']):g}")
    if float(values["lowpass"]) > 0:
        chain.append(f"lowpass=f={float(values['lowpass']):g}")
    return ",".join(chain)


def _samples(milliseconds: float, rate: int) -> int:
    return int(round(milliseconds * rate / 1000.0))


def _process(run: StageRun) -> None:
    use = str(run.asset_params.get("use", ""))
    row = run.settings["sound.use"][use]
    takes_record = read_takes(run.upstream[SLICE_STAGE] / TAKES_FILE)
    kept = KeepRecord.model_validate_json((run.upstream[KEEP_STAGE] / KEEP_FILE).read_text(encoding="utf-8")).kept
    source_rate, source = wav.read_wav(run.upstream[SOURCE_STAGE] / SOURCE_FILE)
    tunes, unmatched = _tunes(run, takes_record.takes, kept)
    rate = ffmpeg.RATE
    out_channels = int(row["channels"])
    target: dict[str, float] = {}
    if row.get("peak") is not None:
        target = {"peak": float(row["peak"])}
    else:
        target = {"lufs": float(row["lufs"]), "true_peak": float(row["true_peak"]), "lra": float(row["lra"])}
    done: list[ProcessedTake] = []
    # the intermediate WAVs stay inside the output folder core gives the Stage, and go before it returns
    with tempfile.TemporaryDirectory(prefix=".scratch-", dir=run.output_dir) as folder:
        work = Path(folder)
        for take in kept:
            run.progress(take.variation - 1, len(kept), f"processing variation {take.variation}")
            run.check_cancel()
            values = {**run.params, **tunes.get(take.variation, {})}
            channels = int(values["channels"]) or out_channels
            first = take.start_sample + _samples(float(values["trim_start"]), source_rate)
            last = take.end_sample - _samples(float(values["trim_end"]), source_rate)
            if last - first < source_rate // 100:
                raise StageFailure(f"variation {take.variation}: trim_start and trim_end leave under 10 ms of the Take")
            wav.write_wav(work / "cut.wav", source_rate, source[first:last])
            ffmpeg.filter_wav(work / "cut.wav", work / "filtered.wav", _filters(values, source_rate), channels, run.check_cancel,
                              rate)
            _, signal = wav.read_wav(work / "filtered.wav")
            looped = values["loop"] == "on" or (values["loop"] == "auto" and use in LOOP_USES)
            offset: float | None = None
            match: float | None = None
            if looped:
                crossfade = min(_samples(float(values["loop_crossfade"]), rate), len(signal) // 4)
                start = max(_samples(float(values["loop_start"]), rate), crossfade)
                window_end = min(_samples(float(values["loop_end"]), rate) or len(signal), len(signal))
                if crossfade < 1 or window_end - start < 4 * crossfade:
                    raise StageFailure(f"variation {take.variation}: the loop window is too short for its crossfade; "
                                       "lower loop_crossfade or widen loop_start and loop_end")
                end, match = ops.find_loop_end(signal, start, window_end, crossfade, _samples(float(values["loop_search"]), rate),
                                               run.check_cancel)
                signal = ops.crossfade_loop(signal, start, end, crossfade, match)
                offset = 0.0  # the file is the loop body alone: it begins where every repeat begins
            else:
                signal = ops.fade(signal, rate, float(values["fade_in"]), float(values["fade_out"]))
            if "peak" in target:
                signal, _ = ops.peak_normalise(signal, target["peak"])
            else:
                length = len(signal)
                wav.write_wav(work / "pre.wav", rate, signal)
                measured = ffmpeg.measure_loudness(work / "pre.wav", target["lufs"], target["true_peak"], target["lra"],
                                                   run.check_cancel)
                ffmpeg.apply_loudness(work / "pre.wav", work / "post.wav", target["lufs"], target["true_peak"], target["lra"],
                                      measured, run.check_cancel, rate)
                _, signal = wav.read_wav(work / "post.wav")
                if len(signal) >= length:
                    signal = signal[:length]
                else:
                    # loudnorm resamples, so its length can be a few samples off: repeat the last sample, never pad with
                    # silence, which would click at a loop's seam
                    signal = np.pad(signal, ((0, length - len(signal)), (0, 0)), mode="edge")
            name = f"{take.variation}.wav"
            wav.write_wav(run.output_dir / name, rate, signal)
            applied: dict[str, float | str] = {k: (v if isinstance(v, str) else float(v)) for k, v in values.items()}
            applied["channels"] = float(channels)
            applied["loop"] = "on" if looped else "off"
            done.append(ProcessedTake(
                variation=take.variation, take=take.take, file=name, start_ms=take.start_ms, end_ms=take.end_ms,
                length_ms=ms(len(signal), rate), peak_dbfs=round(ops.peak_dbfs(signal), 2),
                lufs=round(ops.lufs(signal, rate, run.check_cancel), 2), loop=looped, loop_offset=offset,
                loop_match=match, settings=applied, overridden=take.variation in tunes))
    record = ProcessRecord(use=use, rate=rate, channels=out_channels, target=target, variations=done, unmatched_tunes=unmatched)
    (run.output_dir / PROCESS_RECORD).write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _check_process(run: StageRun) -> list[Finding]:
    record = read_process(run.output_dir / PROCESS_RECORD)
    where = Position(asset=run.asset_id, stage=PROCESS_STAGE)
    found: list[Finding] = []
    for item in record.variations:
        if not item.loop or item.loop_match is None:
            continue
        least = float(item.settings["loop_min_match"])
        if item.loop_match >= least:
            continue
        crossfade = float(item.settings["loop_crossfade"])
        message = (f"variation {item.variation}'s loop end matches its start by {item.loop_match:g} (under {least:g}): "
                   "the seam may be heard")
        data: dict[str, Any] = {"variation": item.variation, "match": item.loop_match}
        if crossfade < 2500:
            found.append(Finding(code="process.loop_seam", severity="warning", message=message, position=where, data=data,
                                 fix=f"kiripix set {run.asset_id} process loop_crossfade={min(crossfade * 2, 5000):g}"))
        else:
            found.append(Finding(code="process.loop_seam", severity="warning", message=message, position=where, data=data,
                                 owner_action="Choose another window with loop_start and loop_end, or another recording."))
    if len(record.variations) >= MIN_ODD_VARIATIONS:
        length = statistics.median(v.length_ms for v in record.variations)
        loud = statistics.median(v.lufs for v in record.variations)
        for item in record.variations:
            why = None
            if item.length_ms > LENGTH_RATIO * length or item.length_ms * LENGTH_RATIO < length:
                why = f"{item.length_ms:g} ms long against the median {length:g} ms"
            elif abs(item.lufs - loud) > LOUDNESS_LU:
                why = f"{item.lufs:g} LUFS against the median {loud:g}"
            if why:
                found.append(Finding(
                    code="process.odd_one_out", severity="warning", position=where,
                    data={"variation": item.variation, "length_ms": item.length_ms, "lufs": item.lufs},
                    message=f"variation {item.variation} is {why}: it may not belong with the others",
                    fix=f"kiripix sound-takes {run.asset_id}"))
    for tune in record.unmatched_tunes:
        found.append(Finding(
            code="process.override_unmatched", severity="warning", position=where,
            message=f"a `tune` for {_span_text(tune.start_ms, tune.end_ms)} names no kept Take, so it changed nothing",
            fix=f"kiripix sound-takes {run.asset_id}"))
    return found


# export (ticket 0400)

EXPORT_STAGE, SOUND_RECORD = "export", "sound.json"
SOUND_SCHEMA_VERSION = 1  # of sound.json: 1 (ticket 0400)
_STEM = re.compile(r"^[A-Za-z0-9_-]+$")
_PROVENANCE_FIELDS = ("url", "author", "licence")


def file_stem(sound_id: str, prefix: str) -> str:
    """The exported files' name: the `sound_id` without its prefix, dots as underscores (`sfx.footstep.asphalt` is
    `footstep_asphalt`). A `sound_id` that is only the prefix, or that doesn't start with it (`sound.id_prefix` says so), keeps
    what it has."""
    rest = sound_id[len(prefix) + 1:] if sound_id.startswith(prefix + ".") else sound_id
    return rest.replace(".", "_")


def file_names(stem: str, count: int) -> list[str]:
    """The OGG file names of `count` variations: `<stem>_<n>.ogg`, or `<stem>.ogg` when there is one (Owner, 2026-11-27)."""
    if count == 1:
        return [f"{stem}.ogg"]
    return [f"{stem}_{number}.ogg" for number in range(1, count + 1)]


def read_provenance(asset_dir: Path, relative: str) -> tuple[str | None, dict[str, str | None]]:
    """The name a stored recording was imported with and its newest Provenance, from `imported.jsonl` (ADR 0016, decision 8).
    Of the lines that name the file and carry any of `url`, `author` and `licence` the one with the latest `at` wins (the file is
    `merge=union`, so file order says nothing; a line without `at` is oldest, a tie goes to the later line). The name is the
    last line's `imported_as`. A Stage can't import core, so it reads the file itself."""
    found: dict[str, str | None] = {name: None for name in _PROVENANCE_FIELDS}
    shown: str | None = None
    try:
        lines = (asset_dir / "imported.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None, found
    best: tuple[str, int] | None = None
    for number, line in enumerate(lines):
        try:
            entry = json.loads(line) if line.strip() else None
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("file") != relative:
            continue
        if entry.get("imported_as"):
            shown = str(entry["imported_as"])
        if not any(entry.get(name) for name in _PROVENANCE_FIELDS):
            continue
        key = (str(entry.get("at") or ""), number)
        if best is None or key >= best:
            best = key
            found = {name: (str(entry[name]) if entry.get(name) else None) for name in _PROVENANCE_FIELDS}
    return shown, found


class SoundTake(_Strict):
    start_ms: float
    end_ms: float


class SoundFile(_Strict):
    """One exported variation in `sound.json`: its file, its Take, and what was measured of the encoded file."""

    variation: int = Field(ge=1)
    file: str
    take: SoundTake
    length_s: float
    peak_dbfs: float
    lufs: float
    loop: bool
    loop_offset: float | None


class SoundSource(_Strict):
    """The recording the sounds were cut from: the name it was imported with, the hash of the stored file, and its Provenance."""

    file: str
    hash: str
    url: str | None
    author: str | None
    licence: str | None


class SoundRecord(_Strict):
    """`sound.json`: Kiripix's own record for the Exporter, which copies it into the Manifest's `sound` block."""

    schema_version: int = SOUND_SCHEMA_VERSION
    id: str
    use: str
    stem: str
    rate: int
    quality: float
    channels: int
    files: list[SoundFile]
    source: SoundSource
    processing: dict[str, Any]


def read_sound(path: Path) -> SoundRecord:
    """`sound.json`; StageFailure (`stage.output_unreadable`) when it is not this version's."""
    try:
        return SoundRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as error:
        raise StageFailure(f"{path.name} can't be read: {error}") from None


def _export(run: StageRun) -> None:
    use = str(run.asset_params.get("use", ""))
    settings = run.settings["sound"]
    prefix = str(settings["use"][use]["prefix"])
    given = run.asset_params.get("sound_id")
    sound_id = str(given) if isinstance(given, str) and given else f"{prefix}.{run.asset_id.split('.', 1)[1]}"
    stem = file_stem(sound_id, prefix)
    if not _STEM.match(stem):
        raise StageFailure(f"{run.asset_id}'s sound_id {sound_id!r} makes the file name {stem!r}, which isn't letters, digits, "
                           "underscores and hyphens", code="sound.id_invalid",
                           owner_action="Set sound_id under [params] in the sound's asset.toml to letters and digits "
                                        "separated by dots, such as sfx.footstep.asphalt.")
    rate, quality = int(settings["rate"]), float(settings["quality"])
    process = read_process(run.upstream[PROCESS_STAGE] / PROCESS_RECORD)
    names = file_names(stem, len(process.variations))
    files: list[SoundFile] = []
    for item, name in zip(process.variations, names, strict=True):
        run.progress(item.variation - 1, len(process.variations), f"encoding {name}")
        run.check_cancel()
        ffmpeg.encode_ogg(run.upstream[PROCESS_STAGE] / item.file, run.output_dir / name, quality, rate, run.check_cancel)
        heard_rate, heard = ffmpeg.decode(run.output_dir / name, run.check_cancel, rate)  # what the game will play
        files.append(SoundFile(
            variation=item.variation, file=name, take=SoundTake(start_ms=item.start_ms, end_ms=item.end_ms),
            length_s=round(len(heard) / heard_rate, 3), peak_dbfs=round(ops.peak_dbfs(heard), 2),
            lufs=round(ops.lufs(heard, heard_rate, run.check_cancel), 2), loop=item.loop, loop_offset=item.loop_offset))
    variant = SourceRecord.model_validate_json((run.upstream[SOURCE_STAGE] / SOURCE_RECORD).read_text(encoding="utf-8")).variant
    stored = sorted(p for p in (run.asset_dir / "src").glob(f"{variant}.*") if p.suffix in SOUND_SUFFIXES)
    if not stored:
        raise StageFailure(f"the picked recording {variant} is not in src/ any more")
    shown, provenance = read_provenance(run.asset_dir, stored[0].relative_to(run.asset_dir).as_posix())
    source = SoundSource(file=shown or stored[0].name, hash=hashlib.sha256(stored[0].read_bytes()).hexdigest(), **provenance)
    processing: dict[str, Any] = {"target": process.target, "settings": [v.settings for v in process.variations]}
    record = SoundRecord(id=sound_id, use=use, stem=stem, rate=rate, quality=quality, channels=process.channels, files=files,
                         source=source, processing=processing)
    (run.output_dir / SOUND_RECORD).write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _check_export(run: StageRun) -> list[Finding]:
    record = read_sound(run.output_dir / SOUND_RECORD)
    missing = [name for name, value in (("author", record.source.author), ("licence", record.source.licence)) if not value]
    if not missing:
        return []
    return [Finding(
        code="sound.provenance_missing", position=Position(asset=run.asset_id, stage=EXPORT_STAGE),
        message=f"{record.source.file}, the recording of {run.asset_id}, has no {' and no '.join(missing)}: the game can't "
                "credit it",
        owner_action=f"Confirm the recording's author and licence, then run: kiripix import {run.asset_id} "
                     f"<{record.source.file}> --author <author> --licence <licence> [--url <url>]. Only the Owner "
                     "confirms a licence.")]


SOUND_KIND = KindSpec(
    name=SOUND,
    description="A sound effect, UI sound, ambience bed or piece of music: cut from one recording into Takes, the kept ones "
                "processed to the use's loudness and exported as numbered OGG Vorbis files.",
    params=(
        ParamSpec(name="use", type="choice", required=True, choices=list(USES),
                  description="What the sound is for: sfx, ui, ambience or music. Picks its row of `[sound.use.<use>]` (the "
                              "loudness target and channels) and its export folder. Frozen once exported."),
        ParamSpec(name="sound_id", type="str", default="",
                  description="The game's ID, such as sfx.footstep.asphalt: it starts with the use's prefix (sfx, ui, amb, "
                              "music). Default <prefix>.<name>. Frozen once exported."),
    ),
    stages=chain(
        StageSpec(
            name=SOURCE_STAGE,
            description="The recording (WAV, FLAC, MP3 or OGG), imported as a Variant and picked, decoded with ffmpeg to "
                        "44.1 kHz float PCM keeping its channels.",
            inputs=StageInputs(files=[f"src/*{suffix}" for suffix in SOUND_SUFFIXES], settings=[ffmpeg.VERSION_SETTING]),
            decisions=(PICK,),
            owner_input="Imports and picks; an agent may pick a lone recording.",
            available_from="M6",
            run=_source,
            needs_input=source_needs_input,
        ),
        StageSpec(
            name=SLICE_STAGE,
            description="Finds the Takes (mode `onsets`: the level or the spectrum rising by `threshold` dB; `whole`: the "
                        "recording less its silent head and tail; `auto`: onsets for sfx and ui, whole for ambience and music) "
                        "and measures each: span, peak, RMS, LUFS, spectral centroid, likeness to the typical Take, clean rank.",
            params=(
                ParamSpec(name="mode", type="choice", default="auto", choices=["auto", "onsets", "whole"],
                          description="onsets, whole, or auto (onsets for sfx and ui; whole for ambience and music)."),
                ParamSpec(name="threshold", type="float", default=12.0, minimum=3, maximum=60,
                          description="Onsets: the dB the level (or any band's) must rise by within a few ms. Lower finds "
                                      "fainter sounds, and more of them."),
                ParamSpec(name="min_gap", type="float", default=120.0, minimum=20, maximum=5000,
                          description="Onsets: the least ms between two onsets."),
                ParamSpec(name="pre_roll", type="float", default=10.0, minimum=0, maximum=500,
                          description="Onsets: ms kept before the onset."),
                ParamSpec(name="tail", type="float", default=1500.0, minimum=20, maximum=30000,
                          description="Onsets: the longest a Take's tail may run after its onset, in ms."),
                ParamSpec(name="floor", type="float", default=30.0, minimum=6, maximum=90,
                          description="The dB under the Take's own early peak (onsets), or under the recording's level "
                                      "(whole), at which the sound is taken to have ended."),
            ),
            checks=(CheckSpec(code="slice.none", description="Something rises over the threshold."),
                    CheckSpec(code="slice.clipped", description="No Take reaches 0 dBFS."),
                    CheckSpec(code="slice.overlap", description="Each Take has died away before the next begins.")),
            available_from="M6",
            run=_slice,
            check=_check_slice,
        ),
        StageSpec(
            name=KEEP_STAGE,
            description="The kept Takes in order, from a `keep` Decision that names each by its span. The order gives the "
                        "variation numbers. A Take that moved (a changed `tail`) is needs-review; one that is gone or split "
                        "is needs-input.",
            decisions=(KEEP,),
            checks=(CheckSpec(code="keep.take_missing", description="Every kept Take is still found by slice."),
                    CheckSpec(code="keep.take_split", description="No kept Take has split into two.")),
            owner_input="The `keep` Decision (an agent may record it).",
            available_from="M6",
            run=_keep,
            needs_input=_keep_needs_input,
            review=_keep_review,
            review_reason="a kept Take's bounds moved: listen, then accept",
        ),
        StageSpec(
            name=PROCESS_STAGE,
            description="Per kept Take: trim, `denoise`, `speed` (tempo and pitch together), `pitch` alone, `highpass`, `lowpass`, "
                        "fades, the use's channels and loudness (peak for sfx and ui, two-pass loudnorm for a LUFS target), and "
                        "for a loop (ambience and music) the end matched to the start by cross-correlation and crossfaded. "
                        "Writes `<n>.wav` (44.1 kHz float) and `process.json`. A `tune` Decision overrides any parameter for "
                        "one Take, named by its span.",
            inputs=StageInputs(upstream=[SOURCE_STAGE, SLICE_STAGE, KEEP_STAGE], settings=[ffmpeg.VERSION_SETTING, "sound.use"]),
            version=2,  # 2: a loop's `loop_offset` is 0, as its file begins at the loop (review of 0397); hashes only `sound.use`
            params=PROCESS_PARAMS,
            decisions=(TUNE,),
            checks=(CheckSpec(code="process.odd_one_out", description="No variation's length or loudness is far from the others'."),
                    CheckSpec(code="process.loop_seam", description="A loop's end matches its start well enough to join."),
                    CheckSpec(code="process.override_unmatched", description="Each `tune` names a kept Take.")),
            owner_input="Per-Take overrides (`tune`).",
            available_from="M6",
            run=_process,
            check=_check_process,
        ),
        StageSpec(
            name=EXPORT_STAGE,
            description="Encodes each variation to OGG Vorbis (`[sound] rate` and `quality`) and leaves `<name>[_<n>].ogg` and "
                        "`sound.json` (the Manifest's `sound` block) for the Exporter. `kiripix export` copies the files to "
                        "`<[sound] folder>/<use>/`.",
            version=2,  # 2: the Stage encodes and writes `sound.json` (ticket 0400); it was a stub
            inputs=StageInputs(upstream=[SOURCE_STAGE, PROCESS_STAGE], files=["imported.jsonl"],
                               settings=[ffmpeg.VERSION_SETTING, "sound"]),
            checks=(CheckSpec(code="sound.provenance_missing", description="The recording has an author and a licence."),),
            output_root="out",
            available_from="M6",
            run=_export,
            check=_check_export,
        ),
    ),
)
