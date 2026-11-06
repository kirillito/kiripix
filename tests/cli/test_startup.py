"""A Command doesn't import the server (ticket 0067): `serve` and `ui` load FastAPI, nothing else does."""

import subprocess
import sys

from conftest import Kiripix, kiripix_env

# Runs the CLI in-process, then reports which heavy modules it loaded, on stderr.
WRAPPER = """
import sys
from kiripix.launch import main
try:
    main()
except SystemExit as done:
    code = done.code
loaded = sorted(m for m in sys.modules if m.split(".")[0] in ("fastapi", "uvicorn", "starlette") or m.startswith("kiripix.server."))
print("LOADED " + ",".join(loaded), file=sys.stderr)
sys.exit(code)
"""


def run_wrapped(kpx: Kiripix, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", WRAPPER, *args], cwd=kpx.cwd, env=kiripix_env(), text=True,
                          encoding="utf-8", capture_output=True, stdin=subprocess.DEVNULL, timeout=60)


def loaded(done: subprocess.CompletedProcess[str]) -> str:
    return [line for line in done.stderr.splitlines() if line.startswith("LOADED ")][-1][len("LOADED "):]


def test_a_command_does_not_load_the_server(kpx: Kiripix) -> None:
    kpx.json("init")

    done = run_wrapped(kpx, "describe", "project", "--json")

    assert '"ok":true' in done.stdout.replace(" ", ""), done.stdout
    assert loaded(done) == ""


def test_help_lists_serve_and_ui_without_loading_the_server(kpx: Kiripix) -> None:
    done = run_wrapped(kpx, "--help")

    assert done.returncode == 0
    assert "serve" in done.stdout and "ui" in done.stdout
    assert loaded(done) == ""
