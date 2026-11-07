"""The Command registry: every operation's typed input, output and metadata (ADR 0006).

Uses `core` and `recipes`. The adapters (`cli`, later `server`) use only this package.
"""

from kiripix.commands import project, show, decisions, sources, checks, export, meta, image_ops, palette, probes, runners, manifest  # noqa: F401, I001 - import order is the help order
from kiripix.checks import Finding
from kiripix.commands.contract import (
    API_VERSION, HTTP_STATUS, Context, Envelope, ExitCode, Outcome, ProgressEvent, http_status,
)
from kiripix.commands.invoke import invoke
from kiripix.commands.jobs import Job, call_line, error_envelope
from kiripix.commands.launcher import Launcher
from kiripix.commands.registry import REGISTRY, CliMeta, Command
from kiripix.commands.session import DEFAULT_WARM_IDLE, INPUT_PART, CancelData, Part, Session, built_web
from kiripix.commands.watch import ProjectWatch
from kiripix.core.errors import KiripixError

__all__ = [
    "API_VERSION",
    "CancelData",
    "DEFAULT_WARM_IDLE",
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
