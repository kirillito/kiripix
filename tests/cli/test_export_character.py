"""The character's export (ticket 0113, spec §6.3 and §9, ADR 0003): the Stage's engine-free outputs, the CanvasTexture,
SpriteFrames and scene in the game, the freeze of each `<clip>_<dir>` animation, and the same ownership rules as a room.
The writers' exact text is in `tests/golden/test_character_export_writers.py`; the CLI tests run on the fake Blender."""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Kiripix
from test_character_clips import IDLE, WALK, clip
from test_character_finish import finished
from test_character_model import HERO
from test_export import GENERATED, godot_project, node, set_target
from test_export import exportable_room as exported_room
from test_export_prop import MANIFEST as PROP_MANIFEST
from test_export_prop import ORIGIN, POLYGON, PROP
from test_prop import decision, to_finish

FOLDER = "game/kiripix/character/hero"
RES = "res://kiripix/character/hero"
SCENE = f"{FOLDER}/hero.tscn"
FRAMES = f"{FOLDER}/frames.tres"
TEXTURE = f"{FOLDER}/texture.tres"
MANIFEST = "game/kiripix/manifest/character.hero.json"
FILES = [f"{RES}/color.png", f"{RES}/frames.tres", f"{RES}/hero.tscn", f"{RES}/normal.png", f"{RES}/texture.tres"]
DIRECTIONS = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]
GAMES = b"the game's own\n"


def exportable_character(project: Kiripix) -> Path:
    """A character built through `sheet`, a Godot project to export into, and the `export` Stage built."""
    folder = finished(project, border=3)
    godot_project(project)
    set_target(project)
    project.json("run", HERO)
    return folder


def manifest(project: Kiripix) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((project.cwd / MANIFEST).read_text("utf-8"))
    return value


