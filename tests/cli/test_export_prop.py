"""The prop's export (ticket 0052, spec §6.2 and §9, ADR 0003): the Stage's engine-free outputs, the scene with its
Sprite2D drawn from the origin and its footprint on collision layer 1, and the same ownership rules as a room."""

import json
import shutil
from pathlib import Path
from typing import Any

from conftest import Kiripix
from test_export import GENERATED, godot_project, node, set_target
from test_export import exportable_room as exported_room
from test_prop import PROP, decision, to_finish, work

FOLDER = "game/kiripix/prop/bench"
SCENE = f"{FOLDER}/bench.tscn"
SPRITE = f"{FOLDER}/sprite.png"
MANIFEST = "game/kiripix/manifest/prop.bench.json"
RES = "res://kiripix/prop/bench"
POLYGON = [[1, 5], [6, 5], [6, 7], [1, 7]]
ORIGIN = [3, 7]
GAMES = b"the game's own\n"


def exportable_prop(project: Kiripix, polygon: list[list[int]] | None = None) -> Path:
    """A prop with a footprint, a Godot project to export into, and every Stage built."""
    folder = to_finish(project)
    project.json("decide", PROP, "footprint", "--decision", decision(POLYGON if polygon is None else polygon, ORIGIN))
    godot_project(project)
    set_target(project)
    project.json("run", PROP)
    return folder


def scene(project: Kiripix) -> str:
    return (project.cwd / SCENE).read_text("utf-8")


def manifest(project: Kiripix) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((project.cwd / MANIFEST).read_text("utf-8"))
    return value


def test_the_stage_leaves_the_sprite_and_prop_json_in_out_export(project: Kiripix) -> None:
    folder = exportable_prop(project)

    out = folder / "out" / "export"
    prop = json.loads((out / "prop.json").read_text("utf-8"))

    assert prop == {"schema_version": 1, "asset": PROP, "size": [8, 8], "origin": ORIGIN,
                    "collision": [[[1, 5], [6, 5], [6, 7], [1, 7]]]}
    assert (out / "sprite.png").read_bytes() == work(folder, "finish", "finish.png").read_bytes()
    assert sorted(path.name for path in out.iterdir() if path.name != ".stage.json") == ["prop.json", "sprite.png"]


def test_a_prop_exports_a_scene_with_the_sprite_offset_from_the_origin_and_the_manifest_lists_its_files(
    project: Kiripix,
) -> None:
    folder = exportable_prop(project)

    data = project.json("export", PROP)["data"]

    assert sorted(data["written"]) == [f"{RES}/bench.tscn", f"{RES}/sprite.png"] and data["counter"] == 1
    text = scene(project)
    assert text.startswith(GENERATED + "\n") and "\r" not in text
    assert 'type="Node2D"' in node(text, "bench") and 'metadata/kiripix_id = "prop.bench"' in node(text, "bench")
    sprite = node(text, "Sprite", ".")
    assert 'type="Sprite2D"' in sprite and 'texture = ExtResource("sprite")' in sprite
    assert "centered = false" in sprite and "offset = Vector2(-3, -7)" in sprite
    assert f'[ext_resource type="Texture2D" path="{RES}/sprite.png" id="sprite"]' in text
    body = node(text, "Footprint", ".")
    assert 'type="StaticBody2D"' in body and "collision_layer = 1" in body and "collision_mask = 0" in body
    polygon = node(text, "polygon_0", "Footprint")
    assert 'type="CollisionPolygon2D"' in polygon
    assert "polygon = PackedVector2Array(-2, -2, 3, -2, 3, 0, -2, 0)" in polygon, "relative to the origin"
    record = manifest(project)
    assert record["asset"] == PROP and record["exported"] is True
    assert sorted(record["files"]) == [f"{RES}/bench.tscn", f"{RES}/sprite.png"]
    assert (project.cwd / SPRITE).read_bytes() == (folder / "out" / "export" / "sprite.png").read_bytes()


def test_a_concave_footprint_becomes_convex_polygons_and_a_counter_clockwise_one_is_accepted(project: Kiripix) -> None:
    l_shape = [[1, 7], [1, 5], [3, 5], [3, 6], [6, 6], [6, 7]]  # not convex, and in either winding
    folder = exportable_prop(project, l_shape)

    shapes = json.loads((folder / "out" / "export" / "prop.json").read_text("utf-8"))["collision"]

    assert len(shapes) >= 2 and all(len(shape) >= 3 for shape in shapes)
    project.json("export", PROP)
    assert "polygon_1" in scene(project)


def test_an_empty_footprint_exports_no_body(project: Kiripix) -> None:
    folder = exportable_prop(project, [])

    project.json("export", PROP)

    assert json.loads((folder / "out" / "export" / "prop.json").read_text("utf-8"))["collision"] == []
    text = scene(project)
    assert "StaticBody2D" not in text and "CollisionPolygon2D" not in text and "Footprint" not in text
    assert "offset = Vector2(-3, -7)" in text


def test_the_scene_is_byte_identical_across_a_rebuild_and_re_exporting_writes_nothing(project: Kiripix) -> None:
    exportable_prop(project)
    project.json("export", PROP)
    before = (project.cwd / SCENE).read_bytes()

    project.json("run", PROP, "export", "--force")
    data = project.json("export", PROP)["data"]

    assert (project.cwd / SCENE).read_bytes() == before
    assert data["written"] == [] and data["counter"] == 1


