"""The folder watch: tells the UI when something other than the UI changed the Project (an agent's CLI call).

It polls file times, so it needs no extra dependency and behaves the same on Windows and Linux. The state folder
(`.kiripix/`), `.git` and the half-built `.tmp-*` folders are ignored.
"""

import os
import threading
from collections.abc import Callable
from pathlib import Path

_SKIP = {".git", ".kiripix", "__pycache__", "node_modules", ".venv"}
Snapshot = dict[str, tuple[int, int]]


def snapshot(root: Path) -> Snapshot:
    found: Snapshot = {}
    pending = [root]
    while pending:
        folder = pending.pop()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    if entry.name in _SKIP or entry.name.startswith(".tmp-"):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(Path(entry.path))
                        else:
                            stat = entry.stat(follow_symlinks=False)
                            found[Path(entry.path).relative_to(root).as_posix()] = (stat.st_mtime_ns, stat.st_size)
                    except OSError:
                        continue
        except OSError:
            continue
    return found


class ProjectWatch:
    """Calls `on_change(paths)` (Project-relative, sorted) whenever files appear, change or go away."""

    def __init__(self, root: Path, on_change: Callable[[list[str]], None], interval: float = 0.3) -> None:
        self._root = root
        self._on_change = on_change
        self._interval = interval
        self._stop = threading.Event()
        self._before: Snapshot = {}
        self._thread = threading.Thread(target=self._loop, name="project-watch", daemon=True)

    def start(self) -> None:
        self._before = snapshot(self._root)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            now = snapshot(self._root)
            changed = sorted(p for p in now.keys() | self._before.keys() if now.get(p) != self._before.get(p))
            self._before = now
            if changed:
                self._on_change(changed)
