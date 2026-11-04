"""The wheel carries the built UI (ticket 0025): `kiripix ui` from an installed wheel, not the checkout, serves it.

It needs `web/dist`, so it runs where the UI was built (`npm run build` in web/) and is skipped elsewhere.
"""

import http.client
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import psutil
import pytest

REPOSITORY = Path(__file__).parents[2]
BUILT = REPOSITORY / "web" / "dist"


def _run(*args: str | Path, cwd: Path = REPOSITORY, env: dict[str, str] | None = None) -> str:
    done = subprocess.run([str(a) for a in args], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                          timeout=300)
    assert done.returncode == 0, f"{args}:\n{done.stdout}\n{done.stderr}"
    return done.stdout


def _no_browser(folder: Path) -> Path:
    """A program that accepts a URL and does nothing, so `ui` opens no real browser."""
    if sys.platform == "win32":
        script = folder / "no_browser.cmd"
        script.write_text("@exit /b 0\n", encoding="ascii")
    else:
        script = folder / "no_browser.sh"
        script.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


@pytest.mark.skipif(not (BUILT / "index.html").is_file(), reason="web/dist isn't built")
def test_ui_from_an_installed_wheel_serves_the_built_app(tmp_path: Path) -> None:
    out = tmp_path / "wheel"
    _run("uv", "build", "--wheel", "--out-dir", out)
    [wheel] = list(out.glob("*.whl"))
    venv = tmp_path / "venv"
    _run("uv", "venv", "--python", "3.12", venv)
    bin_dir = venv / ("Scripts" if sys.platform == "win32" else "bin")
    python = bin_dir / ("python.exe" if sys.platform == "win32" else "python")
    _run("uv", "pip", "install", "--python", python, wheel)
    outside = tmp_path / "game"
    outside.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("KIRIPIX_", "VIRTUAL_ENV", "PYTHONPATH"))}
    env["BROWSER"] = str(_no_browser(tmp_path))
    env["PYTHONIOENCODING"] = "utf-8"

    installed = _run(python, "-c", "import kiripix; print(kiripix.__file__)", cwd=outside, env=env).strip()
    assert REPOSITORY not in Path(installed).parents

    kiripix = bin_dir / ("kiripix.exe" if sys.platform == "win32" else "kiripix")
    _run(kiripix, "init", cwd=outside, env=env)
    server = subprocess.Popen([str(kiripix), "ui", "--port", "0"], cwd=outside, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        assert server.stdout is not None
        ready = json.loads(server.stdout.readline())
        assert ready["web"] is True

        connection = http.client.HTTPConnection("127.0.0.1", int(ready["port"]), timeout=30)
        connection.request("GET", "/")
        response = connection.getresponse()
        page = response.read().decode("utf-8")
        connection.close()
    finally:
        for child in psutil.Process(server.pid).children(recursive=True):
            child.kill()
        server.kill()
        server.wait(timeout=30)
        if server.stdout is not None:
            server.stdout.close()
        if server.stderr is not None:
            server.stderr.close()

    assert response.status == 200
    assert '<div id="root">' in page
    assert page == (BUILT / "index.html").read_text(encoding="utf-8")
