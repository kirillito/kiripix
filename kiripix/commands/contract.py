"""The JSON contract (spec §10.2): the result envelope every Command answers with, on every adapter."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

from kiripix.checks import Finding
from kiripix.core.errors import ExitCode
from kiripix.core.graph import ProgressEvent
from kiripix.core.locks import Busy

API_VERSION: Literal[1] = 1

D = TypeVar("D", bound=BaseModel)


class Envelope(BaseModel, Generic[D]):
    """One Command result. `data` is the Command's output, or the lock holder when busy (exit code 4)."""

    api_version: Literal[1] = API_VERSION
    ok: bool
    data: D | Busy | None = None
    findings: list[Finding] = []


@dataclass
class Outcome(Generic[D]):
    """What a Command handler returns. The exit code travels with the result, never chosen by an adapter."""

    data: D | None
    findings: list[Finding] = field(default_factory=list)
    exit_code: ExitCode = ExitCode.OK


def _no_progress(event: ProgressEvent) -> None:
    pass


@dataclass(frozen=True)
class Context:
    """What an adapter tells a Command about the call: where it runs, how it was invoked, and where progress goes."""

    cwd: Path
    command_line: str
    wait: float = 0.0
    progress: Callable[[ProgressEvent], None] = _no_progress


__all__ = ["API_VERSION", "Busy", "Context", "Envelope", "ExitCode", "Outcome", "ProgressEvent"]
