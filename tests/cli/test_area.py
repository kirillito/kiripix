"""The `area` Marker (ticket 0137, spec §6.1): a box on the room with a stable ID, optionally snapped to a cell and
optionally `walkable`, and the Checks on `place` and `reach` that follow."""

from typing import Any

from conftest import Kiripix
from test_masks import ROOM, decide
from test_place import ON_THE_FLOOR, findings, markers, place, walled_room

# walled_room's Plate is 48 x 32 with `solid` on the left 16 columns; walkable is x 22 to 42, y 4 to 28.


def area(project: Kiripix, marker_id: str, box: tuple[int, int, int, int], expect: int = 0,
         **fields: Any) -> dict[str, Any]:
    x, y, x2, y2 = box
    return place(project, marker_id, "area", (x, y), expect=expect, x2=x2, y2=y2, **fields)


def checked(project: Kiripix) -> Any:
    """Build every Stage, then the Check of the whole room: the result of `check`."""
    project("run", ROOM, "--json")
    return project("check", ROOM, "--json")


def codes(result: Any) -> list[str]:
    """The area findings of a result: a built room has others (the palette, an open edge) that this ticket isn't about."""
    return [code for code in result.codes if code.startswith("area.")]


def test_an_area_goes_into_the_markers_file_with_walkable_and_a_second_decision_moves_it(project: Kiripix) -> None:
    folder = walled_room(project)
    area(project, "battle.yard", (24, 6, 40, 20), walkable=True)
    area(project, "escape.fence", (0, 0, 10, 10))
    area(project, "battle.yard", (26, 8, 38, 22), walkable=True)

    assert "area.no_walkable" not in codes(checked(project))  # (24, 6) to (38, 22) holds walkable ground
    assert markers(folder) == [
        {"id": "battle.yard", "type": "area", "x": 26, "y": 8, "x2": 38, "y2": 22, "walkable": True},
        {"id": "escape.fence", "type": "area", "x": 0, "y": 0, "x2": 10, "y2": 10, "walkable": False},
    ]


def test_undo_puts_an_area_back_where_it_was_and_then_removes_it(project: Kiripix) -> None:
    folder = walled_room(project)
    area(project, "battle.yard", (24, 6, 40, 20))
    area(project, "battle.yard", (26, 8, 38, 22))

    project.json("undo", ROOM, "place")
    project("run", ROOM, "--json")
    assert [(m["x"], m["x2"]) for m in markers(folder)] == [(24, 40)]

    project.json("undo", ROOM, "place")
    project("run", ROOM, "--json")
    assert markers(folder) == []


def test_corners_are_inclusive_and_a_box_one_pixel_wide_is_accepted(project: Kiripix) -> None:
    folder = walled_room(project)
    area(project, "trigger.door", (30, 6, 30, 20))  # x2 == x
    area(project, "trigger.dot", (30, 6, 30, 6))

    project("run", ROOM, "--json")

    assert [(m["x"], m["x2"], m["y"], m["y2"]) for m in markers(folder)] == [(30, 30, 6, 20), (30, 30, 6, 6)]


def test_a_box_with_its_corners_the_wrong_way_round_is_refused_naming_them(project: Kiripix) -> None:
    walled_room(project)

    left = area(project, "battle.a", (30, 6, 20, 20), expect=1)
    above = area(project, "battle.b", (20, 20, 30, 6), expect=1)

    assert [f["code"] for f in left["findings"]] == ["decision.invalid"]
    assert "x2 20" in left["findings"][0]["message"] and "x 30" in left["findings"][0]["message"]
    assert "y2 6" in above["findings"][0]["message"] and "y 20" in above["findings"][0]["message"]


def test_an_area_takes_its_own_fields_and_refuses_those_of_other_types(project: Kiripix) -> None:
    walled_room(project)

    assert area(project, "battle.a", (1, 1, 2, 2), cell=0, expect=1)["findings"][0]["code"] == "decision.invalid"
    assert place(project, "battle.a", "area", expect=1)["findings"][0]["code"] == "decision.invalid"  # no x2, y2
    assert place(project, "battle.a", "area", x2=3, y2=3, layer="rail", expect=1)["findings"][0]["code"] == (
        "decision.invalid")
    assert place(project, "spawn.a", "spawn", x2=3, expect=1)["findings"][0]["code"] == "decision.invalid"
    assert place(project, "spawn.a", "spawn", cell=32, expect=1)["findings"][0]["code"] == "decision.invalid"


def test_a_cell_snaps_the_box_outward_to_multiples_of_it_from_the_top_left(project: Kiripix) -> None:
    folder = walled_room(project)
    area(project, "battle.cells", (5, 3, 20, 9), cell=8)
    area(project, "battle.exact", (8, 8, 15, 15), cell=8)

    project("run", ROOM, "--json")

    assert [(m["x"], m["y"], m["x2"], m["y2"]) for m in markers(folder)] == [(0, 0, 23, 15), (8, 8, 15, 15)]


def test_an_area_leaving_the_room_is_an_error(project: Kiripix) -> None:
    walled_room(project)
    area(project, "battle.big", (24, 6, 48, 20))  # the room is 48 wide: x 0 to 47

    result = checked(project)

    assert result.code == 2
    [finding] = findings(result.json, "area.outside_room")
    assert finding["severity"] == "error" and finding["owner_action"] and finding["fix"] is None
    assert finding["position"]["x"] == 24 and finding["position"]["width"] == 25


