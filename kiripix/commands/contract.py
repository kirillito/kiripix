"""The JSON contract (spec Â§10.2): the result envelope every Command answers with, on every adapter."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

from kiripix.checks import Finding
from kiripix.core.cancel import CancelToken
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
    whether the Owner is at an interactive terminal (the CLI's half of the owner-only guard, spec Â§10.3), and the
    cancel token the adapter sets on Ctrl+C or a cancel request."""

    cwd: Path
    command_line: str
    wait: float = 0.0
    progress: Callable[[ProgressEvent], None] = _no_progress
    interactive: bool = False
    via: Literal["cli", "rest"] = "cli"  # how the Owner proves presence: a terminal, or the session token
    cancel: CancelToken = field(default_factory=CancelToken)


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


class TransportRoute(BaseModel):
    """A REST route that carries Commands but isn't one (ADR 0007). `statuses` maps each HTTP status to when it's
    answered."""

    method: Literal["GET", "POST"]
    path: str
    purpose: str
    statuses: dict[str, str]


TRANSPORT: list[TransportRoute] = [
    TransportRoute(
        method="GET", path="/files/{path}",
        purpose="A file in the Project, such as an image output or a preview. Not `.git/`, nor `.kiripix/` except "
                "`.kiripix/previews/`.",
        statuses={"200": "the file", "404": "file.not_found: no such file, or one that isn't served"},
    ),
    TransportRoute(
        method="GET", path="/api/events",
        purpose="Server-sent events: `progress` (the events of `--progress=jsonl`, with the job and Command), "
                "`job_end`, and `changed` when anyone changes the Project. `?job=<id>` follows one job.",
        statuses={"200": "a text/event-stream that stays open"},
    ),
    TransportRoute(
        method="POST", path="/api/jobs/{job}/cancel",
        purpose="Cancel a running Command as Ctrl+C does; its own request then answers run.cancelled. A job's id is "
                "the X-Kiripix-Job header, given with the request or answered with it.",
        statuses={"200": "data.cancelled: true, or false when the job had just finished",
                  "404": "job.not_found: no running job with that id"},
    ),
]


def http_status(exit_code: int, findings: list[Finding]) -> int:
    for finding in findings:
        if finding.code in FINDING_STATUS:
            return FINDING_STATUS[finding.code]
    return HTTP_STATUS[exit_code]


__all__ = ["API_VERSION", "Busy", "Context", "Envelope", "ExitCode", "FINDING_STATUS", "HTTP_STATUS", "Outcome",
           "ProgressEvent", "TRANSPORT", "TransportRoute", "http_status"]
