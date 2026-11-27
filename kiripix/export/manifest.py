"""The Manifest (ADR 0003, spec §9): one JSON file per Asset under the export root, committed with the game.

It lists every file Kiripix exported with its hash, and that decides what export may overwrite: a file only if the
Manifest lists it and it still has the recorded hash. `.import` sidecars are Godot's: they aren't listed and nothing here
looks at them.
"""

import json
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError, model_serializer

from kiripix.core import atomic
from kiripix.core.errors import fail

MANIFEST_DIR = "manifest"
# 2: `ids.clips`, each exported animation name of a character (ticket 0113). A version 1 Manifest is migrated on read: it
# lists the same files and the IDs it froze, so refusing it would lose the freeze; its `clips` are empty.
# 3: `ids.look_markers`, a room's Look Markers as `<look>/<marker>` (ticket 0316). A version 2 Manifest is migrated on read, with
# none.
# 4: `ids.masks` lists every painted Mask of the room's view, not only `solid` and `pit` (ticket 0345): each is a file name the game's
# grid reads, so it is frozen. A version 3 Manifest is migrated on read: the Masks it lists are the ones it froze.
# 5: `sound`, an optional block of a sound's export: its ID, use, files with their Takes and measures, the source's Provenance and
# the processing (ticket 0400, ADR 0016). A version 4 Manifest is migrated on read: it has no sound block.
MANIFEST_SCHEMA_VERSION: Literal[5] = 5


class ExportedIds(BaseModel):
    """Every ID an export carries into the game. Frozen once exported (ticket 0022)."""

    model_config = ConfigDict(extra="forbid")

    markers: list[str]
    layers: list[str]
    masks: list[str]
    clips: list[str] = Field(default_factory=list)  # a character's animations, `<clip>_<dir>`
    looks: list[str] = Field(default_factory=list)  # a room's Look IDs (ticket 0131); left out of the file when empty
    loops: list[str] = Field(default_factory=list)  # a room's Loop IDs (ticket 0190); left out of the file when empty

    states: list[str] = Field(default_factory=list)  # a Prop's state IDs (ticket 0258); left out of the file when empty
    links: list[str] = Field(default_factory=list)  # a room's Link IDs (ticket 0267); left out of the file when empty
    emotions: list[str] = Field(default_factory=list)  # a portrait's emotion IDs (ticket 0244); left out when empty
    look_markers: list[str] = Field(default_factory=list)  # a room's Look Markers, `<look>/<marker>` (0316); left out when empty

    @model_serializer(mode="wrap")
    def _without_empty_looks(self, handler: Any) -> dict[str, Any]:
        """A Manifest of an Asset with no Looks, Loops, states, Links or emotions is the file it was before they existed: byte for byte."""
        data: dict[str, Any] = handler(self)
        for noun in ("looks", "loops", "states", "links", "emotions", "look_markers"):
            if not data.get(noun):
                data.pop(noun, None)
        return data


class SoundTake(BaseModel):
    """The span of the recording a variation was cut from."""

    model_config = ConfigDict(extra="forbid")

    start_ms: float
    end_ms: float


class SoundFileEntry(BaseModel):
    """One exported variation: where it is, which Take it is, and what was measured of the encoded file. A `loop_offset` of None
    (not a loop) is left out of the file, as every None is."""

    model_config = ConfigDict(extra="forbid")

    path: str  # as `res://...`; also a key of `Manifest.files`
    take: SoundTake
    length_s: float
    peak_dbfs: float
    lufs: float
    loop: bool
    loop_offset: float | None = None


class SoundSourceEntry(BaseModel):
    """The recording the sound was cut from and its Provenance as the Owner gave it (text, never interpreted). An absent `url`,
    `author` or `licence` was not given."""

    model_config = ConfigDict(extra="forbid")

    file: str
    hash: str
    url: str | None = None
    author: str | None = None
    licence: str | None = None


