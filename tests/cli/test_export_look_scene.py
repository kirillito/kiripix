"""A Look's Markers, collision and navigation in the game (ticket 0316, ADR 0013, spec §9): the room's `solid` body without
the pixels a Look clears, a body for them under the Look (or under every Look that clears them), a disabled navigation
region and a hidden node of Markers per Look, `room.json` schema 12 and the Manifest's `look_markers`."""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import Kiripix
from test_export import MANIFEST, SCENE, godot_project, manifest, scene, set_target
from test_export_looks import FOLDER, exported_room, node
from test_layers_stage import ROOM
from test_look_markers import LAMP_BOX, LOOK, OPENING, WALL, decide_place, mask
from test_looks_build import decide as decide_look
from test_looks_build import edited, import_and_pick, room_with_a_lamp_layer
from test_place import line, place

OTHER = "gate_wide"


def area(shapes: list[list[list[int]]]) -> int:
    """The area of convex pieces that don't overlap (a shape is a list of corners)."""
    total = 0
    for shape in shapes:
        points = np.asarray(shape, dtype=np.int64)
        x, y = points[:, 0], points[:, 1]
        total += abs(int(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))) // 2
    return total


def gate_room(project: Kiripix, looks: tuple[str, ...] = (LOOK,), opening: bool = True) -> Path:
    """The lamp room with a wall in `solid`, a Spawn, a y-sort line, a Godot project and a Look (or several) that erases the
    wall's middle, every Stage built (but not exported)."""
    folder = room_with_a_lamp_layer(project)
    project.json("decide", ROOM, "masks", "--decision",
                 json.dumps({"decision": "polygon", "data": {"mask": "solid", "erase": False, "points": WALL}}))
    for name in looks:
        import_and_pick(project, edited(), name)
        decide_look(project, "polygon", {"look": name, "points": LAMP_BOX})
        if opening:
            decide_look(project, "solid", {**OPENING, "look": name})
    place(project, "spawn.main", "spawn", (10, 16))
    line(project, "lamp")
    godot_project(project)
    set_target(project)
    project.json("run", ROOM)
    return folder


def export(project: Kiripix, expect: int = 0) -> dict[str, Any]:
    return project.json("export", ROOM, expect=expect)


def body_paths(text: str) -> list[str]:
    return re.findall(r'^\[node name="(polygon_\d+)"[^\n]* parent="([^"]+)"\]', text, re.MULTILINE)


def test_a_look_that_clears_solid_has_a_cleared_body_and_a_disabled_navigation(project: Kiripix) -> None:
    folder = gate_room(project)

    export(project)

    text = scene(project)
    room = exported_room(project)
    [look] = room["looks"]
    whole, cleared = area(room["collision"]["solid"]), area(look["cleared"]["collision"])
    assert cleared > 0, "the Look erases part of the wall"
    in_scene = area(room["scene"]["solid"])
    # simplified shapes can leave a seam of up to the tolerance (1 px) along the join, so the sum is near, not equal
    assert abs(in_scene - (whole - cleared)) <= 16 and in_scene < whole, "the room's body lacks what the Look clears"
    assert room["scene"]["cleared"][LOOK] and area(room["scene"]["cleared"][LOOK]) == cleared
    # with the Look hidden every body is enabled, and together they hold the room's `solid`
    polygons = body_paths(text)
    assert [parent for name, parent in polygons if parent == "solid"] and any(
        parent == f"LookSolids/{LOOK}/cleared" for _, parent in polygons)
    assert "disabled" not in node(text, "cleared", f"LookSolids/{LOOK}")
    assert "disabled = true" not in "".join(node(text, name, f"LookSolids/{LOOK}/cleared")
                                            for name, parent in polygons if parent == f"LookSolids/{LOOK}/cleared")
    region = node(text, LOOK, "LookNavigation")
    assert 'type="NavigationRegion2D"' in region and "enabled = false" in region
    assert "enabled = false" not in node(text, "Navigation", ".")
    solid = mask(folder / "work" / "masks" / "solid.png")
    assert (mask(project.cwd / FOLDER / "masks" / f"{LOOK}.cleared.png") <= solid).all()
    assert 0 < int(mask(project.cwd / FOLDER / "masks" / f"{LOOK}.cleared.png").sum()) and abs(
        int(mask(project.cwd / FOLDER / "masks" / f"{LOOK}.cleared.png").sum()) - cleared) <= 16  # shapes are simplified


