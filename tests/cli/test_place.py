"""The room's place Stage (spec §6.1): `marker` Decisions replayed into a Markers file, and walkable as a derived Mask."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_layers_stage import accept, click, lift
from test_layers_stage import built_room as layers_room
from test_masks import FLOOR, ROOM, RUG, WALL, built_room, decide

# built_room's Plate is 48 x 32, with a wall on its left 16 columns. With the wall flooded into `solid` and the default
# 12 x 8 Body, walkable is x 22 to 42, y 4 to 28: a footprint at (x, y) covers x - 6 to x + 5 and y - 4 to y + 3.
ON_THE_WALL = (4, 16)
ON_THE_FLOOR = (30, 16)
WALL_EDGE = 21  # one column too near the wall for the footprint


def walled_room(project: Kiripix) -> Path:
    folder = built_room(project)
    decide(project, "flood", {"x": 0, "y": 0, "mask": "solid"})
    return folder


def place(project: Kiripix, marker_id: str, marker_type: str, at: tuple[int, int] = ON_THE_FLOOR, expect: int = 0,
          **fields: Any) -> dict[str, Any]:
    data = {"id": marker_id, "type": marker_type, "x": at[0], "y": at[1], **fields}
    return project.json("decide", ROOM, "place", "--decision", json.dumps({"decision": "marker", "data": data}),
                        expect=expect)


def built_place(project: Kiripix, expect: int = 3) -> dict[str, Any]:
    """Run down to `place`; the run stops at `reach` with no Spawn or Exit, or else at `export`, with no target."""
    return project.json("run", ROOM, expect=expect)


def markers(folder: Path) -> list[dict[str, Any]]:
    value: list[dict[str, Any]] = json.loads((folder / "work" / "place" / "markers.json").read_text("utf-8"))["markers"]
    return value


def read_walkable(folder: Path) -> np.ndarray:
    with Image.open(folder / "work" / "place" / "walkable.png") as image:
        assert image.mode == "1"
        return np.asarray(image, dtype=np.bool_)


def findings(result: dict[str, Any], code: str) -> list[dict[str, Any]]:
    return [f for f in result["findings"] if f["code"] == code]


# walkable


def test_place_derives_walkable_from_solid_and_the_body_as_a_1_bit_mask(project: Kiripix) -> None:
    folder = walled_room(project)

    built_place(project)

    assert stage_status(project, ROOM)["place"] == "done"
    assert markers(folder) == []
    result = read_walkable(folder)
    expected = np.zeros((32, 48), dtype=np.bool_)
    expected[4:29, 22:43] = True
    assert (result == expected).all()


def test_changing_the_body_makes_place_stale_and_rederives_walkable_without_touching_what_is_above(
        project: Kiripix) -> None:
    folder = walled_room(project)
    built_place(project)
    settings = project.cwd / "kiripix.toml"
    text = settings.read_text("utf-8")
    assert "size = [12, 8]" in text
    settings.write_text(text.replace("size = [12, 8]", "size = [4, 4]"), "utf-8")

    status = stage_status(project, ROOM)
    assert status["place"] == "stale"
    assert status["masks"] == status["palette"] == status["fit"] == "done"

    result = built_place(project)

    ran = {r["stage"]: r["outcome"] for r in result["data"]["results"]}
    assert ran["masks"] == ran["palette"] == "skipped" and ran["place"] == "done"
    assert read_walkable(folder)[2, 18]  # a 4 x 4 footprint at (18, 2) covers x 16 to 19, y 0 to 3


def test_a_mask_edit_makes_place_stale_but_leaves_palette_done(project: Kiripix) -> None:
    walled_room(project)
    built_place(project)

    decide(project, "brush", {"mask": "solid", "erase": True, "radius": 4, "points": [[8, 8]]})

    status = stage_status(project, ROOM)
    assert status["palette"] == "done" and status["masks"] == "stale" and status["place"] == "stale"


def test_a_side_view_room_has_no_walkable_and_no_walkable_check(project: Kiripix) -> None:
    project.json("new", "room", "bridge", "--view", "side")
    side = "room.bridge"
    project.json("set", side, "brief", "width=48", "height=32")
    project.json("set", side, "fit", "scale=1")
    Image.fromarray(np.full((32, 48, 4), 255, dtype=np.uint8), "RGBA").save(project.cwd / "source.png")
    project.json("pick", side, str(project.json("import", side, "source.png")["data"]["variant"]))
    project.json("decide", side, "place", "--decision", json.dumps(
        {"decision": "marker", "data": {"id": "spawn.main", "type": "spawn", "x": 0, "y": 0}}))

    project.json("run", side, expect=3)

    folder = project.cwd / "assets" / "room" / "bridge" / "work" / "place"
    assert stage_status(project, side)["place"] == "done" and not (folder / "walkable.png").exists()
    assert findings(project.json("check", side), "marker.not_walkable") == []


# Markers


def test_each_marker_type_keeps_its_own_fields_in_the_markers_file(project: Kiripix) -> None:
    folder = walled_room(project)
    place(project, "spawn.main", "spawn")
    place(project, "exit.east", "exit", (40, 16), target_room="room.street", target_exit="exit.west")
    place(project, "crate", "interactable", (30, 20))
    place(project, "lamp", "light", (30, 8), colour="#FFCC88", radius=24, energy=1.5)
    place(project, "steam", "emitter", (32, 8), name="steam_vent")
    place(project, "ysort.rail", "ysort", (24, 20), layer="rail", x2=40, y2=20)

    result = built_place(project, expect=2)  # the room has no Layer `rail`

    assert [f["code"] for f in findings(result, "ysort.unknown_layer")] == ["ysort.unknown_layer"]
    assert markers(folder) == [
        {"id": "spawn.main", "type": "spawn", "x": 30, "y": 16},
        {"id": "exit.east", "type": "exit", "x": 40, "y": 16, "target_room": "room.street", "target_exit": "exit.west"},
        {"id": "crate", "type": "interactable", "x": 30, "y": 20},
        {"id": "lamp", "type": "light", "x": 30, "y": 8, "colour": "#FFCC88", "radius": 24, "energy": 1.5},
        {"id": "steam", "type": "emitter", "x": 32, "y": 8, "name": "steam_vent", "shape": None,
         "direction": None, "colours": None},
        {"id": "ysort.rail", "type": "ysort", "x": 24, "y": 20, "layer": "rail", "x2": 40, "y2": 20},
    ]


def test_moving_a_marker_with_the_same_id_leaves_one_marker_at_the_new_position(project: Kiripix) -> None:
    folder = walled_room(project)
    place(project, "spawn.main", "spawn", (30, 16))
    place(project, "crate", "interactable", (30, 20))
    place(project, "spawn.main", "spawn", (34, 18))

    built_place(project)

    assert markers(folder) == [{"id": "spawn.main", "type": "spawn", "x": 34, "y": 18},
                               {"id": "crate", "type": "interactable", "x": 30, "y": 20}]


def test_undo_removes_a_marker_and_undoing_a_move_puts_it_back(project: Kiripix) -> None:
    folder = walled_room(project)
    place(project, "spawn.main", "spawn", (30, 16))
    place(project, "spawn.main", "spawn", (34, 18))

    project.json("undo", ROOM, "place")
    built_place(project)
    assert markers(folder) == [{"id": "spawn.main", "type": "spawn", "x": 30, "y": 16}]

    project.json("undo", ROOM, "place")
    built_place(project)
    assert markers(folder) == []


def test_a_marker_is_refused_without_the_fields_of_its_type_or_with_those_of_another(project: Kiripix) -> None:
    built_room(project)

    assert "decision.invalid" in [f["code"] for f in place(project, "exit.a", "exit", expect=1)["findings"]]
    assert "decision.invalid" in [f["code"] for f in place(project, "lamp", "light", colour="#FFFFFF", expect=1)[
        "findings"]]
    assert "decision.invalid" in [f["code"] for f in place(project, "ysort.a", "ysort", x2=1, expect=1)["findings"]]
    assert "decision.invalid" in [f["code"] for f in place(project, "ysort.a", "ysort", x2=9, y2=9, expect=1)["findings"]]
    assert "decision.invalid" in [f["code"] for f in place(project, "spawn.a", "spawn", layer="lamp", expect=1)["findings"]]
    assert "decision.invalid" in [f["code"] for f in place(project, "ysort.a", "ysort", layer="plate", x2=9, y2=9,
                                                           expect=1)["findings"]]
    assert "decision.invalid" in [f["code"] for f in place(project, "spawn.a", "spawn", radius=3, expect=1)["findings"]]
    assert "decision.invalid" in [f["code"] for f in place(project, "lamp", "light", colour="orange", radius=1,
                                                           energy=1, expect=1)["findings"]]
    assert "decision.invalid" in [f["code"] for f in place(project, "Bad ID!", "spawn", expect=1)["findings"]]
    assert "decision.invalid" in [f["code"] for f in place(project, "exit.a", "exit", target_room="not a room",
                                                           target_exit="exit.b", expect=1)["findings"]]


def test_describe_gives_the_marker_decision_schema_and_says_place_is_implemented(kpx: Kiripix) -> None:
    room = kpx.json("describe", "room")["data"]["kinds"][0]
    stage = next(s for s in room["stages"] if s["name"] == "place")

    assert stage["implemented"]
    schema = stage["decisions"][0]["entry_schema"]
    assert schema["required"] == ["id", "type", "x", "y"]
    assert {"target_room", "target_exit", "colour", "radius", "energy", "name", "layer", "x2", "y2"} <= set(
        schema["properties"])
    above = next(d for d in stage["decisions"] if d["name"] == "above")
    assert above["entry_schema"]["required"] == ["layer", "above"]


# Checks


def test_a_spawn_on_solid_reports_marker_not_walkable_with_its_position_and_check_exits_2(project: Kiripix) -> None:
    walled_room(project)
    place(project, "spawn.main", "spawn", ON_THE_WALL)

    assert findings(built_place(project, expect=2), "marker.not_walkable") != []

    result = project.json("check", ROOM, expect=2)
    [finding] = findings(result, "marker.not_walkable")
    position = finding["position"]
    assert (position["asset"], position["stage"], position["x"], position["y"]) == (ROOM, "place", *ON_THE_WALL)
    assert "spawn.main" in finding["message"]
    assert finding["fix"] is None and "spawn.main" in finding["owner_action"]


def test_a_spot_on_the_floor_too_near_a_wall_for_the_footprint_is_not_walkable(project: Kiripix) -> None:
    walled_room(project)
    place(project, "exit.west", "exit", (WALL_EDGE, 16), target_room="room.street", target_exit="exit.east")
    place(project, "spawn.main", "spawn", (WALL_EDGE + 1, 16))
    built_place(project, expect=2)

    [finding] = findings(project.json("check", ROOM, expect=2), "marker.not_walkable")

    assert "exit.west" in finding["message"]


def test_a_spawn_outside_the_room_is_not_walkable(project: Kiripix) -> None:
    walled_room(project)
    place(project, "spawn.main", "spawn", (480, 16))
    built_place(project, expect=2)

    [finding] = findings(project.json("check", ROOM, expect=2), "marker.not_walkable")

    assert (finding["position"]["x"], finding["position"]["y"]) == (480, 16)


def test_only_exits_and_spawns_need_walkable_ground(project: Kiripix) -> None:
    walled_room(project)
    place(project, "lamp", "light", ON_THE_WALL, colour="#FFFFFF", radius=8, energy=1)
    place(project, "crate", "interactable", ON_THE_WALL)
    built_place(project)

    assert findings(project.json("check", ROOM), "marker.not_walkable") == []


def test_erasing_the_wall_under_a_spawn_clears_the_finding_after_a_run(project: Kiripix) -> None:
    built_room(project)
    decide(project, "brush", {"mask": "solid", "erase": False, "radius": 8, "points": [[30, 16]]})
    place(project, "spawn.main", "spawn", (30, 16))
    built_place(project, expect=2)
    assert findings(project.json("check", ROOM, expect=2), "marker.not_walkable") != []

    decide(project, "brush", {"mask": "solid", "erase": True, "radius": 8, "points": [[30, 16]]})
    built_place(project)

    assert findings(project.json("check", ROOM), "marker.not_walkable") == []


def test_the_same_id_on_a_marker_of_another_type_is_a_duplicate_and_keeps_both(project: Kiripix) -> None:
    folder = walled_room(project)
    place(project, "door", "spawn", (30, 16))
    place(project, "door", "interactable", (34, 18))

    built_place(project, expect=2)

    assert [m["type"] for m in markers(folder)] == ["spawn", "interactable"]
    [finding] = findings(project.json("check", ROOM, expect=2), "marker.duplicate_id")
    assert (finding["position"]["x"], finding["position"]["y"]) == (34, 18)
    assert "door" in finding["message"] and finding["fix"] is None and "door" in finding["owner_action"]


def test_a_clean_place_reports_nothing(project: Kiripix) -> None:
    walled_room(project)
    palette = project.cwd / "style" / "palette.gpl"  # the room's own colours, so the mapping is exact, not muddy
    lines = [f"{r} {g} {b} room{i}" for i, (r, g, b, _) in enumerate((WALL, FLOOR, RUG))]
    palette.write_text(palette.read_text("utf-8") + "\n".join(lines) + "\n", "utf-8")
    place(project, "spawn.main", "spawn")
    built_place(project)

    result = project.json("check", ROOM)

    assert {f["code"] for f in result["findings"]} <= {"masks.open_edge"}  # info: the room's other edges are open
    assert f"{ROOM} place" in result["data"]["stages"]


def test_a_view_that_derives_walkable_without_a_solid_mask_fails_the_stage_and_says_why(project: Kiripix) -> None:
    built_room(project)
    settings = project.cwd / "kiripix.toml"
    text = settings.read_text("utf-8")
    renamed = text.replace("solid      = {", "wall       = {", 1).replace('["solid"]', '["wall"]')
    assert renamed != text
    settings.write_text(renamed, "utf-8")

    result = project.json("run", ROOM, expect=1)

    [failure] = findings(result, "stage.failed")
    assert failure["position"]["stage"] == "place" and "solid" in failure["message"]


# y-sort lines and "always above" (ticket 0046, D3)


def lamp_room(project: Kiripix) -> Path:
    """The layers room with one Layer, `lamp`, lifted and accepted, and built down to `place`."""
    folder = layers_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    accept(project)
    built_place(project, expect=2)  # layer.no_ysort: the Layer has no line yet
    return folder


def line(project: Kiripix, layer: str, y: int = 20, y2: int | None = None, marker_id: str = "ysort.lamp",
         expect: int = 0) -> dict[str, Any]:
    return place(project, marker_id, "ysort", (24, y), layer=layer, x2=40, y2=y if y2 is None else y2, expect=expect)


def above(project: Kiripix, layer: str, flag: bool = True) -> dict[str, Any]:
    return project.json("decide", ROOM, "place", "--decision",
                        json.dumps({"decision": "above", "data": {"layer": layer, "above": flag}}))


def sort_of(folder: Path) -> list[dict[str, Any]]:
    value: list[dict[str, Any]] = json.loads((folder / "work" / "place" / "markers.json").read_text("utf-8"))["sort"]
    return value


def shown_sort(project: Kiripix) -> list[dict[str, Any]]:
    stage = next(s for s in project.json("show", ROOM)["data"]["stages"] if s["stage"] == "place")
    value: list[dict[str, Any]] = stage["sort"]
    return value


def test_a_layer_with_no_line_fails_layer_no_ysort_and_a_line_clears_it(project: Kiripix) -> None:
    folder = lamp_room(project)

    [finding] = findings(project.json("check", ROOM, expect=2), "layer.no_ysort")
    assert finding["position"]["stage"] == "place" and "lamp" in finding["message"]
    assert finding["fix"] is None and "lamp" in finding["owner_action"]
    assert sort_of(folder) == [{"layer": "lamp", "above": False, "marker": None, "y": None, "slope": 0}]
    assert shown_sort(project) == []  # nothing decided yet

    line(project, "lamp")
    built_place(project)

    assert findings(project.json("check", ROOM), "layer.no_ysort") == []
    assert sort_of(folder) == [{"layer": "lamp", "above": False, "marker": "ysort.lamp", "y": 20, "slope": 0}]


def test_the_above_flag_clears_layer_no_ysort_and_sorts_at_none_and_false_takes_it_back(project: Kiripix) -> None:
    folder = lamp_room(project)

    above(project, "lamp")
    built_place(project)

    assert findings(project.json("check", ROOM), "layer.no_ysort") == []
    assert sort_of(folder) == [{"layer": "lamp", "above": True, "marker": None, "y": None, "slope": 0}]
    assert shown_sort(project) == sort_of(folder)

    above(project, "lamp", False)
    built_place(project, expect=2)

    assert findings(project.json("check", ROOM, expect=2), "layer.no_ysort") != []
    assert shown_sort(project) == []


def test_above_wins_over_a_line_on_the_same_layer(project: Kiripix) -> None:
    folder = lamp_room(project)
    line(project, "lamp")
    above(project, "lamp")

    built_place(project)

    assert sort_of(folder) == [{"layer": "lamp", "above": True, "marker": None, "y": None, "slope": 0}]


def test_a_second_line_on_a_layer_sorts_nothing_and_warns(project: Kiripix) -> None:
    folder = lamp_room(project)
    line(project, "lamp")
    line(project, "lamp", y=26, marker_id="ysort.lamp_low")
    built_place(project)

    assert sort_of(folder) == [{"layer": "lamp", "above": False, "marker": "ysort.lamp", "y": 20, "slope": 0}]
    [warning] = findings(project.json("check", ROOM), "ysort.extra_line")
    assert warning["severity"] == "warning" and "ysort.lamp_low" in warning["message"] and warning["owner_action"]


def test_a_room_with_no_layers_passes_and_a_ysort_without_a_layer_warns_and_is_kept(project: Kiripix) -> None:
    folder = walled_room(project)
    place(project, "spawn.main", "spawn")
    place(project, "ysort.rail", "ysort", (24, 20), layer="rail", x2=40, y2=20)
    journal = folder / "decisions" / "place.jsonl"
    entries = [json.loads(text) for text in journal.read_text("utf-8").splitlines()]
    del entries[-1]["data"]["layer"]  # as an M1 journal has it
    journal.write_text("".join(json.dumps(entry) + "\n" for entry in entries), "utf-8")

    built_place(project)

    result = project.json("check", ROOM)
    [warning] = findings(result, "ysort.no_layer")
    assert warning["severity"] == "warning" and warning["fix"] is None and "ysort.rail" in warning["owner_action"]
    assert findings(result, "layer.no_ysort") == []
    assert markers(folder)[-1] == {"id": "ysort.rail", "type": "ysort", "x": 24, "y": 20, "x2": 40, "y2": 20}
    assert sort_of(folder) == []


def test_a_sloped_line_sorts_at_its_mean_y_rounded_half_up_and_warns_past_half_a_tile(project: Kiripix) -> None:
    folder = lamp_room(project)
    line(project, "lamp", y=20, y2=25)  # 5 px apart: within half of the 16 px tile
    built_place(project)

    assert sort_of(folder) == [{"layer": "lamp", "above": False, "marker": "ysort.lamp", "y": 23, "slope": 5}]
    assert findings(project.json("check", ROOM), "ysort.sloped") == []

    line(project, "lamp", y=20, y2=29)  # 9 px apart
    built_place(project)

    [warning] = findings(project.json("check", ROOM), "ysort.sloped")
    assert warning["severity"] == "warning" and "ysort.lamp" in warning["message"] and warning["owner_action"]
    assert sort_of(folder)[0]["y"] == 25 and sort_of(folder)[0]["slope"] == 9
    assert shown_sort(project) == sort_of(folder)


def test_a_line_or_flag_naming_an_unknown_layer_is_its_own_finding(project: Kiripix) -> None:
    folder = lamp_room(project)
    line(project, "lamp")
    line(project, "ghost", marker_id="ysort.ghost")
    above(project, "phantom")
    built_place(project, expect=2)

    result = project.json("check", ROOM, expect=2)

    unknown = findings(result, "ysort.unknown_layer")
    assert sorted(f["message"].split("'")[1] for f in unknown) == ["ghost", "phantom"]
    assert all(f["fix"] is None and f["owner_action"] for f in unknown)
    assert findings(result, "layer.no_ysort") == []
    assert [e["layer"] for e in sort_of(folder)] == ["lamp", "ghost", "phantom"]


def test_show_gives_the_sort_position_of_each_layer_before_any_build(project: Kiripix) -> None:
    lamp_room(project)

    line(project, "lamp", y=18, y2=21)
    above(project, "crate")

    assert shown_sort(project) == [
        {"layer": "lamp", "above": False, "marker": "ysort.lamp", "y": 20, "slope": 3},
        {"layer": "crate", "above": True, "marker": None, "y": None, "slope": 0},
    ]
