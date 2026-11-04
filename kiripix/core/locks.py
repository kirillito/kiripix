"""Project, Asset and GPU locks (spec §10.4): files in `.kiripix/locks/`.

Locks are always taken in the order project, Asset, GPU, so two writers can't deadlock. A lock whose process is gone
on this host is stale and is taken over; a lock from another host never is.
"""

import json
import os
import socket
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from pathlib import Path

import psutil
from pydantic import BaseModel, ValidationError

from kiripix.checks import Finding
from kiripix.core import cancel
from kiripix.core.errors import ExitCode, KiripixError

PROJECT_LOCK = "project"
GPU_LOCK = "gpu"
_POLL_SECONDS = 0.1
_TAKEOVER_GUARD_SECONDS = 10.0
_EMPTY_LOCK_SECONDS = 5.0  # a lock file still unreadable after this was left by a crash while being written


class LockHolder(BaseModel):
    """Who holds a lock: written into the lock file, and returned in `data` when a Command is busy."""

    lock: str
    pid: int
    host: str
    started: str
    command: str
    process_started: float


class Busy(BaseModel):
    """The `data` of a busy result (exit code 4)."""

    holder: LockHolder


def asset_lock(asset_id: str) -> str:
    return f"asset.{asset_id}"


def _rank(lock: str) -> int:
    return 0 if lock == PROJECT_LOCK else 2 if lock == GPU_LOCK else 1


def _this_process() -> tuple[int, float]:
    pid = os.getpid()
    return pid, psutil.Process(pid).create_time()


def _read(path: Path) -> LockHolder | None:
    try:
        return LockHolder.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError):
        return None


def _is_stale(holder: LockHolder) -> bool:
    if holder.host != socket.gethostname():
        return False
    try:
        return abs(psutil.Process(holder.pid).create_time() - holder.process_started) > 0.01
    except psutil.NoSuchProcess:
        return True
    except psutil.Error:
        return False


def _age(path: Path) -> float:
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return 0.0


def _take_over(path: Path, stale: LockHolder | None) -> None:
    """Remove a stale lock, unless someone else replaced it first. A short-lived guard file serialises takers."""
    guard = path.with_suffix(".takeover")
    try:
        fd = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            if time.time() - guard.stat().st_mtime > _TAKEOVER_GUARD_SECONDS:
                guard.unlink(missing_ok=True)
        except OSError:
            pass
        return
    os.close(fd)
    try:
        if _read(path) == stale:
            path.unlink(missing_ok=True)
    finally:
        guard.unlink(missing_ok=True)


def _busy(holder: LockHolder, command_line: str) -> KiripixError:
    where = "this host" if holder.host == socket.gethostname() else f"host {holder.host}"
    what = "the GPU" if holder.lock == GPU_LOCK else "the Project" if holder.lock == PROJECT_LOCK else holder.lock[6:]
    finding = Finding(
        code="lock.busy",
        message=(
            f"{what} is locked by process {holder.pid} on {where} since {holder.started}, "
            f"running `{holder.command}`"
        ),
        fix=f"{command_line} --wait 60",
    )
    return KiripixError([finding], ExitCode.BUSY, Busy(holder=holder))


def _acquire(directory: Path, lock: str, wait: float, command_line: str) -> Path:
    path = directory / f"{lock}.lock"
    pid, process_started = _this_process()
    holder = LockHolder(
        lock=lock,
        pid=pid,
        host=socket.gethostname(),
        started=datetime.now(UTC).isoformat(timespec="seconds"),
        command=command_line,
        process_started=process_started,
    )
    deadline = time.monotonic() + wait
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            current = _read(path)
            if current is not None and _is_stale(current) or current is None and _age(path) > _EMPTY_LOCK_SECONDS:
                _take_over(path, current)
                continue
            if time.monotonic() >= deadline:
                if current is None:
                    # Being written right now, or unreadable: report what we know.
                    current = holder.model_copy(update={"pid": 0, "host": "unknown", "command": "unknown"})
                raise _busy(current, command_line) from None
            cancel.sleep(_POLL_SECONDS)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(holder.model_dump()))
        return path


@contextmanager
def hold(state_dir: Path, locks: list[str], wait: float, command_line: str) -> Iterator[None]:
    """Hold the named locks for the duration, taken in the order project, Asset, GPU; released in reverse."""
    directory = state_dir / "locks"
    directory.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        for lock in sorted(set(locks), key=lambda name: (_rank(name), name)):
            path = _acquire(directory, lock, wait, command_line)
            stack.callback(path.unlink, missing_ok=True)
        yield
