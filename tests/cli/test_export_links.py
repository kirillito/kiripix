"""A Link in the Godot scene and in `room.json` (ticket 0267, spec §9): a `Links` node with a `Node2D` per Link and two
`Marker2D` ends, its metadata, the Manifest's own list of Link IDs, and the freeze of them."""

import json
import re
from typing import Any

from conftest import Kiripix
from test_export import MANIFEST, ROOM, godot_project, manifest, node, scene, set_target
from test_place import link, place, walled_room

FOLDER = "game/kiripix/room/alley"


def exported_links(project: Kiripix) -> None:
    """walled_room's Plate is 48 x 32, with `solid` on the left 16 columns."""
    walled_room(project)
    place(project, "spawn.main", "spawn")
    link(project, "hop.down", (24, 8), (40, 24), two_way=False)
    link(project, "climb.up", (30, 26), (40, 10), kind="climb")
    godot_project(project)
    set_target(project)
    project.json("run", ROOM)
    project.json("export", ROOM)


def room_json(project: Kiripix) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((project.cwd / FOLDER / "room.json").read_text("utf-8"))
    return value


def test_a_link_is_a_node2d_with_two_marker2d_ends_and_its_metadata(project: Kiripix) -> None:
    exported_links(project)

    text = scene(project)

    assert '[node name="Links" type="Node2D" parent="."]' in text
    hop = node(text, "hop-down", "Links")
    assert 'type="Node2D"' in hop
    assert 'metadata/kiripix_id = "hop.down"' in hop and 'metadata/kiripix_type = "link"' in hop
    assert 'metadata/kind = "hop"' in hop and "metadata/two_way = false" in hop
    assert '[node name="from" type="Marker2D" parent="Links/hop-down"]\nposition = Vector2(24, 8)\n' in text
    assert '[node name="to" type="Marker2D" parent="Links/hop-down"]\nposition = Vector2(40, 24)\n' in text
    climb = node(text, "climb-up", "Links")
    assert 'metadata/kind = "climb"' in climb and "metadata/two_way = true" in climb
    assert '[node name="from" type="Marker2D" parent="Links/climb-up"]\nposition = Vector2(30, 26)\n' in text
    assert '[node name="to" type="Marker2D" parent="Links/climb-up"]\nposition = Vector2(40, 10)\n' in text
    assert text.index('name="Links"') > text.index('name="Markers"')  # after the Markers, in ID order below
    assert text.index('name="climb-up"') < text.index('name="hop-down"')


def test_room_json_lists_the_links_and_has_the_new_schema_version(project: Kiripix) -> None:
    exported_links(project)

    room = room_json(project)

    assert room["schema_version"] == 12
    assert room["links"] == [
        {"id": "climb.up", "kind": "climb", "from": [30, 26], "to": [40, 10], "two_way": True},
        {"id": "hop.down", "kind": "hop", "from": [24, 8], "to": [40, 24], "two_way": False},
    ]
    assert [m["id"] for m in room["markers"]] == ["spawn.main"]


def test_the_manifest_lists_link_ids_in_their_own_list(project: Kiripix) -> None:
    exported_links(project)

    ids = manifest(project)["ids"]

    assert ids["links"] == ["climb.up", "hop.down"] and ids["markers"] == ["spawn.main"]


def test_a_room_with_no_link_has_no_links_node_and_no_links_in_its_manifest(project: Kiripix) -> None:
    walled_room(project)
    place(project, "spawn.main", "spawn")
    godot_project(project)
    set_target(project)
    project.json("run", ROOM)
    project.json("export", ROOM)

    assert "Links" not in scene(project) and "links" not in manifest(project)["ids"]
    assert room_json(project)["links"] == []


def test_a_re_export_of_the_unchanged_room_writes_nothing(project: Kiripix) -> None:
    exported_links(project)
    before = (project.cwd / FOLDER / "alley.tscn").read_bytes()

    assert project.json("export", ROOM)["data"]["written"] == []
    assert (project.cwd / FOLDER / "alley.tscn").read_bytes() == before and b"\r" not in before


def test_moving_an_exported_link_is_allowed_and_rewrites_the_scene(project: Kiripix) -> None:
    exported_links(project)

    link(project, "hop.down", (24, 8), (40, 22), two_way=False)
    project.json("run", ROOM)
    project.json("export", ROOM)

    assert "position = Vector2(40, 22)" in scene(project)


def test_a_new_link_is_a_new_id_and_is_allowed(project: Kiripix) -> None:
    exported_links(project)

    link(project, "jump.gap", (24, 20), (40, 20), kind="jump")
    project.json("run", ROOM)
    project.json("export", ROOM)

    assert manifest(project)["ids"]["links"] == ["climb.up", "hop.down", "jump.gap"]


def test_renaming_an_exported_link_is_refused_naming_the_id(project: Kiripix) -> None:
    exported_links(project)
    assert (project.cwd / MANIFEST).is_file()

    project.json("undo", ROOM, "place")  # the climb's Decision
    link(project, "climb.ladder", (30, 26), (40, 10), kind="climb")
    project.json("run", ROOM)
    result = project.json("export", ROOM, expect=2)

    frozen = [f for f in result["findings"] if f["code"] == "export.id_frozen"]
    assert [f["message"].split("'")[1] for f in frozen] == ["climb.up"]
    assert "Link" in frozen[0]["message"]
    assert frozen[0]["owner_action"] and frozen[0]["fix"] is None
    assert "climb-up" in scene(project)
    assert re.search(r"climb-ladder", scene(project)) is None
