"""Foreground Layers in the room's exported scene (ticket 0047, D3 of 0037): a Sprite2D per Layer under a y-sorted
parent at its sort position, "always above" Layers over the actors, each Layer's PNG owned like any other file, and its
ID frozen. With no Layers the scene is the M1 scene."""

import json
from pathlib import Path
from typing import Any

from conftest import Kiripix
from PIL import Image
from test_export import MANIFEST, PLATE, SCENE, godot_project, manifest, node, scene, set_target, times
from test_layers_stage import ROOM, accept, click, lift
from test_layers_stage import built_room as layers_room
from test_masks import decide
from test_place import above, line, place

LAMP_PNG = "game/kiripix/room/alley/layer.lamp.png"
CRATE_PNG = "game/kiripix/room/alley/layer.crate.png"
LAMP_RES = "res://kiripix/room/alley/layer.lamp.png"
CRATE_RES = "res://kiripix/room/alley/layer.crate.png"


def layered_room(project: Kiripix) -> Path:
    """Two Layers, `lamp` sorted at y 20 by a line and `crate` flagged above, a wall, a Spawn, a target, all built."""
    folder = layers_room(project)
    click(project, "lamp", 8, 8)
    click(project, "crate", 40, 24)
    lift(project)
    accept(project)
    decide(project, "flood", {"x": 0, "y": 0, "mask": "solid"})
    place(project, "spawn.main", "spawn")
    line(project, "lamp")
    above(project, "crate")
    godot_project(project)
    set_target(project)
    project.json("run", ROOM)
    return folder


