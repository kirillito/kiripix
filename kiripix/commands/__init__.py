"""The Command registry: every operation's typed input, output and metadata (ADR 0006).

Uses `core` and `recipes`. The adapters (`cli`, later `server`) use only this package.

Importing this package imports almost nothing (ticket 0277): the names below load on first use (PEP 562), so
`kiripix --help` needs neither pydantic nor the stage graph. No Command module is imported until `REGISTRY` looks the
Command up (or all of them, when it is iterated); the static index is `kiripix.commands.index`.
"""

import importlib
from typing import TYPE_CHECKING, Any

from kiripix.commands.index import INDEX

if TYPE_CHECKING:
    from kiripix.checks import Finding
    from kiripix.commands.contract import (
        API_VERSION, HTTP_STATUS, Context, Envelope, ExitCode, Outcome, ProgressEvent, http_status,
    )
    from kiripix.commands.calling import invoke
    from kiripix.commands.jobs import Job, call_line, error_envelope
    from kiripix.commands.launcher import Launcher
    from kiripix.commands.registry import REGISTRY, CliMeta, Command
    from kiripix.commands.session import DEFAULT_WARM_IDLE, INPUT_PART, CancelData, Part, Session, built_web
    from kiripix.commands.watch import ProjectWatch
    from kiripix.core.errors import KiripixError

# name -> the module it comes from, imported on first use
_LAZY = {
    "Finding": "kiripix.checks",
    **dict.fromkeys(("API_VERSION", "HTTP_STATUS", "Context", "Envelope", "ExitCode", "Outcome", "ProgressEvent",
                     "http_status"), "kiripix.commands.contract"),
    "invoke": "kiripix.commands.calling",
    **dict.fromkeys(("Job", "call_line", "error_envelope"), "kiripix.commands.jobs"),
    "Launcher": "kiripix.commands.launcher",
    **dict.fromkeys(("REGISTRY", "CliMeta", "Command"), "kiripix.commands.registry"),
    **dict.fromkeys(("DEFAULT_WARM_IDLE", "INPUT_PART", "CancelData", "Part", "Session", "built_web"),
                    "kiripix.commands.session"),
    "ProjectWatch": "kiripix.commands.watch",
    "KiripixError": "kiripix.core.errors",
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(_LAZY[name]), name)
    globals()[name] = value
    return value


__all__ = [
    "API_VERSION",
    "CancelData",
    "DEFAULT_WARM_IDLE",
    "INDEX",
    "INPUT_PART",
    "Part",
    "Session",
    "built_web",
    "REGISTRY",
    "CliMeta",
    "Command",
    "Context",
    "Envelope",
    "ExitCode",
    "Finding",
    "HTTP_STATUS",
    "Job",
    "KiripixError",
    "Launcher",
    "Outcome",
    "ProgressEvent",
    "ProjectWatch",
    "call_line",
    "error_envelope",
    "invoke",
    "http_status",
]
