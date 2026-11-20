"""`reach` per Look (ticket 0315, ADR 0013): a flood over each Look's own walkable, and its report."""

import json
from pathlib import Path
from typing import Any

from conftest import Kiripix, stage_status
from test_layers_stage import ROOM
from test_look_markers import LOOK, decide_place, marker, mask, run_place, walled_room_with_a_look
from test_looks_build import decide as decide_look

SPAWN = {"id": "spawn.main", "type": "spawn", "x": 10, "y": 16}


def spawn(project: Kiripix, **fields: Any) -> None:
    decide_place(project, "marker", {**SPAWN, **fields})


def run_reach(project: Kiripix) -> dict[str, Any]:
    run_place(project)
    result = project("run", ROOM, "reach", "--json")
    assert result.code in (0, 2), result.json
    return dict(result.json)


def reach_findings(project: Kiripix) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = project("check", ROOM, "--json").json["findings"]
    return [f for f in found if f["code"].startswith(("reach.", "area."))]


def report_of(folder: Path) -> dict[str, Any]:
    built: dict[str, Any] = json.loads((folder / "work" / "reach" / "report.json").read_text("utf-8"))
    return built


def test_a_yard_behind_a_wall_that_a_look_erases_is_info_under_the_look_and_exits_zero(project: Kiripix) -> None:
    walled_room_with_a_look(project)
    spawn(project)
    run_place(project)
    project.json("run", ROOM, "reach")  # exit 0

    found = reach_findings(project)

    assert "reach.unreachable_island" not in [f["code"] for f in found]
    [under] = [f for f in found if f["code"] == "reach.island_under_look"]
    assert under["severity"] == "info" and LOOK in under["message"]
    assert (under["fix"] is None) != (under["owner_action"] is None)


def test_report_json_is_schema_1_with_a_look_entry_and_its_reachable_mask(project: Kiripix) -> None:
    folder = walled_room_with_a_look(project)
    spawn(project)
    run_reach(project)

    report = report_of(folder)

    assert report["schema_version"] == 1
    assert list(report["looks"]) == [LOOK]
    own = report["looks"][LOOK]
    assert set(own) == {"markers", "main", "islands", "areas"}
    assert own["main"] == ["spawn.main"] and own["islands"] == []
    [island] = report["islands"]
    assert island["looks"] == [LOOK]
    reachable = mask(folder / "work" / "reach" / "looks" / LOOK / "reachable.png")
    room = mask(folder / "work" / "reach" / "reachable.png")
    assert reachable.shape == room.shape and reachable[:, 20:28].any() and not room[:, 20:28].any()
    assert (reachable >= room).all()


def test_a_look_without_its_own_solid_has_no_entry(project: Kiripix) -> None:
    folder = walled_room_with_a_look(project, opening=False)
    spawn(project)
    run_reach(project)

    assert report_of(folder)["looks"] == {}
    assert not (folder / "work" / "reach" / "looks").exists()
    assert [f["code"] for f in reach_findings(project)].count("reach.unreachable_island") == 1


def test_a_look_that_adds_ground_it_does_not_reach_warns_look_island(project: Kiripix) -> None:
    folder = walled_room_with_a_look(project, opening=False)
    # a block of solid with a pocket the Look cuts out of its middle: ground only the Look makes walkable
    block = [[32, 0], [47, 0], [47, 31], [32, 31]]  # whole cells: the project snaps solid to its tile
    project.json("decide", ROOM, "masks", "--decision",
                 json.dumps({"decision": "polygon", "data": {"mask": "solid", "erase": False, "points": block}}))
    decide_look(project, "solid", {"look": LOOK, "erase": True, "points": [[32, 0], [47, 0], [47, 15], [32, 15]]})
    spawn(project)
    run_reach(project)

    [island] = report_of(folder)["looks"][LOOK]["islands"]
    assert island["added"] > 0 and island["added"] == island["spots"]
    found = [f for f in reach_findings(project) if f["code"] == "reach.look_island"]
    [finding] = found
    assert finding["severity"] == "warning" and LOOK in finding["message"]


def test_a_look_that_walls_off_a_spawn_is_info_look_cuts_off(project: Kiripix) -> None:
    walled_room_with_a_look(project, opening=False)
    # the Look fills the top-left cell with solid, which has the second Spawn in it
    decide_look(project, "solid", {"look": LOOK, "erase": False, "points": [[0, 0], [15, 0], [15, 15], [0, 15]]})
    decide_place(project, "marker", {**SPAWN, "y": 24})
    decide_place(project, "marker", {"id": "spawn.corner", "type": "spawn", "x": 8, "y": 6})
    run_reach(project)

    found = [f for f in reach_findings(project) if f["code"] == "reach.look_cuts_off"]

    assert [f["message"].split("'")[1] for f in found] == ["spawn.corner"]
    assert all(f["severity"] == "info" and LOOK in f["message"] for f in found)
    assert all((f["fix"] is None) != (f["owner_action"] is None) for f in found)


def test_an_older_report_is_refused_naming_the_rebuild_and_a_look_edit_makes_reach_stale(project: Kiripix) -> None:
    folder = walled_room_with_a_look(project)
    spawn(project)
    run_reach(project)
    assert stage_status(project, ROOM)["reach"] == "done"

    path = folder / "work" / "reach" / "report.json"
    old = json.loads(path.read_text("utf-8"))
    del old["schema_version"]
    path.write_text(json.dumps(old), "utf-8")
    refused = project.json("check", ROOM, expect=2)  # a finding naming the rebuild, not internal.error
    assert any(f["code"] == "stage.output_unreadable" and f["fix"].startswith(f"kiripix run {ROOM} reach")
               for f in refused["findings"])
    assert any(f"kiripix run {ROOM} reach" in json.dumps(f) for f in refused["findings"])

    project.json("run", ROOM, "reach", "--force")
    decide_look(project, "solid", {"look": LOOK, "points": [[2, 2], [4, 2], [4, 4], [2, 4]]})
    project.json("run", ROOM, "looks")
    assert stage_status(project, ROOM)["reach"] == "stale"


def test_a_walkable_area_a_look_reaches_is_info(project: Kiripix) -> None:
    walled_room_with_a_look(project)
    spawn(project)
    marker(project, "yard", "area", x=34, y=10, x2=44, y2=22, walkable=True)
    run_reach(project)

    [found] = [f for f in reach_findings(project) if f["code"] == "area.not_reached"]

    assert found["severity"] == "info" and LOOK in found["message"]

