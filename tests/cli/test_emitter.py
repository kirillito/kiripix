"""An emitter's shape, direction and colours (ticket 0185, spec §6.1): optional fields of the `marker` Decision, the
Checks on `place` that follow, and `room.json`'s schema 4."""

import json
from pathlib import Path
from typing import Any

from conftest import Kiripix, Result
from test_export import godot_project, set_target
from test_masks import FLOOR, ROOM, WALL
from test_place import built_place, markers, place, walled_room

# walled_room's Plate is 48 x 32.
NEW = {"shape": None, "direction": None, "colours": None}
ON = ("#C8BEAA", "#2814C8")  # FLOOR and WALL: added to the palette by `with_palette`


def with_palette(project: Kiripix) -> None:
    palette = project.cwd / "style" / "palette.gpl"
    lines = [f"{r} {g} {b} room{i}" for i, (r, g, b, _) in enumerate((WALL, FLOOR))]
    palette.write_text(palette.read_text("utf-8") + "\n".join(lines) + "\n", "utf-8")


def emitter(project: Kiripix, marker_id: str = "steam", at: tuple[int, int] = (30, 16), expect: int = 0,
            **fields: Any) -> dict[str, Any]:
    return place(project, marker_id, "emitter", at, expect=expect, name="steam_pipe", **fields)


def checked(project: Kiripix) -> Result:
    project("run", ROOM, "--json")
    return project("check", ROOM, "--json")


def ids(findings: list[dict[str, Any]]) -> list[str]:
    return sorted(f["message"].split("'")[1] for f in findings)


def test_each_shape_type_a_direction_and_colours_are_kept_in_the_markers_file(project: Kiripix) -> None:
    folder = walled_room(project)
    with_palette(project)
    box = {"type": "box", "x2": 40, "y2": 24}
    emitter(project, "a", (30, 8), shape={"type": "point"})
    emitter(project, "b", (24, 8), shape={"type": "line", "x2": 40, "y2": 12})
    emitter(project, "c", (24, 12), shape=box, direction={"x": 24, "y": 4}, colours=list(ON))
    emitter(project, "d", (24, 12), shape={"type": "polygon", "points": [[24, 12], [40, 12], [32, 20]]})

    project("run", ROOM, "--json")  # the exit code is the findings' (no Spawn, an open edge); the file is what's checked

    by_id = {m["id"]: m for m in markers(folder)}
    assert by_id["a"]["shape"] == {"type": "point"} and by_id["a"]["direction"] is None
    assert by_id["b"]["shape"] == {"type": "line", "x2": 40, "y2": 12}
    assert by_id["c"]["shape"] == box and by_id["c"]["direction"] == {"x": 24, "y": 4}
    assert by_id["c"]["colours"] == list(ON)
    assert by_id["d"]["shape"]["points"] == [[24, 12], [40, 12], [32, 20]]
    assert all(m["name"] == "steam_pipe" for m in by_id.values())


def test_an_emitter_with_no_new_fields_is_built_as_before_apart_from_the_nulls(project: Kiripix) -> None:
    folder = walled_room(project)
    emitter(project, "steam", (32, 8))

    built_place(project)

    assert markers(folder) == [{"id": "steam", "type": "emitter", "x": 32, "y": 8, "name": "steam_pipe", **NEW}]


def test_a_second_decision_moves_and_changes_the_emitter_and_undo_puts_it_back(project: Kiripix) -> None:
    folder = walled_room(project)
    emitter(project, "steam", (30, 8), shape={"type": "line", "x2": 40, "y2": 8})
    emitter(project, "steam", (28, 10), direction={"x": 28, "y": 2})

    project("run", ROOM, "--json")
    [moved] = markers(folder)
    assert (moved["x"], moved["y"], moved["shape"], moved["direction"]) == (28, 10, None, {"x": 28, "y": 2})

    project.json("undo", ROOM, "place")
    project("run", ROOM, "--json")
    [first] = markers(folder)
    assert (first["x"], first["shape"], first["direction"]) == (30, {"type": "line", "x2": 40, "y2": 8}, None)

    project.json("undo", ROOM, "place")
    project("run", ROOM, "--json")
    assert markers(folder) == []


def test_the_decision_refuses_what_it_can(project: Kiripix) -> None:
    walled_room(project)
    cases: list[dict[str, Any]] = [
        {"shape": {"type": "polygon", "points": [[1, 1], [5, 5]]}},
        {"shape": {"type": "line", "x2": 30, "y2": 16}},  # a line with no length
        {"shape": {"type": "box", "x2": 20, "y2": 20}},  # corners the wrong way round
        {"shape": {"type": "box", "x2": 40}},
        {"shape": {"type": "circle"}},
        {"shape": {"type": "point", "x2": 3}},
        {"direction": {"x": 3}},
        {"colours": []},
        {"colours": ["#12345"]},
        {"colours": ["#112233"] * 17},
    ]
    for fields in cases:
        result = emitter(project, "steam", expect=1, **fields)
        assert [f["code"] for f in result["findings"]] == ["decision.invalid"], fields
    box = emitter(project, "steam", expect=1, shape={"type": "box", "x2": 20, "y2": 20})
    assert "x2 20" in box["findings"][0]["message"] and "steam" in box["findings"][0]["message"]