def test_moving_the_origin_changes_the_scene_and_raises_the_counter(project: Kiripix) -> None:
    exportable_prop(project)
    project.json("export", PROP)

    project.json("decide", PROP, "footprint", "--decision", decision(POLYGON, [4, 7]))
    project.json("run", PROP)
    data = project.json("export", PROP)["data"]

    assert data["written"] == [f"{RES}/bench.tscn"] and data["counter"] == 2
    assert "offset = Vector2(-4, -7)" in scene(project)


def test_editing_the_scene_refuses_and_force_backs_it_up(project: Kiripix) -> None:
    exportable_prop(project)
    project.json("export", PROP)
    original = (project.cwd / SCENE).read_bytes()
    (project.cwd / SCENE).write_bytes(original + GAMES)

    result = project.json("export", PROP, expect=3)

    [finding] = [f for f in result["findings"] if f["code"] == "export.file_changed"]
    assert f"{RES}/bench.tscn" in finding["message"] and "--force" in finding["owner_action"]
    assert (project.cwd / SCENE).read_bytes() == original + GAMES

    data = project.json("export", PROP, "--force")["data"]
    assert data["backed_up"] == [f"{RES}/bench.tscn"] and (project.cwd / SCENE).read_bytes() == original
    [backup] = (project.cwd / ".kiripix" / "backups").glob("*/game/kiripix/prop/bench/bench.tscn")
    assert backup.read_bytes() == original + GAMES


def test_an_unlisted_file_is_adopted_and_a_dry_run_writes_nothing(project: Kiripix) -> None:
    exportable_prop(project)
    (project.cwd / SPRITE).parent.mkdir(parents=True)
    (project.cwd / SPRITE).write_bytes(GAMES)

    dry = project.json("export", PROP, "--dry-run")
    assert dry["data"]["unmanaged"] == [f"{RES}/sprite.png"] and not (project.cwd / SCENE).exists()
    assert project.json("export", PROP, expect=3)["findings"][0]["code"] == "export.file_unmanaged"
    assert not (project.cwd / SCENE).exists()

    data = project.json("export", PROP, "--adopt")["data"]
    assert data["backed_up"] == [f"{RES}/sprite.png"] and (project.cwd / SCENE).is_file()


def test_a_prop_freezes_no_id_so_its_body_can_go_and_a_deleted_prop_can_be_pruned(project: Kiripix) -> None:
    exportable_prop(project)
    project.json("export", PROP)
    assert manifest(project)["ids"] == {"markers": [], "layers": [], "masks": []}

    project.json("decide", PROP, "footprint", "--decision", decision([], ORIGIN))
    project.json("run", PROP)
    project.json("export", PROP)

    assert "StaticBody2D" not in scene(project)
    shutil.rmtree(project.cwd / "assets" / "prop" / "bench")
    removed = project.json("export", "--prune")["data"]["removed"]
    assert f"{RES}/bench.tscn" in removed and not (project.cwd / SCENE).exists()


def test_export_all_exports_rooms_and_props_together_and_exit_pairing_looks_only_at_rooms(project: Kiripix) -> None:
    exported_room(project)  # a room alley, built, with its target set
    to_finish(project)
    project.json("decide", PROP, "footprint", "--decision", decision(POLYGON, ORIGIN))
    project.json("run", PROP)

    data = project.json("export", "--all")["data"]

    assert sorted(a["asset"] for a in data["assets"]) == [PROP, "room.alley"]
    assert (project.cwd / SCENE).is_file() and (project.cwd / "game/kiripix/room/alley/alley.tscn").is_file()
    assert (project.cwd / MANIFEST).is_file()
    assert not [f for f in project.json("check", "--all")["findings"] if f["code"].startswith("exit.")]


def test_next_names_export_until_the_game_has_the_prop(project: Kiripix) -> None:
    exportable_prop(project)

    advice = project.json("next", PROP)["data"]
    assert not advice["done"] and advice["stage"] == "export" and advice["command"] == f"kiripix export {PROP}"
    assert project.json("show", PROP)["data"]["export_command"] == f"kiripix export {PROP}"

    project.json("export", PROP)
    assert project.json("next", PROP)["data"]["done"]
    assert project.json("show", PROP)["data"]["export_command"] is None


def test_without_a_target_the_export_waits_for_the_owner(project: Kiripix) -> None:
    to_finish(project)
    project.json("decide", PROP, "footprint", "--decision", decision(POLYGON, ORIGIN))

    result = project.json("run", PROP, expect=3)

    assert "no Godot project" in json.dumps(result)
    assert project.json("next", PROP)["data"]["owner_action"]


def test_a_built_prop_file_a_newer_kiripix_wrote_is_refused(project: Kiripix) -> None:
    folder = exportable_prop(project)
    path = folder / "out" / "export" / "prop.json"
    built = json.loads(path.read_text("utf-8"))
    path.write_text(json.dumps({**built, "schema_version": 9}), "utf-8")

    [finding] = project.json("export", PROP, expect=1)["findings"]

    assert finding["code"] == "export.prop_invalid" and finding["fix"] == f"kiripix run {PROP} export --force"
