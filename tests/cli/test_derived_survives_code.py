"""Ticket 0372: a derived answer survives a change to another recipe's source file, and doesn't survive a `version` bump of its
own Stage (spec §5, ADR 0005).

The test Kind `counted` counts how often its Runner call list is worked out in `.kiripix/calls-asked.txt`, which no cache reads.
An open that replays a lift is what costs seconds in a real Project, so what is measured here is whether it replays."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import kiripix.recipes
import pytest
from conftest import Kiripix, make_demo, save_image

ASSET = "counted.a"


def asked(project: Kiripix) -> int:
    path = project.cwd / ".kiripix" / "calls-asked.txt"
    return len(path.read_text(encoding="utf-8").splitlines()) if path.is_file() else 0


def decided(project: Kiripix) -> None:
    project.json("new", "counted", "a")
    save_image(project.cwd / "assets" / "counted" / "a" / "src" / "input.png", (8, 4), (200, 100, 50, 255))
    project.json("decide", ASSET, "shot", "--decision", '{"decision": "mark", "data": {"label": "x"}}')


@contextmanager
def touched(path: Path) -> Iterator[None]:
    """A source file with a new time (a `git pull` does that), put back after."""
    before = path.stat()
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 5_000_000_000))
    try:
        yield
    finally:
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))


def test_the_runner_calls_survive_a_change_to_another_recipes_source_file(project: Kiripix) -> None:
    decided(project)
    project.json("status")
    first = asked(project)
    assert first >= 1
    project.json("status")
    assert asked(project) == first, "a second status reads the kept answer"

    other = Path(kiripix.recipes.__file__).parent / "prop.py"
    with touched(other):
        project.json("status")

    assert asked(project) == first


def test_the_runner_calls_are_worked_out_again_after_a_version_bump_of_their_stage(
        project: Kiripix, monkeypatch: pytest.MonkeyPatch) -> None:
    decided(project)
    project.json("status")
    first = asked(project)
    project.json("status")
    assert asked(project) == first

    monkeypatch.setenv("KIRIPIX_TEST_SHOT_VERSION", "2")
    project.json("status")

    assert asked(project) > first


def test_a_check_s_findings_survive_a_change_to_another_recipes_source_file(project: Kiripix) -> None:
    folder = make_demo(project, "a")
    (folder / "src" / "input.txt").write_text("bad input", encoding="utf-8")
    project.json("run", "demo.a", "copy", expect=2)
    project("check", "demo.a", "--json")
    path = project.cwd / ".kiripix" / "check-calls.txt"
    kept = len(path.read_text(encoding="utf-8").splitlines())

    with touched(Path(kiripix.recipes.__file__).parent / "prop.py"):
        found = project("check", "demo.a", "--json").json["findings"]

    assert len(path.read_text(encoding="utf-8").splitlines()) == kept
    assert found[0]["code"] == "demo.bad_text"
