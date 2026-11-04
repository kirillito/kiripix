"""The server adapter: `serve` and `ui` start the REST API and the web UI (spec §10.6, §11).

Uses only `kiripix.commands`. The entry point (`kiripix.launch`) passes `LAUNCHERS` to the CLI. All it decides itself is
the socket: where to listen, and whether the port is free.
"""

import json
import socket
import sys
import webbrowser
from pathlib import Path

import uvicorn
from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands import (
    DEFAULT_WARM_IDLE, ExitCode, Finding, KiripixError, Launcher, Session, built_web, error_envelope,
)
from kiripix.server.app import create_app

DEFAULT_PORT = 8765


class ServeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = Field("127.0.0.1", description="The address to listen on. Keep it local: there is no login.")
    port: int = Field(DEFAULT_PORT, ge=0, le=65535, description="The port; 0 picks a free one.")
    web: Path | None = Field(None, description="The built web app to serve. Default: web/dist in the Project, else the one shipped with Kiripix.")
    print_token: bool = Field(False, description="Include the session token in the ready line (for another UI).")
    warm_idle: float = Field(DEFAULT_WARM_IDLE, gt=0, description="Unload a warm Runner after this many seconds unused.")


def _emit(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _report(findings: list[Finding]) -> ExitCode:
    """The one place an error envelope is written."""
    _emit(error_envelope(findings).model_dump_json())
    return ExitCode.ERROR


def _serve(arguments: ServeInput, cwd: Path, open_browser: bool) -> ExitCode:
    try:
        session = Session.open(cwd, arguments.warm_idle)
    except KiripixError as error:
        return _report(error.findings)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform != "win32":  # on Windows SO_REUSEADDR would let a second server share the port
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind((arguments.host, arguments.port))
    except OSError as error:
        listener.close()
        return _report([Finding(code="serve.port_unavailable",
                                message=f"can't listen on {arguments.host}:{arguments.port}: {error}",
                                fix="kiripix serve --port 0")])
    listener.listen(128)
    port = int(listener.getsockname()[1])
    url = f"http://{arguments.host}:{port}"
    web = built_web(session.root, arguments.web)
    _emit(json.dumps(session.ready(url, port, web, with_token=arguments.print_token), separators=(",", ":")))
    if open_browser:
        webbrowser.open(session.browser_url(url))
    config = uvicorn.Config(create_app(session, web), log_level="warning", timeout_graceful_shutdown=2)
    uvicorn.Server(config).run(sockets=[listener])
    return ExitCode.OK


def _run_serve(arguments: ServeInput, cwd: Path) -> ExitCode:
    return _serve(arguments, cwd, open_browser=False)


def _run_ui(arguments: ServeInput, cwd: Path) -> ExitCode:
    return _serve(arguments, cwd, open_browser=True)


LAUNCHERS = (
    Launcher("serve", "Serve the REST API and the web UI for this Project; prints one JSON ready line.",
             ServeInput, _run_serve),
    Launcher("ui", "Serve, and open the browser with the session token (needed for the Owner's Commands).",
             ServeInput, _run_ui),
)

__all__ = ["LAUNCHERS", "ServeInput", "create_app"]
