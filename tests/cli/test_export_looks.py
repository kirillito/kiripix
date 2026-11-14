"""A room's Looks in the game (ticket 0131, ADR 0009, spec §9): hidden pieces in the scene, `room.json` listing them, and
each Look's own `solid` as a Mask file and a body whose shapes start disabled. The game binds a Look by its ID."""

import json
import re
from pathlib import Path
from typing import Any

from conftest import Kiripix
from test_export import MANIFEST, SCENE, godot_project, manifest, scene, set_target
from test_layers_stage import ROOM
from test_looks_build import (
    LAMP_BOX,
    LOOK,
    decide,
    edited,
    import_and_pick,
    room_with_a_lamp_layer,
)
from test_masks import decide as decide_mask
from test_place import line, place

FOLDER = "game/kiripix/room/alley"
RES = "res://kiripix/room/alley"
SOLID = [[16, 16], [23, 16], [23, 23], [16, 23]]


def looked_room(project: Kiripix, condition: str | None = "circuit.hall:off", solid: bool = True) -> Path:
    """The lamp room with a Layer, a Look over it (with a Condition and a `solid`, or not) and every Stage built."""
    folder = room_with_a_lamp_layer(project)
    decide_mask(project, "flood", {"x": 0, "y": 0, "mask": "solid"})
    place(project, "spawn.main", "spawn")
    line(project, "lamp")
    godot_project(project)
    set_target(project)
    import_and_pick(project, edited())
    decide(project, "polygon", {"look": LOOK, "points": LAMP_BOX})
    if condition is not None:
        decide(project, "look", {"look": LOOK, "condition": condition})
    if solid:
        decide(project, "solid", {"look": LOOK, "points": SOLID})
    project.json("run", ROOM)
    return folder


def node(text: str, name: str, parent: str) -> str:
    """The section of the node `name` under `parent`, with its properties."""
    head = f'^\\[node name="{re.escape(name)}"[^\n]* parent="{re.escape(parent)}"\\]\n'
    found = re.search(head + "(?:[^\\[\n][^\n]*\n)*", text, re.MULTILINE)
    assert found, f"no node {name} under {parent} in:\n{text}"
    return found.group(0)


def exported_room(project: Kiripix) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((project.cwd / FOLDER / "room.json").read_text("utf-8"))
    return value


def test_a_look_over_a_layer_with_a_solid_exports_hidden_nodes_with_metadata(project: Kiripix) -> None:
    folder = looked_room(project)

    data = project.json("export", ROOM)["data"]

    text = scene(project)
    plate = node(text, LOOK, "Looks")
    assert "visible = false" in plate and f'metadata/kiripix_id = "{LOOK}"' in plate
    assert 'metadata/condition = "circuit.hall:off"' in plate and "position = Vector2(1, 1)" in plate
    piece = node(text, LOOK, "Foreground/lamp")
    assert "visible = false" in piece and f'metadata/kiripix_id = "{LOOK}"' in piece
    assert "position = Vector2(1, -19)" in piece, "relative to the Layer's sort line at y 20"
    body = node(text, LOOK, "LookSolids")
    assert "StaticBody2D" in body and "collision_layer = 1" in body
    polygon = node(text, "polygon_0", f"LookSolids/{LOOK}")
    assert "disabled = true" in polygon
    assert f"{RES}/looks/{LOOK}/plate.png" in data["written"] and f"{RES}/looks/{LOOK}/layer.lamp.png" in data["written"]
    assert f"{RES}/masks/{LOOK}.solid.png" in data["written"]
    out = folder / "work" / "looks"
    exported = project.cwd / FOLDER
    assert (exported / "masks" / f"{LOOK}.solid.png").read_bytes() == (out / LOOK / "solid.png").read_bytes()
    assert (exported / "looks" / LOOK / "plate.png").read_bytes() == (out / LOOK / "plate.png").read_bytes()
    room = exported_room(project)
    [look] = room["looks"]
    assert look["id"] == LOOK and look["condition"] == "circuit.hall:off" and look["box"] == [1, 1, 19, 19]
    assert look["file"] == f"looks/{LOOK}/plate.png"
    assert look["pieces"] == [{"layer": "lamp", "file": f"looks/{LOOK}/layer.lamp.png"}]
    assert look["solid"] == f"masks/{LOOK}.solid.png" and look["collision"]["solid"]
    assert room["masks"][f"{LOOK}.solid"] == f"masks/{LOOK}.solid.png"
    listed = manifest(project)
    assert f"{RES}/masks/{LOOK}.solid.png" in listed["files"] and listed["ids"]["looks"] == [LOOK]


def test_a_look_with_no_condition_has_null_in_room_json_and_no_condition_metadata(project: Kiripix) -> None:
    looked_room(project, condition=None, solid=False)
    project.json("export", ROOM)

    [look] = exported_room(project)["looks"]

    assert look["condition"] is None and look["solid"] is None and look["collision"] == {}
    assert "metadata/condition" not in scene(project) and "LookSolids" not in scene(project)


def test_the_scene_is_byte_identical_across_a_rebuild(project: Kiripix) -> None:
    looked_room(project)
    project.json("export", ROOM)
    before = (project.cwd / SCENE).read_bytes(), (project.cwd / FOLDER / "room.json").read_bytes()

    project.json("run", ROOM, "export", "--rerun")
    project.json("export", ROOM)

    assert before == ((project.cwd / SCENE).read_bytes(), (project.cwd / FOLDER / "room.json").read_bytes())
    assert b"\r" not in before[0]


def test_a_room_with_no_looks_has_no_look_nodes(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    decide_mask(project, "flood", {"x": 0, "y": 0, "mask": "solid"})
    place(project, "spawn.main", "spawn")
    line(project, "lamp")
    godot_project(project)
    set_target(project)
    project.json("run", ROOM)
    project.json("export", ROOM)

    assert not re.search(r"Looks|LookSolids", scene(project)) and exported_room(project)["looks"] == []
    assert "looks" not in manifest(project)["ids"], "the Manifest of a room with no Looks is as it was"
    assert folder.is_dir()


def test_removing_an_exported_look_is_refused_by_the_id_freeze(project: Kiripix) -> None:
    looked_room(project)
    project.json("export", ROOM)
    for _ in range(4):  # the pick, the Condition, the region and the `solid`: every Decision that names the Look
        project.json("undo", ROOM, "looks")

    result = project.json("export", ROOM, expect=2)

    frozen = [f for f in result["findings"] if f["code"] == "export.id_frozen"]
    assert frozen and f"'{LOOK}'" in frozen[0]["message"] and "Look" in frozen[0]["message"]
    assert (project.cwd / MANIFEST).is_file() and (project.cwd / FOLDER / "looks" / LOOK / "plate.png").is_file()


def test_a_look_png_the_game_edited_is_refused_by_name(project: Kiripix) -> None:
    looked_room(project)
    project.json("export", ROOM)
    (project.cwd / FOLDER / "looks" / LOOK / "plate.png").write_bytes(b"mine")

    result = project.json("export", ROOM, expect=3)

    assert any(f["code"] == "export.file_changed" and "plate.png" in f["message"] for f in result["findings"])
