"""The JSON contract (spec Â§10.2): the result envelope every Command answers with, on every adapter."""

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
    """What an adapter tells a Command about the call: where it runs, how it was invoked, where progress goes, and
    whether the Owner is at an interactive terminal (the CLI's half of the owner-only guard, spec Â§10.3)."""

    cwd: Path
    command_line: str
    wait: float = 0.0
    progress: Callable[[ProgressEvent], None] = _no_progress
    interactive: bool = False
    via: Literal["cli", "rest"] = "cli"  # how the Owner proves presence: a terminal, or the session token


# The HTTP status REST answers with for each exit code, and for the findings that name a more exact one. `schema`
# documents both (spec §10.6); `http_status` picks.
HTTP_STATUS: dict[int, int] = {
    ExitCode.OK: 200,
    ExitCode.ERROR: 400,
    ExitCode.CHECK_FAILED: 422,
    ExitCode.NEEDS_OWNER: 403,
    ExitCode.BUSY: 423,
}
FINDING_STATUS: dict[str, int] = {"job.not_found": 404, "file.not_found": 404, "job.duplicate": 409}


def http_status(exit_code: int, findings: list[Finding]) -> int:
    for finding in findings:
        if finding.code in FINDING_STATUS:
            return FINDING_STATUS[finding.code]
    return HTTP_STATUS[exit_code]


__all__ = ["API_VERSION", "Busy", "Context", "Envelope", "ExitCode", "FINDING_STATUS", "HTTP_STATUS", "Outcome", "ProgressEvent", "http_status"]
