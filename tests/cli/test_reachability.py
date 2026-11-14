"""The room's reach Stage (spec §6.1): the Body's flood from each Spawn and Exit, the Reachable Mask and a report."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_masks import ROOM, built_room, decide
from test_place import findings, place, walled_room

# With the left wall flooded into `solid`, walkable is x 22 to 42, y 4 to 28 (see test_place). A second wall across the
# room at x 30 to 34 blocks the spots x 25 to 40, which leaves x 22 to 24 on its left and x 41 to 42 on its right.
LEFT = (23, 16)
RIGHT = (41, 16)
WALL = [[32, 0], [32, 31]]
EXIT = {"target_room": "room.street", "target_exit": "exit.west"}


def split_room(project: Kiripix, mask: str = "solid") -> Path:
    folder = walled_room(project)
    decide(project, "brush", {"mask": mask, "erase": False, "radius": 2, "points": WALL})
    return folder


def read_reachable(folder: Path) -> np.ndarray:
    with Image.open(folder / "work" / "reach" / "reachable.png") as image:
        assert image.mode == "1"
        return np.asarray(image, dtype=np.bool_)


def report(folder: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((folder / "work" / "reach" / "report.json").read_text("utf-8"))
    return value


def set_body(project: Kiripix, line: str) -> None:
    settings = project.cwd / "kiripix.toml"
    text = settings.read_text("utf-8")
    assert "dash = 0" in text
    settings.write_text(text.replace("dash = 0", line), "utf-8")


# no Spawn or Exit to flood from


def test_a_room_with_no_spawn_or_exit_needs_the_owner_to_place_one(project: Kiripix) -> None:
    walled_room(project)
    place(project, "lamp", "light", colour="#FFFFFF", radius=8, energy=1)  # a Marker, but nothing to flood from

    result = project.json("run", ROOM, expect=3)

    assert result["data"]["results"][-1]["stage"] == "reach"
    assert stage_status(project, ROOM)["reach"] == "needs-input"
    advice = project.json("next", ROOM)["data"]
    assert advice["stage"] == "reach" and "Spawn or Exit" in advice["reason"]
    assert advice["command"] is None and "Spawn or an Exit" in advice["owner_action"]
    assert "kiripix decide" not in advice["owner_action"], "where the Body starts is the owner's: no command to guess into"

    place(project, "spawn.main", "spawn")
    project.json("run", ROOM, expect=3)  # stops at export, which has no target

    assert stage_status(project, ROOM)["reach"] == "done"


def test_a_side_view_room_waits_for_m5(project: Kiripix) -> None:
    project.json("new", "room", "bridge", "--view", "side")
    side = "room.bridge"
    project.json("set", side, "brief", "width=48", "height=32")
    project.json("set", side, "fit", "scale=1")
    Image.fromarray(np.full((32, 48, 4), 255, dtype=np.uint8), "RGBA").save(project.cwd / "source.png")
    project.json("pick", side, str(project.json("import", side, "source.png")["data"]["variant"]))
    project.json("decide", side, "place", "--decision", json.dumps(
        {"decision": "marker", "data": {"id": "spawn.main", "type": "spawn", "x": 0, "y": 0}}))

    project.json("run", side, expect=3)

    assert stage_status(project, side)["reach"] == "needs-input"
    assert "not planned yet" in project.json("next", side)["data"]["reason"]


# the Reachable Mask and the report


def test_reach_writes_the_reachable_mask_as_1_bit_and_a_report(project: Kiripix) -> None:
    folder = walled_room(project)
    place(project, "spawn.main", "spawn")

    project.json("run", ROOM, expect=3)

    assert stage_status(project, ROOM)["reach"] == "done"
    expected = np.zeros((32, 48), dtype=np.bool_)
    expected[4:29, 22:43] = True
    assert (read_reachable(folder) == expected).all()
    assert report(folder)["markers"] == [{"id": "spawn.main", "type": "spawn", "x": 30, "y": 16, "on_ground": True,
                                           "reached": True}]
    # the walled room has a wall on its left only, so its other edges are open (info)
    assert {f["code"] for f in project.json("check", ROOM)["findings"]} - {"palette.mapping_error"} == {"masks.open_edge"}


def test_the_reachable_mask_is_the_union_of_every_flood(project: Kiripix) -> None:
    folder = split_room(project)
    place(project, "spawn.main", "spawn", LEFT)
    place(project, "spawn.far", "spawn", RIGHT)
    project.json("run", ROOM, expect=2)

    expected = np.zeros((32, 48), dtype=np.bool_)
    expected[4:29, 22:25] = True
    expected[4:29, 41:43] = True
    assert (read_reachable(folder) == expected).all()


# reach.unreachable_marker


def test_an_exit_behind_a_wall_is_reported_with_its_position_and_erasing_the_wall_clears_it(project: Kiripix) -> None:
    folder = split_room(project)
    place(project, "spawn.main", "spawn", LEFT)
    place(project, "exit.east", "exit", RIGHT, **EXIT)

    assert findings(project.json("run", ROOM, expect=2), "reach.unreachable_marker") != []

    result = project.json("check", ROOM, expect=2)
    [finding] = findings(result, "reach.unreachable_marker")
    position = finding["position"]
    assert (position["asset"], position["stage"], position["x"], position["y"]) == (ROOM, "reach", *RIGHT)
    assert "exit.east" in finding["message"] and "spawn.main" in finding["message"]
    assert finding["severity"] == "error" and finding["fix"] is None
    assert f"kiripix decide {ROOM} masks" in finding["owner_action"]
    advice = project.json("next", ROOM)["data"]
    assert advice["stage"] == "reach" and advice["owner_action"] == finding["owner_action"]
    assert [m["reached"] for m in report(folder)["markers"]] == [True, False]

    decide(project, "brush", {"mask": "solid", "erase": True, "radius": 2, "points": WALL})
    project.json("run", ROOM, expect=3)

    assert findings(project.json("check", ROOM), "reach.unreachable_marker") == []


def test_the_markers_cut_off_are_those_outside_the_largest_group(project: Kiripix) -> None:
    split_room(project)
    place(project, "exit.far", "exit", RIGHT, **EXIT)  # the first Marker, but alone
    place(project, "spawn.main", "spawn", LEFT)
    place(project, "exit.near", "exit", (23, 8), **EXIT)
    project.json("run", ROOM, expect=2)

    [finding] = findings(project.json("check", ROOM, expect=2), "reach.unreachable_marker")

    assert "exit.far" in finding["message"] and (finding["position"]["x"], finding["position"]["y"]) == RIGHT


def test_a_tie_between_two_sides_keeps_the_spawn_and_reports_the_exit(project: Kiripix) -> None:
    split_room(project)
    place(project, "exit.far", "exit", RIGHT, **EXIT)
    place(project, "spawn.main", "spawn", LEFT)
    project.json("run", ROOM, expect=2)

    [finding] = findings(project.json("check", ROOM, expect=2), "reach.unreachable_marker")

    assert finding["message"].startswith("the exit 'exit.far'")


def test_a_marker_on_solid_is_unreachable_as_well_as_not_walkable(project: Kiripix) -> None:
    walled_room(project)
    place(project, "spawn.main", "spawn")
    place(project, "exit.west", "exit", (4, 16), **EXIT)
    project.json("run", ROOM, expect=2)

    result = project.json("check", ROOM, expect=2)

    [finding] = findings(result, "reach.unreachable_marker")
    assert "exit.west" in finding["message"] and "not on walkable ground" in finding["message"]
    assert findings(result, "marker.not_walkable") != []


def test_only_spawns_and_exits_are_flooded(project: Kiripix) -> None:
    folder = split_room(project)
    place(project, "spawn.main", "spawn", LEFT)
    place(project, "crate", "interactable", RIGHT)
    project.json("run", ROOM, expect=3)

    assert [m["id"] for m in report(folder)["markers"]] == ["spawn.main"]
    assert findings(project.json("check", ROOM), "reach.unreachable_marker") == []


# reach.unreachable_island


def test_walkable_ground_nothing_reaches_is_a_warning_with_its_bounding_box(project: Kiripix) -> None:
    split_room(project)
    place(project, "spawn.main", "spawn", LEFT)
    result = project.json("run", ROOM, expect=3)  # a warning fails nothing

    assert findings(result, "reach.unreachable_island") != []
    [finding] = findings(project.json("check", ROOM), "reach.unreachable_island")
    position = finding["position"]
    assert (position["x"], position["y"], position["width"], position["height"]) == (41, 4, 2, 25)
    assert finding["severity"] == "warning" and finding["fix"] is None and finding["owner_action"]
    advice = project.json("next", ROOM)
    assert advice["data"]["stage"] == "export"  # never a reason to stop, but `next` still says it
    assert [f["code"] for f in advice["findings"] if f["code"] not in ("masks.open_edge", "palette.mapping_error")] == ["reach.unreachable_island"]


# reach.narrow_gap


def test_the_narrowest_gaps_are_information(project: Kiripix) -> None:
    folder = walled_room(project)
    for rows in ((0, 11), (19, 31)):  # the wall at x 30 to 34 with a gap at y 12 to 18: a row short for the 8 px Body
        points = [[x, y] for x in range(30, 35) for y in (rows if x % 2 == 0 else rows[::-1])]
        decide(project, "brush", {"mask": "solid", "erase": False, "radius": 0, "points": points})
    place(project, "spawn.main", "spawn", LEFT)
    place(project, "exit.east", "exit", RIGHT, **EXIT)
    project.json("run", ROOM, expect=2)

    result = project.json("check", ROOM, expect=2)

    [finding] = findings(result, "reach.narrow_gap")
    assert finding["severity"] == "info" and finding["fix"] is None and finding["owner_action"]
    assert "7 px" in finding["message"] and "8 px" in finding["message"]
    assert (finding["position"]["x"], finding["position"]["y"]) == (32, 15)
    assert report(folder)["gaps"] == [{"width": 7, "needed": 8, "x": 32, "y": 15}]


# inputs


def test_a_pit_stops_walking_and_a_dash_as_wide_as_it_crosses_it(project: Kiripix) -> None:
    split_room(project, "pit")
    place(project, "spawn.main", "spawn", LEFT)
    place(project, "exit.east", "exit", RIGHT, **EXIT)
    project.json("run", ROOM, expect=2)  # with no dash, the pit parts them

    set_body(project, "dash = 5")  # the pit is 5 px wide
    assert stage_status(project, ROOM)["reach"] == "stale"
    project.json("run", ROOM, expect=3)

    assert findings(project.json("check", ROOM), "reach.unreachable_marker") == []


def test_a_dash_one_pixel_short_of_the_pit_does_not_cross_it(project: Kiripix) -> None:
    split_room(project, "pit")
    place(project, "spawn.main", "spawn", LEFT)
    place(project, "exit.east", "exit", RIGHT, **EXIT)
    set_body(project, "dash = 4")

    assert findings(project.json("run", ROOM, expect=2), "reach.unreachable_marker") != []


def test_a_dash_does_not_cross_a_solid_wall(project: Kiripix) -> None:
    split_room(project)
    place(project, "spawn.main", "spawn", LEFT)
    place(project, "exit.east", "exit", RIGHT, **EXIT)
    set_body(project, "dash = 40")

    assert findings(project.json("run", ROOM, expect=2), "reach.unreachable_marker") != []


def test_a_marker_on_a_pit_is_not_on_walkable_ground(project: Kiripix) -> None:
    split_room(project, "pit")
    place(project, "spawn.main", "spawn", LEFT)
    place(project, "exit.mid", "exit", (32, 16), **EXIT)

    result = project.json("run", ROOM, expect=2)

    assert findings(result, "marker.not_walkable") != []


def test_a_project_with_no_pit_mask_still_works(project: Kiripix) -> None:
    folder = walled_room(project)
    settings = project.cwd / "kiripix.toml"
    lines = settings.read_text("utf-8").splitlines(keepends=True)
    kept = [line for line in lines if not line.startswith("pit")]
    assert len(kept) == len(lines) - 1
    settings.write_text("".join(kept), "utf-8")
    place(project, "spawn.main", "spawn")
    set_body(project, "dash = 5")

    project.json("run", ROOM, expect=3)

    assert not (folder / "work" / "masks" / "pit.png").exists()
    assert stage_status(project, ROOM)["reach"] == "done"


def test_the_step_is_a_parameter_that_defaults_to_exact_and_makes_reach_stale(project: Kiripix) -> None:
    folder = walled_room(project)
    place(project, "spawn.main", "spawn")
    project.json("run", ROOM, expect=3)
    before = read_reachable(folder).copy()

    project.json("set", ROOM, "reach", "step=4")
    assert stage_status(project, ROOM)["reach"] == "stale"
    project.json("run", ROOM, expect=3)

    assert (read_reachable(folder) == before).all()  # an open floor comes out whole at any step


def test_describe_says_reach_is_implemented_with_its_checks(kpx: Kiripix) -> None:
    room = kpx.json("describe", "room")["data"]["kinds"][0]
    stage = next(s for s in room["stages"] if s["name"] == "reach")

    assert stage["implemented"]
    assert stage["params"][0]["name"] == "step" and stage["params"][0]["default"] == 1
    assert {c["code"] for c in stage["checks"]} == {"reach.unreachable_marker", "reach.unreachable_island",
                                                    "reach.narrow_gap", "area.not_reached"}


def test_a_view_that_stops_deriving_walkable_fails_reach_and_check_still_answers(project: Kiripix) -> None:
    walled_room(project)
    place(project, "spawn.main", "spawn")
    project.json("run", ROOM, expect=3)
    settings = project.cwd / "kiripix.toml"
    lines = settings.read_text("utf-8").splitlines(keepends=True)
    kept = [line for line in lines if not line.startswith("walkable")]
    assert len(kept) == len(lines) - 1
    settings.write_text("".join(kept), "utf-8")

    result = project.json("run", ROOM, expect=1)

    [failure] = findings(result, "stage.failed")
    assert failure["position"]["stage"] == "reach" and "walkable" in failure["message"]
    assert findings(project.json("check", ROOM), "internal.error") == []


def test_a_masks_edit_makes_reach_stale(project: Kiripix) -> None:
    built_room(project)
    place(project, "spawn.main", "spawn", (30, 16))
    project.json("run", ROOM, expect=3)

    decide(project, "brush", {"mask": "solid", "erase": False, "radius": 1, "points": [[8, 8]]})

    assert stage_status(project, ROOM)["reach"] == "stale"
