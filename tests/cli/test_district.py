"""`kiripix district <glob>`: a district's rooms, their Exits and what waits (ticket 0328)."""

import json
from typing import Any

from conftest import Kiripix, make_demo
from test_export_ownership import STREET, put, two_paired_rooms
from test_masks import ROOM

THIRD = "room.cellar"


def previews(project: Kiripix) -> dict[str, int]:
    folder = project.cwd / ".kiripix" / "previews"
    return {p.name: p.stat().st_mtime_ns for p in folder.glob("*.thumb.*")} if folder.is_dir() else {}


def three_rooms(project: Kiripix) -> None:
    """The alley and the street, paired; a cellar whose Exit points at a room outside the district."""
    two_paired_rooms(project)
    project.json("new", "room", "cellar", "--view", "top")
    put(project, THIRD, "exit.up", "exit", target_room=ROOM, target_exit="exit.east")


def district(project: Kiripix, glob: str = "room.*", expect: int = 0) -> dict[str, Any]:
    return project.json("district", glob, expect=expect)


def exits_of(data: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(x["room"], x["exit"]): x for x in data["exits"]}


def test_three_rooms_in_id_order_with_thumbnails_and_each_pairing_state(project: Kiripix) -> None:
    three_rooms(project)

    data = district(project)["data"]

    assert [r["asset"] for r in data["rooms"]] == [ROOM, THIRD, STREET]
    alley, cellar, street = data["rooms"]
    assert alley["thumbnail"] and (project.cwd / alley["thumbnail"]).is_file() and street["thumbnail"]
    assert alley["width"] % 16 == 0 and alley["tiles_wide"] == alley["width"] // 16
    assert alley["built"]["stage"] == "export" or alley["built"]["status"] in ("done", "stale")
    assert set(alley["queue"]) == {"review", "input", "finding", "agent_fixable"}
    assert cellar["thumbnail"] is None and "Source" in cellar["thumbnail_reason"]
    assert cellar["waiting"]["stage"] == "brief" or cellar["waiting"]["status"] != "done"
    found = exits_of(data)
    assert found[ROOM, "exit.east"]["pairing"] == "paired"
    assert found[STREET, "exit.west"]["pairing"] == "paired"
    assert found[THIRD, "exit.up"]["pairing"] == "unpaired" and found[THIRD, "exit.up"]["code"] == "exit.not_paired"
    assert found[THIRD, "exit.up"]["reason"]


def test_an_exit_to_a_room_outside_the_district_is_outside_and_checked_against_the_project(project: Kiripix) -> None:
    three_rooms(project)

    found = exits_of(district(project, "room.al*")["data"])

    assert found[ROOM, "exit.east"]["pairing"] == "outside" and found[ROOM, "exit.east"]["reason"] is None
    project.json("undo", STREET, "place")
    put(project, STREET, "exit.west", "exit", at=(30, 12), target_room="room.nowhere", target_exit="exit.east")
    broken = exits_of(district(project, "room.al*")["data"])[ROOM, "exit.east"]
    assert broken["pairing"] == "outside" and broken["code"] == "exit.not_paired" and broken["reason"]


def test_the_exit_side_comes_from_the_brief(project: Kiripix) -> None:
    two_paired_rooms(project)
    project.json("set", ROOM, "brief", "exits=exit.east:right, door:top")

    found = exits_of(district(project, ROOM)["data"])

    assert found[ROOM, "exit.east"]["side"] == "right"
    assert exits_of(district(project, STREET)["data"])[STREET, "exit.west"]["side"] is None


def test_a_second_call_writes_no_thumbnail(project: Kiripix) -> None:
    three_rooms(project)
    first = district(project)["data"]
    written = previews(project)
    assert len(written) == 2

    again = district(project)["data"]

    assert previews(project) == written and again["rooms"] == first["rooms"]


def test_links_are_listed_with_their_room(project: Kiripix) -> None:
    two_paired_rooms(project)
    link = {"decision": "link", "data": {"id": "hop.fence", "from": [20, 16], "to": [40, 16], "kind": "hop",
                                         "two_way": False}}
    project.json("decide", ROOM, "place", "--decision", json.dumps(link))

    data = district(project)["data"]

    assert data["links"] == [{"room": ROOM, "id": "hop.fence", "kind": "hop", "two_way": False, "start": [20, 16],
                              "end": [40, 16]}]


def test_another_kind_is_left_out_with_an_info_finding_and_a_missed_glob_is_refused(project: Kiripix) -> None:
    two_paired_rooms(project)
    make_demo(project, "a")

    result = district(project, "[dr][eo]*")

    assert [r["asset"] for r in result["data"]["rooms"]] == [ROOM, STREET]
    [note] = [f for f in result["findings"] if f["code"] == "district.not_a_room"]
    assert note["severity"] == "info" and "demo.a" in note["message"]
    assert project.json("district", "zz*", expect=1)["findings"][0]["code"] == "match.none"