def built(folder: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((folder / "out" / "export" / "character.json").read_text("utf-8"))
    return value


def test_the_stage_leaves_both_atlases_and_character_json_in_out_export(project: Kiripix) -> None:
    folder = exportable_character(project)

    out = folder / "out" / "export"
    character = built(folder)
    sheet = json.loads((folder / "work" / "sheet" / "sheet.json").read_text("utf-8"))

    assert sorted(p.name for p in out.iterdir() if p.name != ".stage.json") == ["character.json", "color.png", "normal.png"]
    assert character == {"schema_version": 1, "asset": HERO, "files": {"color": "color.png", "normal": "normal.png"},
                         **{key: sheet[key] for key in ("cell", "pivot", "atlas", "directions", "clips")}}
    for name in ("color.png", "normal.png"):
        assert (out / name).read_bytes() == (folder / "work" / "sheet" / name).read_bytes()


def test_a_character_exports_a_texture_sprite_frames_and_a_scene_and_the_manifest_lists_them(project: Kiripix) -> None:
    folder = exportable_character(project)

    data = project.json("export", HERO)["data"]

    assert sorted(data["written"]) == FILES and data["counter"] == 1
    for res in FILES:
        assert (project.cwd / "game" / res.removeprefix("res://")).is_file()
    for path in (SCENE, FRAMES, TEXTURE):
        text = (project.cwd / path).read_text("utf-8")
        assert text.startswith(GENERATED + "\n") and "\r" not in text
    texture = (project.cwd / TEXTURE).read_text("utf-8")
    assert f'path="{RES}/color.png"' in texture and "diffuse_texture" in texture and "normal_texture" in texture
    scene = (project.cwd / SCENE).read_text("utf-8")
    sprite = node(scene, "Sprite", ".")
    assert 'type="AnimatedSprite2D"' in sprite and "centered = false" in sprite
    pivot = built(folder)["pivot"]
    assert f"offset = Vector2({-pivot['x']}, {-pivot['y']})" in sprite
    frames = (project.cwd / FRAMES).read_text("utf-8")
    names = re.findall(r'"name": &"([a-z_]+)"', frames)
    assert names == [f"{c}_{d}" for c in ("hit", "idle") for d in DIRECTIONS]
    assert frames.count('"loop": false') == 8 and frames.count('"speed": 15.0') == 8 and frames.count('"speed": 12.0') == 8
    assert f'path="{RES}/texture.tres"' in frames and frames.count("[sub_resource") == 8 * 14
    record = manifest(project)
    assert record["asset"] == HERO and record["exported"] is True and record["schema_version"] == 2
    assert sorted(record["files"]) == FILES
    assert record["ids"] == {"markers": [], "layers": [], "masks": [],
                             "clips": sorted(f"{c}_{d}" for c in ("hit", "idle") for d in DIRECTIONS)}
    assert (project.cwd / FOLDER / "color.png").read_bytes() == (folder / "out" / "export" / "color.png").read_bytes()


def test_re_exporting_writes_nothing_and_a_rebuild_is_byte_identical(project: Kiripix) -> None:
    exportable_character(project)
    project.json("export", HERO)
    before = {path: (project.cwd / path).read_bytes() for path in (SCENE, FRAMES, TEXTURE)}

    project.json("run", HERO, "export", "--force")
    data = project.json("export", HERO)["data"]

    assert {path: (project.cwd / path).read_bytes() for path in before} == before
    assert data["written"] == [] and data["counter"] == 1


def test_a_clip_taken_away_is_refused_and_a_clip_added_is_fine(project: Kiripix) -> None:
    exportable_character(project)
    project.json("export", HERO)

    project.json("undo", HERO, "clips")  # the last Decision, `hit`
    result = project.json("export", HERO, expect=2)
    frozen = [f for f in result["findings"] if f["code"] == "export.id_frozen"]
    assert sorted(f["message"].split("'")[1] for f in frozen) == [f"hit_{d}" for d in sorted(DIRECTIONS)]
    assert all(f["owner_action"] and f["fix"] is None for f in frozen)
    assert [f["code"] for f in project.json("check", HERO, expect=2)["findings"]].count("export.id_frozen") == 8

    project.json("redo", HERO, "clips")
    clip(project, WALK)
    project.json("run", HERO)
    data = project.json("export", HERO)["data"]
    assert data["counter"] == 2
    assert len(manifest(project)["ids"]["clips"]) == 24
    assert {f"walk_{d}" for d in DIRECTIONS} <= set(manifest(project)["ids"]["clips"])


def test_a_clip_changed_after_an_export_keeps_its_ids_and_exports_fewer_frames(project: Kiripix) -> None:
    exportable_character(project)  # hit (4 frames) and idle (10)
    project.json("export", HERO)
    ids = manifest(project)["ids"]["clips"]

    clip(project, {**IDLE, "end": 12})  # 5 frames
    project.json("run", HERO)
    data = project.json("export", HERO)["data"]

    assert data["counter"] == 2
    assert manifest(project)["ids"]["clips"] == ids
    assert (project.cwd / FRAMES).read_text("utf-8").count("[sub_resource") == 8 * 9


def test_editing_the_scene_refuses_and_force_backs_it_up(project: Kiripix) -> None:
    exportable_character(project)
    project.json("export", HERO)
    original = (project.cwd / SCENE).read_bytes()
    (project.cwd / SCENE).write_bytes(original + GAMES)

    result = project.json("export", HERO, expect=3)

    [finding] = [f for f in result["findings"] if f["code"] == "export.file_changed"]
    assert f"{RES}/hero.tscn" in finding["message"] and "--force" in finding["owner_action"]
    assert (project.cwd / SCENE).read_bytes() == original + GAMES

    data = project.json("export", HERO, "--force")["data"]
    assert data["backed_up"] == [f"{RES}/hero.tscn"] and (project.cwd / SCENE).read_bytes() == original
    [backup] = (project.cwd / ".kiripix" / "backups").glob("*/game/kiripix/character/hero/hero.tscn")
    assert backup.read_bytes() == original + GAMES


def test_an_unlisted_file_is_adopted(project: Kiripix) -> None:
    exportable_character(project)
    (project.cwd / TEXTURE).parent.mkdir(parents=True)
    (project.cwd / TEXTURE).write_bytes(GAMES)

    assert project.json("export", HERO, expect=3)["findings"][0]["code"] == "export.file_unmanaged"
    data = project.json("export", HERO, "--adopt")["data"]

    assert data["backed_up"] == [f"{RES}/texture.tres"] and (project.cwd / SCENE).is_file()


def test_export_all_exports_rooms_props_and_characters_together(project: Kiripix) -> None:
    exported_room(project)  # a room alley, built, with its target set
    to_finish(project)
    project.json("decide", PROP, "footprint", "--decision", decision(POLYGON, ORIGIN))
    project.json("run", PROP)
    finished(project, border=3)
    project.json("run", HERO)

    data = project.json("export", "--all")["data"]

    assert sorted(a["asset"] for a in data["assets"]) == [HERO, PROP, "room.alley"]
    assert (project.cwd / SCENE).is_file() and (project.cwd / PROP_MANIFEST).is_file()
    assert (project.cwd / MANIFEST).is_file()


def test_show_names_export_until_the_game_has_the_character(project: Kiripix) -> None:
    exportable_character(project)

    assert project.json("show", HERO)["data"]["export_command"] == f"kiripix export {HERO}"

    project.json("export", HERO)
    assert project.json("show", HERO)["data"]["export_command"] is None


def test_without_a_target_the_export_waits_for_the_owner(project: Kiripix) -> None:
    finished(project, border=3)

    result = project.json("run", HERO, expect=3)

    assert "no Godot project" in json.dumps(result)


def test_a_built_character_file_a_newer_kiripix_wrote_is_refused(project: Kiripix) -> None:
    folder = exportable_character(project)
    path = folder / "out" / "export" / "character.json"
    path.write_text(json.dumps({**built(folder), "schema_version": 9}), "utf-8")

    [finding] = project.json("export", HERO, expect=1)["findings"]

    assert finding["code"] == "export.character_invalid" and finding["fix"] == f"kiripix run {HERO} export --force"


def test_a_version_1_manifest_is_read_and_rewritten_as_version_2(project: Kiripix) -> None:
    exportable_character(project)
    project.json("export", HERO)
    old = manifest(project)
    del old["ids"]["clips"]
    (project.cwd / MANIFEST).write_text(json.dumps({**old, "schema_version": 1}, indent=2) + "\n", "utf-8")

    project.json("export", HERO)

    record = manifest(project)
    assert record["schema_version"] == 2 and len(record["ids"]["clips"]) == 16 and record["counter"] == 1


PROBE = """extends SceneTree

func _init() -> void:
	var hero: Node = load("res://kiripix/character/hero/hero.tscn").instantiate()
	var sprite: AnimatedSprite2D = hero.get_node("Sprite")
	var frames: SpriteFrames = sprite.sprite_frames
	var found := {}
	for name in frames.get_animation_names():
		found[str(name)] = [frames.get_frame_count(name), frames.get_animation_speed(name), frames.get_animation_loop(name)]
	var first: AtlasTexture = frames.get_frame_texture(&"idle_s", 0)
	print("PROBE ", JSON.stringify({"animations": found, "offset": [sprite.offset.x, sprite.offset.y],
		"canvas": first.atlas is CanvasTexture, "normal": first.atlas.normal_texture != null,
		"region": [first.region.size.x, first.region.size.y]}))
	quit()
"""


@pytest.mark.godot
def test_godot_opens_the_scene_and_the_animations_are_the_clips(project: Kiripix) -> None:
    """Marked: real Godot 4.7 loads the exported scene headlessly. Lighting itself needs a window and is the gate's."""
    exportable_character(project)
    project.json("export", HERO)
    game = project.cwd / "game"
    (game / "probe.gd").write_text(PROBE, "utf-8")
    godot = os.environ["KIRIPIX_GODOT"]

    subprocess.run([godot, "--headless", "--path", str(game), "--import", "--quit"], capture_output=True, timeout=300,
                   check=False)
    done = subprocess.run([godot, "--headless", "--path", str(game), "-s", "res://probe.gd"], capture_output=True,
                          text=True, encoding="utf-8", timeout=120, check=False)

    [line] = [line for line in done.stdout.splitlines() if line.startswith("PROBE ")]
    probe = json.loads(line.removeprefix("PROBE "))
    assert sorted(probe["animations"]) == sorted(f"{c}_{d}" for c in ("hit", "idle") for d in DIRECTIONS)
    assert probe["animations"]["hit_sw"] == [4, 15.0, False] and probe["animations"]["idle_s"] == [10, 12.0, True]
    assert probe["canvas"] and probe["normal"] and probe["region"] == [78, 78] and probe["offset"] == [-39, -72]
    # Godot reports resources still held at exit as an ERROR; a scene it can't parse or load is what matters here
    assert not re.search(r"Parse Error|Failed loading|Failed to load|Invalid|Cannot", done.stderr + done.stdout)
