"""Frame Loops in the game (ticket 0195, spec §9): a Layer a Loop moves shows the Loop's strip in its own Sprite2D, at the
same sort position; the Plate under it is the filled Plate; strips wrap into rows; a strip over 4096 x 4096 is refused."""

import json
import re
from pathlib import Path
from typing import Any

from conftest import Kiripix
from PIL import Image
from test_export import godot_project, scene, set_target
from test_export_looks import FOLDER, RES, exported_room, node
from test_layers_stage import ROOM, rgba
from test_loop_kit import KIT, TRIANGLE, painted
from test_loops import WHOLE, tiles
from test_looks_build import room_with_a_lamp_layer
from test_masks import decide as decide_mask
from test_place import line, place

SWAY = "lamp_sway"
FLAME = "flame"


def decide(project: Kiripix, decision: str, data: dict[str, Any], expect: int = 0) -> dict[str, Any]:
    return project.json("decide", ROOM, "loops", "--decision", json.dumps({"decision": decision, "data": data}), expect=expect)


def exportable_room(project: Kiripix) -> Path:
    """The lamp room with its sort line, its Godot project and target, ready for Loops to be declared."""
    folder = room_with_a_lamp_layer(project)
    decide_mask(project, "flood", {"x": 0, "y": 0, "mask": "solid"})
    place(project, "spawn.main", "spawn")
    line(project, "lamp")
    godot_project(project)
    set_target(project)
    return folder


def moving_room(project: Kiripix) -> Path:
    """A `sway` Loop that moves the lamp Layer, and a kit Loop on the Plate (and over the Layer), every Stage built."""
    folder = exportable_room(project)
    decide(project, "loop", {"loop": SWAY, "form": "frames", "layer": "lamp"})
    decide(project, "frames", {"loop": SWAY, "op": "sway", "params": {"amplitude": 2}})
    decide(project, "loop", {"loop": FLAME, "form": "frames"})
    decide(project, "polygon", {"loop": FLAME, "points": TRIANGLE})
    project.json("run", ROOM, "masks")
    project.json("run", ROOM, "palette")
    project.json("loop", "kit", ROOM, FLAME, KIT, "--frames", "2")
    painted(project, 1)
    project.json("import", ROOM, project.cwd / KIT / "frame_001.png", "--loop", FLAME)
    project.json("run", ROOM)
    return folder


def test_a_moving_layer_shows_its_strip_at_the_same_sort_position(project: Kiripix) -> None:
    moving_room(project)

    data = project.json("export", ROOM)["data"]

    room = exported_room(project)
    [flame, sway] = sorted(room["loops"], key=lambda loop: loop["id"] != FLAME)
    assert sway["source"] == "op" and sway["moves_layer"] is True and sway["file"] is None
    assert [piece["layer"] for piece in sway["pieces"]] == ["lamp"] and sway["frames"] == 4
    assert flame["source"] == "kit" and flame["moves_layer"] is False and flame["frames"] == 2
    [lamp] = [layer for layer in room["layers"] if layer["id"] == "lamp"]
    y = lamp["y"]
    text = scene(project)
    layer = node(text, "lamp", "Foreground")
    x0, y0 = sway["box"][:2]
    for expected in ("Sprite2D", "centered = false", f"offset = Vector2({x0}, {y0 - y})", f"hframes = {sway['hframes']}",
                     f"vframes = {sway['vframes']}", "frame = 0", 'metadata/kiripix_id = "lamp"',
                     f'metadata/kiripix_loop = "{SWAY}"', 'metadata/kiripix_type = "loop"',
                     "metadata/sequence = PackedInt32Array(", "metadata/phase = 0"):
        assert expected in layer, expected
    if y:
        assert f"position = Vector2(0, {y})" in layer
    assert f'texture = ExtResource("loop_{SWAY}_lamp")' in layer and "layer_lamp" not in text
    assert not re.search(rf'name="{SWAY}"', text), "no second node for the Layer's Loop"
    child = node(text, FLAME, "Foreground/lamp")  # the kit Loop's piece over the Layer is still a child
    assert 'metadata/kiripix_type = "loop"' in child and 'metadata/kiripix_id = "flame"' in child
    assert f"{RES}/{sway['pieces'][0]['file']}" in data["written"] and f"{RES}/{lamp['file']}" in data["written"]


