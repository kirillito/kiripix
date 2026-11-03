"""Running a Command as a cancellable job, for the long-running adapters (the server).

The CLI calls `invoke` on its main thread, where Ctrl+C raises KeyboardInterrupt. A server has no Ctrl+C, so a Job runs
`invoke` on a thread of its own and cancels it by raising that same KeyboardInterrupt in the thread. Core then stops it
exactly as it stops for Ctrl+C: atomic writes leave nothing half-done, and the run is recorded as cancelled.
"""

import ctypes
import shlex
import threading
from collections.abc import Callable
from concurrent.futures import Future
from pathlib import Path
from typing import Any

from kiripix.checks import Finding
from kiripix.commands.contract import Context, Envelope, ExitCode, ProgressEvent
from kiripix.commands.invoke import invoke
from kiripix.commands.registry import Command


def error_envelope(findings: list[Finding]) -> Envelope[Any]:
    """A result for a call that never reached a Command (bad JSON, an unknown Command)."""
    return Envelope(ok=False, findings=findings)


def call_line(command: Command[Any, Any], raw: dict[str, Any]) -> str:
    """The `kiripix ...` line for a call made over REST: the Command and its positional arguments. It goes into
    lock holders and into the `fix` of a busy result, so it should be something a person can run."""
    words = ["kiripix", *command.path]
    for name in command.cli.positional:
        value = raw.get(name)
        if isinstance(value, list):
            words.extend(str(v) for v in value)
        elif value is not None:
            words.append(str(value))
    return shlex.join(words)


def _raise_in(thread_id: int, error: type[BaseException]) -> None:
    ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(thread_id), ctypes.py_object(error))


def _ignore(event: ProgressEvent) -> None:
    pass


class Job:
    """One call of a Command on its own thread. `result` resolves to the envelope and the exit code."""

    def __init__(
        self,
        command: Command[Any, Any],
        raw: Any,
        *,
        id: str,
        cwd: Path,
        wait: float = 0.0,
        owner: bool = False,
        progress: Callable[[ProgressEvent], None] = _ignore,
    ) -> None:
        """`owner` says the caller proved the Owner is present (the session token): the REST half of spec §10.3."""
        self.id = id
        self.command = command
        self.raw = raw
        self.result: Future[tuple[Envelope[Any], ExitCode]] = Future()
        line = call_line(command, raw) if isinstance(raw, dict) else f"kiripix {command.name}"
        self._context = Context(cwd=cwd, command_line=line, wait=wait, progress=progress, interactive=owner,
                                via="rest")
        self._thread = threading.Thread(target=self._body, name=f"job-{command.name}", daemon=True)
        self._lock = threading.Lock()
        self._finished = False

    def start(self) -> None:
        self._thread.start()

    def _body(self) -> None:
        outcome: tuple[Envelope[Any], ExitCode] | None = None
        try:
            try:
                outcome = invoke(self.command, self.raw, self._context)
            finally:
                with self._lock:
                    self._finished = True
        except BaseException:  # noqa: BLE001 - a cancel that landed just as the Command finished
            pass
        if outcome is None:
            cancelled = Finding(code="run.cancelled", message="cancelled; no output was left half-written",
                                fix=self._context.command_line)
            outcome = (error_envelope([cancelled]), ExitCode.ERROR)
        self.result.set_result(outcome)

    def cancel(self) -> bool:
        """Stop the Command as Ctrl+C would. False when it had already finished."""
        with self._lock:
            ident = self._thread.ident
            if self._finished or ident is None:
                return False
            _raise_in(ident, KeyboardInterrupt)
            return True
