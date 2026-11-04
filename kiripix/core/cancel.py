"""Cooperative cancel (spec §10.1, §10.6): a token set by Ctrl+C or the server's cancel route, checked by core.

CPython delivers an asynchronous KeyboardInterrupt only between bytecodes, so it can't break a worker thread out of a
sleep, a lock wait or a long native call. So every wait in core goes through `sleep`, which wakes at once when the
token is set, and core checks the token between Stages, after each Stage's run and at each progress report. A Stage
checks it between chunks of its own work through `StageRun.check_cancel`.

`invoke` makes a Command's token the current one for the duration of the call (`scope`), so core reaches it without
passing it through every function. Outside a Command the current token is never set.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar


class Cancelled(BaseException):
    """The Command was cancelled. A BaseException, like KeyboardInterrupt, so `except Exception` doesn't catch it."""


class CancelToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        """Raise Cancelled if the token is set."""
        if self._event.is_set():
            raise Cancelled

    def sleep(self, seconds: float) -> None:
        """Wait `seconds`, or raise Cancelled as soon as the token is set."""
        if self._event.wait(seconds):
            raise Cancelled


_current: ContextVar[CancelToken] = ContextVar("kiripix_cancel", default=CancelToken())


def current() -> CancelToken:
    return _current.get()


@contextmanager
def scope(token: CancelToken) -> Iterator[None]:
    """Make `token` the current one inside the block."""
    reset = _current.set(token)
    try:
        yield
    finally:
        _current.reset(reset)


def check() -> None:
    current().check()


def sleep(seconds: float) -> None:
    """The one wait core uses instead of `time.sleep`."""
    current().sleep(seconds)
