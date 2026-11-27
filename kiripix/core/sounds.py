"""Sounds in core (ticket 0395, ADR 0016): importing a recording with its Provenance, reading the Takes `slice` found, writing
the `keep` Decision from the Take numbers a person types, and the sound's game ID.

The Stages themselves are in `kiripix.recipes.sound`; ffmpeg runs only through `kiripix.recipes.ffmpeg`. The caller holds the
Asset lock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kiripix.checks import Finding, Position
from kiripix.core import atomic, cancel, editing
from kiripix.core.assets import ASSET_FILE, Asset
from kiripix.core.errors import KiripixError, fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache, hash_bytes
from kiripix.core.project import Project
from kiripix.core.settings import ProjectSettings
from kiripix.core.sources import (
    IMPORTED_FILE,
    IMPORTED_SCHEMA_VERSION,
    SOUND,
    SOUND_SUFFIXES,
    VARIANT_NAME_LENGTH,
    imported_as,
)
from kiripix.recipes import ffmpeg
from kiripix.recipes.base import StageFailure
from kiripix.recipes.sound import (
    KEEP,
    KEEP_STAGE,
    SLICE_STAGE,
    TAKES_FILE,
    TakeRecord,
    TakesRecord,
    latest_keep,
    kept_spans,
    file_stem,
    match_takes,
    read_provenance,
    read_takes,
)


@dataclass(frozen=True)
class Provenance:
    """Where a recording came from (ADR 0016, decision 8): the Owner's own words, stored as text and never interpreted."""

    url: str | None = None
    author: str | None = None
    licence: str | None = None


def _ffmpeg_failure(error: StageFailure, position: Position) -> KiripixError:
    code = error.code or "ffmpeg.failed"
    if error.owner_action:
        return fail(code, str(error), owner_action=error.owner_action, position=position)
    return fail(code, str(error), fix=error.fix or "uv sync", position=position)


# import


def provenance(asset: Asset, path: Path) -> Provenance | None:
    """The newest Provenance recorded for a stored recording: of the lines of `imported.jsonl` that name it and carry any of
    `url`, `author` and `licence`, the one with the latest `at` (the file is `merge=union`, so file order says nothing);
    a line without `at` is oldest, and a tie goes to the later line. None when it has none."""
    _, found = read_provenance(asset.dir, path.relative_to(asset.dir).as_posix())
    return Provenance(**found) if any(found.values()) else None


@dataclass(frozen=True)
class Recording:
    """What `import` stored: the Variant's name and path, whether it is new, what ffmpeg read of it and its Provenance."""

    name: str
    path: Path
    created: bool
    info: ffmpeg.AudioInfo
    provenance: Provenance | None


