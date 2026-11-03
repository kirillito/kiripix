"""Launchers: the long-running entry points (`serve`, `ui`) that the CLI starts but that are not Commands.

A Command answers once with the result envelope; a launcher runs until it is stopped. It is declared here so the CLI
can list it and generate its options, while the code behind it lives in the adapter (`kiripix.server`). The entry point
(`kiripix.launch`) hands the adapter's launchers to the CLI, so the CLI never imports the server.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from kiripix.core.errors import ExitCode


@dataclass(frozen=True)
class Launcher:
    name: str
    summary: str
    input: type[BaseModel]
    run: Callable[[Any, Path], ExitCode]  # (the parsed input, the working folder) -> the process exit code
