"""The `reach` Probe (ticket 0078, spec §10.1): what the `reach` Stage reports, from the Masks as built (one awaiting review
too) and the `place` journal's Markers, with nothing recorded and no status changed."""

from typing import Any

from conftest import Kiripix, stage_status
from test_masks import ROOM, decide
from test_place import place, walled_room
from test_reachability import EXIT, LEFT, RIGHT, report, split_room
from test_runner_calls import accept, rerun

PROBE = ["probe", "reach", ROOM]
OPEN_WALL = {"x0": 28, "y0": 0, "x1": 36, "y1": 31, "mask": "solid", "positive": False}  # the fake Runner's Mask is the box


def answer(project: Kiripix, expect: int = 0) -> dict[str, Any]:
    result: dict[str, Any] = project.json(*PROBE, expect=expect)["data"]["result"]
    return result


def test_on_a_done_room_the_answer_is_the_reach_report(project: Kiripix) -> None:
    folder = split_room(project)
    place(project, "spawn.main", "spawn", LEFT)
    project.json("run", ROOM, expect=3)  # a warning for the island, and no target for export
    assert stage_status(project, ROOM)["reach"] == "done"

    result = answer(project)

    assert result["report"] == report(folder) and report(folder)["islands"] != []
    assert result["awaiting_review"] is False and result["masks_status"] == "done" and result["status"] == "done"


def test_a_pending_box_that_opens_a_way_shows_the_marker_reached_while_masks_awaits_review(project: Kiripix) -> None:
    folder = split_room(project)
    place(project, "spawn.main", "spawn", LEFT)
    place(project, "exit.east", "exit", RIGHT, **EXIT)
    project.json("run", ROOM, expect=2)
    parted = report(folder)
    assert [m["reached"] for m in parted["markers"]] == [True, False]
    assert [m["reached"] for m in answer(project)["report"]["markers"]] == [True, False]

    decide(project, "box", OPEN_WALL)
    rerun(project)
    assert stage_status(project, ROOM)["masks"] == "needs-review"

    result = answer(project)

    assert [m["reached"] for m in result["report"]["markers"]] == [True, True]
    assert result["awaiting_review"] is True and result["masks_status"] == "needs-review"
    assert result["status"] != "done"
    assert stage_status(project, ROOM)["masks"] == "needs-review"
    assert report(folder) == parted, "the Stage's own report is untouched; reach stays stopped"
    project.json("run", ROOM, expect=3)  # still stops at masks, awaiting the owner
    assert stage_status(project, ROOM)["reach"] != "done"

    accept(project)
    project.json("run", ROOM, expect=3)
    assert answer(project)["report"] == report(folder) and answer(project)["awaiting_review"] is False


def test_it_uses_the_markers_the_place_journal_holds_now(project: Kiripix) -> None:
    folder = split_room(project)
    place(project, "spawn.main", "spawn", LEFT)
    project.json("run", ROOM, expect=3)
    before = report(folder)

    place(project, "exit.east", "exit", RIGHT, **EXIT)  # place and reach are stale now
    assert stage_status(project, ROOM)["reach"] == "stale"

    result = answer(project)

    assert [m["id"] for m in result["report"]["markers"]] == ["spawn.main", "exit.east"]
    assert [m["reached"] for m in result["report"]["markers"]] == [True, False]
    assert report(folder) == before and result["status"] == "stale"


def test_nothing_is_written_and_no_lock_is_taken(project: Kiripix) -> None:
    folder = split_room(project)
    place(project, "spawn.main", "spawn", LEFT)
    project.json("run", ROOM, expect=3)
    decide(project, "box", OPEN_WALL)
    rerun(project)
    status = stage_status(project, ROOM)
    before = {p: p.read_bytes() for p in folder.rglob("*") if p.is_file() and ".kiripix" not in p.parts}
    locks = project.cwd / ".kiripix" / "locks"

    answer(project)

    assert stage_status(project, ROOM) == status
    assert {p: p.read_bytes() for p in folder.rglob("*") if p.is_file() and ".kiripix" not in p.parts} == before
    assert not locks.exists() or not any(locks.iterdir())


def test_with_no_spawn_or_exit_placed_the_finding_says_so(project: Kiripix) -> None:
    walled_room(project)
    place(project, "lamp", "light", colour="#FFFFFF", radius=8, energy=1)

    [finding] = project.json(*PROBE, expect=1)["findings"]

    assert finding["code"] == "probe.no_markers" and "Spawn or Exit" in finding["message"]
    assert (finding["fix"] is None) != (finding["owner_action"] is None)


def test_without_built_masks_the_finding_names_the_run(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")

    [finding] = project.json(*PROBE, expect=1)["findings"]

    assert finding["code"] == "probe.not_ready" and finding["fix"] == f"kiripix run {ROOM} masks"


def test_a_side_view_room_and_a_prop_are_refused_and_arguments_too(project: Kiripix) -> None:
    walled_room(project)
    place(project, "spawn.main", "spawn")

    assert project.json(*PROBE, "x", expect=1)["findings"][0]["code"] == "input.invalid"
    project.json("new", "prop", "bench")
    assert project.json("probe", "reach", "prop.bench", expect=1)["findings"][0]["code"] == "probe.not_supported"
    project.json("new", "room", "bridge", "--view", "side")
    [finding] = project.json("probe", "reach", "room.bridge", expect=1)["findings"]
    assert finding["code"] in ("probe.not_ready", "probe.not_supported") and "not planned yet" in finding["message"]
