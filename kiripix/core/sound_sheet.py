"""The sound contact sheet (spec §6.8, ticket 0396): a picture of a sound's recording with its Takes marked, then a row for each
Take (its waveform, its spectrogram and its numbers) and, after `process`, a row under it for the processed variation, so that
a change of speed or loudness shows in its numbers. The drawing is `kiripix.ops.sound_sheet`; this module lays the pictures
out, writes the text (PIL's default font, as the cast sheet does) and the PNG. Nothing is recorded in the Project.

Width is fixed at `WIDTH` pixels. A Take row and its processed row share one time scale (the longer of the two fills the
picture), so a speed change is a shorter waveform; levels are absolute (a louder file is taller and brighter).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.core import atomic
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.core.sounds import TakesView, takes_view
from kiripix.checks import Position
from kiripix.ops import sound as sound_ops
from kiripix.ops import sound_sheet as draw
from kiripix.recipes import wav
from kiripix.recipes.sound import (
    PROCESS_PARAMS,
    PROCESS_RECORD,
    PROCESS_STAGE,
    SOURCE_FILE,
    SOURCE_STAGE,
    ProcessedTake,
    TakeRecord,
    read_process,
)

WIDTH = 1500
MARGIN = 8
TITLE_HEIGHT = 18
OVERVIEW_HEIGHT = 96
RULER_HEIGHT = 16
CELL_WIDTH = 420  # a Take's waveform, and its spectrogram beside it
CELL_HEIGHT = 64
ROW_GAP = 4
PAIR_GAP = 10
LINE = 13  # px between lines of text
TEXT_COLOUR = (225, 225, 230)
DIM_COLOUR = (150, 150, 165)
PAGE: draw.Rgb = (14, 14, 18)
KEPT_COLOUR: draw.Rgb = (90, 230, 110)
TAKE_COLOUR: draw.Rgb = (245, 175, 60)
UNLISTED_COLOUR: draw.Rgb = (100, 100, 110)
ONSET_COLOUR: draw.Rgb = (90, 200, 110)
SEAM_COLOUR: draw.Rgb = (255, 80, 220)
_RULER_STEPS = (0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0)


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Box:
    """A Take's box in the picture: the rectangle on the overview waveform."""

    take: TakeRecord
    rect: Rect
    kept: int | None
    listed: bool


@dataclass(frozen=True)
class Processed:
    item: ProcessedTake
    wave: Rect
    spectrogram: Rect
    length_ratio: float
    peak_change_db: float
    lufs_change: float
    seam_step: float | None
    changed: dict[str, float | str]


@dataclass(frozen=True)
class Row:
    take: TakeRecord
    kept: int | None
    wave: Rect
    spectrogram: Rect
    processed: Processed | None


@dataclass(frozen=True)
class Sheet:
    path: Path
    width: int
    height: int
    overview: Rect
    boxes: tuple[Box, ...]
    rows: tuple[Row, ...]
    slice_status: str
    process_status: str | None
    view: TakesView
    notes: list[str] = field(default_factory=list)


def parse_takes(text: str, view: TakesView, asset: Asset) -> list[int]:
    """`--takes 1,3,5-7` as Take numbers, in time order, each once. Refused for a number that isn't a Take."""
    where = Position(asset=asset.id)
    numbers: set[int] = set()
    for part in (p.strip() for p in text.split(",")):
        low, _, high = part.partition("-")
        if not (low.isdigit() and (not _ or high.isdigit())) or (high and int(high) < int(low)):
            raise fail("input.invalid", f"--takes {text!r} is not Take numbers like 1,3,5-7",
                       fix=f"kiripix sound-takes {asset.id}", position=where)
        numbers.update(range(int(low), int(high or low) + 1))
    known = {t.number for t in view.record.takes}
    unknown = sorted(numbers - known)
    if unknown:
        raise fail("sheet.take_unknown", f"there is no Take {', '.join(map(str, unknown))}: the Takes are 1 to {len(known)}",
                   fix=f"kiripix sound-takes {asset.id}", position=where)
    return sorted(numbers)


