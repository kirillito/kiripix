"""Content hashes, with a cache keyed on modification time and size in `.kiripix/`.

The cache only saves time: deleting it makes the next status slower, never different. A file modified less than two
seconds before it is hashed isn't cached, so a quick second write with the same size and timestamp can't be missed.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from kiripix.core import atomic

_RACY_SECONDS = 2.0


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_json(value: Any) -> str:
    """The hash of a value's canonical JSON."""
    return hash_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class HashCache:
    """File hashes keyed by path, valid while the file's mtime and size are unchanged."""

    def __init__(self, state_dir: Path) -> None:
        self._path = state_dir / "hash-cache.json"
        self._entries: dict[str, list[Any]] = {}
        self._dirty = False
        self._derived_path = state_dir / "derived-cache.json"
        self._derived: dict[str, Any] = {}
        self._derived_dirty = False
        try:
            loaded = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self._entries = loaded
        except (OSError, ValueError):
            pass
        try:
            loaded = json.loads(self._derived_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self._derived = loaded
        except (OSError, ValueError):
            pass

    def derived(self, name: str, key: str) -> Any | None:
        """A computed value remembered under `name`, if it was stored for exactly this `key` (what it derives from)."""
        entry = self._derived.get(name)
        if isinstance(entry, list) and len(entry) == 2 and entry[0] == key:
            return entry[1]
        return None

    def remember(self, name: str, key: str, value: Any) -> None:
        """Remember a computation for `key`. It only saves work and is never a status (ADR 0005)."""
        self._derived[name] = [key, value]
        self._derived_dirty = True

    def file_hash(self, path: Path) -> str:
        stat = path.stat()
        key = os.path.abspath(path)
        entry = self._entries.get(key)
        if entry and entry[0] == stat.st_mtime_ns and entry[1] == stat.st_size:
            return str(entry[2])
        digest = _hash_file(path)
        if time.time() - stat.st_mtime > _RACY_SECONDS:
            self._entries[key] = [stat.st_mtime_ns, stat.st_size, digest]
            self._dirty = True
        return digest

    def save(self) -> None:
        if self._dirty:
            try:
                atomic.write_json(self._path, self._entries)
            except OSError:
                pass  # Another process may be replacing it; the cache is only an optimisation.
            self._dirty = False
        if self._derived_dirty:
            try:
                atomic.write_json(self._derived_path, self._derived)
            except OSError:
                pass
            self._derived_dirty = False