def test_frame_zero_is_the_exported_layer_and_the_plate_under_it_is_the_filled_plate(project: Kiripix) -> None:
    folder = moving_room(project)
    project.json("export", ROOM)

    exported = project.cwd / FOLDER
    room = exported_room(project)
    [sway] = [loop for loop in room["loops"] if loop["id"] == SWAY]
    [lamp] = [layer for layer in room["layers"] if layer["id"] == "lamp"]
    layer = rgba(exported / lamp["file"])
    x, y, width, height = sway["box"]
    first = tiles(exported / sway["pieces"][0]["file"], sway["box"], sway["frames"], sway["hframes"])[0]
    shown = first[..., 3] > 0
    assert shown.any() and (first[shown] == layer[y:y + height, x:x + width][shown]).all()
    assert (first[..., 3] > 0).sum() == (layer[y:y + height, x:x + width, 3] > 0).sum(), "frame 0 is the whole Layer"
    filled = folder / "work" / "palette" / "plate.png"
    assert (exported / "plate.png").read_bytes() == filled.read_bytes(), "the mapped, filled Plate"
    covered = layer[..., 3] > 0
    composite = rgba(folder / "work" / "palette" / "palette.png")
    assert (rgba(exported / "plate.png")[covered] != composite[covered]).any(), "not the composite under the Layer"


def test_a_strip_over_4096_px_wraps_into_rows_and_room_json_carries_both(project: Kiripix) -> None:
    exportable_room(project)
    decide(project, "loop", {"loop": FLAME, "form": "frames"})
    decide(project, "polygon", {"loop": FLAME, "points": WHOLE})
    decide(project, "frames", {"loop": FLAME, "op": "shimmer", "params": {"frames": 150}})
    project.json("run", ROOM)

    project.json("export", ROOM)

    [loop] = exported_room(project)["loops"]
    assert loop["frames"] == 150 and loop["hframes"] == 4096 // loop["box"][2] and loop["vframes"] == 2
    assert loop["source"] == "op" and loop["moves_layer"] is False
    with Image.open(project.cwd / FOLDER / loop["file"]) as strip:
        assert strip.width == loop["hframes"] * loop["box"][2] <= 4096
        assert strip.height == loop["vframes"] * loop["box"][3]
    assert f"vframes = {loop['vframes']}" in scene(project)


def test_a_strip_over_4096_x_4096_is_refused(project: Kiripix) -> None:
    exportable_room(project)
    decide(project, "loop", {"loop": FLAME, "form": "frames"})
    decide(project, "polygon", {"loop": FLAME, "points": WHOLE})
    decide(project, "frames", {"loop": FLAME, "op": "shimmer", "params": {"frames": 18600}})
    project.json("run", ROOM, expect=2)

    result = project.json("export", ROOM, expect=2)

    [finding] = [f for f in result["findings"] if f["code"] == "export.loop_too_large"]
    assert finding["severity"] == "error" and finding["fix"] is None and FLAME in finding["message"]
    assert "fewer frames" in finding["owner_action"]
    assert not (project.cwd / FOLDER / "room.json").exists()


def test_a_region_whose_box_holds_the_layer_but_not_all_its_pixels_does_not_take_the_layer(project: Kiripix) -> None:
    """An L-shaped region round the lamp: its box holds the whole Layer, but the region doesn't, so the strip stays a child
    piece and the Layer keeps its own texture (the pixels outside the region must not vanish in the game)."""
    exportable_room(project)
    decide(project, "loop", {"loop": SWAY, "form": "frames", "layer": "lamp"})
    decide(project, "polygon", {"loop": SWAY, "points": [[1, 1], [30, 1], [30, 4], [4, 4], [4, 30], [1, 30]]})
    decide(project, "frames", {"loop": SWAY, "op": "sway", "params": {"amplitude": 2}})
    project.json("run", ROOM)

    project.json("export", ROOM)

    [sway] = exported_room(project)["loops"]
    assert sway["moves_layer"] is False
    text = scene(project)
    assert 'texture = ExtResource("layer_lamp")' in node(text, "lamp", "Foreground")
    assert 'metadata/kiripix_type = "loop"' in node(text, SWAY, "Foreground/lamp")