def _ruler_step(seconds: float, width: int) -> float:
    """The first nice step of seconds whose ticks are at least 70 px apart."""
    for step in _RULER_STEPS:
        if step * width / max(seconds, 1e-9) >= 70:
            return step
    return _RULER_STEPS[-1]


def _paste(canvas: Any, image: Any, x: int, y: int) -> None:
    height, width = image.shape[:2]
    canvas[y:y + height, x:x + width] = image


def _signed(value: float, unit: str) -> str:
    return f"{value:+.1f} {unit}"


def sound_sheet(project: Project, asset: Asset, out: Path, only: list[int] | None) -> Sheet:
    """Draw the sheet of `asset` to `out` (a PNG path; its folder is made). `only` limits the rows to those Take numbers
    (the overview shows every Take). Needs `source` and `slice` built; shows `process` when it is built."""
    from PIL import Image, ImageDraw, ImageFont

    view = takes_view(project, asset)
    record = view.record
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    source_spec = graph.spec(SOURCE_STAGE)
    source_path = graph.output_dir(source_spec) / SOURCE_FILE
    if graph.built_hash(source_spec) is None or not source_path.is_file():
        raise fail("sheet.source_not_built", f"{asset.id}'s recording is not decoded yet", fix=f"kiripix next {asset.id}",
                   position=Position(asset=asset.id, stage=SOURCE_STAGE))
    rate, source = wav.read_wav(source_path)
    process_spec = graph.spec(PROCESS_STAGE)
    process_dir = graph.output_dir(process_spec)
    process_status: str | None = None
    variations: dict[int, ProcessedTake] = {}
    notes: list[str] = []
    if graph.built_hash(process_spec) is not None and (process_dir / PROCESS_RECORD).is_file():
        process_status = graph.state(PROCESS_STAGE).status
        processed_record = read_process(process_dir / PROCESS_RECORD)
        variations = {v.take: v for v in processed_record.variations}
        if process_status != "done":
            notes.append(f"process is {process_status}: its variations may be of an older cut")
    if view.slice_status != "done":
        notes.append(f"slice is {view.slice_status}: the Takes may be of an older cut")
    chosen = {t.number for t in record.takes} if only is None else set(only)
    shown = [t for t in record.takes if t.number in chosen]
    defaults = {p.name: p.default for p in PROCESS_PARAMS}

    # layout, top to bottom
    overview_y = MARGIN + TITLE_HEIGHT
    overview_width = WIDTH - 2 * MARGIN
    rows_top = overview_y + OVERVIEW_HEIGHT + RULER_HEIGHT + PAIR_GAP
    heights = [CELL_HEIGHT * (2 if t.number in variations else 1) + (ROW_GAP if t.number in variations else 0) + PAIR_GAP
               for t in shown]
    height = rows_top + sum(heights) + MARGIN
    canvas = np.empty((height, WIDTH, 3), dtype=np.uint8)
    canvas[:] = PAGE

    labels: list[tuple[int, int, str, tuple[int, int, int], bool]] = []  # x, y, text, colour, on a plate

    # the overview
    total = len(source)
    overview = draw.waveform_image(source, overview_width, OVERVIEW_HEIGHT)
    boxes: list[Box] = []
    for take in record.takes:
        x, w = draw.span_columns(take.start_sample, take.end_sample, total, overview_width)
        is_kept = view.kept.get(take.number)
        listed = take.number in chosen
        colour = KEPT_COLOUR if is_kept is not None else TAKE_COLOUR
        overview = draw.draw_box(overview, x, 0, x + w - 1, OVERVIEW_HEIGHT - 1, colour if listed else UNLISTED_COLOUR,
                                 2 if is_kept is not None else 1)
        boxes.append(Box(take, Rect(MARGIN + x, overview_y, w, OVERVIEW_HEIGHT), is_kept, listed))
        tag = str(take.number) + ("*" if is_kept is not None else "")
        labels.append((MARGIN + x + 3, overview_y + 2 + (take.number % 2) * 12, tag, colour if listed else DIM_COLOUR, True))
    _paste(canvas, overview, MARGIN, overview_y)

    # the ruler under it
    seconds = record.duration_ms / 1000.0
    step = _ruler_step(seconds, overview_width)
    tick = 0.0
    while tick <= seconds + 1e-9:
        column = int(np.rint(tick * overview_width / max(seconds, 1e-9)))
        column = min(column, overview_width - 1)
        canvas[overview_y + OVERVIEW_HEIGHT:overview_y + OVERVIEW_HEIGHT + 4, MARGIN + column] = DIM_COLOUR
        labels.append((MARGIN + column + 2, overview_y + OVERVIEW_HEIGHT + 3, f"{tick:g} s", DIM_COLOUR, False))
        tick += step

    title = (f"{asset.id}: {len(record.takes)} Take(s) in {seconds:.2f} s, {rate} Hz, {record.channels} ch, {record.mode}; "
             f"kept {len(view.kept)}; slice {view.slice_status}"
             + (f"; process {process_status}" if process_status else "")
             + ("; rows: " + ",".join(str(t.number) for t in shown) if only is not None else ""))
    labels.append((MARGIN, MARGIN, title, TEXT_COLOUR, False))

    # the rows
    rows: list[Row] = []
    y = rows_top
    text_x = MARGIN + CELL_WIDTH * 2 + MARGIN * 2
    for take in shown:
        part = source[take.start_sample:take.end_sample]
        item = variations.get(take.number)
        length_ms = take.end_ms - take.start_ms
        processed_signal = None
        processed_rate = rate
        if item is not None and (process_dir / item.file).is_file():
            processed_rate, processed_signal = wav.read_wav(process_dir / item.file)
        longest = max(length_ms, item.length_ms if processed_signal is not None and item is not None else 0.0)
        width = max(1, int(np.rint(CELL_WIDTH * length_ms / longest)))
        wave_image = draw.waveform_image(part, width, CELL_HEIGHT)
        onset_x, _ = draw.span_columns(take.onset_sample - take.start_sample, take.end_sample - take.start_sample,
                                       len(part), width)
        wave_image = draw.draw_column(wave_image, onset_x, ONSET_COLOUR)
        _paste(canvas, wave_image, MARGIN, y)
        _paste(canvas, draw.spectrogram_image(part, rate, width, CELL_HEIGHT), MARGIN + CELL_WIDTH + MARGIN, y)
        wave_rect = Rect(MARGIN, y, width, CELL_HEIGHT)
        spec_rect = Rect(MARGIN + CELL_WIDTH + MARGIN, y, width, CELL_HEIGHT)
        is_kept = view.kept.get(take.number)
        flags = [name for name, on in (("CLIPPED", take.clipped), ("OVERLAPS NEXT", take.overlaps_next)) if on]
        labels.append((text_x, y, f"take {take.number}   " + (f"kept as variation {is_kept}" if is_kept is not None else "not kept")
                       + (f"   {' '.join(flags)}" if flags else ""), KEPT_COLOUR if is_kept is not None else TAKE_COLOUR, False))
        labels.append((text_x, y + LINE, f"length {length_ms:.0f} ms   peak {take.peak_dbfs:.1f} dBFS   lufs {take.lufs:.1f}   "
                                         f"centroid {take.centroid_hz:.0f} Hz", TEXT_COLOUR, False))
        labels.append((text_x, y + 2 * LINE, f"clean rank {take.clean_rank} (1 is cleanest)   like {take.similarity:.2f}   "
                                             f"tail {take.tail_dbfs:.0f} dBFS", TEXT_COLOUR, False))
        labels.append((text_x, y + 3 * LINE, f"in the recording {take.start_ms:.0f} to {take.end_ms:.0f} ms; sound begins at "
                                             f"{take.onset_ms:.0f}", DIM_COLOUR, False))
        done: Processed | None = None
        y += CELL_HEIGHT
        if item is not None and processed_signal is not None:
            y += ROW_GAP
            pw = max(1, int(np.rint(CELL_WIDTH * item.length_ms / longest)))
            wave2 = draw.waveform_image(processed_signal, pw, CELL_HEIGHT, colour=(150, 255, 190))
            seam: float | None = None
            if item.loop:
                seam = sound_ops.seam_step(processed_signal)
                wave2 = draw.draw_column(draw.draw_column(wave2, 0, SEAM_COLOUR), pw - 1, SEAM_COLOUR)
            _paste(canvas, wave2, MARGIN, y)
            _paste(canvas, draw.spectrogram_image(processed_signal, processed_rate, pw, CELL_HEIGHT),
                   MARGIN + CELL_WIDTH + MARGIN, y)
            ratio = round(item.length_ms / length_ms, 3) if length_ms > 0 else 0.0
            peak_change = round(item.peak_dbfs - take.peak_dbfs, 2)
            lufs_change = round(item.lufs - take.lufs, 2)
            changed = {k: v for k, v in item.settings.items() if k in defaults and v != defaults[k]
                       and not (k == "loop" and v == "off") and not (k == "channels")}
            done = Processed(item, Rect(MARGIN, y, pw, CELL_HEIGHT),
                             Rect(MARGIN + CELL_WIDTH + MARGIN, y, pw, CELL_HEIGHT), ratio, peak_change, lufs_change, seam,
                             changed)
            labels.append((text_x, y, f"variation {item.variation} processed" + ("   tuned" if item.overridden else ""),
                           (150, 255, 190), False))
            labels.append((text_x, y + LINE, f"length {item.length_ms:.0f} ms (x{ratio:.2f})   peak {item.peak_dbfs:.1f} dBFS "
                                             f"({_signed(peak_change, 'dB')})   lufs {item.lufs:.1f} ({_signed(lufs_change, 'LU')})",
                           TEXT_COLOUR, False))
            speed = float(item.settings.get("speed", 1.0))
            labels.append((text_x, y + 2 * LINE, "settings: " + (", ".join(f"{k} {v:g}" if not isinstance(v, str) else f"{k} {v}"
                                                                        for k, v in changed.items()) or "defaults")
                           + (f"   (speed x{speed:g})" if speed != 1.0 else ""), DIM_COLOUR, False))
            if item.loop:
                labels.append((text_x, y + 3 * LINE, f"loop seam (pink): match {item.loop_match if item.loop_match is not None else 0:g}"
                                                     f"   step {seam:g} (about 1 is no click, 5 or more is one)", SEAM_COLOUR, False))
            y += CELL_HEIGHT
        rows.append(Row(take, is_kept, wave_rect, spec_rect, done))
        y += PAIR_GAP

    # the text, and the PNG
    picture = Image.fromarray(canvas, "RGB")
    pen = ImageDraw.Draw(picture)
    font = ImageFont.load_default()
    for x, label_y, text, colour, plate in labels:
        if plate:
            left, top, right, bottom = pen.textbbox((x, label_y), text, font=font)
            pen.rectangle((left - 1, top - 1, right + 1, bottom + 1), fill=(10, 10, 14))
        pen.text((x, label_y), text, fill=colour, font=font)
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG", compress_level=6, optimize=False)
    atomic.write_bytes(out, buffer.getvalue())
    return Sheet(out, WIDTH, height, Rect(MARGIN, overview_y, overview_width, OVERVIEW_HEIGHT), tuple(boxes), tuple(rows),
                 view.slice_status, process_status, view, notes)
