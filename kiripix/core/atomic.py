"""Atomic writes and append-only JSON Lines. Every file Kiripix writes goes through here."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from kiripix.core import cancel


def _replace(source: Path, target: Path) -> None:
    # On Windows a reader (an editor, a virus scanner) can hold the target open for a moment.
    for attempt in range(20):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == 19:
                raise
            cancel.sleep(0.05)


def write_bytes(path: Path, data: bytes) -> None:
    """Write to a temporary file beside `path`, then rename it into place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 text with the line endings as given (LF), atomically."""
    write_bytes(path, text.encode("utf-8"))


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def append_jsonl_many(path: Path, entries: list[dict[str, Any]]) -> None:
    """Append several objects, one LF-terminated line each, all or none: the file is rewritten whole, atomically, so an
    interruption leaves the journal as it was. Existing bytes are kept as they are. The caller holds the file's lock
    (a journal's is its Asset's), or a concurrent append between the read and the rename would be lost."""
    lines = "".join(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n" for e in entries)
    existing = path.read_bytes() if path.exists() else b""
    if existing and not existing.endswith(b"\n"):
        existing += b"\n"
    write_bytes(path, existing + lines.encode("utf-8"))


def append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    """Append one JSON object as one LF-terminated line, in a single write."""
    line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("ab") as handle:
        handle.write(line.encode("utf-8"))