def room_json(folder: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((folder / "out" / "export" / "room.json").read_text("utf-8"))
    return value


def test_room_json_lists_each_layer_with_its_file_and_sort_position(project: Kiripix) -> None:
    folder = layered_room(project)

    room = room_json(folder)

    assert room["schema_version"] == 2
    assert room["layers"] == [{"id": "lamp", "file": "layer.lamp.png", "above": False, "y": 20},
                              {"id": "crate", "file": "layer.crate.png", "above": True, "y": None}]
    out = folder / "out" / "export"
    for name in ("plate.png", "layer.lamp.png", "layer.crate.png"):
        assert (out / name).read_bytes() == (folder / "work" / "palette" / name).read_bytes()


def test_the_scene_has_a_node_per_layer_at_its_sort_position_and_the_manifest_lists_them(project: Kiripix) -> None:
    layered_room(project)

    data = project.json("export", ROOM)["data"]

    assert sorted(data["written"]) == sorted([
        "res://kiripix/room/alley/alley.tscn", "res://kiripix/room/alley/plate.png", LAMP_RES, CRATE_RES])
    text = scene(project)
    assert f'[ext_resource type="Texture2D" path="{LAMP_RES}" id="layer_lamp"]' in text
    assert "y_sort_enabled = true" in node(text, "alley")
    assert "y_sort_enabled = true" in node(text, "Foreground", ".")
    lamp = node(text, "lamp", "Foreground")
    assert 'type="Sprite2D"' in lamp and 'texture = ExtResource("layer_lamp")' in lamp and "centered = false" in lamp
    assert "position = Vector2(0, 20)" in lamp and "offset = Vector2(0, -20)" in lamp
    assert 'metadata/kiripix_id = "lamp"' in lamp
    crate = node(text, "crate", "Above")
    assert 'texture = ExtResource("layer_crate")' in crate and "position" not in crate
    assert "z_index = 100" in node(text, "Above", ".")
    assert text.index('name="Plate"') < text.index('name="Foreground"') < text.index('name="Above"')
    assert "load_steps=5 " in text, "three images and the navigation, and one more"
    record = manifest(project)
    assert record["ids"]["layers"] == ["plate", "crate", "lamp"]
    assert record["ids"]["markers"] == ["spawn.main"], "a y-sort line makes no node, so its ID isn't frozen"
    assert {LAMP_RES, CRATE_RES} <= set(record["files"])
    assert "ysort-lamp" not in text


def test_the_exported_plate_is_the_mapped_plate_not_the_composite(project: Kiripix) -> None:
    folder = layered_room(project)
    project.json("export", ROOM)

    with Image.open(project.cwd / PLATE) as plate, Image.open(folder / "work" / "palette" / "palette.png") as composite:
        assert plate.tobytes() != composite.tobytes()
    assert (project.cwd / PLATE).read_bytes() == (folder / "work" / "palette" / "plate.png").read_bytes()


def test_the_scene_is_byte_identical_across_a_rebuild(project: Kiripix) -> None:
    folder = layered_room(project)
    project.json("export", ROOM)
    before = (project.cwd / SCENE).read_bytes()
    counter = manifest(project)["counter"]

    project.json("run", ROOM, "export", "--force")
    data = project.json("export", ROOM)["data"]

    assert (project.cwd / SCENE).read_bytes() == before and b"\r" not in before
    assert data["written"] == [] and data["counter"] == counter
    assert room_json(folder)["layers"][0]["y"] == 20


def test_moving_the_line_changes_only_the_scene(project: Kiripix) -> None:
    layered_room(project)
    project.json("export", ROOM)

    line(project, "lamp", y=24)
    project.json("run", ROOM)
    data = project.json("export", ROOM)["data"]

    assert data["written"] == ["res://kiripix/room/alley/alley.tscn"] and data["counter"] == 2
    assert "position = Vector2(0, 24)" in scene(project) and "offset = Vector2(0, -24)" in scene(project)


def test_removing_an_exported_layer_fails_with_id_frozen(project: Kiripix) -> None:
    layered_room(project)
    project.json("export", ROOM)

    project.json("undo", ROOM, "layers")  # the crate's click
    project.json("undo", ROOM, "layers")  # the lamp's
    project.json("run", ROOM, "layers", "--rerun")
    project.json("run", ROOM, expect=3)
    project.json("accept", ROOM, "masks", owner=True)
    project.json("run", ROOM, expect=2)  # the line and the flag now name no Layer
    result = project.json("export", ROOM, expect=2)

    frozen = [f for f in result["findings"] if f["code"] == "export.id_frozen"]
    assert {"crate", "lamp"} <= {name for f in frozen for name in ("crate", "lamp") if f"'{name}'" in f["message"]}
    assert (project.cwd / LAMP_PNG).is_file() and (project.cwd / CRATE_PNG).is_file()


def test_a_layer_png_the_game_edited_is_refused_like_any_other_file(project: Kiripix) -> None:
    layered_room(project)
    project.json("export", ROOM)
    (project.cwd / LAMP_PNG).write_bytes(b"the game's own")
    before = times(project)

    result = project.json("export", ROOM, expect=3)

    [finding] = [f for f in result["findings"] if f["code"] == "export.file_changed"]
    assert LAMP_RES in finding["message"] and "--force" in finding["owner_action"]
    assert (project.cwd / LAMP_PNG).read_bytes() == b"the game's own" and times(project) == before

    project.json("export", ROOM, "--force", expect=0)
    assert (project.cwd / LAMP_PNG).read_bytes() != b"the game's own"
    assert (project.cwd / MANIFEST).is_file()


def test_with_no_layers_the_scene_has_no_foreground_and_the_plate_is_palette_png(project: Kiripix) -> None:
    folder = layers_room(project)
    decide(project, "flood", {"x": 0, "y": 0, "mask": "solid"})
    place(project, "spawn.main", "spawn")
    godot_project(project)
    set_target(project)
    project.json("run", ROOM)

    project.json("export", ROOM)

    text = scene(project)
    assert "Foreground" not in text and "Above" not in text and "y_sort" not in text and "layer_" not in text
    assert manifest(project)["ids"]["layers"] == ["plate"]
    assert (project.cwd / PLATE).read_bytes() == (folder / "work" / "palette" / "palette.png").read_bytes()
    before = times(project)
    project.json("run", ROOM, "export", "--force")
    data = project.json("export", ROOM)["data"]
    assert data["written"] == [] and data["counter"] == 1 and times(project) == before


def test_an_exported_room_with_a_layer_left_unsorted_still_shows_and_its_export_is_refused(project: Kiripix) -> None:
    """Exported, then `crate`'s above flag undone and rebuilt: `export` Stage is built with `crate` neither sorted nor
    above. Working out whether the game is behind must not build its scene; the export refuses it and writes nothing."""
    layered_room(project)
    project.json("export", ROOM)
    before = times(project)
    project.json("undo", ROOM, "place")
    project.json("run", ROOM, expect=2)

    project.json("show", ROOM)
    project.json("status")
    findings = project.json("export", ROOM, expect=2)["findings"]

    assert [f["code"] for f in findings if f["severity"] == "error"] == ["layer.no_ysort"]
    assert times(project) == before


def test_an_m1_build_is_refused_naming_the_rebuild_and_then_exports_nothing(project: Kiripix) -> None:
    """An M1 room exported, then its built room.json as M1 left it (schema 1, no `layers`): after the rebuild the export
    writes nothing and leaves the counter alone."""
    folder = layers_room(project)
    decide(project, "flood", {"x": 0, "y": 0, "mask": "solid"})
    place(project, "spawn.main", "spawn")
    godot_project(project)
    set_target(project)
    project.json("run", ROOM)
    project.json("export", ROOM)
    before = times(project)
    path = folder / "out" / "export" / "room.json"
    built = json.loads(path.read_text("utf-8"))
    del built["layers"]
    path.write_text(json.dumps({**built, "schema_version": 1}), "utf-8")

    [finding] = project.json("export", ROOM, expect=1)["findings"]
    assert finding["code"] == "export.room_invalid" and finding["fix"] == f"kiripix run {ROOM} export --force"

    project.json("run", ROOM, "export", "--force")
    data = project.json("export", ROOM)["data"]
    assert data["written"] == [] and data["counter"] == 1 and times(project) == before