class SoundEntry(BaseModel):
    """A sound's block of the Manifest (ADR 0016, decision 9): what the game builds its `audio.json` entries and `CREDITS.md`
    lines from. It plays no part in ownership; `id` and `use` are frozen once exported."""

    model_config = ConfigDict(extra="forbid")

    id: str
    use: str
    files: list[SoundFileEntry]  # in variation order
    source: SoundSourceEntry
    processing: dict[str, Any]


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[5] = MANIFEST_SCHEMA_VERSION
    kiripix_version: str
    asset: str
    exported: bool
    counter: int
    ids: ExportedIds
    files: dict[str, str]  # each file as `res://...`, with its SHA-256
    # Only while an export is writing: the hash each file had before it. So one that was stopped can be run again.
    replacing: dict[str, str] | None = None
    sound: SoundEntry | None = None  # a sound's export (ticket 0400); left out of every other Kind's Manifest
    # Set when it was read from an older schema, so that an export rewrites the file once, though nothing else changed.
    _migrated: bool = PrivateAttr(default=False)

    @property
    def migrated(self) -> bool:
        return self._migrated

    @classmethod
    def from_value(cls, value: Any) -> "Manifest":
        """Validate a decoded Manifest, migrating one from an older schema version first (a newer one fails validation)."""
        migrated = isinstance(value, dict) and value.get("schema_version") in (1, 2, 3, 4)
        if migrated:
            assert isinstance(value, dict)
            if value.get("schema_version") == 1:
                value = migrate_v1(value)
            if value.get("schema_version") == 2:
                value = migrate_v2(value)
            if value.get("schema_version") == 3:
                value = migrate_v3(value)
            value = migrate_v4(value)
        manifest = cls.model_validate(value)
        manifest._migrated = migrated
        return manifest


def migrate_v1(value: dict[str, Any]) -> dict[str, Any]:
    """Schema 1 to 2: `ids` gains `clips`, empty. Pure."""
    ids = value.get("ids")
    ids = {**ids, "clips": ids.get("clips", [])} if isinstance(ids, dict) else ids
    return {**value, "schema_version": 2, "ids": ids}


def migrate_v2(value: dict[str, Any]) -> dict[str, Any]:
    """Schema 2 to 3: `ids` gains `look_markers`, empty. Pure."""
    ids = value.get("ids")
    ids = {**ids, "look_markers": ids.get("look_markers", [])} if isinstance(ids, dict) else ids
    return {**value, "schema_version": 3, "ids": ids}


def migrate_v3(value: dict[str, Any]) -> dict[str, Any]:
    """Schema 3 to 4: only the version changes; `ids.masks` already lists what the Manifest froze. Pure."""
    return {**value, "schema_version": 4}


def migrate_v4(value: dict[str, Any]) -> dict[str, Any]:
    """Schema 4 to 5: only the version changes; a Manifest with no `sound` block has none. Pure."""
    return {**value, "schema_version": 5}


def kiripix_version() -> str:
    return metadata.version("kiripix")


def has_conflict_markers(data: bytes) -> bool:
    """Whether git left conflict markers in `data`: a `<<<<<<<` line, and a `>>>>>>>` line after it."""
    opened = False
    for line in data.splitlines():
        if line.startswith(b"<<<<<<< "):
            opened = True
        elif opened and line.startswith(b">>>>>>> "):
            return True
    return False


def read_manifest(path: Path, shown: str) -> Manifest | None:
    """The Manifest at `path`; None when there is none. `shown` is its `res://` path, for messages."""
    try:
        data = path.read_bytes()
        return Manifest.from_value(json.loads(data))
    except FileNotFoundError:
        return None
    except (OSError, ValidationError, ValueError) as error:
        if isinstance(error, ValueError) and has_conflict_markers(data):
            raise fail("export.manifest_conflicted", f"the Manifest {shown} has git conflict markers in it",
                       fix="kiripix manifest repair") from None
        raise fail("export.manifest_invalid", f"the Manifest {shown} can't be read: {error}",
                   owner_action=f"Restore {shown} from the game's git history, or upgrade Kiripix if a newer one "
                                "wrote it.") from None


def write_manifest(path: Path, manifest: Manifest) -> None:
    atomic.write_text(path, manifest.model_dump_json(indent=2, exclude_none=True) + "\n")
