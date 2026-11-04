"""The warm Runner (spec §10.4, §10.6): in `serve` only, a Runner stays loaded after use, and each image's embedding stays
cached by the image's hash, so a hover runs only the decoder. It holds the GPU lock while loaded, and unloads after an idle
timeout or when another process asks for the lock.

Everything a Runner does in this process, warm or not, goes one at a time: `one_runner_loaded` for a call that loads and
unloads its own, which unloads the warm one first because a server's Commands share the registered Runners.
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from kiripix.core import cancel, locks
from kiripix.runners import Device, EmbeddingRunner, pull, weights_dir

DEFAULT_IDLE_SECONDS = 300.0
_WATCH_SECONDS = 0.1
_CACHED_EMBEDDINGS = 4  # each is some megabytes, and a room's masks are made on one image

_RUNNER_LOADED = threading.Lock()  # a --cpu call holds no GPU lock, so this is what keeps them apart in one process


@dataclass
class _Warm:
    runner: EmbeddingRunner
    state_dir: Path
    device: Device
    gpu_lock: Path | None
    idle_seconds: float
    used: float
    embeddings: OrderedDict[str, tuple[Any, tuple[int, int]]] = field(default_factory=OrderedDict)
    gone: threading.Event = field(default_factory=threading.Event)


_current: _Warm | None = None  # guarded by _RUNNER_LOADED
_idle_seconds = DEFAULT_IDLE_SECONDS


def set_idle_seconds(seconds: float) -> None:
    global _idle_seconds
    _idle_seconds = seconds


def _unload() -> None:
    """With _RUNNER_LOADED held."""
    global _current
    warm, _current = _current, None
    if warm is None:
        return
    warm.gone.set()
    try:
        warm.runner.unload()
    finally:
        if warm.gpu_lock is not None:
            locks.release_warm(warm.gpu_lock)


@contextmanager
def _exclusive() -> Iterator[None]:
    """Wait for this process's other Runner work to finish, for as long as the Command isn't cancelled."""
    while not _RUNNER_LOADED.acquire(timeout=0.05):
        cancel.check()
    try:
        yield
    finally:
        _RUNNER_LOADED.release()


@contextmanager
def one_runner_loaded() -> Iterator[None]:
    """The turn of a call that loads a Runner itself. The warm Runner gives way."""
    with _exclusive():
        _unload()
        yield


def _watch(warm: _Warm) -> None:
    """Unload once idle or asked to. A preview in progress holds _RUNNER_LOADED, so this waits for the next look."""
    while not warm.gone.wait(_WATCH_SECONDS):
        idle = time.monotonic() - warm.used > warm.idle_seconds
        if not idle and (warm.gpu_lock is None or not locks.unload_requested(warm.state_dir)):
            continue
        if _RUNNER_LOADED.acquire(blocking=False):
            try:
                if _current is warm:
                    _unload()
            finally:
                _RUNNER_LOADED.release()


def _loaded(runner: EmbeddingRunner, state_dir: Path, device: Device, command_line: str) -> _Warm:
    """With _RUNNER_LOADED held: the warm Runner, loaded if it wasn't. A process that asked for the GPU lock comes first,
    or hovers one after another could keep the watcher from ever unloading."""
    global _current
    if _current is not None and _current.runner is runner and _current.state_dir == state_dir and \
            _current.device == device and not (_current.gpu_lock is not None and locks.unload_requested(state_dir)):
        return _current
    _unload()
    directory = weights_dir(state_dir, runner)
    pull(directory, runner, cancel.check)
    gpu_lock = None if device == "cpu" else locks.acquire_warm(state_dir, command_line)
    try:
        runner.load(directory, device)
    except BaseException:
        if gpu_lock is not None:
            locks.release_warm(gpu_lock)
        raise
    _current = _Warm(runner, state_dir, device, gpu_lock, _idle_seconds, time.monotonic())
    threading.Thread(target=_watch, args=(_current,), name="warm-runner", daemon=True).start()
    return _current


def warm_call(runner: EmbeddingRunner, state_dir: Path, device: Device, image_hash: str, image: Callable[[], np.ndarray],
              params: dict[str, Any], command_line: str) -> tuple[np.ndarray, bool, str]:
    """A call on the warm Runner: its result, whether the embedding had to be computed, and the device used. `image` is
    read only then. A cancelled encoder run leaves no entry in the cache, and the Runner stays loaded."""
    with _exclusive():
        warm = _loaded(runner, state_dir, device, command_line)
        warm.used = time.monotonic()
        cached = warm.embeddings.get(image_hash)
        computed = cached is None
        if cached is None:
            pixels = image()
            cached = (runner.embed(pixels, cancel.check), pixels.shape[:2])
            warm.embeddings[image_hash] = cached
            while len(warm.embeddings) > _CACHED_EMBEDDINGS:
                warm.embeddings.popitem(last=False)
        warm.embeddings.move_to_end(image_hash)
        result = runner.decode(cached[0], cached[1], params, cancel.check)
        warm.used = time.monotonic()
        return result, computed, runner.device_used


def shut_down() -> None:
    """Let go of the Runner and the GPU lock, when the server stops."""
    with _RUNNER_LOADED:
        _unload()


__all__ = ["DEFAULT_IDLE_SECONDS", "one_runner_loaded", "set_idle_seconds", "shut_down", "warm_call"]