def test_a_snapped_box_that_leaves_the_room_says_so(project: Kiripix) -> None:
    walled_room(project)
    area(project, "battle.edge", (24, 6, 40, 20), cell=32)  # snaps to x 0 to 63, y 0 to 31

    [finding] = findings(checked(project).json, "area.outside_room")

    assert "snapped" in finding["message"]


def test_an_area_over_solid_has_no_finding_without_walkable_and_no_walkable_with_it(project: Kiripix) -> None:
    walled_room(project)
    area(project, "escape.fence", (0, 0, 10, 10))

    quiet = checked(project)
    assert quiet.code == 0 and codes(quiet) == []

    area(project, "escape.fence", (0, 0, 10, 10), walkable=True)
    loud = checked(project)

    assert loud.code == 2
    [finding] = findings(loud.json, "area.no_walkable")
    assert finding["severity"] == "error" and finding["fix"] is None
    assert "move" in finding["owner_action"] and "walkable" in finding["owner_action"]


def test_areas_with_different_prefixes_and_a_one_cell_wide_area_are_accepted(project: Kiripix) -> None:
    folder = walled_room(project)
    area(project, "battle.yard", (24, 6, 40, 20), walkable=True)
    area(project, "escape.fence", (0, 0, 10, 10))
    area(project, "trigger.door", (40, 6, 40, 20))
    area(project, "camera.shot", (24, 8, 31, 31), cell=8)  # one cell wide

    result = checked(project)

    assert result.code == 0 and codes(result) == []
    assert [m["id"] for m in markers(folder)] == ["battle.yard", "escape.fence", "trigger.door", "camera.shot"]


def test_an_area_shares_the_id_rule_of_every_marker(project: Kiripix) -> None:
    walled_room(project)
    area(project, "battle.yard", (24, 6, 40, 20))
    place(project, "battle.yard", "spawn")

    result = checked(project)

    assert result.code == 2 and result.codes.count("marker.duplicate_id") == 1
    assert area(project, "Battle Yard", (1, 1, 2, 2), expect=1)["findings"][0]["code"] == "decision.invalid"


def test_cells_a_mask_half_covers_are_listed_with_their_positions_as_info(project: Kiripix) -> None:
    walled_room(project)
    # `solid` covers x 0 to 15: with a cell of 8 the cells at x 0 and 8 are whole, so none is ambiguous.
    area(project, "battle.a", (0, 0, 31, 15), cell=8)
    assert findings(checked(project).json, "area.ambiguous_cells") == []

    # a cell of 12 over x 12 to 23 is a third covered (x 12 to 15), and x 0 to 11 is whole: one ambiguous cell.
    area(project, "battle.a", (0, 0, 35, 11), cell=12)
    result = checked(project)

    assert result.code == 0  # info only
    [finding] = findings(result.json, "area.ambiguous_cells")
    assert finding["severity"] == "info" and finding["fix"] is None and finding["owner_action"]
    assert "1 cells" in finding["message"] and "(12, 0)" in finding["message"]


def test_no_ambiguity_is_reported_for_an_area_without_a_cell(project: Kiripix) -> None:
    walled_room(project)
    area(project, "battle.a", (12, 0, 23, 11))

    assert findings(checked(project).json, "area.ambiguous_cells") == []


def test_a_walkable_area_the_body_cannot_reach_warns_on_reach(project: Kiripix) -> None:
    walled_room(project)
    # a two-column wall across the floor splits walkable: x 22 to 24 on the left, 38 to 42 on the right
    decide(project, "polygon", {"mask": "solid", "erase": False, "points": [[30, 0], [31, 0], [31, 31], [30, 31]]})
    place(project, "spawn.main", "spawn", (40, 16))
    area(project, "battle.left", (22, 4, 24, 28), walkable=True)
    area(project, "battle.right", (38, 4, 42, 28), walkable=True)
    area(project, "escape.left", (22, 4, 24, 28))  # not for standing in: no finding

    warnings = findings(checked(project).json, "area.not_reached")

    assert [w["position"]["x"] for w in warnings] == [22]
    assert warnings[0]["severity"] == "warning" and warnings[0]["owner_action"] and "battle.left" in (
        warnings[0]["message"])


def test_an_area_the_body_can_reach_has_no_reach_finding(project: Kiripix) -> None:
    walled_room(project)
    place(project, "spawn.main", "spawn", ON_THE_FLOOR)
    area(project, "battle.yard", (24, 6, 40, 20), walkable=True)

    assert findings(checked(project).json, "area.not_reached") == []


def test_describe_room_place_shows_the_area_fields_and_what_walkable_asks_for(kpx: Kiripix) -> None:
    room = kpx.json("describe", "room")["data"]["kinds"][0]
    stage = next(s for s in room["stages"] if s["name"] == "place")
    marker = next(d for d in stage["decisions"] if d["name"] == "marker")

    schema = marker["entry_schema"]
    assert "area" in schema["properties"]["type"]["enum"]
    assert {"x2", "y2", "cell", "walkable"} <= set(schema["properties"])
    assert schema["properties"]["walkable"] == {"type": "boolean"} and schema["properties"]["cell"]["minimum"] == 1
    assert "walkable" in marker["description"] and "battle area" in marker["description"]
    assert {"area.outside_room", "area.no_walkable", "area.ambiguous_cells"} <= {c["code"] for c in stage["checks"]}
    reach = next(s for s in room["stages"] if s["name"] == "reach")
    assert "area.not_reached" in [c["code"] for c in reach["checks"]]
    assert "problem" not in marker  # the cross-field rule is code, not described
