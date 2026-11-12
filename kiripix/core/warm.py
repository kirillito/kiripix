"""The warm Runners (spec §10.4, §10.6): in `serve` only, a Runner that says it `can_stay_warm` stays loaded after use, and
each image's embedding stays cached by the image's hash, so a hover runs only the decoder. At most `MAX_WARM` stay loaded
together (SAM 2 and LaMa measure about 2 GB of VRAM between them); a third evicts the least recently used. They share the
one GPU lock, held while any is loaded, and each unloads after an idle timeout or when another process asks for the lock.

Everything a Runner does in this process, warm or not, goes one at a time: `one_runner_loaded` for a call that loads and
unloads its own, which unloads the warm ones first because a server's Commands share the registered Runners.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.core import cancel, locks
from kiripix.runners import Device, EmbeddingRunner, Runner, pull, weights_dir

DEFAULT_IDLE_SECONDS = 300.0
MAX_WARM = 2
_WATCH_SECONDS = 0.1
_CACHED_EMBEDDINGS = 4  # each is some megabytes, and a room's masks are made on one image

_RUNNER_LOADED = threading.Lock()  # a --cpu call holds no GPU lock, so this is what keeps them apart in one process


@dataclass
class _Warm:
    runner: Runner
    state_dir: Path
    device: Device
    uses_gpu_lock: bool
    idle_seconds: float
    used: float
    embeddings: OrderedDict[str, tuple[Any, tuple[int, int]]] = field(default_factory=OrderedDict)
    gone: threading.Event = field(default_factory=threading.Event)


_warm: OrderedDict[str, _Warm] = OrderedDict()  # by Runner ID, least recently used first; guarded by _RUNNER_LOADED
_gpu_lock: Path | None = None  # the one lock the warm Runners share; guarded by _RUNNER_LOADED
_idle_seconds = DEFAULT_IDLE_SECONDS
_abandoned: dict[int, threading.Thread] = {}  # a load a cancel walked away from, by Runner, until it has unloaded again


def set_idle_seconds(seconds: float) -> None:
    global _idle_seconds
    _idle_seconds = seconds


def _release_lock_if_unused() -> None:
    global _gpu_lock
    if _gpu_lock is not None and not any(w.uses_gpu_lock for w in _warm.values()):
        lock, _gpu_lock = _gpu_lock, None
        locks.release_warm(lock)


def _unload_one(runner_id: str) -> None:
    """With _RUNNER_LOADED held."""
    warm = _warm.pop(runner_id, None)
    if warm is None:
        return
    warm.gone.set()
    try:
        warm.runner.unload()
    finally:
        _release_lock_if_unused()


def _unload() -> None:
    """With _RUNNER_LOADED held: every warm Runner."""
    for runner_id in list(_warm):
        _unload_one(runner_id)


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
    """The turn of a call that loads a Runner itself. The warm Runners give way."""
    with _exclusive():
        _unload()
        yield


def load_runner(runner: Runner, directory: Path, device: Device) -> None:
    """`runner.load`, which a cancel can walk away from. A load can take 20 s inside the engine, where nothing can stop
    it, so it runs on a thread, and a cancel raises at once. The thread finishes alone and unloads what it loaded, and the
    next load of any Runner in this process waits for it, so an abandoned load and a new one never fill the GPU together.
    Raises what `runner.load` raised."""
    key = id(runner)
    for other, previous in list(_abandoned.items()):
        while previous.is_alive():
            previous.join(0.05)
            cancel.check()
        _abandoned.pop(other, None)
    outcome: dict[str, BaseException] = {}
    guard = threading.Lock()
    state = {"abandoned": False, "done": False}

    def work() -> None:
        try:
            runner.load(directory, device)
        except BaseException as error:  # noqa: BLE001 - handed to the waiting thread
            outcome["error"] = error
        with guard:
            state["done"] = True  # from here, whoever abandons the load unloads it
            if state["abandoned"] and "error" not in outcome:
                runner.unload()

    thread = threading.Thread(target=work, name="runner-load", daemon=True)
    thread.start()
    try:
        while thread.is_alive():
            thread.join(0.05)
            cancel.check()
    except BaseException:
        with guard:
            state["abandoned"] = True
            if not state["done"]:
                _abandoned[key] = thread  # the thread unloads when its load returns
            elif "error" not in outcome:
                runner.unload()
        raise
    if "error" in outcome:
        raise outcome["error"]


def _watch(warm: _Warm) -> None:
    """Unload once idle or asked to. A preview in progress holds _RUNNER_LOADED, so this waits for the next look."""
    runner_id = warm.runner.id
    while not warm.gone.wait(_WATCH_SECONDS):
        idle = time.monotonic() - warm.used > warm.idle_seconds
        if not idle and (not warm.uses_gpu_lock or not locks.unload_requested(warm.state_dir)):
            continue
        if _RUNNER_LOADED.acquire(blocking=False):
            try:
                if _warm.get(runner_id) is warm:
                    _unload_one(runner_id)
            finally:
                _RUNNER_LOADED.release()


def _loaded(runner: Runner, state_dir: Path, device: Device, command_line: str,
            loaded: list[float] | None = None) -> _Warm:
    """With _RUNNER_LOADED held: the warm Runner, loaded if it wasn't. A process that asked for the GPU lock comes first,
    or hovers one after another could keep the watcher from ever unloading. If it loaded the Runner, the seconds that
    took (the load alone) are appended to `loaded`."""
    global _gpu_lock
    asked = locks.unload_requested(state_dir)
    current = _warm.get(runner.id)
    if current is not None and current.runner is runner and current.state_dir == state_dir and \
            current.device == device and not (current.uses_gpu_lock and asked):
        _warm.move_to_end(runner.id)
        return current
    if any(w.state_dir != state_dir or w.device != device or (w.uses_gpu_lock and asked) for w in _warm.values()):
        _unload()
    _unload_one(runner.id)
    while len(_warm) >= MAX_WARM:
        _unload_one(next(iter(_warm)))
    directory = weights_dir(state_dir, runner)
    pull(directory, runner, cancel.check)
    took_lock = False
    if device != "cpu" and _gpu_lock is None:
        _gpu_lock = locks.acquire_warm(state_dir, command_line)
        took_lock = True
    started = time.monotonic()
    try:
        load_runner(runner, directory, device)
    except BaseException:
        if took_lock:
            _release_lock_if_unused()
        raise
    if loaded is not None:
        loaded.append(round(time.monotonic() - started, 3))
    warm = _Warm(runner, state_dir, device, device != "cpu", _idle_seconds, time.monotonic())
    _warm[runner.id] = warm
    threading.Thread(target=_watch, args=(warm,), name=f"warm-{runner.id}", daemon=True).start()
    return warm


def warm_call(runner: Runner, state_dir: Path, device: Device, image_hash: str, image: Callable[[], np.ndarray],
              params: dict[str, Any], command_line: str,
              loaded: list[float] | None = None) -> tuple[np.ndarray, bool, str]:
    """A call on a warm Runner: its result, whether the embedding had to be computed (a Runner with no embedding always
    computes), and the device used. `image` is read only then. A cancelled encoder run leaves no entry in the cache, and
    the Runner stays loaded. When the call had to load the Runner, the load's seconds are appended to `loaded`."""
    with _exclusive():
        warm = _loaded(runner, state_dir, device, command_line, loaded)
        warm.used = time.monotonic()
        if not isinstance(runner, EmbeddingRunner):
            result = runner.call(image(), params, cancel.check)
            warm.used = time.monotonic()
            return result, True, runner.device_used
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
    """Let go of the Runners and the GPU lock, when the server stops."""
    with _RUNNER_LOADED:
        _unload()


__all__ = ["DEFAULT_IDLE_SECONDS", "MAX_WARM", "load_runner", "one_runner_loaded", "set_idle_seconds", "shut_down",
           "warm_call"]
