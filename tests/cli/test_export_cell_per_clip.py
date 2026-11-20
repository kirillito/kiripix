"""A character whose clips have their own cells (ticket 0304, spec §9): every frame is padded to one logical cell with
`AtlasTexture.margin`, so the scene has one offset and every clip's feet stay on the same pixel. The fixture is
`test_cell_per_clip`'s (a held clip that reaches past the body's cell), on the fake Blender. The real Godot test is marked."""

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
from test_cell_per_clip import BODY, built, by_name, exported
from test_export import godot_project, node, set_target
from test_export_character import FRAMES, HERO, RES, SCENE

FRAME = re.compile(r'\[sub_resource type="AtlasTexture" id="([a-z_]+)_(\d+)"\]\natlas = ExtResource\("texture"\)\n'
                   r'region = Rect2\(([^)]*)\)(?:\nmargin = Rect2\(([^)]*)\))?')


def parsed(project: Kiripix) -> dict[tuple[str, int], tuple[list[int], list[int] | None]]:
    text = (project.cwd / FRAMES).read_text("utf-8")
    return {(name, int(index)): ([int(v) for v in region.split(",")], [int(v) for v in margin.split(",")] if margin else None)
            for name, index, region, margin in FRAME.findall(text)}


def logical(character: dict[str, Any]) -> tuple[int, int, int, int]:
    clips = character["clips"]
    px, py = max(c["pivot"]["x"] for c in clips), max(c["pivot"]["y"] for c in clips)
    return (px, py, px + max(c["cell"]["width"] - c["pivot"]["x"] for c in clips),
            py + max(c["cell"]["height"] - c["pivot"]["y"] for c in clips))


def test_a_clip_with_its_own_cell_has_its_regions_at_that_cell_and_every_frame_is_padded_to_one_logical_cell(project: Kiripix) -> None:
    _, _, character = exported(project)
    project.json("export", HERO)

    frames = parsed(project)
    clips = by_name(character)
    side = clips["hit"]["cell"]["width"]
    assert side > BODY
    px, py, width, height = logical(character)
    assert (width, height) == (side, side)  # the larger clip's cell holds the body's, feet to feet
    seen = set()
    for name, entry in clips.items():
        for direction, listed in entry["directions"].items():
            for frame in listed:
                region, margin = frames[(f"{name}_{direction}", frame["index"])]
                r = frame["rect"]
                assert region == [r["x"], r["y"], r["width"], r["height"]]
                cell = entry["cell"]
                assert region[2:] == [cell["width"], cell["height"]]  # the regions are the clip's own cell
                want = [px - entry["pivot"]["x"], py - entry["pivot"]["y"], width - cell["width"], height - cell["height"]]
                seen.add(name)
                if name == "hit":
                    assert margin is None  # the logical cell is this clip's own
                else:
                    assert margin == want and want[0] > 0 and want[1] > 0
    assert seen == {"idle", "walk", "hit"}
    sprite = node((project.cwd / SCENE).read_text("utf-8"), "Sprite", ".")
    assert f"offset = Vector2({-px}, {-py})" in sprite  # one offset for the scene: the logical pivot


def test_a_character_whose_clips_share_one_cell_has_no_margin_and_the_bodys_offset(project: Kiripix) -> None:
    _, _, character = exported(project, None)
    project.json("export", HERO)

    assert "margin" not in (project.cwd / FRAMES).read_text("utf-8")
    sprite = node((project.cwd / SCENE).read_text("utf-8"), "Sprite", ".")
    assert f"offset = Vector2({-character['pivot']['x']}, {-character['pivot']['y']})" in sprite