def test_the_new_fields_belong_to_emitters_only(project: Kiripix) -> None:
    walled_room(project)

    for field, value in (("shape", {"type": "point"}), ("direction", {"x": 1, "y": 1}), ("colours", ["#112233"])):
        result = place(project, "lamp", "light", (30, 8), expect=1, colour="#FFCC88", radius=24, energy=1,
                       **{field: value})
        assert [f["code"] for f in result["findings"]] == ["decision.invalid"]


def test_a_colour_off_the_palette_is_an_error_whose_fix_is_the_nearest_palette_colour(project: Kiripix) -> None:
    walled_room(project)
    with_palette(project)
    emitter(project, "steam", (30, 8), colours=["#C8BEAA", "#C8BEA0"])  # the second is not on the palette

    result = checked(project)

    [finding] = [f for f in result.json["findings"] if f["code"] == "place.emitter_colour_off_palette"]
    assert finding["severity"] == "error" and not finding.get("owner_action")
    assert "#C8BEA0" in finding["message"] and "steam" in finding["message"]
    assert '"#C8BEAA", "#C8BEAA"' in finding["fix"] and "#C8BEA0" not in finding["fix"]
    assert result.code == 2

    emitter(project, "steam", (30, 8), colours=["#C8BEAA"])
    assert "place.emitter_colour_off_palette" not in checked(project).codes


def test_an_emitter_leaving_the_room_is_a_warning(project: Kiripix) -> None:
    walled_room(project)
    emitter(project, "line", (30, 8), shape={"type": "line", "x2": 60, "y2": 8})
    emitter(project, "aim", (30, 12), direction={"x": 30, "y": 40})
    emitter(project, "poly", (30, 14), shape={"type": "polygon", "points": [[30, 14], [40, 14], [40, 33]]})
    emitter(project, "inside", (30, 16), shape={"type": "box", "x2": 47, "y2": 31}, direction={"x": 0, "y": 0})

    result = checked(project)

    outside = [f for f in result.json["findings"] if f["code"] == "place.emitter_outside_room"]
    assert ids(outside) == ["aim", "line", "poly"]
    assert all(f["severity"] == "warning" and f["owner_action"] and not f.get("fix") for f in outside)


def test_an_emitter_with_neither_field_is_not_judged_for_its_position(project: Kiripix) -> None:
    walled_room(project)
    emitter(project, "steam", (60, 60))

    assert "place.emitter_outside_room" not in checked(project).codes


def test_a_shape_gone_wrong_after_the_decision_is_an_error(project: Kiripix) -> None:
    # The Decision refuses a bad shape, so only a hand-edited markers file reaches the Check: build it, then break it.
    folder = walled_room(project)
    emitter(project, "steam", (30, 8), shape={"type": "line", "x2": 40, "y2": 8})
    project("run", ROOM, "--json")
    path = folder / "work" / "place" / "markers.json"
    document = json.loads(path.read_text("utf-8"))
    document["markers"][0]["shape"] = {"type": "polygon", "points": [[1, 1], [2, 2]]}
    path.write_text(json.dumps(document), "utf-8")

    result = project("check", ROOM, "--json")

    finding = next(f for f in result.json["findings"] if f["code"] == "place.emitter_shape_invalid")
    assert finding["severity"] == "error" and finding["owner_action"] and "three" in finding["message"]


def test_describe_shows_the_schema_and_says_the_colours_are_what_the_game_draws(kpx: Kiripix) -> None:
    room = kpx.json("describe", "room")["data"]["kinds"][0]
    stage = next(s for s in room["stages"] if s["name"] == "place")
    marker = next(d for d in stage["decisions"] if d["name"] == "marker")

    properties = marker["entry_schema"]["properties"]
    assert {"shape", "direction", "colours"} <= set(properties)
    assert properties["colours"]["maxItems"] == 16
    text = marker["description"]
    assert "opaque" in text and "game draws" in text and "palette" in text
    assert {"place.emitter_colour_off_palette", "place.emitter_outside_room", "place.emitter_shape_invalid"} <= {
        c["code"] for c in stage["checks"]}


def test_a_built_room_exports_the_emitter_fields_in_room_json_schema_4(project: Kiripix) -> None:
    folder = walled_room(project)
    place(project, "spawn.main", "spawn")
    emitter(project, "steam", (30, 8), shape={"type": "point"}, colours=["#112233"])
    emitter(project, "plain", (30, 10))
    godot_project(project)
    set_target(project)
    project.json("run", ROOM, expect=2)  # the colour is off the palette; the Stages still build

    room = json.loads((folder / "out" / "export" / "room.json").read_text("utf-8"))
    assert room["schema_version"] == 8
    by_id = {m["id"]: m for m in room["markers"]}
    assert by_id["plain"]["shape"] is None and by_id["steam"]["colours"] == ["#112233"]
    assert isinstance(folder, Path)
