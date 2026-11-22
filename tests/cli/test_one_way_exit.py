"""A one-way Exit: `one_way` on an Exit Marker needs no return (ticket 0352)."""

import json
from typing import Any

from conftest import Kiripix
from test_export_ownership import STREET, put, two_paired_rooms
from test_masks import ROOM

THIRD = "room.cellar"


def exits_of(project: Kiripix, glob: str = "room.*") -> dict[tuple[str, str], dict[str, Any]]:
    return {(x["room"], x["exit"]): x for x in project.json("district", glob)["data"]["exits"]}


def exit_codes(result: dict[str, Any]) -> list[str]:
    return [f["code"] for f in result["findings"] if f["code"].startswith("exit.")]


def point_alley_one_way(project: Kiripix, **fields: Any) -> None:
    """The alley's `exit.east` leads to the street's `exit.west`, which now pairs with the alley's `exit.south`."""
    two_paired_rooms(project)
    put(project, ROOM, "exit.south", "exit", at=(32, 14), target_room=STREET, target_exit="exit.west")
    project.json("undo", STREET, "place")
    put(project, STREET, "exit.west", "exit", at=(30, 12), target_room=ROOM, target_exit="exit.south")
    if fields:
        put(project, ROOM, "exit.east", "exit", at=(30, 12), target_room=STREET, target_exit="exit.west", **fields)
    project.json("run", ROOM)
    project.json("run", STREET)


def test_a_one_way_exit_is_not_unpaired_and_without_the_flag_it_is(project: Kiripix) -> None:
    point_alley_one_way(project)
    assert exit_codes(project.json("check", "--all", expect=2)) == ["exit.not_paired"]
    assert exits_of(project)[ROOM, "exit.east"]["pairing"] == "unpaired"

    put(project, ROOM, "exit.east", "exit", at=(30, 12), target_room=STREET, target_exit="exit.west", one_way=True)
    project.json("run", ROOM)

    result = project.json("check", "--all")
    assert exit_codes(result) == []
    assert exits_of(project)[ROOM, "exit.east"]["pairing"] == "one_way"
    assert exits_of(project)[STREET, "exit.west"]["pairing"] == "paired"  # an ordinary Exit is checked as before


def test_a_one_way_exit_to_a_missing_room_or_exit_is_still_a_finding(project: Kiripix) -> None:
    point_alley_one_way(project, one_way=True)
    put(project, ROOM, "exit.east", "exit", at=(30, 12), target_room="room.nowhere", target_exit="exit.west", one_way=True)
    project.json("run", ROOM)
    assert "exit.no_room" in exit_codes(project.json("check", "--all", expect=2))

    put(project, ROOM, "exit.east", "exit", at=(30, 12), target_room=STREET, target_exit="exit.nope", one_way=True)
    project.json("run", ROOM)
    assert "exit.no_exit" in exit_codes(project.json("check", "--all", expect=2))


def test_markers_and_room_json_carry_one_way_on_every_exit(project: Kiripix) -> None:
    point_alley_one_way(project, one_way=True)
    project.json("export", ROOM)

    room = json.loads((project.cwd / "game/kiripix/room/alley/room.json").read_text("utf-8"))
    assert room["schema_version"] == 15
    assert [m["one_way"] for m in room["markers"] if m["type"] == "exit"] == [True, False]
    other = json.loads((project.cwd / "game/kiripix/room/street/room.json").read_text("utf-8"))         if (project.cwd / "game/kiripix/room/street/room.json").is_file() else None
    if other is not None:
        assert [m["one_way"] for m in other["markers"] if m["type"] == "exit"] == [False]
    [built] = [p for p in project.cwd.rglob("markers.json") if "alley" in p.parts]
    markers = json.loads(built.read_text("utf-8"))
    assert markers["schema_version"] == 4
    assert [m["one_way"] for m in markers["markers"] if m["type"] == "exit"] == [True, False]
