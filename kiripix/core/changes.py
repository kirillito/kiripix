"""The record of what Kiripix wrote (spec §10.6): how `serve` tells the UI what changed without scanning the Project.

Each process appends a line to its own file, `.kiripix/changes/<pid>-<process start, ms>.jsonl`, after a write is in
place: `{"t": <epoch seconds>, "paths": ["assets/room/a/asset.toml", ...]}` with Project-relative, `/`-separated paths.
Nothing else ever writes to that file, so no lock is needed between processes. It is a record of writes, never of status
(ADR 0005): deleting the folder loses nothing but events the UI has not seen yet. A line that does not parse is skipped.

Nothing is recorded for `.kiripix/`, `.git`, a `.tmp-*` or `.old-*` folder, or a `time.jsonl`. A write outside a Project
(an export into a Godot project) is not recorded either. Recording never fails the write it follows.
"""

import json
import os
import threading
import time
from collections.abc import Iterable
from pathlib import Path

import psutil

PROJECT_FILE = "kiripix.toml"
STATE_DIR = ".kiripix"
CHANGES_DIR = "changes"
_SKIP = {".git", STATE_DIR}
_SKIP_PREFIXES = (".tmp-", ".old-")

_lock = threading.Lock()
_roots: set[str] = set()
_own: tuple[int, str] | None = None  # (pid, file name)


def process_stamp(pid: int) -> int | None:
    """The start time of a process in milliseconds, or None if it is not running."""
    try:
        return round(psutil.Process(pid).create_time() * 1000)
    except psutil.Error:
        return None


def own_file_name() -> str:
    """The name of this process's change file (a forked process gets its own)."""
    global _own
    pid = os.getpid()
    if _own is None or _own[0] != pid:
        _own = (pid, f"{pid}-{process_stamp(pid) or 0}.jsonl")
    return _own[1]


def changes_dir(root: Path) -> Path:
    return root / STATE_DIR / CHANGES_DIR


def is_stale(name: str) -> bool:
    """Whether the process that owns the change file `name` is gone (a reused pid has a new start time)."""
    stem = name.removesuffix(".jsonl")
    pid_text, _, stamp_text = stem.partition("-")
    if not (pid_text.isdigit() and stamp_text.isdigit()):
        return True
    return process_stamp(int(pid_text)) != int(stamp_text)


def _root_of(path: Path) -> str | None:
    folder = os.path.dirname(os.path.abspath(path))
    while True:
        if folder in _roots:
            return folder
        if os.path.isfile(os.path.join(folder, PROJECT_FILE)):
            _roots.add(folder)
            return folder
        parent = os.path.dirname(folder)
        if parent == folder:
            return None
        folder = parent


def _ignored(parts: Iterable[str]) -> bool:
    for part in parts:
        if part in _SKIP or part.startswith(_SKIP_PREFIXES):
            return True
    return False


def record(*paths: Path) -> None:
    """Record that these paths (files or folders, already in place or already gone) were written."""
    by_root: dict[str, list[str]] = {}
    for path in paths:
        try:
            root = _root_of(path)
            if root is None:
                continue
            relative = os.path.relpath(os.path.abspath(path), root).replace(os.sep, "/")
        except (OSError, ValueError):
            continue
        parts = relative.split("/")
        if parts[0] == ".." or _ignored(parts) or parts[-1] == "time.jsonl":
            continue
        by_root.setdefault(root, []).append(relative)
    for root, relatives in by_root.items():
        line = json.dumps({"t": round(time.time(), 3), "paths": relatives}, ensure_ascii=False,
                          separators=(",", ":")) + "\n"
        _append(Path(root), line.encode("utf-8"))


def _append(root: Path, data: bytes) -> None:
    from kiripix.core import atomic  # here, not at the top: atomic records every write through this module

    with _lock:
        try:
            atomic.append_line(changes_dir(root) / own_file_name(), data)
        except OSError:
            return


def remove(path: Path) -> None:
    """Delete a file (none is fine) and record it."""
    path.unlink(missing_ok=True)
    record(path)


class ChangeReader:
    """Reads the change files of a Project from where it last stopped, up to the last complete line of each.

    The file `serve` keeps its memory of the Project in step with (`kiripix.core.memory`): `read` lists the folder and
    returns the Project-relative paths on the lines written since the last call. A reader starts at the end of every file
    that is there when it is made, since nothing is remembered yet. Safe to call from any thread.
    """

    def __init__(self, root: Path) -> None:
        self._folder = changes_dir(root)
        self._lock = threading.Lock()
        self._offsets: dict[str, int] = {name: size for name, size in self._listing().items()}

    def _listing(self) -> dict[str, int]:
        try:
            with os.scandir(self._folder) as entries:
                return {e.name: e.stat().st_size for e in entries if e.name.endswith(".jsonl")}
        except OSError:
            return {}

    def read(self) -> list[str]:
        """The paths recorded since the last call (a path more than once if it was written more than once)."""
        found: list[str] = []
        with self._lock:
            for name, size in self._listing().items():
                start = self._offsets.get(name, 0)
                if size < start:  # replaced by a shorter file: read it afresh
                    start = 0
                if size == start:
                    self._offsets[name] = start
                    continue
                try:
                    with open(self._folder / name, "rb") as handle:
                        handle.seek(start)
                        data = handle.read()
                except OSError:
                    continue
                complete = data[: data.rfind(b"\n") + 1]
                self._offsets[name] = start + len(complete)
                for line in complete.splitlines():
                    try:
                        paths = json.loads(line)["paths"]
                    except (ValueError, KeyError, TypeError):
                        continue
                    found.extend(p for p in paths if isinstance(p, str))
        return found
