"""The Command registry: every operation's typed input, output and metadata (ADR 0006).

Uses `core` and `recipes`. The adapters (`cli`, later `server`) use only this package.
"""

from kiripix.commands import project, decisions, sources, checks, meta, image_ops  # noqa: F401, I001 - import order is the help order
from kiripix.checks import Finding
from kiripix.commands.contract import API_VERSION, Context, Envelope, ExitCode, Outcome, ProgressEvent
from kiripix.commands.invoke import invoke
from kiripix.commands.registry import REGISTRY, CliMeta, Command

__all__ = [
    "API_VERSION",
    "REGISTRY",
    "CliMeta",
    "Command",
    "Context",
    "Envelope",
    "ExitCode",
    "Finding",
    "Outcome",
    "ProgressEvent",
    "invoke",
]
