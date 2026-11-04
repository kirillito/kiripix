"""The Decision journal (spec §5): `decisions/<stage>.jsonl`, append-only, one entry per line, LF, `merge=union`.

Entries are never removed or rewritten. A Decision entry carries a ULID `id`, its `parent` (the entry that came before
it), the Decision's name and data, and, for a click or an Override, the hash of the image it was made on. `undo` and
`redo` are entries too. The Stage's current Decisions are the journal replayed in ULID order.

`accept` appends two more kinds of entry, so no status is ever stored: a Decision re-recorded against the new image
(`replaces` names the entry it takes the place of, keeping its position), and `{accept: [ids]}`, which accepts the
divergent entries and the pinned results (as `<key>:<hash of the result>`) it lists.
"""

import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from kiripix.checks import Finding, Position
from kiripix.core import atomic
from kiripix.core.errors import KiripixError
from kiripix.recipes.base import CurrentDecision

DIVERGENT = "divergent Decisions"
OVERRIDE = "override"  # the Decision `override` records: {"png": <hash>} of a PNG in decisions/overrides/
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford's base 32: sorts like the numbers it encodes


def _encode(number: int) -> str:
    digits = []
    for _ in range(26):
        digits.append(_ALPHABET[number & 31])
        number >>= 5
    return "".join(reversed(digits))


def _decode(ulid: str) -> int:
    number = 0
    for char in ulid:
        number = number << 5 | _ALPHABET.index(char)
    return number


def new_ulid(after: str | None = None) -> str:
    """A ULID for now. Given the latest ID in the journal, the result sorts after it even within the same millisecond
    or when this machine's clock is behind the one that wrote `after`."""
    number = (int(time.time() * 1000) << 80) | int.from_bytes(secrets.token_bytes(10), "big")
    if after is not None and number <= _decode(after):
        number = _decode(after) + 1
    return _encode(number)


class JournalEntry(BaseModel):
    """One line of a journal: a Decision, or the undo or redo of an earlier entry."""

    model_config = ConfigDict(extra="forbid")

    id: str
    parent: str | None
    decision: str | None = None
    data: dict[str, Any] | None = None
    image_hash: str | None = None
    replaces: str | None = None
    undo: str | None = None
    redo: str | None = None
    accept: list[str] | None = None

    @model_validator(mode="after")
    def _one_kind_of_entry(self) -> Self:
        kinds = [self.decision is not None, self.undo is not None, self.redo is not None, self.accept is not None]
        if sum(kinds) != 1:
            raise ValueError("an entry is a Decision, an undo, a redo or an accept, exactly one of them")
        if self.decision is not None and self.data is None:
            raise ValueError("a Decision entry needs 'data'")
        if self.decision is None and (self.data is not None or self.image_hash is not None or
                                      self.replaces is not None):
            raise ValueError("only a Decision entry has 'data', 'image_hash' and 'replaces'")
        return self

    def line(self) -> dict[str, Any]:
        """The entry as written: `parent` always, the other keys only when set."""
        return {key: value for key, value in self.model_dump().items() if key == "parent" or value is not None}


@dataclass(frozen=True)
class Replay:
    """What a journal says now: the current Decisions in order, the redo stack, the divergent entries not yet accepted,
    and everything any accept entry has listed."""

    current: tuple[CurrentDecision, ...]
    undone: tuple[str, ...]
    last_id: str | None
    conflicts: tuple[str, ...]
    accepted: frozenset[str] = frozenset()

    @property
    def divergent(self) -> bool:
        return bool(self.conflicts)

    def next_undo(self) -> str | None:
        return self.current[-1].id if self.current else None

    def next_redo(self) -> str | None:
        return self.undone[-1] if self.undone else None


def journal_path(asset_dir: Path, stage: str) -> Path:
    return asset_dir / "decisions" / f"{stage}.jsonl"


def override_path(asset_dir: Path, png_hash: str) -> Path:
    return asset_dir / "decisions" / "overrides" / f"{png_hash}.png"


def read_entries(path: Path, file: str) -> list[JournalEntry]:
    """The entries of a journal in ULID order. A missing file is an empty journal."""
    try:
        text = path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        return []
    entries = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(JournalEntry.model_validate(json.loads(line)))
        except (ValueError, ValidationError) as error:
            raise KiripixError(
                [
                    Finding(
                        code="journal.invalid",
                        message=f"{file}:{number}: {error}",
                        position=Position(file=file),
                        owner_action=f"Fix line {number} of {file}, or remove it if a bad merge left it behind.",
                    )
                ]
            ) from None
    return sorted(entries, key=lambda entry: entry.id)


def replay(entries: list[JournalEntry]) -> Replay:
    """Replay entries (in ULID order) into the current Decisions.

    A Decision makes the redo stack empty; an undo takes a current Decision out and puts it on the redo stack; a redo
    brings the latest one back. A re-recorded Decision takes the place of the current one it replaces. Entries that
    name nothing current, undoable or redoable change nothing. Entries sharing a parent are divergent until an accept
    entry lists them all.
    """
    decisions: dict[str, JournalEntry] = {}
    active: set[str] = set()
    position: dict[str, str] = {}
    undone: list[str] = []
    children: dict[str | None, list[str]] = {}
    accepted: set[str] = set()
    for entry in entries:
        children.setdefault(entry.parent, []).append(entry.id)
        if entry.decision is not None:
            decisions[entry.id] = entry
            if entry.replaces is None:
                active.add(entry.id)
                position[entry.id] = entry.id
                undone.clear()
            elif entry.replaces in active:
                active.discard(entry.replaces)
                active.add(entry.id)
                position[entry.id] = position[entry.replaces]
        elif entry.undo is not None:
            if entry.undo in active:
                active.discard(entry.undo)
                undone.append(entry.undo)
        elif entry.redo is not None:
            if entry.redo in undone:
                undone.remove(entry.redo)
                active.add(entry.redo)
        elif entry.accept is not None:
            accepted.update([*entry.accept, entry.id])
    current = tuple(
        CurrentDecision(i, str(decisions[i].decision), decisions[i].data or {}, decisions[i].image_hash)
        for i in sorted(active, key=lambda i: position[i])
    )
    conflicts = tuple(sorted(i for ids in children.values() if len(ids) > 1 and not accepted.issuperset(ids)
                             for i in ids))
    return Replay(current, tuple(undone), entries[-1].id if entries else None, conflicts, frozenset(accepted))


def hashable(view: Replay) -> list[dict[str, Any]]:
    """What of the current Decisions goes into the Stage's input hash: what was decided, not when or on which image
    (the image is already covered by the upstream hash)."""
    return [{"decision": d.name, "data": d.data} for d in view.current]


def append(path: Path, entry: JournalEntry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic.append_jsonl(path, entry.line())

