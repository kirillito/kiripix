"""The character's export (ticket 0113, spec §6.3 and §9, ADR 0003): the Stage's engine-free outputs, the CanvasTexture,
SpriteFrames and scene in the game, the freeze of each `<clip>_<dir>` animation, and the same ownership rules as a room.
The writers' exact text is in `tests/golden/test_character_export_writers.py`; the CLI tests run on the fake Blender."""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import Kiripix
from PIL import Image
from test_character_clips import IDLE, WALK, clip
from test_character_finish import finished
from test_character_model import HERO
from test_character_ramps import built_parts
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
    assert character == {"schema_version": 4, "asset": HERO, "files": {"color": "color.png", "normal": "normal.png"},
                         **{key: sheet[key] for key in ("cell", "pivot", "atlas", "directions")},
                         "clips": [{**c, "events": {"foot": []}} for c in sheet["clips"]], "parts": [], "rows": []}
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


RAMPS = f"{FOLDER}/ramps.png"
PARTS = "cloth,skin"


def exportable_parts(project: Kiripix) -> Path:
    """The same character with `parts` (cloth and skin, on the fake Blender's split material pass), built through `export`."""
    folder = built_parts(project, PARTS)
    finish_without_outline(project)
    godot_project(project)
    set_target(project)
    project.json("run", HERO)
    return folder


def finish_without_outline(project: Kiripix) -> None:
    """`finish` refuses an outline colour that is in a ramp (the swap would recolour it), so these draw none."""
    project.json("set", HERO, "finish", "outline=false")
    project.json("run", HERO, "finish")


def palette_parts(folder: Path) -> list[dict[str, Any]]:
    document = json.loads((folder / "work" / "palette" / "palette.json").read_text("utf-8"))
    parts: list[dict[str, Any]] = document["parts"]
    return parts


def test_character_json_lists_each_part_dark_to_light_in_palettes_order(project: Kiripix) -> None:
    folder = exportable_parts(project)

    character = built(folder)

    assert character["schema_version"] == 4
    assert character["parts"] == [{key: part[key] for key in ("name", "materials", "row", "shared", "indexes", "rgb")}
                                  for part in palette_parts(folder)]
    assert [(p["name"], p["row"], p["shared"]) for p in character["parts"]] == [("cloth", 0, False), ("skin", 1, False)]
    assert character["rows"] == [{"name": p["name"], "length": len(p["rgb"])} for p in palette_parts(folder)]


def test_ramps_png_has_one_row_per_part_with_the_ramps_exact_colours(project: Kiripix) -> None:
    folder = exportable_parts(project)
    parts = palette_parts(folder)

    data = project.json("export", HERO)["data"]

    assert sorted(data["written"]) == sorted(FILES + [f"{RES}/ramps.png"]) and data["counter"] == 1
    image = np.array(Image.open(project.cwd / RAMPS).convert("RGBA"))
    longest = max(len(p["rgb"]) for p in parts)
    assert image.shape == (len(parts), longest, 4)
    for row, part in enumerate(parts):
        assert image[row, :len(part["rgb"])].tolist() == [[*rgb, 255] for rgb in part["rgb"]]
        assert (image[row, len(part["rgb"]):] == 0).all()  # padded with transparent pixels
    assert f"{RES}/ramps.png" in manifest(project)["files"]


def test_ramps_png_is_padded_to_the_longest_ramp(project: Kiripix) -> None:
    folder = built_parts(project, "cloth:2,skin:4")
    finish_without_outline(project)
    godot_project(project)
    set_target(project)
    project.json("run", HERO)

    project.json("export", HERO)

    image = np.array(Image.open(project.cwd / RAMPS).convert("RGBA"))
    assert [len(p["rgb"]) for p in palette_parts(folder)] == [2, 4]
    assert image.shape == (2, 4, 4) and (image[0, 2:] == 0).all() and (image[0, :2, 3] == 255).all()


def test_the_scene_names_the_ramps_and_the_parts_in_row_order(project: Kiripix) -> None:
    exportable_parts(project)
    project.json("export", HERO)

    root = node((project.cwd / SCENE).read_text("utf-8"), "hero")

    assert f'metadata/kiripix_ramps = "{RES}/ramps.png"' in root
    assert 'metadata/kiripix_parts = PackedStringArray("cloth", "skin")' in root


def test_re_exporting_a_character_with_parts_writes_nothing_and_a_rebuild_is_byte_identical(project: Kiripix) -> None:
    exportable_parts(project)
    project.json("export", HERO)
    before = {path: (project.cwd / path).read_bytes() for path in (SCENE, RAMPS, MANIFEST)}

    project.json("run", HERO, "export", "--force")
    data = project.json("export", HERO)["data"]

    assert {path: (project.cwd / path).read_bytes() for path in before} == before
    assert data["written"] == [] and data["counter"] == 1