def enabled_area(text: str) -> int:
    """The area of every collision polygon in the scene that is enabled: what collides with no Look shown."""
    total = 0
    for name, parent in body_paths(text):
        body = node(text, name, parent)
        if "disabled = true" not in body:
            numbers = [int(value) for value in re.findall(r"-?\d+", body.split("polygon = PackedVector2Array(")[1].split(")")[0])]
            total += area([[numbers[i:i + 2] for i in range(0, len(numbers), 2)]])
    return total


def test_with_no_look_shown_the_scene_collides_exactly_as_before(project: Kiripix) -> None:
    gate_room(project)
    export(project)
    room = exported_room(project)
    text = scene(project)

    # every enabled body together (the room's and the Look's cleared one) holds the room's whole `solid`; `added` is off
    assert abs(enabled_area(text) - area(room["collision"]["solid"])) <= 16
    assert enabled_area(text) > area(room["scene"]["solid"])
    assert room["collision"]["solid"], "collision.solid stays the room's whole solid"


def test_a_room_with_no_look_clearing_anything_keeps_its_one_solid_body(project: Kiripix) -> None:
    gate_room(project, opening=False)
    export(project)
    room = exported_room(project)

    assert room["scene"]["solid"] == room["collision"]["solid"] and room["scene"]["shared"] == []
    assert body_paths(scene(project)) and enabled_area(scene(project)) == area(room["collision"]["solid"])


def test_two_looks_that_clear_the_same_pixels_share_one_body(project: Kiripix) -> None:
    gate_room(project, (LOOK, OTHER))

    export(project)

    text = scene(project)
    room = exported_room(project)
    [shared] = room["scene"]["shared"]
    assert shared["looks"] == sorted([LOOK, OTHER]) and shared["collision"]
    assert room["scene"]["cleared"] == {LOOK: [], OTHER: []}
    body = node(text, f"Shared_{LOOK}+{OTHER}", "LookSolids")
    assert f'metadata/kiripix_looks = PackedStringArray("{LOOK}", "{OTHER}")' in body
    assert "disabled" not in body
    assert "polygon_0" in re.findall(r'name="(polygon_0)"[^\n]*parent="LookSolids/Shared', text)
    assert area(shared["collision"]) == area(room["looks"][0]["cleared"]["collision"])


def test_a_looks_light_is_under_the_look_disabled_and_in_room_json_under_the_look(project: Kiripix) -> None:
    gate_room(project)
    decide_place(project, "marker", {"id": "lamp.main", "type": "light", "x": 10, "y": 10, "colour": "#FFAA00",
                                     "radius": 20, "energy": 1.0})
    decide_place(project, "marker", {"id": "lamp.gate", "type": "light", "x": 24, "y": 12, "colour": "#FFAA00",
                                     "radius": 20, "energy": 1.0, "look": LOOK})
    project.json("run", ROOM)

    export(project)

    text = scene(project)
    glow = node(text, "lamp-gate", f"LookMarkers/{LOOK}")
    assert "PointLight2D" in glow and "enabled = false" in glow and f'metadata/kiripix_look = "{LOOK}"' in glow
    assert "visible = false" in node(text, LOOK, "LookMarkers")
    assert "enabled = false" not in node(text, "lamp-main", "Lights")
    assert 'name="lamp-gate"' not in re.sub(r"\[node name=\"lamp-gate\"[^\n]*parent=\"LookMarkers/[^\n]*", "", text)
    room = exported_room(project)
    assert [m["id"] for m in room["markers"]] == ["spawn.main", "lamp.main"] or {m["id"] for m in room["markers"]} == {
        "spawn.main", "lamp.main", "ysort.lamp"}
    assert "lamp.gate" not in [m["id"] for m in room["markers"]]
    [look] = room["looks"]
    assert [m["id"] for m in look["markers"]] == ["lamp.gate"] and "look" not in look["markers"][0]


