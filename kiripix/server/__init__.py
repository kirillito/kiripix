"""The server adapter: `serve` and `ui` start the REST API and the web UI (spec §10.6, §11).

Uses only `kiripix.commands`. The entry point (`kiripix.launch`) passes the Launchers to the CLI. All the adapter decides
itself is the socket: where to listen, and whether the port is free.

Importing this package must stay cheap, and import nothing: the CLI lists `serve` and `ui` in `--help` from
`LAUNCHER_LISTING`, and the code behind them (`kiripix.server.launchers`, with pydantic) loads only when one of them
runs, through `load_launchers`. FastAPI and uvicorn load later still (tickets 0067, 0277).
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kiripix.commands import Launcher

# (name, summary) of each Launcher, for the help. `tests/cli/test_command_index.py` checks they match the Launchers.
LAUNCHER_LISTING = (
    ("serve", "Serve the REST API and the web UI for this Project; prints one JSON ready line."),
    ("ui", "Serve, and open the browser with the session token (needed for the Owner's Commands)."),
)


def load_launchers() -> Sequence["Launcher"]:
    from kiripix.server.launchers import LAUNCHERS

    return LAUNCHERS


__all__ = ["LAUNCHER_LISTING", "load_launchers"]
