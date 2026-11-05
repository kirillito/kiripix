"""`show`: one Asset as a UI needs it. A Probe: it answers from the files and writes nothing a status would see."""

import json
from pathlib import Path

from conftest import Kiripix, stage_status, make_demo
from test_masks import ROOM, built_room, decide


def stage(data: dict[str, object], name: str) -> dict[str, object]:
    stages = data["stages"]
    assert isinstance(stages, list)
    found: dict[str, object] = next(s for s in stages if s["stage"] == name)
    return found


def test_a_new_room_shows_its_view_its_stages_and_no_variants(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")

    data = project.json("show", ROOM)["data"]

    assert (data["asset"], data["kind"], data["params"]) == (ROOM, "room", {"view": "top"})
    assert data["variants"] == [] and data["picked"] is None
    assert data["resolution"] == [640, 360]
    assert [s["stage"] for s in data["stages"]][:3] == ["brief", "source", "fit"]
    assert stage(data, "source")["status"] == "needs-input" and stage(data, "source")["reason"] == "no Source picked"
    assert stage(data, "fit")["image"] is None and stage(data, "fit")["input_image"] is None


def test_parameters_are_the_current_values_defaults_and_all(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    project.json("set", ROOM, "fit", "mode=downscale", "scale=2")

    assert stage(project.json("show", ROOM)["data"], "fit")["params"] == {
        "mode": "downscale", "scale": 2, "offset_x": 0, "offset_y": 0}


def test_variants_and_the_pick_with_files_the_file_route_serves(project: Kiripix) -> None:
    folder = built_room(project)

    data = project.json("show", ROOM)["data"]

    [variant] = data["variants"]
    assert variant["file"] == f"assets/room/alley/src/{variant['name']}.png"
    assert (project.cwd / variant["file"]).is_file() and (folder / "src").is_dir()
    assert data["picked"] == variant["name"]
    assert [d["name"] for d in stage(data, "source")["decisions"]] == ["pick"]  # type: ignore[attr-defined]


def test_a_built_stage_has_its_image_and_the_image_it_was_made_from(project: Kiripix) -> None:
    built_room(project)

    data = project.json("show", ROOM)["data"]

    assert stage(data, "palette")["image"] == "assets/room/alley/work/palette/palette.png"
    assert stage(data, "palette")["input_image"] == "assets/room/alley/work/layers/plate.png"
    assert stage(data, "fit")["input_image"] == "assets/room/alley/work/source/source.png"
    assert stage(data, "masks")["image"] is None  # a Mask isn't the Stage's image
    assert stage(data, "masks")["input_image"] == "assets/room/alley/work/layers/plate.png"
    assert stage(data, "brief")["input_image"] is None


def test_a_built_stage_lists_its_output_files_and_the_body_comes_from_the_project(project: Kiripix) -> None:
    built_room(project)

    data = project.json("show", ROOM)["data"]

    assert stage(data, "masks")["outputs"] == ["assets/room/alley/work/masks/floods.json",
                                               "assets/room/alley/work/masks/pit.png",
                                               "assets/room/alley/work/masks/solid.png"]
    assert stage(data, "export")["outputs"] == []
    assert data["body"] == {"size": [12, 8], "dash": 0}


def test_markers_are_the_current_ones_with_a_move_in_the_first_place_before_any_build(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    for marker, x in (("a", 1), ("b", 2), ("a", 3)):
        data = {"id": marker, "type": "spawn", "x": x, "y": 0}
        project.json("decide", ROOM, "place", "--decision", json.dumps({"decision": "marker", "data": data}))

    shown = project.json("show", ROOM)["data"]

    assert stage(shown, "place")["markers"] == [{"id": "a", "type": "spawn", "x": 3, "y": 0},
                                                {"id": "b", "type": "spawn", "x": 2, "y": 0}]
    assert stage(shown, "masks")["markers"] == []


def test_decisions_are_the_current_ones_after_an_undo(project: Kiripix) -> None:
    built_room(project)
    decide(project, "flood", {"x": 0, "y": 0, "mask": "solid"})
    decide(project, "flood", {"x": 30, "y": 16, "mask": "solid"})
    project.json("undo", ROOM, "masks")

    [decision] = stage(project.json("show", ROOM)["data"], "masks")["decisions"]  # type: ignore[misc]

    assert decision["name"] == "flood" and decision["data"] == {"x": 0, "y": 0, "mask": "solid"}


def test_show_changes_nothing_and_an_unknown_asset_is_refused(project: Kiripix) -> None:
    built_room(project)
    before = stage_status(project, ROOM)
    journal = Path(project.cwd / "assets" / "room" / "alley" / "decisions" / "source.jsonl").read_bytes()

    project.json("show", ROOM)

    assert stage_status(project, ROOM) == before
    assert Path(project.cwd / "assets" / "room" / "alley" / "decisions" / "source.jsonl").read_bytes() == journal
    assert project.json("show", "room.nothing", expect=1)["findings"][0]["code"] == "asset.not_found"


def test_a_kind_without_a_pick_shows_no_variants(project: Kiripix) -> None:
    make_demo(project)

    data = project.json("show", "demo.a")["data"]

    assert data["variants"] == [] and data["picked"] is None
    assert json.dumps(data)  # plain JSON all the way down
