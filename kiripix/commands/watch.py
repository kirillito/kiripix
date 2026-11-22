"""The Project watch: tells the UI when something changed in the Project, from Kiripix's own record, not a scan.

Every process that writes the Project (a CLI call, `serve`) appends what it wrote to its own file in
`.kiripix/changes/` (`kiripix.core.changes`). `ProjectWatch` lists that folder every 0.3 s, reads each file that grew
from where it stopped up to the last complete line, and calls `on_change` once per tick that had new lines. It never
walks the Project, and it starts at the end of every file that is there when it starts, so `serve` answers at once.

What it does not see: a file changed outside Kiripix (an `asset.toml` edited by hand, a file dropped into a folder).
The UI covers that by refreshing when its window gets the focus again and with its Reload button.

`on_change(paths, own)`: `paths` is every Project-relative path written in the tick (sorted, `/`-separated, a folder
for a Stage's output or a swapped-in snapshot); `own` is the sorted subset written only by this process (the Commands
`serve` itself ran), so the UI can tell its own writes from an agent's. A path both wrote in the same tick is not own.

When it starts, the watch deletes the change files of processes that are gone and older than a day. A CLI process's file
stays for any `serve` that is running to read.
"""

import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

from kiripix.core import changes

STALE_AFTER_SECONDS = 24 * 60 * 60


def clean_up(root: Path, now: float | None = None) -> None:
    """Delete the change files whose process is gone and that are more than a day old."""
    now = time.time() if now is None else now
    try:
        entries = list(os.scandir(changes.changes_dir(root)))
    except OSError:
        return
    for entry in entries:
        try:
            if entry.name.endswith(".jsonl") and now - entry.stat().st_mtime > STALE_AFTER_SECONDS \
                    and changes.is_stale(entry.name):
                os.unlink(entry.path)
        except OSError:
            continue


class ProjectWatch:
    """Calls `on_change(paths, own)` whenever Kiripix recorded new writes in the Project."""

    def __init__(self, root: Path, on_change: Callable[[list[str], list[str]], None], interval: float = 0.3) -> None:
        self._folder = changes.changes_dir(root)
        self._on_change = on_change
        self._interval = interval
        self._stop = threading.Event()
        self._offsets: dict[str, int] = {}
        self._root = root
        self._thread = threading.Thread(target=self._loop, name="project-watch", daemon=True)

    def start(self) -> None:
        clean_up(self._root)
        for name, size in self._listing().items():
            self._offsets[name] = size
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _listing(self) -> dict[str, int]:
        try:
            with os.scandir(self._folder) as entries:
                return {e.name: e.stat().st_size for e in entries if e.name.endswith(".jsonl")}
        except OSError:
            return {}

    def _read(self, name: str, size: int) -> list[str]:
        """The paths on the complete lines this file has gained since the last read."""
        start = self._offsets.get(name, 0)
        if size <= start:
            if size < start:  # the file was replaced by a shorter one: read it afresh
                self._offsets[name] = 0
            return []
        try:
            with open(self._folder / name, "rb") as handle:
                handle.seek(start)
                data = handle.read()
        except OSError:
            return []
        complete = data[: data.rfind(b"\n") + 1]
        self._offsets[name] = start + len(complete)
        found: list[str] = []
        for line in complete.splitlines():
            try:
                paths = json.loads(line)["paths"]
                found.extend(p for p in paths if isinstance(p, str))
            except (ValueError, KeyError, TypeError):
                continue
        return found

    def poll(self) -> None:
        """One tick: read what was recorded since the last one and report it."""
        own_name = changes.own_file_name()
        own: set[str] = set()
        other: set[str] = set()
        for name, size in self._listing().items():
            (own if name == own_name else other).update(self._read(name, size))
        if own or other:
            paths = sorted(own | other)
            self._on_change(paths, sorted(own - other))

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self.poll()
            except Exception:  # a tick that fails must not end the watch
                continue
