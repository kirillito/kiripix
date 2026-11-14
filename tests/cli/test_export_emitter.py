"""An emitter's shape, direction and colours in the exported scene (ticket 0186, spec §9): metadata relative to the node, read
from `room.json` only."""

import json
import re

from conftest import Kiripix
from test_emitter import emitter, with_palette
from test_export import SCENE, godot_project, node, scene, set_target
from test_masks import ROOM
from test_place import place, walled_room

ON = ("#C8BEAA", "#283CC8")  # on the palette once `with_palette` has run


def exported(project: Kiripix) -> str:
    place(project, "spawn.main", "spawn")
    godot_project(project)
    set_target(project)
    project.json("run", ROOM)
    project.json("export", ROOM)
    return scene(project)


def test_an_emitter_of_each_shape_type_exports_its_shape_relative_to_the_node(project: Kiripix) -> None:
    folder = walled_room(project)
    with_palette(project)
    emitter(project, "a", (30, 8), shape={"type": "point"})
    emitter(project, "b", (24, 8), shape={"type": "line", "x2": 40, "y2": 12})
    emitter(project, "c", (24, 12), shape={"type": "box", "x2": 40, "y2": 20}, direction={"x": 24, "y": 4},
            colours=list(ON))
    emitter(project, "d", (24, 12), shape={"type": "polygon", "points": [[24, 12], [40, 12], [32, 20]]})

    text = exported(project)

    a, b, c, d = (node(text, name, "Emitters") for name in "abcd")
    assert 'metadata/shape_type = "point"' in a and "metadata/shape =" not in a
    assert 'metadata/shape_type = "line"' in b and "metadata/shape = PackedVector2Array(0, 0, 16, 4)" in b
    assert 'metadata/shape_type = "box"' in c
    assert "metadata/shape = PackedVector2Array(0, 0, 16, 0, 16, 8, 0, 8)" in c
    assert "metadata/direction = Vector2(0, -8)" in c
    assert 'metadata/shape_type = "polygon"' in d
    assert "metadata/shape = PackedVector2Array(0, 0, 16, 0, 8, 8)" in d
    # the colours are opaque: every fourth value is 1
    colours = re.search(r"metadata/colours = PackedColorArray\(([^)]*)\)", c)
    assert colours
    values = [float(value) for value in colours.group(1).split(",")]
    assert len(values) == 8 and values[3] == 1 and values[7] == 1
    assert [round(value * 255) for value in values[:3]] == [0xC8, 0xBE, 0xAA]
    assert [round(value * 255) for value in values[4:7]] == [0x28, 0x3C, 0xC8]
    # the scene agrees with room.json
    room = json.loads((folder / "out" / "export" / "room.json").read_text("utf-8"))
    by_id = {marker["id"]: marker for marker in room["markers"]}
    assert by_id["c"]["direction"] == {"x": 24, "y": 4} and by_id["c"]["colours"] == list(ON)
    assert by_id["d"]["shape"]["points"] == [[24, 12], [40, 12], [32, 20]]


def test_an_emitter_with_no_new_fields_exports_the_node_it_always_did(project: Kiripix) -> None:
    walled_room(project)
    emitter(project, "steam", (32, 9))

    text = exported(project)

    assert node(text, "steam", "Emitters") == (
        '[node name="steam" type="GPUParticles2D" parent="Emitters"]\n'
        "position = Vector2(32, 9)\n"
        "emitting = false\n"
        'metadata/kiripix_id = "steam"\n'
        'metadata/kiripix_type = "emitter"\n'
        'metadata/emitter = "steam_pipe"\n')


def test_the_same_room_exports_the_same_bytes(project: Kiripix) -> None:
    walled_room(project)
    with_palette(project)
    emitter(project, "c", (24, 12), shape={"type": "box", "x2": 40, "y2": 20}, direction={"x": 24, "y": 4},
            colours=list(ON))
    first = exported(project)

    project.json("export", ROOM, "--force")

    assert (project.cwd / SCENE).read_text("utf-8") == first
