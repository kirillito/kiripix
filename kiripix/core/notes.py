"""Hand-over notes (spec §5, ticket 0326): `notes.jsonl` in an Asset's folder, append-only, one object per line, LF.

A note says why a first pass stopped and what is left. It is not a Decision: it changes no output and no input hash,
and `undo` doesn't reach it. A note is *live* while its Stage's journal has no Decision and no `accept` written after it
(an undo or a redo doesn't end it); that is derived from the two files, never stored (ADR 0005).
"""

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from kiripix.checks import Finding, Position
from kiripix.core import atomic, journal
from kiripix.core.assets import Asset
from kiripix.core.errors import KiripixError, fail

NOTES_FILE = "notes.jsonl"
SCHEMA_VERSION = 1
MAX_LENGTH = 2000


class Note(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    id: str
    stage: str
    text: str
    input_hash: str


@dataclass(frozen=True)
class HeldNote:
    note: Note
    live: bool


def notes_path(asset: Asset) -> Path:
    return asset.dir / NOTES_FILE


def read_notes(asset: Asset) -> list[Note]:
    """Every note of the Asset in ULID order. A missing file is no notes."""
    path = notes_path(asset)
    try:
        text = path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        return []
    notes: list[Note] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            note = Note.model_validate(json.loads(line))
            if note.schema_version != SCHEMA_VERSION:
                raise ValueError(f"schema_version {note.schema_version} isn't one this Kiripix reads")
            notes.append(note)
        except (ValueError, ValidationError) as error:
            raise KiripixError([Finding(
                code="note.invalid", message=f"{NOTES_FILE}:{number} of {asset.id}: {error}",
                position=Position(asset=asset.id, file=f"{asset.dir.name}/{NOTES_FILE}"),
                owner_action=f"Fix line {number} of {notes_path(asset)}, or remove it if a bad merge left it behind.")]
            ) from None
    return sorted(notes, key=lambda n: n.id)


def _entries(asset: Asset, stage: str) -> list[journal.JournalEntry]:
    path = journal.journal_path(asset.dir, stage)
    if not path.is_file():
        return []
    return journal.read_entries(path, f"{asset.dir.name}/decisions/{stage}.jsonl")


def _last_ending(asset: Asset, stage: str) -> str | None:
    """The ID of the Stage's latest Decision or accept: what ends a note written before it."""
    return next((e.id for e in reversed(_entries(asset, stage)) if e.decision is not None or e.accept is not None), None)


def held_notes(asset: Asset) -> list[HeldNote]:
    """Every note with whether it is live: its Stage's journal has no Decision or accept after it. Reads each journal at
    most once."""
    notes = read_notes(asset)
    last: dict[str, str | None] = {}
    for stage in {n.stage for n in notes}:
        last[stage] = _last_ending(asset, stage)
    return [HeldNote(n, (latest := last[n.stage]) is None or latest < n.id) for n in notes]


def live_notes(asset: Asset) -> dict[str, list[Note]]:
    """The live notes of each Stage that has any, oldest first. The one call `queue` makes per Asset."""
    found: dict[str, list[Note]] = {}
    for held in held_notes(asset):
        if held.live:
            found.setdefault(held.note.stage, []).append(held.note)
    return found


def add_note(asset: Asset, stage: str, text: str, input_hash: str) -> Note:
    """Append a note. The caller holds the Asset's lock and has checked the Stage exists."""
    if len(text) > MAX_LENGTH:
        raise fail("note.too_long", f"{asset.id} {stage}: a note is at most {MAX_LENGTH} characters, this one has "
                   f"{len(text)}", position=Position(asset=asset.id, stage=stage),
                   fix=f"kiripix note {asset.id} {stage} \"<a shorter text>\"")
    if not text.strip():
        raise fail("note.empty", f"{asset.id} {stage}: a note needs some text", position=Position(asset=asset.id, stage=stage),
                   fix=f"kiripix note {asset.id} {stage} \"<what is left, and why>\"")
    existing = read_notes(asset)
    # After the latest note and the Stage's latest journal entry, so a note written in the same millisecond as a Decision
    # still sorts after it and is live.
    entries = _entries(asset, stage)
    after = max([*(n.id for n in existing[-1:]), *(e.id for e in entries[-1:])], default=None)
    note = Note(id=journal.new_ulid(after), stage=stage, text=text, input_hash=input_hash)
    atomic.append_jsonl(notes_path(asset), note.model_dump())
    return note
