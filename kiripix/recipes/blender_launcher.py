"""The one place that runs Blender (spec §12, ticket 0101): `blender -b -P kiripix/blender/<script>.py -- <args.json>
<result.json>`, as a separate process, with the arguments and the result as JSON files.

Blender is found through `[character] blender` or `PATH`, and only 5.2 is accepted (docs/versions.md): another version is a
finding, never a guess. The script reports progress by printing `PROGRESS <done> <total> <message>` lines. A cancel kills the
process; the Stage's output folder is swapped in whole, so nothing is left behind.

A test replaces it, as it replaces a Runner: `set_launcher` in `KIRIPIX_TEST_RECIPES`. A Stage calls `launch` and never
runs a process itself.
"""

import json
import queue
import re
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from kiripix.recipes.base import StageFailure, StageRun, computed_setting

BLENDER_VERSION = (5, 2)
VERSION_SETTING = "blender.version"  # a computed Stage input (ADR 0010): the major and minor version Blender runs at
SETTING = "character.blender"  # where Blender is: add it to `StageInputs.given`, never `settings` (moving it stales nothing)

# Read at call time, not import time, so a test that changes BLENDER_VERSION changes every hash that holds it.
computed_setting(VERSION_SETTING, lambda: ".".join(str(part) for part in BLENDER_VERSION))
SCRIPTS = Path(__file__).resolve().parent.parent / "blender"
PROGRESS = "PROGRESS "
_VERSION_TIMEOUT = 60  # seconds, for `blender --version`
_POLL = 0.1  # seconds between looks at the cancel token while Blender runs

_INSTALL = ("Install Blender 5.2 LTS from https://www.blender.org/download/lts/, then set `[character] blender` in "
            "kiripix.toml to its executable, or put it on PATH.")


class Launcher(Protocol):
    """What a Stage needs of Blender. `executable` is the `[character] blender` setting, or None."""

    def run(self, script: str, args: dict[str, Any], *, executable: str | None, progress: Callable[[int, int, str], None],
            check_cancel: Callable[[], None]) -> dict[str, Any]:
        """Run `kiripix/blender/<script>.py` with `args`; return the result JSON the script wrote."""
        ...


def find_blender(executable: str | None) -> str:
    """The Blender executable to run: the setting, else PATH. Refuses a missing one and a version other than 5.2."""
    found = executable or shutil.which("blender")
    if not found:
        raise StageFailure(
            "Blender 5.2 was not found: `blender` is not set under [character] in kiripix.toml and is not on PATH",
            code="blender.not_found", owner_action=_INSTALL)
    if executable and not Path(executable).is_file() and shutil.which(executable) is None:
        raise StageFailure(
            f"Blender 5.2 was not found at {executable}, the [character] blender setting in kiripix.toml",
            code="blender.not_found", owner_action=_INSTALL)
    try:
        stamp = (found, BLENDER_VERSION, Path(shutil.which(found) or found).stat().st_mtime_ns)
    except OSError:
        stamp = None
    if stamp is not None and stamp in _checked:  # `--version` starts Blender too: ask once per executable and process
        return found
    try:
        done = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=_VERSION_TIMEOUT,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as error:
        raise StageFailure(f"{found} could not run: {error}; Kiripix needs Blender 5.2",
                           code="blender.not_found", owner_action=_INSTALL) from None
    match = re.search(r"Blender (\d+)\.(\d+)", done.stdout)
    if match is None or (int(match.group(1)), int(match.group(2))) != BLENDER_VERSION:
        said = match.group(0) if match else "no Blender version"
        raise StageFailure(
            f"{found} is not Blender 5.2 (it printed {said}); Kiripix renders only on 5.2 LTS (docs/versions.md)",
            code="blender.wrong_version",
            owner_action="Point `[character] blender` in kiripix.toml to a Blender 5.2 executable. " + _INSTALL)
    if stamp is not None:
        _checked.add(stamp)
    return found


_checked: set[tuple[str, tuple[int, int], int]] = set()  # executables already found to be Blender 5.2, by file time


class ProcessLauncher:
    """The real one: a Blender process per call."""

    def run(self, script: str, args: dict[str, Any], *, executable: str | None, progress: Callable[[int, int, str], None],
            check_cancel: Callable[[], None]) -> dict[str, Any]:
        blender = find_blender(executable)
        path = SCRIPTS / f"{script}.py"
        if not path.is_file():
            raise StageFailure(f"there is no Blender script {script}")
        with tempfile.TemporaryDirectory(prefix="kiripix-blender-") as temporary:
            arguments, result = Path(temporary, "args.json"), Path(temporary, "result.json")
            arguments.write_text(json.dumps(args), encoding="utf-8")
            command = [blender, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(path),
                       "--", str(arguments), str(result)]
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            lines: queue.Queue[str | None] = queue.Queue()
            threading.Thread(target=_read_lines, args=(process, lines), daemon=True).start()
            tail: list[str] = []
            try:
                while True:
                    check_cancel()
                    try:
                        line = lines.get(timeout=_POLL)
                    except queue.Empty:
                        continue
                    if line is None:
                        break
                    if line.startswith(PROGRESS):
                        _report(line[len(PROGRESS):], progress)
                    elif line.strip():
                        tail = [*tail[-19:], line.rstrip()]
                code = process.wait()
            finally:
                if process.poll() is None:  # a cancel, or an error in this loop: Blender goes with it
                    process.kill()
                    process.wait()
            if code != 0 or not result.is_file():
                raise StageFailure(f"Blender failed (exit {code}) running {script}: " + " | ".join(tail[-5:]))
            document: dict[str, Any] = json.loads(result.read_text(encoding="utf-8"))
        if "error" in document:
            raise StageFailure(str(document["error"]))
        return document


def _read_lines(process: "subprocess.Popen[str]", lines: "queue.Queue[str | None]") -> None:
    assert process.stdout is not None
    for line in process.stdout:
        lines.put(line)
    lines.put(None)


def _report(text: str, progress: Callable[[int, int, str], None]) -> None:
    parts = text.strip().split(" ", 2)
    try:
        progress(int(parts[0]), int(parts[1]), parts[2] if len(parts) > 2 else "")
    except (ValueError, IndexError):
        pass  # not a progress line after all


_launcher: Launcher = ProcessLauncher()


def set_launcher(launcher: Launcher) -> None:
    """Replace how Blender runs. For the test harness only (`KIRIPIX_TEST_RECIPES`)."""
    global _launcher
    _launcher = launcher


def launch(run: StageRun, script: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run a Blender script for a Stage, with its progress and cancel token. Raises StageFailure."""
    executable = run.settings.get(SETTING)
    return launch_for(script, args, executable=executable if isinstance(executable, str) else None,
                      progress=run.progress, check_cancel=run.check_cancel)


def launch_for(script: str, args: dict[str, Any], *, executable: str | None, progress: Callable[[int, int, str], None],
               check_cancel: Callable[[], None]) -> dict[str, Any]:
    """Run a Blender script outside a Stage (a Probe, ticket 0123). Raises StageFailure."""
    return _launcher.run(script, args, executable=executable, progress=progress, check_cancel=check_cancel)
