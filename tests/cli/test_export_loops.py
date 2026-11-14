"""A room's Loops in the game (ticket 0190, spec §9): visible strips in the scene, `room.json` listing them, files beside the
scene, the ID freeze and prune. The game steps `frame` from its own counter through `sequence`."""

import re
from pathlib import Path

from conftest import Kiripix
from test_export import MANIFEST, godot_project, manifest, scene, set_target
from test_export_looks import FOLDER, RES, exported_room, node
from test_layers_stage import ROOM, rgba
from test_loops import LOOP, WHOLE, colours, decide, tiles
from test_looks_build import room_with_a_lamp_layer
from test_masks import decide as decide_mask
from test_place import line, place

ON_LAYER = "lamp_pulse"


def looping_room(project: Kiripix, plain: bool = False) -> Path:
    """The lamp room with a Plate Loop over the lamp's Layer (and a light), a Loop on the Layer itself, every Stage built."""
    folder = room_with_a_lamp_layer(project)
    c = colours(folder)
    decide_mask(project, "flood", {"x": 0, "y": 0, "mask": "solid"})
    place(project, "spawn.main", "spawn")
    line(project, "lamp")
    place(project, "light.glow", "light", colour="#ffd080", radius=20, energy=1.0)
    godot_project(project)
    set_target(project)
    if not plain:
        decide(project, "loop", {"loop": LOOP, "light": "light.glow", "phase": 3})
        decide(project, "polygon", {"loop": LOOP, "points": WHOLE})
        decide(project, "cycle", {"loop": LOOP, "colours": [c["floor"], c["lamp"], c["wall"]]})
        decide(project, "timing", {"loop": LOOP, "ticks": 6})
        decide(project, "loop", {"loop": ON_LAYER, "layer": "lamp"})
        decide(project, "polygon", {"loop": ON_LAYER, "points": WHOLE})
        decide(project, "cycle", {"loop": ON_LAYER, "colours": [c["lamp"], c["crate"]]})
    project.json("run", ROOM)
    return folder


def test_loops_export_nodes_metadata_files_and_room_json(project: Kiripix) -> None:
    folder = looping_room(project)

    data = project.json("export", ROOM)["data"]

    room = exported_room(project)
    [glow, pulse] = room["loops"]
    assert glow["id"] == LOOP and pulse["id"] == ON_LAYER
    assert glow["form"] == "cycle" and glow["layer"] == "plate" and glow["box"] == [1, 1, 30, 30]
    assert glow["file"] == f"loops/{LOOP}/plate.png" and glow["frames"] == 3
    assert glow["hframes"] * glow["vframes"] >= 3 and glow["sequence"] == [0, 6, 1, 6, 2, 6] and glow["ticks"] == 18
    assert glow["phase"] == 3 and glow["light"] == "light.glow" and glow["mode"] == "rotate" and len(glow["colours"]) == 3
    assert glow["pieces"] == [{"layer": "lamp", "file": f"loops/{LOOP}/layer.lamp.png", "box": glow["box"]}]
    assert glow["index"] == f"loops/{LOOP}/index.png"
    assert pulse["file"] is None and pulse["light"] is None and pulse["phase"] == 0
    assert [p["layer"] for p in pulse["pieces"]] == ["lamp"] and pulse["layer"] == "lamp"

    text = scene(project)
    assert re.search(r'^\[node name="Loops" type="Node2D" parent="\."\]$', text, re.MULTILINE)
    sprite = node(text, LOOP, "Loops")
    for expected in ("Sprite2D", "centered = false", "position = Vector2(1, 1)", f"hframes = {glow['hframes']}",
                     f"vframes = {glow['vframes']}", "frame = 0", 'material = SubResource("loop_unshaded")',
                     f'metadata/kiripix_id = "{LOOP}"', 'metadata/kiripix_type = "loop"',
                     "metadata/sequence = PackedInt32Array(0, 6, 1, 6, 2, 6)", "metadata/phase = 3",
                     'metadata/light = "light.glow"'):
        assert expected in sprite, expected
    assert "visible = false" not in sprite
    assert 'type="CanvasItemMaterial"' in text and "light_mode = 1" in text and "AnimatedSprite2D" not in text
    piece = node(text, LOOP, "Foreground/lamp")
    assert "position = Vector2(1, -19)" in piece and 'metadata/kiripix_type = "loop"' in piece
    on_layer = node(text, ON_LAYER, "Foreground/lamp")
    assert "metadata/light" not in on_layer and "metadata/phase = 0" in on_layer
    assert text.index('name="Loops"') < text.index('name="Foreground"')
    for file in (glow["file"], glow["pieces"][0]["file"], glow["index"], pulse["pieces"][0]["file"], pulse["index"]):
        assert f"{RES}/{file}" in data["written"]
        assert (project.cwd / FOLDER / file).read_bytes() == (folder / "work" / "loops" / file.removeprefix("loops/")).read_bytes()
    assert manifest(project)["ids"]["loops"] == sorted([ON_LAYER, LOOP])


