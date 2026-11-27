"""The Commands for sounds (ticket 0395, ADR 0016): `sound-takes`. A sound's `import` is `import`, its `keep` is `decide keep
--takes`, its `pick` is `pick`."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, command
from kiripix.core import sound_sheet, sounds
from kiripix.core.assets import load_asset
from kiripix.core.errors import fail
from kiripix.core.project import find_project
from kiripix.core.sources import SOUND


class SoundTakesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The sound Asset ID, such as sound.footstep_asphalt.")


class TakeRow(BaseModel):
    number: int = Field(description="Its place in time order, from 1: what `decide <id> keep --takes 3,5,8` types.")
    start_ms: float = Field(description="Where the Take begins in the recording (its onset less the pre-roll).")
    onset_ms: float = Field(description="Where the sound itself begins.")
    end_ms: float
    length_ms: float
    peak_dbfs: float
    rms_dbfs: float
    lufs: float = Field(description="Integrated loudness (BS.1770); for a Take under 400 ms, its mean square over the Take.")
    centroid_hz: float = Field(description="The spectral centroid: higher is brighter.")
    similarity: float = Field(description="0 to 1: how like the typical Take it is. A scrape among steps scores low.")
    clean_rank: int = Field(description="1 is the cleanest: no clipping, no overlap with the next Take, a quiet tail.")
    tail_dbfs: float = Field(description="The level of the Take's last 10 ms.")
    clipped: bool = Field(description="The Take reaches 0 dBFS.")
    overlaps_next: bool = Field(description="The next Take began before this one had died away.")
    kept: int | None = Field(description="The variation number the `keep` Decision gives it; null when not kept.")


class SoundTakesData(BaseModel):
    asset: str
    rate: int
    channels: int
    duration_ms: float
    mode: str = Field(description="onsets or whole: how `slice` cut the recording.")
    settings: dict[str, float | str] = Field(description="The `slice` settings the Takes were cut with.")
    slice_status: str = Field(description="The Stage status of `slice`: done, or stale when its inputs changed since.")
    takes: list[TakeRow]

    def text(self) -> str:
        head = (f"{self.asset}: {len(self.takes)} Take(s) in {self.duration_ms / 1000:.2f} s ({self.rate} Hz, "
                f"{self.channels} ch, {self.mode}); slice {self.slice_status}")
        columns = f"{'#':>3} {'start':>9} {'end':>9} {'len':>7} {'peak':>7} {'lufs':>7} {'rms':>7} {'centroid':>9} {'like':>5} " \
                  f"{'rank':>4} {'kept':>4}  flags"
        rows = [f"{t.number:>3} {t.start_ms:>9.1f} {t.end_ms:>9.1f} {t.length_ms:>7.1f} {t.peak_dbfs:>7.1f} {t.lufs:>7.1f} "
                f"{t.rms_dbfs:>7.1f} {t.centroid_hz:>9.0f} {t.similarity:>5.2f} {t.clean_rank:>4} "
                f"{t.kept if t.kept is not None else '-':>4}  "
                f"{' '.join(flag for flag, on in (('clipped', t.clipped), ('overlaps-next', t.overlaps_next)) if on)}"
                for t in self.takes]
        return "\n".join([head, "times in ms, levels in dB", columns, *rows])


@command(
    "sound-takes",
    summary="The Takes `slice` found in a sound's recording, with their spans, peak, RMS, LUFS, spectral centroid, likeness to "
            "the typical Take, clean rank and which are kept. A table; --json for agents. Records nothing.",
    input=SoundTakesInput,
    output=SoundTakesData,
    kind="probe",
    mcp="exposed",
    cli=CliMeta(positional=("asset",)),
)
def sound_takes(arguments: SoundTakesInput, context: Context) -> Outcome[SoundTakesData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    if asset.kind != SOUND:
        raise fail("sound.not_a_sound", f"{asset.id} is a {asset.kind}, not a sound", fix=f"kiripix show {asset.id}")
    view = sounds.takes_view(project, asset)
    rows = [TakeRow(number=t.number, start_ms=t.start_ms, onset_ms=t.onset_ms, end_ms=t.end_ms,
                    length_ms=round(t.end_ms - t.start_ms, 3), peak_dbfs=t.peak_dbfs, rms_dbfs=t.rms_dbfs, lufs=t.lufs,
                    centroid_hz=t.centroid_hz, similarity=t.similarity, clean_rank=t.clean_rank, tail_dbfs=t.tail_dbfs,
                    clipped=t.clipped, overlaps_next=t.overlaps_next, kept=view.kept.get(t.number))
            for t in view.record.takes]
    return Outcome(SoundTakesData(asset=asset.id, rate=view.record.rate, channels=view.record.channels,
                                  duration_ms=view.record.duration_ms, mode=view.record.mode, settings=view.record.settings,
                                  slice_status=view.slice_status, takes=rows))


class SoundSheetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The sound Asset ID, such as sound.footstep_asphalt.")
    out: str = Field(description="The PNG to write, relative to the working directory, such as sheet.png.")
    takes: str | None = Field(None, description="Draw rows for only these Takes, such as 1,3,5-7 (the overview shows every Take). "
                                                "Default: every Take.")


class Rect(BaseModel):
    x: int
    y: int
    width: int
    height: int


class SheetBox(BaseModel):
    take: int
    x: int = Field(description="The box's left edge in the PNG, px.")
    y: int
    width: int
    height: int
    start_ms: float
    end_ms: float
    kept: int | None = Field(description="The variation number when the Take is kept (its label has a star); else null.")
    listed: bool = Field(description="False for a Take left out of --takes: its box is grey and it has no row.")


class SheetProcessed(BaseModel):
    variation: int
    wave: Rect
    spectrogram: Rect
    length_ms: float
    length_ratio: float = Field(description="Processed length over the source Take's: 0.67 for speed 1.5.")
    peak_dbfs: float
    peak_change_db: float = Field(description="Processed peak less the source Take's.")
    lufs: float
    lufs_change: float = Field(description="Processed loudness less the source Take's.")
    speed: float
    settings_changed: dict[str, float | str] = Field(description="The process settings that aren't at their default.")
    loop: bool
    loop_match: float | None
    seam_step: float | None = Field(description="A loop: the jump at its seam over the ordinary step (about 1: no click; 5+: a click).")
    overridden: bool


class SheetRow(BaseModel):
    take: int
    kept: int | None
    wave: Rect
    spectrogram: Rect
    length_ms: float
    peak_dbfs: float
    lufs: float
    centroid_hz: float
    clean_rank: int
    processed: SheetProcessed | None = Field(description="After `process`: its variation, drawn under the Take.")


class SoundSheetData(BaseModel):
    path: str = Field(description="The PNG, as given (relative to the working directory).")
    width: int
    height: int
    asset: str
    rate: int
    duration_ms: float
    slice_status: str
    process_status: str | None = Field(description="The Stage status of `process`, or null when it has no output.")
    overview: Rect = Field(description="The whole recording's waveform; `boxes` are on it, and px are in the PNG.")
    boxes: list[SheetBox]
    rows: list[SheetRow]
    notes: list[str]

    def text(self) -> str:
        return self.path


@command(
    "sound-sheet",
    summary="Draw a sound's whole recording with each Take boxed and numbered (kept ones starred), then a row per Take: waveform, "
            "log-frequency spectrogram and its numbers; after `process`, the processed variation under its Take with its own "
            "numbers and, for a loop, its seam. A PNG under 1600 px wide. A Probe: records nothing.",
    input=SoundSheetInput,
    output=SoundSheetData,
    kind="probe",
    mcp="exposed",
    cli=CliMeta(positional=("asset", "out")),
)
def sound_sheet_command(arguments: SoundSheetInput, context: Context) -> Outcome[SoundSheetData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    if asset.kind != SOUND:
        raise fail("sound.not_a_sound", f"{asset.id} is a {asset.kind}, not a sound", fix=f"kiripix show {asset.id}")
    out = Path(arguments.out)
    if out.suffix.lower() != ".png":
        raise fail("input.invalid", f"{arguments.out} is not a .png path", fix=f"kiripix sound-sheet {asset.id} sheet.png")
    only = None
    if arguments.takes is not None:
        only = sound_sheet.parse_takes(arguments.takes, sounds.takes_view(project, asset), asset)
    made = sound_sheet.sound_sheet(project, asset, context.cwd / out, only)

    def rect(r: sound_sheet.Rect) -> Rect:
        return Rect(x=r.x, y=r.y, width=r.width, height=r.height)

    boxes = [SheetBox(take=b.take.number, x=b.rect.x, y=b.rect.y, width=b.rect.width, height=b.rect.height,
                      start_ms=b.take.start_ms, end_ms=b.take.end_ms, kept=b.kept, listed=b.listed) for b in made.boxes]
    rows = []
    for r in made.rows:
        p = r.processed
        done = None if p is None else SheetProcessed(
            variation=p.item.variation, wave=rect(p.wave), spectrogram=rect(p.spectrogram), length_ms=p.item.length_ms,
            length_ratio=p.length_ratio, peak_dbfs=p.item.peak_dbfs, peak_change_db=p.peak_change_db, lufs=p.item.lufs,
            lufs_change=p.lufs_change, speed=float(p.item.settings.get("speed", 1.0)), settings_changed=p.changed,
            loop=p.item.loop, loop_match=p.item.loop_match, seam_step=p.seam_step, overridden=p.item.overridden)
        rows.append(SheetRow(take=r.take.number, kept=r.kept, wave=rect(r.wave), spectrogram=rect(r.spectrogram),
                             length_ms=round(r.take.end_ms - r.take.start_ms, 3), peak_dbfs=r.take.peak_dbfs, lufs=r.take.lufs,
                             centroid_hz=r.take.centroid_hz, clean_rank=r.take.clean_rank, processed=done))
    return Outcome(SoundSheetData(
        path=arguments.out, width=made.width, height=made.height, asset=asset.id, rate=made.view.record.rate,
        duration_ms=made.view.record.duration_ms, slice_status=made.slice_status, process_status=made.process_status,
        overview=rect(made.overview), boxes=boxes, rows=rows, notes=made.notes))