def trimmed(project: Kiripix) -> tuple[Path, dict[str, Any]]:
    """The cell-per-clip fixture with each finished frame's border cleared by a different amount (so every frame has its own box
    and offset), then sheet and export: the frames are trimmed in the atlas."""
    folder = built(project)
    godot_project(project)
    set_target(project)
    project.json("run", HERO)
    for layer in ("color", "normal"):
        for path in sorted((folder / "work" / "finish" / layer).rglob("*.png")):
            image = np.array(Image.open(path))
            number = int(path.stem)
            image[:2 + number % 5], image[-3:], image[:, :4 + number % 3], image[:, -2:] = 0, 0, 0, 0
            Image.fromarray(image, "RGBA").save(path)
    for path in sorted((folder / "work" / "render" / "depth").rglob("*.png")):  # far where nothing is drawn, as a render's is
        depth = np.array(Image.open(path), dtype=np.uint16)
        number = int(path.stem)
        depth[:2 + number % 5], depth[-3:], depth[:, :4 + number % 3], depth[:, -2:] = 65535, 65535, 65535, 65535
        Image.fromarray(depth).save(path)
    project.json("run", HERO, "--force", "--from", "sheet")
    project.json("export", HERO)
    return folder, json.loads((folder / "out" / "export" / "character.json").read_text("utf-8"))


def test_a_trimmed_frame_has_its_region_at_its_packed_rect_and_a_margin_restoring_the_logical_cell(project: Kiripix) -> None:
    _, character = trimmed(project)

    frames = parsed(project)
    px, py, width, height = logical(character)
    clips = by_name(character)
    trims = set()
    for name, entry in clips.items():
        for direction, listed in entry["directions"].items():
            for frame in listed:
                region, margin = frames[(f"{name}_{direction}", frame["index"])]
                r, o = frame["rect"], frame["offset"]
                assert region == [r["x"], r["y"], r["width"], r["height"]]
                assert r["width"] < entry["cell"]["width"] and r["height"] < entry["cell"]["height"]
                trims.add((o["x"], o["y"]))
                assert margin == [o["x"] + px - entry["pivot"]["x"], o["y"] + py - entry["pivot"]["y"],
                                  width - r["width"], height - r["height"]]  # region + margin is the logical cell
    assert len(trims) > 3


PROBE = """extends SceneTree
# Draws the first frame of every animation as the scene does (root at a fixed point of a viewport) and reports where its opaque box lies.

func _initialize() -> void:
	var packed: PackedScene = load("res://kiripix/character/hero/hero.tscn")
	var vp := SubViewport.new()
	vp.size = Vector2i(400, 400)
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
	root.add_child(vp)
	var hero: Node2D = packed.instantiate()
	hero.position = Vector2(200, 300)
	vp.add_child(hero)
	var sprite: AnimatedSprite2D = hero.get_node("Sprite")
	var found := {}
	for name in sprite.sprite_frames.get_animation_names():
		if not str(name).ends_with("_s"):
			continue
		sprite.animation = name
		sprite.frame = 0
		await process_frame
		await process_frame
		var image: Image = vp.get_texture().get_image()
		var box := Rect2i()
		var any := false
		for y in range(image.get_height()):
			for x in range(image.get_width()):
				if image.get_pixel(x, y).a > 0.0:
					box = Rect2i(x, y, 1, 1) if not any else box.expand(Vector2i(x + 1, y + 1))
					any = true
		found[str(name)] = [box.position.x, box.position.y, box.end.x, box.end.y, sprite.sprite_frames.get_frame_texture(name, 0).get_size().x]
	print("PROBE ", JSON.stringify(found))
	quit()
"""


@pytest.mark.godot
def test_godot_plays_both_clips_with_the_feet_on_the_same_pixel(project: Kiripix) -> None:
    """Marked: real Godot 4.7 draws the first frame of each clip (OpenGL, a small window: a viewport needs a renderer). The fake
    Blender's frames are flat cells, so a cell's bottom edge is its feet, 6 px under the pivot in every cell: the bottom edge of what
    is drawn must be the same row for every clip, and each clip's frame as wide as the logical cell."""
    _, _, character = exported(project)
    project.json("export", HERO)
    game = project.cwd / "game"
    (game / "probe.gd").write_text(PROBE, "utf-8")
    godot = os.environ["KIRIPIX_GODOT"]
    subprocess.run([godot, "--headless", "--path", str(game), "--import", "--quit"], capture_output=True, timeout=300, check=False)

    done = subprocess.run([godot, "--path", str(game), "--rendering-driver", "opengl3", "--resolution", "64x64", "-s", "res://probe.gd"],
                          capture_output=True, text=True, encoding="utf-8", timeout=180, check=False)

    [line] = [line for line in done.stdout.splitlines() if line.startswith("PROBE ")]
    probe = json.loads(line.removeprefix("PROBE "))
    px, py, width, height = logical(character)
    assert sorted(probe) == ["hit_s", "idle_s", "walk_s"]
    for name, (left, top, right, bottom, drawn) in probe.items():
        assert drawn == width  # every frame is the logical cell wide, margin included
        assert bottom == 300 + (height - py)  # the feet: the same row, whatever the clip's own cell
        own = by_name(character)[name.removesuffix("_s")]  # flat cells: the clip's own cell is opaque, its pivot at the root
        assert (left, top) == (200 - own["pivot"]["x"], 300 - own["pivot"]["y"])
        assert (right, bottom) == (left + own["cell"]["width"], top + own["cell"]["height"])
    assert not re.search(r"Parse Error|Failed loading|Failed to load|Invalid|Cannot", done.stderr + done.stdout)


