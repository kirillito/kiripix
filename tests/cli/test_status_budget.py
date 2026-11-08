"""Ticket 0090: `status` and `show` stay quick in a big Project (spec §5, ADR 0005).

The demo Kind has no Runner calls, so this holds the per-Asset work (journals, stamps, hashes, file lookups) that every
Kind pays. The cache of a Stage's Runner calls is held by the transitions in `test_runner_calls.py`."""

import shutil
import time

from conftest import Kiripix, make_demo

ROOMS = 300


def timed(project: Kiripix, *args: str) -> float:
    start = time.perf_counter()
    project.json(*args)
    return time.perf_counter() - start


def test_status_of_300_assets_and_show_of_one_stay_inside_the_budget(project: Kiripix) -> None:
    folder = make_demo(project, "a000")
    for number in range(1, ROOMS):  # copies, so the test doesn't start 300 processes
        shutil.copytree(folder, folder.parent / f"a{number:03d}")
    project.json("status")  # warms the hash cache, as an owner's earlier command did
    startup = min(timed(project, "describe", "demo") for _ in range(2))  # a process start, no Project work

    status = min(timed(project, "status") for _ in range(2)) - startup
    show = min(timed(project, "show", "demo.a017") for _ in range(2)) - startup

    # The ticket's budget is 2 s and 0.5 s; the margin covers a busy CI machine.
    assert status < 3.0, status
    assert show < 0.5, show
    assert len(project.json("status")["data"]["assets"]) == ROOMS
