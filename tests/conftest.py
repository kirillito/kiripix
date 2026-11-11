"""The test harness: drive `kiripix` as a subprocess, the way an agent does, in a temporary Project.

Tests check only what an agent can see: the JSON result, the exit code and the files on disk.
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--update-golden", action="store_true", help="Rewrite the expected golden images.")


def pytest_configure(config: pytest.Config) -> None:
    """`--update-golden` rewrites files in the repository, so it runs serially: refuse it under pytest-xdist."""
    if not config.getoption("--update-golden"):
        return
    workers = getattr(config.option, "numprocesses", None)
    if os.environ.get("PYTEST_XDIST_WORKER") or workers not in (None, 0, "0"):
        raise pytest.UsageError("--update-golden rewrites the expected images and runs without -n: "
                                "`uv run pytest tests/golden --update-golden`")


@dataclass
class Result:
    code: int
    stdout: str
    stderr: str

    @property
    def json(self) -> dict[str, Any]:
        lines = [line for line in self.stdout.splitlines() if line.strip()]
        assert len(lines) == 1, f"expected exactly one JSON line on stdout, got:\n{self.stdout}\n{self.stderr}"
        value: dict[str, Any] = json.loads(lines[0])
        return value

    @property
    def codes(self) -> list[str]:
        return [f["code"] for f in self.json["findings"]]


def kiripix_env(test_recipes: bool = True, owner: bool = False) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("KIRIPIX_TEST_RECIPES", None)
    env.pop("KIRIPIX_TEST_OWNER", None)
    env["PYTHONIOENCODING"] = "utf-8"
    if owner:
        env["KIRIPIX_TEST_OWNER"] = "1"
    if test_recipes:
        env["PYTHONPATH"] = os.pathsep.join([str(FIXTURES), env.get("PYTHONPATH", "")])
        env["KIRIPIX_TEST_RECIPES"] = "kiripix_test_recipes"
    return env


def kiripix_args(*args: str | Path) -> list[str]:
    return [sys.executable, "-m", "kiripix", *[str(a) for a in args]]


class Kiripix:
    """Runs `kiripix` in a folder."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd

    def __call__(self, *args: str | Path, test_recipes: bool = True, owner: bool = False,
                 timeout: float = 60) -> Result:
        """`owner=True` stands in for the Owner at a terminal, through KIRIPIX_TEST_OWNER."""
        done = subprocess.run(
            kiripix_args(*args),
            cwd=self.cwd,
            env=kiripix_env(test_recipes, owner),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
        return Result(done.returncode, done.stdout, done.stderr)

    def json(self, *args: str | Path, expect: int = 0, **kwargs: Any) -> dict[str, Any]:
        """Run with `--json`, check the exit code, and return the result object."""
        result = self(*args, "--json", **kwargs)
        assert result.code == expect, f"exit {result.code}, expected {expect}:\n{result.stdout}\n{result.stderr}"
        return result.json

    def popen(self, *args: str | Path) -> subprocess.Popen[str]:
        return subprocess.Popen(
            kiripix_args(*args, "--json"),
            cwd=self.cwd,
            env=kiripix_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )


@pytest.fixture
def kpx(tmp_path: Path) -> Kiripix:
    """`kiripix` in an empty folder."""
    return Kiripix(tmp_path)


@pytest.fixture
def project(tmp_path: Path) -> Kiripix:
    """`kiripix` in a freshly initialised Project."""
    runner = Kiripix(tmp_path)
    runner.json("init")
    return runner


def make_demo(project: Kiripix, name: str = "a", extra: str = "extra") -> Path:
    """A demo Asset (the test Kind) with its input files. Returns its folder."""
    project.json("new", "demo", name)
    folder = project.cwd / "assets" / "demo" / name
    (folder / "src").mkdir()
    (folder / "src" / "input.txt").write_text("input", encoding="utf-8")
    (folder / "src" / "extra.txt").write_text(extra, encoding="utf-8")
    return folder


def save_image(path: Path, size: tuple[int, int] = (4, 4), colour: tuple[int, int, int, int] = (255, 0, 77, 255)) -> Path:
    """A one-colour PNG."""
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, colour).save(path)
    return path


def make_sketch(project: Kiripix, name: str = "a") -> Path:
    """A sketch Asset (the test Kind with image Stages) with a 4x4 input image. Returns its folder."""
    project.json("new", "sketch", name)
    folder = project.cwd / "assets" / "sketch" / name
    save_image(folder / "src" / "input.png")
    return folder


def stage_status(project: Kiripix, asset: str) -> dict[str, str]:
    data = project.json("status")["data"]
    row = next(a for a in data["assets"] if a["asset"] == asset)
    return {s["stage"]: s["status"] for s in row["stages"]}


MARK = '{"decision": "mark", "data": {"label": "door"}}'  # a valid `mark` Decision of the demo Kind


def sketched(project: Kiripix) -> None:
    """A sketch Asset that has run once, and a painted fix.png to override it with."""
    make_sketch(project)
    project.json("run", "sketch.a")
    save_image(project.cwd / "fix.png")


def in_review(project: Kiripix) -> None:
    """sketch.a's draw Stage waiting for the Owner's accept."""
    sketched(project)
    project.json("override", "sketch.a", "draw", "fix.png")
    project.json("run", "sketch.a")
    save_image(project.cwd / "assets" / "sketch" / "a" / "src" / "input.png", colour=(41, 173, 255, 255))
    project.json("run", "sketch.a", expect=3)


def find_blender() -> tuple[str | None, str]:
    """The Blender executable (`KIRIPIX_BLENDER`, else PATH) and, when there's none to use, the reason to skip."""
    import re
    import shutil

    found = os.environ.get("KIRIPIX_BLENDER") or shutil.which("blender")
    if not found:
        return None, "Blender 5.2 not found: set KIRIPIX_BLENDER or put blender on PATH"
    try:
        out = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"Blender at {found} could not run: {error}"
    match = re.search(r"Blender (\d+)\.(\d+)", out)
    if not match or (match.group(1), match.group(2)) != ("5", "2"):
        return None, f"Blender at {found} is {match.group(0) if match else 'of unknown version'}, not 5.2.x"
    return found, ""


def find_godot() -> tuple[str | None, str]:
    """The Godot 4.7 executable (`KIRIPIX_GODOT`, else PATH) and, when there's none to use, the reason to skip."""
    import re
    import shutil

    found = os.environ.get("KIRIPIX_GODOT") or shutil.which("godot") or shutil.which("godot4")
    if not found:
        return None, "Godot 4.7 not found: set KIRIPIX_GODOT or put godot on PATH"
    try:
        out = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"Godot at {found} could not run: {error}"
    if not re.match(r"4\.7\.", out):
        return None, f"Godot at {found} is {out.strip() or 'of unknown version'}, not 4.7.x"
    return found, ""


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """A test marked `blender` is skipped, with the reason, unless Blender 5.2.x is available; one marked `godot`, unless
    Godot 4.7.x is."""
    marked = [item for item in items if "blender" in item.keywords]
    if marked:
        found, reason = find_blender()
        if found:
            os.environ["KIRIPIX_BLENDER"] = found
        else:
            skip = pytest.mark.skip(reason=reason)
            for item in marked:
                item.add_marker(skip)
    marked = [item for item in items if "godot" in item.keywords]
    if marked:
        found, reason = find_godot()
        if found:
            os.environ["KIRIPIX_GODOT"] = found
        else:
            skip = pytest.mark.skip(reason=reason)
            for item in marked:
                item.add_marker(skip)
