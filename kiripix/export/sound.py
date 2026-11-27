"""A sound's built export (`out/export/`) and what the Exporter makes of it (ticket 0400, ADR 0016, decision 9).

The `export` Stage leaves `<name>[_<n>].ogg` and `sound.json`. The Exporter copies the OGGs byte for byte to
`<[sound] folder>/<use>/` (outside the export root, the one exception) and records `sound.json` in the Manifest's `sound`
block. It writes no `audio.json` and no `CREDITS.md`: the game builds both from the Manifest.
"""

from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.export.built import built_dir
from kiripix.export.manifest import SoundEntry, SoundFileEntry, SoundSourceEntry, SoundTake
from kiripix.export.target import GodotTarget
from kiripix.recipes.base import StageFailure
from kiripix.recipes.sound import SOUND_RECORD, SOUND_SCHEMA_VERSION, SoundRecord, read_sound


def read_built_sound(graph: AssetGraph) -> SoundRecord:
    """`sound.json` of the Asset's built export, refused with `export.sound_invalid` and the rebuild when it can't be read."""
    rebuild = f"kiripix run {graph.asset.id} export --force"
    try:
        record = read_sound(built_dir(graph) / SOUND_RECORD)
    except StageFailure as error:
        raise fail("export.sound_invalid", f"{graph.asset.id}'s {SOUND_RECORD}: {error}", fix=rebuild) from None
    if record.schema_version != SOUND_SCHEMA_VERSION:
        raise fail("export.sound_invalid", f"{graph.asset.id}'s {SOUND_RECORD} has schema_version {record.schema_version}; "
                   f"this Kiripix reads {SOUND_SCHEMA_VERSION}", fix=rebuild)
    return record


def sound_folder(target: GodotTarget, record: SoundRecord) -> str:
    """Where the sound's files go, as `res://...`: `<[sound] folder>/<use>`."""
    return f"{target.sound_files_folder()}/{record.use}"


def sound_files(graph: AssetGraph, target: GodotTarget) -> tuple[dict[str, bytes], SoundEntry]:
    """The OGGs by `res://` path, in variation order, and the Manifest's `sound` block."""
    record = read_built_sound(graph)
    folder = sound_folder(target, record)
    files = {f"{folder}/{item.file}": (built_dir(graph) / item.file).read_bytes() for item in record.files}
    entry = SoundEntry(
        id=record.id, use=record.use,
        files=[SoundFileEntry(path=f"{folder}/{item.file}", take=SoundTake(start_ms=item.take.start_ms, end_ms=item.take.end_ms),
                              length_s=item.length_s, peak_dbfs=item.peak_dbfs, lufs=item.lufs, loop=item.loop,
                              loop_offset=item.loop_offset) for item in record.files],
        source=SoundSourceEntry(file=record.source.file, hash=record.source.hash, url=record.source.url,
                                author=record.source.author, licence=record.source.licence),
        processing={"rate": record.rate, "quality": record.quality, "channels": record.channels, **record.processing})
    return files, entry
