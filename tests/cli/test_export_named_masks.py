"""Ticket 0345 (spec §9): every painted Mask of the room's view is exported as `masks/<name>.png`, `room.json` lists each with
its meaning, and the names are frozen in the Manifest's `ids.masks`."""

import json
import os
import re
import subprocess

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_export import MANIFEST, ROOM, exportable_room, manifest
from test_masks import decide
from test_place import findings

import pytest

FOLDER = "game/kiripix/room/alley"
RES = "res://kiripix/room/alley"
MEANING = "half cover for a grid battle"


def cover_room(project: Kiripix) -> None:
    exportable_room(project)
    project.json("masks-add", "cover", "--colour", "#00AA00", "--meaning", MEANING)
    decide(project, "brush", {"mask": "cover", "points": [[20, 10], [30, 10]], "radius": 2, "erase": False})
    project.json("run", ROOM)


def exported_room(project: Kiripix) -> dict[str, object]:
    value: dict[str, object] = json.loads((project.cwd / FOLDER / "room.json").read_text("utf-8"))
    return value


def test_a_painted_named_mask_is_exported_listed_and_frozen(project: Kiripix) -> None:
    cover_room(project)

    data = project.json("export", ROOM)["data"]

    built = project.cwd / "assets" / "room" / "alley" / "work" / "masks" / "cover.png"
    exported = project.cwd / FOLDER / "masks" / "cover.png"
    assert exported.read_bytes() == built.read_bytes() and f"{RES}/masks/cover.png" in data["written"]
    with Image.open(exported) as image:
        assert image.mode == "1" and image.size == (48, 32) and np.asarray(image)[10, 25]
    listed = {mask["name"]: mask for mask in exported_room(project)["masks"]}  # type: ignore[attr-defined]
    assert exported_room(project)["schema_version"] == 15
    assert listed["cover"] == {"name": "cover", "file": "masks/cover.png", "meaning": MEANING}  # no `collision`
    assert listed["solid"]["collision"] is True and listed["pit"]["collision"] is True
    record = manifest(project)
    assert f"{RES}/masks/cover.png" in record["files"]
    assert record["ids"]["masks"] == ["cover", "pit", "solid"] and record["schema_version"] == 5
    assert re.search(r'\[node name="cover"', (project.cwd / FOLDER / "alley.tscn").read_text("utf-8")) is None


def test_removing_an_exported_mask_from_the_project_is_id_frozen(project: Kiripix) -> None:
    cover_room(project)
    project.json("export", ROOM)
    path = project.cwd / "kiripix.toml"
    text = path.read_text("utf-8")
    gone = re.sub(r"^(?:\[masks\.top\.cover\]\n(?:[^\[\n][^\n]*\n)*|cover\s*=[^\n]*\n)", "", text, flags=re.MULTILINE)
    assert gone != text and "cover" not in gone
    path.write_text(gone, "utf-8")

    result = project.json("export", ROOM, expect=2)

    frozen = findings(result, "export.id_frozen")
    assert frozen and "'cover'" in frozen[0]["message"]
    assert (project.cwd / FOLDER / "masks" / "cover.png").is_file()


def test_a_schema_3_manifest_is_migrated_and_rewritten_once(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)
    old = manifest(project)
    old["schema_version"] = 3
    (project.cwd / MANIFEST).write_text(json.dumps(old, indent=2) + "\n", "utf-8")

    project.json("export", ROOM)

    assert manifest(project)["schema_version"] == 5 and manifest(project)["ids"]["masks"] == ["pit", "solid"]


PROBE = """extends SceneTree

func _init() -> void:
	var room: Node = load("res://kiripix/room/alley/alley.tscn").instantiate()
	var description: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(room.get_meta("kiripix_room")))
	var folder: String = room.get_meta("kiripix_room").get_base_dir()
	for mask in description["masks"]:
		if mask["name"] != "cover":
			continue
		var image: Image = load(folder + "/" + mask["file"]).get_image()
		var rows := []
		for y in image.get_height():
			var row := ""
			for x in image.get_width():
				row += "1" if image.get_pixel(x, y).r > 0.5 else "0"
			rows.append(row)
		print("PROBE ", JSON.stringify(rows))
	room.free()
	quit()
"""


@pytest.mark.godot
def test_godot_reads_the_painted_pixels_of_a_named_mask_exactly(project: Kiripix) -> None:
    """Marked: real Godot 4.7 reads `masks/cover.png` through `Texture2D.get_image()`."""
    cover_room(project)
    project.json("export", ROOM)
    game = project.cwd / "game"
    (game / "probe.gd").write_text(PROBE, "utf-8")
    godot = os.environ["KIRIPIX_GODOT"]

    subprocess.run([godot, "--headless", "--path", str(game), "--import", "--quit"], capture_output=True, timeout=300, check=False)
    done = subprocess.run([godot, "--headless", "--path", str(game), "-s", "res://probe.gd"], capture_output=True, text=True,
                          encoding="utf-8", timeout=120, check=False)

    [line] = [x for x in done.stdout.splitlines() if x.startswith("PROBE ")]
    rows = json.loads(line.removeprefix("PROBE "))
    with Image.open(project.cwd / FOLDER / "masks" / "cover.png") as image:
        painted = np.asarray(image.convert("1"))
    assert ["".join("1" if cell else "0" for cell in row) for row in painted] == rows
    assert painted.any()
