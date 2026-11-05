"""The Manifest (ADR 0003, spec §9): one JSON file per Asset under the export root, committed with the game.

It lists every file Kiripix exported with its hash, and that decides what export may overwrite: a file only if the
Manifest lists it and it still has the recorded hash. `.import` sidecars are Godot's: they aren't listed and nothing here
looks at them.
"""

from importlib import metadata
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from kiripix.core import atomic
from kiripix.core.errors import fail

MANIFEST_DIR = "manifest"
MANIFEST_SCHEMA_VERSION: Literal[1] = 1


class ExportedIds(BaseModel):
    """Every ID an export carries into the game. Frozen once exported (ticket 0022)."""

    model_config = ConfigDict(extra="forbid")

    markers: list[str]
    layers: list[str]
    masks: list[str]


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = MANIFEST_SCHEMA_VERSION
    kiripix_version: str
    asset: str
    exported: bool
    counter: int
    ids: ExportedIds
    files: dict[str, str]  # each file as `res://...`, with its SHA-256
    # Only while an export is writing: the hash each file had before it. So one that was stopped can be run again.
    replacing: dict[str, str] | None = None


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
        return Manifest.model_validate_json(data)
    except FileNotFoundError:
        return None
    except (OSError, ValidationError) as error:
        if isinstance(error, ValidationError) and has_conflict_markers(data):
            raise fail("export.manifest_conflicted", f"the Manifest {shown} has git conflict markers in it",
                       fix="kiripix manifest repair") from None
        raise fail("export.manifest_invalid", f"the Manifest {shown} can't be read: {error}",
                   owner_action=f"Restore {shown} from the game's git history, or upgrade Kiripix if a newer one "
                                "wrote it.") from None


def write_manifest(path: Path, manifest: Manifest) -> None:
    atomic.write_text(path, manifest.model_dump_json(indent=2, exclude_none=True) + "\n")