def test_frame_zero_of_every_strip_is_the_exported_plate_or_layer(project: Kiripix) -> None:
    folder = looping_room(project)
    project.json("export", ROOM)
    exported = project.cwd / FOLDER
    plate = rgba(exported / "plate.png")
    room = exported_room(project)
    [lamp] = [entry for entry in room["layers"] if entry["id"] == "lamp"]
    layer = rgba(exported / lamp["file"])
    for loop in room["loops"]:
        x, y, width, height = loop["box"]
        for file, base in [(loop["file"], plate)] + [(p["file"], layer) for p in loop["pieces"]]:
            if file is None:
                continue
            first = tiles(exported / file, loop["box"], loop["frames"], loop["hframes"])[0]
            shown = first[..., 3] > 0
            assert shown.any()
            assert (first[shown] == base[y:y + height, x:x + width][shown]).all(), file
    assert folder.is_dir()


def test_the_scene_and_room_json_are_byte_identical_across_a_rebuild(project: Kiripix) -> None:
    looping_room(project)
    project.json("export", ROOM)
    before = (project.cwd / FOLDER / "room.json").read_bytes(), scene(project).encode()

    project.json("run", ROOM, "export", "--rerun")
    project.json("export", ROOM)

    assert before == ((project.cwd / FOLDER / "room.json").read_bytes(), scene(project).encode())
    assert b"\r" not in before[1]


def test_a_room_with_no_loops_has_no_loop_nodes_and_an_unchanged_manifest(project: Kiripix) -> None:
    looping_room(project, plain=True)
    project.json("export", ROOM)

    assert exported_room(project)["loops"] == []
    assert not re.search(r"Loops|loop_unshaded|CanvasItemMaterial", scene(project))
    assert "loops" not in manifest(project)["ids"]


def test_renaming_an_exported_loop_is_refused_by_the_id_freeze(project: Kiripix) -> None:
    looping_room(project)
    project.json("export", ROOM)
    for _ in range(3):  # `loop`, `polygon` and `cycle`: every Decision that names the Loop on the Layer
        project.json("undo", ROOM, "loops")
    result = project.json("export", ROOM, expect=2)

    frozen = [f for f in result["findings"] if f["code"] == "export.id_frozen"]
    assert frozen and "Loop" in frozen[0]["message"] and any(f"'{ON_LAYER}'" in f["message"] for f in frozen)
    assert (project.cwd / MANIFEST).is_file() and (project.cwd / FOLDER / "loops" / ON_LAYER).is_dir()


def test_a_loop_png_the_game_edited_is_refused_by_name(project: Kiripix) -> None:
    looping_room(project)
    project.json("export", ROOM)
    path = project.cwd / FOLDER / "loops" / LOOP / "plate.png"
    path.write_bytes(b"mine")

    result = project.json("export", ROOM, expect=3)

    assert any(f["code"] == "export.file_changed" and "plate.png" in f["message"] for f in result["findings"])
    assert path.read_bytes() == b"mine", "the game's file is untouched"