DRAW_PROBE = """extends SceneTree
# Draws every frame of every south animation as the scene does (root at (200, 300) of a viewport) and saves each as a PNG.

func _initialize() -> void:
	var packed: PackedScene = load("res://kiripix/character/hero/hero.tscn")
	var vp := SubViewport.new()
	vp.size = Vector2i(400, 400)
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
	root.add_child(vp)
	var hero: Node2D = packed.instantiate()
	hero.position = Vector2(200, 300)
	vp.add_child(hero)
	var sprite: AnimatedSprite2D = hero.get_node("Sprite")
	for name in sprite.sprite_frames.get_animation_names():
		if not str(name).ends_with("_s"):
			continue
		sprite.animation = name
		for i in range(sprite.sprite_frames.get_frame_count(name)):
			sprite.frame = i
			await process_frame
			await process_frame
			vp.get_texture().get_image().save_png(OS.get_environment("KIRIPIX_DRAW") + "/%s_%d.png" % [name, i])
	print("PROBE done")
	quit()
"""


@pytest.mark.godot
def test_godot_draws_every_trimmed_frame_as_the_untrimmed_one_with_the_feet_on_one_pixel(project: Kiripix, tmp_path: Path) -> None:
    """Marked: real Godot 4.7 (OpenGL, a small window) draws every frame of the trimmed export; each equals the finished, untrimmed
    cell placed with its pivot at the root, so the feet stay on one pixel."""
    folder, character = trimmed(project)
    game = project.cwd / "game"
    (game / "probe.gd").write_text(DRAW_PROBE, "utf-8")
    drawn = tmp_path / "drawn"
    drawn.mkdir()
    godot = os.environ["KIRIPIX_GODOT"]
    subprocess.run([godot, "--headless", "--path", str(game), "--import", "--quit"], capture_output=True, timeout=300, check=False)

    done = subprocess.run([godot, "--path", str(game), "--rendering-driver", "opengl3", "--resolution", "64x64", "-s", "res://probe.gd"],
                          capture_output=True, text=True, encoding="utf-8", timeout=300, check=False,
                          env={**os.environ, "KIRIPIX_DRAW": str(drawn)})

    assert "PROBE done" in done.stdout, done.stdout + done.stderr
    checked = 0
    for name, entry in by_name(character).items():
        for frame in entry["directions"]["s"]:
            source = np.array(Image.open(folder / "work" / "finish" / "color" / name / "s" / f"{frame['index']:03d}.png").convert("RGBA"))
            expected = np.zeros((400, 400, 4), dtype=np.uint8)
            x, y = 200 - entry["pivot"]["x"], 300 - entry["pivot"]["y"]
            expected[y:y + source.shape[0], x:x + source.shape[1]] = source
            got = np.array(Image.open(drawn / f"{name}_s_{frame['index']}.png").convert("RGBA"))
            assert (got[..., 3] == expected[..., 3]).all(), f"{name} {frame['index']}: the drawn box differs"
            solid = expected[..., 3] > 0
            assert (got[solid][:, :3] == expected[solid][:, :3]).all(), f"{name} {frame['index']}: the drawn pixels differ"
            checked += 1
    assert checked == sum(len(c["directions"]["s"]) for c in character["clips"])
    assert not re.search(r"Parse Error|Failed loading|Failed to load|Invalid|Cannot", done.stderr + done.stdout)