def import_recording(asset: Asset, file: Path, shown: str, *, url: str | None, author: str | None,
                     licence: str | None) -> Recording:
    """Store a recording whole in `src/` (a WAV, FLAC, MP3 or OGG that ffmpeg decodes) as a Variant named by its hash, and
    record the name it was imported with and its Provenance on its line in `imported.jsonl`. The same bytes again with
    other flags add a newer line and no Variant; a flag left out keeps what the newest line had."""
    position = Position(asset=asset.id, file=shown)
    try:
        data = file.read_bytes()
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        raise fail("import.not_found", f"no file at {shown}", owner_action=f"Check the path {shown}.") from None
    suffix = file.suffix.lower()
    if suffix not in SOUND_SUFFIXES:
        raise fail("import.not_a_sound", f"{shown} is not a recording Kiripix takes: a {asset.kind} takes a "
                   f"{', '.join(SOUND_SUFFIXES)} file", owner_action=f"Export {shown} as a WAV or FLAC and import that.",
                   position=position)
    try:
        info = ffmpeg.probe(file, cancel.check)
    except StageFailure as error:
        raise _ffmpeg_failure(error, position) from None
    if info is None:
        raise fail("import.not_audio", f"ffmpeg could not read {shown} as audio (it is damaged, or not what its name says)",
                   owner_action=f"Export {shown} again as a WAV or FLAC.", position=position)
    name = hash_bytes(data)[:VARIANT_NAME_LENGTH]
    known = [p for p in sorted((asset.dir / "src").glob(f"{name}.*")) if p.suffix in SOUND_SUFFIXES]
    path = known[0] if known else asset.dir / "src" / f"{name}{suffix}"
    created = not known
    if created:
        atomic.write_bytes(path, data)
    current = provenance(asset, path)
    wanted = Provenance(url=url or (current.url if current else None), author=author or (current.author if current else None),
                        licence=licence or (current.licence if current else None))
    changed = any((url, author, licence)) and wanted != current
    if changed or imported_as(asset, path) != file.name:
        line: dict[str, object] = {"schema_version": IMPORTED_SCHEMA_VERSION, "file": path.relative_to(asset.dir).as_posix(),
                                   "imported_as": file.name}
        if changed:
            line.update({"url": wanted.url, "author": wanted.author, "licence": wanted.licence,
                         "at": datetime.now(UTC).isoformat(timespec="seconds")})
        atomic.append_jsonl_many(asset.dir / IMPORTED_FILE, [line])
    return Recording(name=name, path=path, created=created, info=info, provenance=provenance(asset, path))


# the sound's game ID


def sound_id(asset: Asset, settings: ProjectSettings) -> str:
    """The game's ID: the `sound_id` parameter, else `<prefix>.<name>` with the use's prefix."""
    given = asset.settings.params.get("sound_id")
    if isinstance(given, str) and given:
        return given
    return f"{use_prefix(asset, settings)}.{asset.name}"


def use_prefix(asset: Asset, settings: ProjectSettings) -> str:
    use = str(asset.settings.params.get("use", ""))
    row = settings.sound.use.get(use)
    return row.prefix if row is not None else use


def check_sound_ids(project: Project, assets: list[Asset]) -> list[Finding]:
    """The Project check `sound.id_prefix`: a sound's `sound_id` starts with its use's prefix and a dot."""
    found: list[Finding] = []
    for asset in assets:
        if asset.kind != SOUND:
            continue
        prefix = use_prefix(asset, project.settings)
        wanted = sound_id(asset, project.settings)
        if wanted != prefix and not wanted.startswith(prefix + "."):
            file = project.relative(asset.dir / ASSET_FILE)
            found.append(Finding(
                code="sound.id_prefix", position=Position(asset=asset.id, file=file, field="params.sound_id"),
                message=f"{asset.id}'s sound_id {wanted!r} does not start with {prefix + '.'!r}, the prefix of the use "
                        f"{asset.settings.params.get('use')}",
                owner_action=f"Set sound_id under [params] in {file} to {prefix}.<name>, or change the use."))
    return found


def check_sound_names(project: Project, assets: list[Asset]) -> list[Finding]:
    """The Project check `sound.name_taken`: two sounds of one use whose `sound_id` gives the same file name
    (`sfx.footstep.asphalt` and `sfx.footstep_asphalt` are both `footstep_asphalt`) would write the same file. The first
    in Asset ID order keeps the name. (A name that is another's with `_<n>` added, which only several variations make, is
    caught at export: the second Asset's file isn't its Manifest's.)"""
    taken: dict[tuple[str, str], str] = {}
    found: list[Finding] = []
    for asset in sorted((a for a in assets if a.kind == SOUND), key=lambda a: a.id):
        use = str(asset.settings.params.get("use", ""))
        stem = file_stem(sound_id(asset, project.settings), use_prefix(asset, project.settings))
        first = taken.setdefault((use, stem), asset.id)
        if first != asset.id:
            file = project.relative(asset.dir / ASSET_FILE)
            found.append(Finding(
                code="sound.name_taken", position=Position(asset=asset.id, file=file, field="params.sound_id"),
                message=f"{asset.id} and {first} are both {use} sounds named {stem!r} in the game ({stem}.ogg)",
                owner_action=f"Give {asset.id} another sound_id under [params] in {file}, such as {use_prefix(asset, project.settings)}"
                             f".{stem}_2."))
    return found