def test_room_json_is_schema_13_and_masks_list_added_and_cleared(project: Kiripix) -> None:
    gate_room(project)

    export(project)

    room = exported_room(project)
    assert room["schema_version"] == 15
    assert [mask["name"] for mask in room["masks"]] == ["pit", "solid"]  # a Look's files are listed under the Look
    [look] = room["looks"]
    assert look["navigation"]["polygons"] and look["added"]["file"] == f"masks/{LOOK}.added.png"
    assert look["cleared"]["file"] == f"masks/{LOOK}.cleared.png" and look["markers"] == []
    added = mask(project.cwd / FOLDER / "masks" / f"{LOOK}.added.png")
    assert added.shape == tuple(room["size"][::-1]) and not added.any()


def test_a_look_without_its_own_solid_has_no_navigation_added_or_cleared(project: Kiripix) -> None:
    gate_room(project, opening=False)

    export(project)

    [look] = exported_room(project)["looks"]
    assert look["navigation"] is None and look["added"] is None and look["cleared"] is None
    assert "LookNavigation" not in scene(project) and all(not mask["name"].startswith(LOOK) for mask in exported_room(project)["masks"])


def test_an_older_room_json_is_refused_naming_the_rebuild(project: Kiripix) -> None:
    folder = gate_room(project)
    path = folder / "out" / "export" / "room.json"
    old = json.loads(path.read_text("utf-8"))
    old["schema_version"] = 11
    path.write_text(json.dumps(old), "utf-8")

    result = project("export", ROOM, "--json")

    assert result.code != 0
    refusal = next(f for f in result.json["findings"] if f["code"] == "export.room_invalid")
    assert "run room.alley export --force" in str(refusal["fix"]).replace("kiripix ", "") or "export" in str(refusal["fix"])


def test_the_manifest_is_schema_3_with_look_markers_and_a_version_2_one_is_rewritten(project: Kiripix) -> None:
    gate_room(project)
    decide_place(project, "marker", {"id": "lamp.gate", "type": "light", "x": 24, "y": 12, "colour": "#FFAA00",
                                     "radius": 20, "energy": 1.0, "look": LOOK})
    project.json("run", ROOM)
    export(project)
    record = manifest(project)
    assert record["schema_version"] == 4 and record["ids"]["look_markers"] == [f"{LOOK}/lamp.gate"]
    assert "lamp.gate" not in record["ids"]["markers"]

    old = json.loads(json.dumps(record))
    old["schema_version"] = 2
    del old["ids"]["look_markers"]
    (project.cwd / MANIFEST).write_text(json.dumps(old, indent=2) + "\n", "utf-8")

    export(project)  # reads the schema 2 Manifest and rewrites it once
    after = manifest(project)
    assert after["schema_version"] == 4 and after["ids"]["look_markers"] == [f"{LOOK}/lamp.gate"]


def test_a_room_without_look_markers_has_no_look_markers_key_and_no_look_markers_node(project: Kiripix) -> None:
    gate_room(project)

    export(project)

    assert "look_markers" not in manifest(project)["ids"] and "LookMarkers" not in scene(project)
    assert manifest(project)["schema_version"] == 4


def test_moving_an_exported_marker_into_a_look_is_refused(project: Kiripix) -> None:
    gate_room(project)
    decide_place(project, "marker", {"id": "lamp.gate", "type": "light", "x": 24, "y": 12, "colour": "#FFAA00",
                                     "radius": 20, "energy": 1.0})
    project.json("run", ROOM)
    export(project)
    assert "lamp.gate" in manifest(project)["ids"]["markers"]

    decide_place(project, "marker", {"id": "lamp.gate", "type": "light", "x": 24, "y": 12, "colour": "#FFAA00",
                                     "radius": 20, "energy": 1.0, "look": LOOK})
    result = project("run", ROOM, "--json")
    checked = project("check", ROOM, "--json")
    again = project("export", ROOM, "--json")

    frozen = [f for r in (result, checked, again) for f in r.json["findings"] if f["code"] == "export.id_frozen"]
    assert frozen and all("lamp.gate" in f["message"] for f in frozen)
    assert again.code == 2
    assert SCENE and (project.cwd / SCENE).is_file()


