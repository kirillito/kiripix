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


def kiripix_env(test_recipes: bool = True) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("KIRIPIX_TEST_RECIPES", None)
    env["PYTHONIOENCODING"] = "utf-8"
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

    def __call__(self, *args: str | Path, test_recipes: bool = True, timeout: float = 60) -> Result:
        done = subprocess.run(
            kiripix_args(*args),
            cwd=self.cwd,
            env=kiripix_env(test_recipes),
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


def stage_status(project: Kiripix, asset: str) -> dict[str, str]:
    data = project.json("status")["data"]
    row = next(a for a in data["assets"] if a["asset"] == asset)
    return {s["stage"]: s["status"] for s in row["stages"]}
