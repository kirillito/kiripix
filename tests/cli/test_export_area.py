"""An `area` Marker in the Godot scene (ticket 0138, spec §9): an `Area2D` with a `RectangleShape2D` the size of its box that
never touches physics, its metadata, and the freeze of its ID (ticket 0137's third criterion)."""

import json
import os
import subprocess
from pathlib import Path

import pytest
from conftest import Kiripix
from test_area import area
from test_export import MANIFEST, ROOM, godot_project, manifest, node, scene, set_target
from test_place import place, walled_room


def exported_areas(project: Kiripix) -> None:
    """walled_room's Plate is 48 x 32, with `solid` on the left 16 columns."""
    walled_room(project)
    place(project, "spawn.main", "spawn")
    area(project, "battle.yard", (24, 8, 39, 23), walkable=True, cell=8)  # 16 x 16, on whole cells of 8
    area(project, "escape.fence", (0, 0, 9, 4))  # over `solid`: no walkable pixel, and no `walkable` asked
    godot_project(project)
    set_target(project)
    project.json("run", ROOM)
    project.json("export", ROOM)


def test_an_area_is_an_area2d_with_a_shape_the_size_of_its_box_and_no_physics(project: Kiripix) -> None:
    exported_areas(project)

    text = scene(project)

    yard = node(text, "battle-yard", "Markers")
    assert 'type="Area2D"' in yard and "position = Vector2(32, 16)" in yard
    for line in ("collision_layer = 0", "collision_mask = 0", "monitoring = false", "monitorable = false"):
        assert line in yard
    assert 'metadata/kiripix_id = "battle.yard"' in yard and 'metadata/kiripix_type = "area"' in yard
    assert "metadata/walkable = true" in yard and "metadata/cell = 8" in yard
    shape = node(text, "Shape", "Markers/battle-yard")
    assert 'type="CollisionShape2D"' in shape and 'shape = SubResource("area_battle_yard")' in shape
    assert '[sub_resource type="RectangleShape2D" id="area_battle_yard"]\nsize = Vector2(16, 16)\n' in text


def test_an_area_with_no_walkable_pixel_and_no_cell_exports_like_any_other(project: Kiripix) -> None:
    exported_areas(project)

    text = scene(project)

    fence = node(text, "escape-fence", "Markers")
    assert "position = Vector2(5, 2.5)" in fence  # a box 10 x 5 px, its centre half a pixel in
    assert "metadata/walkable = false" in fence and "metadata/cell" not in fence
    assert "size = Vector2(10, 5)" in text
    assert manifest(project)["ids"]["markers"] == ["battle.yard", "escape.fence", "spawn.main"]


def test_a_re_export_of_the_unchanged_room_writes_nothing(project: Kiripix) -> None:
    exported_areas(project)
    before = (project.cwd / "game/kiripix/room/alley/alley.tscn").read_bytes()

    assert project.json("export", ROOM)["data"]["written"] == []
    assert (project.cwd / "game/kiripix/room/alley/alley.tscn").read_bytes() == before and b"\r" not in before


def test_renaming_an_exported_area_is_refused_naming_the_id(project: Kiripix) -> None:
    exported_areas(project)
    assert (project.cwd / MANIFEST).is_file()

    project.json("undo", ROOM, "place")  # the fence's Decision
    area(project, "escape.hedge", (0, 0, 9, 4))
    project.json("run", ROOM)
    result = project.json("export", ROOM, expect=2)

    frozen = [f for f in result["findings"] if f["code"] == "export.id_frozen"]
    assert [f["message"].split("'")[1] for f in frozen] == ["escape.fence"]
    assert frozen[0]["owner_action"] and frozen[0]["fix"] is None
    assert "escape-fence" in scene(project)


def test_a_new_area_is_a_new_id_and_is_allowed(project: Kiripix) -> None:
    exported_areas(project)

    area(project, "trigger.door", (30, 6, 30, 20))
    project.json("run", ROOM)
    project.json("export", ROOM)

    assert manifest(project)["ids"]["markers"] == ["battle.yard", "escape.fence", "spawn.main", "trigger.door"]
    assert "size = Vector2(1, 15)" in scene(project)


def test_two_area_ids_that_meet_once_their_dots_are_underscores_get_distinct_shapes(project: Kiripix) -> None:
    """Godot allows only letters, digits and `_` in a resource ID, so `.` becomes `_`; `a_b.c` and `a.b_c` would meet."""
    exported_areas(project)

    area(project, "a_b.c", (30, 6, 31, 7))
    area(project, "a.b_c", (34, 6, 35, 7))
    project.json("run", ROOM)
    project.json("export", ROOM)
    text = scene(project)

    assert '[node name="Shape" type="CollisionShape2D" parent="Markers/a-b_c"]\nshape = SubResource("area_a_b_c")\n' in text
    assert '[node name="Shape" type="CollisionShape2D" parent="Markers/a_b-c"]\nshape = SubResource("area_a_b_c_2")\n' in text
    assert text.count('[sub_resource type="RectangleShape2D" id="area_a_b_c"]') == 1


PROBE = """extends SceneTree

func _init() -> void:
	var room: Node = load("res://kiripix/room/alley/alley.tscn").instantiate()
	var found := []
	for node in room.get_node("Markers").get_children():
		if node is Area2D:
			var shape: CollisionShape2D = node.get_node("Shape")
			var rect: RectangleShape2D = shape.shape
			found.append([node.get_meta("kiripix_id"), node.get_meta("walkable"), node.position.x, node.position.y,
				rect.size.x, rect.size.y, node.monitoring, node.monitorable, node.collision_layer, node.collision_mask])
	print("PROBE ", JSON.stringify(found))
	room.free()
	quit()
"""


@pytest.mark.godot
def test_godot_loads_the_scene_with_no_warnings_and_reads_the_rectangle_back(project: Kiripix) -> None:
    """Marked: real Godot 4.7 loads the exported scene headlessly and reads each area's rectangle."""
    exported_areas(project)
    game: Path = project.cwd / "game"
    (game / "probe.gd").write_text(PROBE, "utf-8")
    godot = os.environ["KIRIPIX_GODOT"]

    subprocess.run([godot, "--headless", "--path", str(game), "--import", "--quit"], capture_output=True, timeout=300, check=False)
    done = subprocess.run([godot, "--headless", "--path", str(game), "-s", "res://probe.gd"], capture_output=True, text=True,
                          encoding="utf-8", timeout=120, check=False)

    [line] = [x for x in done.stdout.splitlines() if x.startswith("PROBE ")]
    assert json.loads(line.removeprefix("PROBE ")) == [
        ["battle.yard", True, 32, 16, 16, 16, False, False, 0, 0], ["escape.fence", False, 5, 2.5, 10, 5, False, False, 0, 0]]
    assert "WARNING" not in done.stdout + done.stderr and "ERROR" not in done.stdout + done.stderr