def test_moving_an_exported_look_marker_out_of_its_look_is_refused(project: Kiripix) -> None:
    gate_room(project)
    fields = {"id": "lamp.gate", "type": "light", "x": 24, "y": 12, "colour": "#FFAA00", "radius": 20, "energy": 1.0}
    decide_place(project, "marker", {**fields, "look": LOOK})
    project.json("run", ROOM)
    export(project)

    decide_place(project, "marker", fields)
    again = project("export", ROOM, "--json")

    assert again.code == 2
    assert any(f["code"] == "export.id_frozen" and f"{LOOK}/lamp.gate" in f["message"] for f in again.json["findings"])


def test_the_scene_and_room_json_are_byte_identical_across_a_rebuild(project: Kiripix) -> None:
    gate_room(project, (LOOK, OTHER))
    export(project)
    before = (project.cwd / SCENE).read_bytes(), (project.cwd / FOLDER / "room.json").read_bytes()

    project.json("run", ROOM, "export", "--rerun")
    export(project)

    assert before == ((project.cwd / SCENE).read_bytes(), (project.cwd / FOLDER / "room.json").read_bytes())
    assert b"\r" not in before[0]


PROBE = """extends SceneTree

func _count(body: Node) -> Array:
	var on := 0
	var off := 0
	for each in body.get_children():
		if each is CollisionPolygon2D:
			if each.disabled:
				off += 1
			else:
				on += 1
	return [on, off]

func _init() -> void:
	var room: Node = load("res://kiripix/room/alley/alley.tscn").instantiate()
	var look := "%s"
	var found := {
		"solid": _count(room.get_node("solid")),
		"cleared": _count(room.get_node("LookSolids/" + look + "/cleared")),
		"added": _count(room.get_node("LookSolids/" + look + "/added")),
		"navigation_enabled": room.get_node("LookNavigation/" + look).enabled,
		"room_navigation_enabled": room.get_node("Navigation").enabled,
		"markers_visible": room.get_node("LookMarkers/" + look).visible,
		"light_enabled": room.get_node("LookMarkers/" + look + "/lamp-gate").enabled,
		"light_look": room.get_node("LookMarkers/" + look + "/lamp-gate").get_meta("kiripix_look"),
	}
	print("PROBE ", JSON.stringify(found))
	room.free()
	quit()
""" % LOOK


@pytest.mark.godot
def test_godot_loads_the_scene_with_a_look_and_reads_its_nodes_back(project: Kiripix) -> None:
    """Marked: real Godot 4.7 loads the scene headlessly; the Look's cleared body is on, its added body and region are off."""
    gate_room(project)
    decide_place(project, "marker", {"id": "lamp.gate", "type": "light", "x": 24, "y": 12, "colour": "#FFAA00",
                                     "radius": 20, "energy": 1.0, "look": LOOK})
    project.json("run", ROOM)
    export(project)
    game: Path = project.cwd / "game"
    (game / "probe.gd").write_text(PROBE, "utf-8")
    godot = os.environ.get("KIRIPIX_GODOT") or "godot"

    subprocess.run([godot, "--headless", "--path", str(game), "--import", "--quit"], capture_output=True, timeout=300, check=False)
    done = subprocess.run([godot, "--headless", "--path", str(game), "-s", "res://probe.gd"], capture_output=True, text=True,
                          encoding="utf-8", timeout=120, check=False)

    [line] = [x for x in done.stdout.splitlines() if x.startswith("PROBE ")]
    found = json.loads(line.removeprefix("PROBE "))
    assert found["solid"][0] > 0 and found["solid"][1] == 0
    assert found["cleared"][0] > 0 and found["cleared"][1] == 0
    assert found["added"] == [0, 0]
    assert found["navigation_enabled"] is False and found["room_navigation_enabled"] is True
    assert found["markers_visible"] is False and found["light_enabled"] is False and found["light_look"] == LOOK
    assert "WARNING" not in done.stdout + done.stderr and "ERROR" not in done.stdout + done.stderr