def test_a_character_without_parts_exports_no_ramps_and_names_none(project: Kiripix) -> None:
    exportable_character(project)

    project.json("export", HERO)

    assert not (project.cwd / RAMPS).exists()
    assert "kiripix_ramps" not in (project.cwd / SCENE).read_text("utf-8")
    assert "ramps.png" not in " ".join(manifest(project)["files"])


def test_an_edited_ramps_png_is_refused_like_any_owned_file(project: Kiripix) -> None:
    exportable_parts(project)
    project.json("export", HERO)
    original = (project.cwd / RAMPS).read_bytes()
    (project.cwd / RAMPS).write_bytes(original + GAMES)

    result = project.json("export", HERO, expect=3)

    [finding] = [f for f in result["findings"] if f["code"] == "export.file_changed"]
    assert f"{RES}/ramps.png" in finding["message"]
    assert project.json("export", HERO, "--force")["data"]["backed_up"] == [f"{RES}/ramps.png"]
    assert (project.cwd / RAMPS).read_bytes() == original


SWAP = """shader_type canvas_item;
// A test of the game's swap: a pixel that is a step of ramps.png's row `row` takes the same step of `swapped`'s first row.
uniform sampler2D ramps : filter_nearest;
uniform sampler2D swapped : filter_nearest;
uniform int row = 0;
void fragment() {
	vec4 c = texture(TEXTURE, UV);
	int n = textureSize(ramps, 0).x;
	for (int i = 0; i < n; i++) {
		vec4 from = texelFetch(ramps, ivec2(i, row), 0);
		if (from.a > 0.5 && distance(from.rgb, c.rgb) < 0.002) {
			c = vec4(texelFetch(swapped, ivec2(i, 0), 0).rgb, c.a);
			break;
		}
	}
	COLOR = c;
}
"""

SWAP_PROBE = """extends SceneTree

func _init() -> void:
	var hero: Node = load("res://kiripix/character/hero/hero.tscn").instantiate()
	var ramps_image: Image = load(hero.get_meta("kiripix_ramps")).get_image()
	var names: PackedStringArray = hero.get_meta("kiripix_parts")
	var sprite: AnimatedSprite2D = hero.get_node("Sprite")
	var atlas: AtlasTexture = sprite.sprite_frames.get_frame_texture(&"idle_s", 0)
	var source: Image = atlas.atlas.diffuse_texture.get_image()
	var region := Rect2i(atlas.region)
	var rows := []
	for r in range(names.size()):
		var colours := []
		for i in range(ramps_image.get_width()):
			var c := ramps_image.get_pixel(i, r)
			if c.a > 0.5:
				colours.append(c)
		rows.append(colours)
	# the shader's rule for row `swap_row`: only a pixel on that row's steps changes; the rest of the frame stays
	var swap_row: int = int(OS.get_environment("KIRIPIX_SWAP_ROW"))
	var changed := {}
	var kept := {}
	for y in range(region.position.y, region.end.y):
		for x in range(region.position.x, region.end.x):
			var pixel := source.get_pixel(x, y)
			if pixel.a < 0.5:
				continue
			var owner := "(fixed)"
			for r in range(names.size()):
				for c in rows[r]:
					if pixel.is_equal_approx(c):
						owner = names[r]
			var found: Dictionary = changed if owner == names[swap_row] else kept
			found[owner] = found.get(owner, 0) + 1
	print("PROBE ", JSON.stringify({"parts": names, "changed": changed, "kept": kept}))
	quit()
"""


@pytest.mark.godot
def test_godot_swapping_one_row_of_ramps_png_changes_only_that_parts_pixels(project: Kiripix) -> None:
    """Marked: real Godot 4.7 loads the scene and `ramps.png` headlessly. A canvas shader needs a window, so the script applies
    the shader's rule (`swap.gdshader`, written to the game too, for the Owner's window) to the atlas itself."""
    exportable_parts(project)
    project.json("export", HERO)
    game = project.cwd / "game"
    (game / "swap.gdshader").write_text(SWAP, "utf-8")
    (game / "probe.gd").write_text(SWAP_PROBE, "utf-8")
    godot = os.environ["KIRIPIX_GODOT"]
    subprocess.run([godot, "--headless", "--path", str(game), "--import", "--quit"], capture_output=True, timeout=300, check=False)

    result = {}
    for row in (0, 1):
        done = subprocess.run([godot, "--headless", "--path", str(game), "-s", "res://probe.gd"], capture_output=True, text=True,
                              encoding="utf-8", timeout=120, check=False, env={**os.environ, "KIRIPIX_SWAP_ROW": str(row)})
        [line] = [line for line in done.stdout.splitlines() if line.startswith("PROBE ")]
        result[row] = json.loads(line.removeprefix("PROBE "))

    assert result[0]["parts"] == ["cloth", "skin"]
    assert set(result[0]["changed"]) == {"cloth"} and set(result[1]["changed"]) == {"skin"}
    assert set(result[0]["kept"]) <= {"skin", "(fixed)"} and set(result[1]["kept"]) <= {"cloth", "(fixed)"}


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