# the Takes


@dataclass(frozen=True)
class TakesView:
    """The built `slice` output of a sound, with whether `slice` is up to date and which Takes the `keep` Decision keeps."""

    record: TakesRecord
    slice_status: str
    kept: dict[int, int]  # Take number -> variation number


def takes_view(project: Project, asset: Asset) -> TakesView:
    """The Takes `slice` built. Refused (`slice.not_built`) before there is a built `slice`."""
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    spec = graph.spec(SLICE_STAGE)
    path = graph.output_dir(spec) / TAKES_FILE
    if graph.built_hash(spec) is None or not path.is_file():
        raise fail("slice.not_built", f"{asset.id} has not been sliced yet: there are no Takes",
                   fix=f"kiripix next {asset.id}", position=Position(asset=asset.id, stage=SLICE_STAGE))
    try:
        record = read_takes(path)
    except StageFailure as error:
        raise fail("slice.output_unreadable", str(error), fix=f"kiripix run {asset.id} slice --force",
                   position=Position(asset=asset.id, stage=SLICE_STAGE)) from None
    kept: dict[int, int] = {}
    decision = latest_keep(graph.decisions(graph.spec(KEEP_STAGE)))
    if decision is not None:
        for match in match_takes(kept_spans(decision), record.takes):
            if match.take is not None and match.status in ("exact", "moved"):
                kept[match.take.number] = match.index + 1
    return TakesView(record=record, slice_status=graph.state(SLICE_STAGE).status, kept=kept)


def keep_document(project: Project, asset: Asset, text: str) -> editing.DecisionDocument:
    """The `keep` Decision for Take numbers typed as `3,5,8,11`: each Take's span in `slice`'s built output, in the order
    typed (which gives the variation numbers). Refused for a `slice` that isn't up to date, for a number that isn't a Take
    and for a Take twice."""
    position = Position(asset=asset.id, stage=KEEP_STAGE)
    if asset.kind != SOUND:
        raise fail("decide.takes_need_sound", f"--takes is for a sound's `keep`; {asset.id} is a {asset.kind}",
                   fix=f"kiripix describe {asset.kind}", position=position)
    parts = [part.strip() for part in text.split(",")]
    if not all(part.isdigit() for part in parts):
        raise fail("keep.takes_invalid", f"--takes {text!r} is not Take numbers like 3,5,8,11",
                   fix=f"kiripix sound-takes {asset.id}", position=position)
    numbers = [int(part) for part in parts]
    if len(set(numbers)) != len(numbers):
        raise fail("keep.takes_invalid", f"--takes {text!r} names a Take twice: a Take is kept once",
                   fix=f"kiripix sound-takes {asset.id}", position=position)
    view = takes_view(project, asset)
    if view.slice_status != "done":
        raise fail("keep.slice_not_done", f"{asset.id}'s slice is {view.slice_status}: the Take numbers would be of an "
                   "older cut", fix=f"kiripix run {asset.id} slice", position=position)
    by_number: dict[int, TakeRecord] = {t.number: t for t in view.record.takes}
    unknown = [n for n in numbers if n not in by_number]
    if unknown:
        raise fail("keep.take_unknown", f"there is no Take {', '.join(map(str, unknown))}: the Takes are 1 to "
                   f"{len(by_number)}", fix=f"kiripix sound-takes {asset.id}", position=position)
    return editing.DecisionDocument(decision=KEEP.name, data={"takes": [
        {"start_ms": by_number[n].start_ms, "end_ms": by_number[n].end_ms} for n in numbers]})
