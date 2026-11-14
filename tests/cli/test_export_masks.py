"""The Masks and `room.json` in the game (ticket 0140, spec §9): `masks/solid.png` and `masks/pit.png` beside the scene,
byte for byte what the `masks` Stage built, and `room.json` listing them. The Manifest owns them like any exported file."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from conftest import Kiripix
from PIL import Image
from test_export import MANIFEST, SCENE, exportable_room, manifest, node, scene
from test_export_ownership import backups
from test_masks import ROOM
from test_place import findings

FOLDER = "game/kiripix/room/alley"
RES = "res://kiripix/room/alley"
MASK_FILES = ("masks/pit.png", "masks/solid.png", "room.json")


def built_mask(folder: Path, name: str) -> Path:
    return folder / "work" / "masks" / f"{name}.png"


def test_the_masks_and_room_json_are_written_beside_the_scene(project: Kiripix) -> None:
    folder = exportable_room(project)

    data = project.json("export", ROOM)["data"]

    for name in ("solid", "pit"):
        exported = project.cwd / FOLDER / "masks" / f"{name}.png"
        assert exported.read_bytes() == built_mask(folder, name).read_bytes(), "pixel-equal to the `masks` Stage's output"
        with Image.open(exported) as image:
            assert image.mode == "1" and image.size == (48, 32)
        assert f"{RES}/masks/{name}.png" in data["written"]
    with Image.open(project.cwd / FOLDER / "masks" / "solid.png") as image:
        assert int(np.asarray(image).sum()) == 16 * 32  # the left wall
    exported_room = json.loads((project.cwd / FOLDER / "room.json").read_text("utf-8"))
    assert exported_room == json.loads((folder / "out" / "export" / "room.json").read_text("utf-8"))
    assert exported_room["masks"] == {"pit": "masks/pit.png", "solid": "masks/solid.png"}
    assert f"{RES}/room.json" in data["written"]


def test_the_scene_root_names_room_json(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)

    root = node(scene(project), "alley")

    assert f'metadata/kiripix_room = "{RES}/room.json"' in root


def test_the_manifest_lists_the_masks_and_room_json(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)

    listed = manifest(project)["files"]

    for name in MASK_FILES:
        assert f"{RES}/{name}" in listed
    assert manifest(project)["ids"]["masks"] == ["pit", "solid"]


def test_a_mask_the_game_changed_is_refused_by_name_and_force_backs_it_up(project: Kiripix) -> None:
    folder = exportable_room(project)
    project.json("export", ROOM)
    target = project.cwd / FOLDER / "masks" / "solid.png"
    target.write_bytes(b"the game's own mask")

    refused = project.json("export", ROOM, expect=3)

    assert f"{RES}/masks/solid.png" in str(findings(refused, "export.file_changed"))
    assert target.read_bytes() == b"the game's own mask" and not backups(project)
    project.json("export", ROOM, "--force")
    [kept] = backups(project)
    assert (kept / "game" / "kiripix" / "room" / "alley" / "masks" / "solid.png").read_bytes() == b"the game's own mask"
    assert target.read_bytes() == built_mask(folder, "solid").read_bytes()


def test_an_unmanaged_mask_is_refused_and_adopt_takes_it_over(project: Kiripix) -> None:
    exportable_room(project)
    target = project.cwd / FOLDER / "masks" / "solid.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"the game's own mask")

    assert f"{RES}/masks/solid.png" in str(findings(project.json("export", ROOM, expect=3), "export.file_unmanaged"))
    project.json("export", ROOM, "--adopt")

    assert target.read_bytes() != b"the game's own mask" and len(backups(project)) == 1


def test_prune_removes_the_masks_and_room_json_of_a_deleted_room(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)
    shutil.rmtree(project.cwd / "assets" / "room" / "alley")

    data = project.json("export", "--prune")["data"]

    for name in MASK_FILES:
        assert f"{RES}/{name}" in data["removed"] and not (project.cwd / FOLDER / name).exists()
    assert not (project.cwd / MANIFEST).exists() and not (project.cwd / SCENE).exists()


PROBE = """extends SceneTree

func _init() -> void:
	var room: Node = load("res://kiripix/room/alley/alley.tscn").instantiate()
	var description: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(room.get_meta("kiripix_room")))
	var folder: String = room.get_meta("kiripix_room").get_base_dir()
	var counts := {}
	for name in description["masks"]:
		var image: Image = load(folder + "/" + description["masks"][name]).get_image()
		var set_pixels := 0
		for y in image.get_height():
			for x in image.get_width():
				if image.get_pixel(x, y).r > 0.5:
					set_pixels += 1
		counts[name] = [image.get_width(), image.get_height(), set_pixels]
	print("PROBE ", JSON.stringify(counts))
	room.free()
	quit()
"""


@pytest.mark.godot
def test_godot_reads_the_solid_mask_and_counts_the_same_set_pixels(project: Kiripix) -> None:
    """Marked: real Godot 4.7 reads `masks/solid.png` through `Texture2D.get_image()` and counts what Kiripix counts."""
    folder = exportable_room(project)
    project.json("export", ROOM)
    game = project.cwd / "game"
    (game / "probe.gd").write_text(PROBE, "utf-8")
    godot = os.environ["KIRIPIX_GODOT"]

    subprocess.run([godot, "--headless", "--path", str(game), "--import", "--quit"], capture_output=True, timeout=300, check=False)
    done = subprocess.run([godot, "--headless", "--path", str(game), "-s", "res://probe.gd"], capture_output=True, text=True,
                          encoding="utf-8", timeout=120, check=False)

    [line] = [x for x in done.stdout.splitlines() if x.startswith("PROBE ")]
    counts = json.loads(line.removeprefix("PROBE "))
    for name in ("solid", "pit"):
        with Image.open(built_mask(folder, name)) as image:
            assert counts[name] == [48, 32, int(np.asarray(image.convert("1")).sum())]
    assert counts["solid"][2] == 16 * 32
