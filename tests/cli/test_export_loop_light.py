"""A frame Loop under a room light in the game (ticket 0404, spec §9): a strip holds only the pixels that change (ticket 0403),
the export carries it byte for byte, and the unshaded Loop sprite then draws nothing over the lit Plate where the room didn't
change, so no box shows."""

import os
import subprocess
from pathlib import Path

import numpy as np
import pytest
from conftest import Kiripix
from PIL import Image
from test_export import PLATE, godot_project, manifest, scene
from test_export_layer_loops import FLAME, decide, exportable_room
from test_export_looks import FOLDER, exported_room, node
from test_layers_stage import ROOM, rgba
from test_loop_kit import KIT, TRIANGLE
from test_loops import tiles
from test_place import place

LIGHT = "window"


def lit_room(project: Kiripix) -> dict[str, object]:
    """The lamp room with a two-frame kit Loop on the Plate (the triangle's box, 1, 1 to 30, 30) and a light over the left half
    of its box, exported. Returns the Loop's `room.json` entry."""
    folder = exportable_room(project)
    decide(project, "loop", {"loop": FLAME, "form": "frames"})
    decide(project, "polygon", {"loop": FLAME, "points": TRIANGLE})
    project.json("run", ROOM, "masks")
    project.json("run", ROOM, "palette")
    project.json("loop", "kit", ROOM, FLAME, KIT, "--frames", "2", "--force")
    frame = rgba(project.cwd / KIT / "frame_000.png")
    palette = rgba(folder / "work" / "palette" / "palette.png")
    spots = (slice(18, 20), slice(3, 5)), (slice(14, 16), slice(14, 16))  # a few moving pixels, off the lamp Layer, one group in the light
    for spot in spots:  # a colour of the room's palette that the room doesn't have there
        other = next(c for c in (palette[8, 8], palette[20, 20], palette[20, 1], palette[24, 40]) if (frame[spot] != c).any(axis=-1).all())
        frame[spot] = other
    Image.fromarray(frame, "RGBA").save(project.cwd / KIT / "frame_001.png")
    project.json("import", ROOM, project.cwd / KIT / "frame_001.png", "--loop", FLAME)
    project.json("run", ROOM)
    place(project, LIGHT, "light", (1, 16), colour="#FFCC88", radius=14, energy=1.5)  # lights the box's left half
    project.json("run", ROOM)
    project.json("export", ROOM)
    [loop] = exported_room(project)["loops"]
    return dict(loop)


def test_the_exported_strip_is_the_built_one_with_frame_zero_clear(project: Kiripix) -> None:
    loop = lit_room(project)

    exported = project.cwd / FOLDER / str(loop["file"])
    built = project.cwd / "assets" / "room" / "alley" / "work" / "loops" / str(loop["file"]).removeprefix("loops/")
    first, second = tiles(exported, loop["box"], loop["frames"], loop["hframes"])  # type: ignore[arg-type]
    assert (first == 0).all(), "frame 0 is clear: nothing in the export fills it"
    assert (second[..., 3] > 0).any() and ((second[..., 3] > 0) | (second == 0).all(axis=-1)).all()
    assert built.is_file() and exported.read_bytes() == built.read_bytes(), "the export carries the strip byte for byte"
    text = scene(project)
    assert 'material = SubResource("loop_unshaded")' in node(text, FLAME, "Loops")
    assert "texture_filter" not in node(text, FLAME, "Loops"), "no filter of its own: the Plate's (the project's nearest)"
    assert "light_mode = 1" in text
    assert any(str(loop["file"]) in entry for entry in str(manifest(project)).split("'"))


def test_a_room_with_no_loop_has_no_loop_nodes_or_material(project: Kiripix) -> None:
    exportable_room(project)
    project.json("run", ROOM)

    project.json("export", ROOM)

    text = scene(project)
    assert "Loops" not in text and "loop_unshaded" not in text and exported_room(project)["loops"] == []
    assert not (project.cwd / FOLDER / "loops").exists()


PROBE = """extends SceneTree
# Draws the room scene in a viewport the size of the Plate, lit, in the day and under a dark CanvasModulate, three ways each:
# the Loops node hidden, the Loop on frame 0 and the Loop on frame 1. Also saves the strip as Godot imported it.

func _draw_room(name: String, size: Vector2i, night: bool, loops_visible: bool, frame: int) -> void:
	var packed: PackedScene = load("res://kiripix/room/alley/alley.tscn")
	var vp := SubViewport.new()
	vp.size = size
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
	root.add_child(vp)
	if night:
		var dark := CanvasModulate.new()
		dark.color = Color(0.25, 0.25, 0.35)
		vp.add_child(dark)
	var room: Node2D = packed.instantiate()
	vp.add_child(room)
	room.get_node("Loops").visible = loops_visible
	room.get_node("Loops/flame").frame = frame
	await process_frame
	await process_frame
	await process_frame
	vp.get_texture().get_image().save_png(OS.get_environment("KIRIPIX_DRAW") + "/" + name + ".png")
	vp.queue_free()

func _initialize() -> void:
	var plate: Texture2D = load("res://kiripix/room/alley/plate.png")
	var size := Vector2i(plate.get_width(), plate.get_height())
	for night in [false, true]:
		var tag := "night" if night else "day"
		await _draw_room(tag + "_off", size, night, false, 0)
		await _draw_room(tag + "_0", size, night, true, 0)
		await _draw_room(tag + "_1", size, night, true, 1)
	var strip: Texture2D = load("res://%s")
	strip.get_image().save_png(OS.get_environment("KIRIPIX_DRAW") + "/strip.png")
	print("PROBE done")
	quit()
"""


@pytest.mark.godot
def test_godot_draws_no_box_under_a_light_and_keeps_the_strip_s_pixels(project: Kiripix, tmp_path: Path) -> None:
    """Marked: real Godot 4.7 (OpenGL, a small window) draws the lit room with the Loop and without it, day and night. On frame 0
    nothing differs from the room without the Loop; on frame 1 only pixels the strip keeps differ. The strip as Godot imported
    it has the file's alpha and, where opaque, its colours (no premultiply or border fix shows)."""
    loop = lit_room(project)
    game = project.cwd / "game"
    drawn = tmp_path / "drawn"
    drawn.mkdir()
    (game / "probe.gd").write_text(PROBE % f"kiripix/room/alley/{loop['file']}", "utf-8")
    godot = os.environ["KIRIPIX_GODOT"]
    subprocess.run([godot, "--headless", "--path", str(game), "--import", "--quit"], capture_output=True, timeout=300, check=False)

    done = subprocess.run([godot, "--path", str(game), "--rendering-driver", "opengl3", "--resolution", "64x64", "-s", "res://probe.gd"],
                          capture_output=True, text=True, encoding="utf-8", timeout=300, check=False,
                          env={**os.environ, "KIRIPIX_DRAW": str(drawn)})

    assert "PROBE done" in done.stdout, done.stdout + done.stderr
    x, y, width, height = loop["box"]  # type: ignore[misc]
    first, second = tiles(project.cwd / FOLDER / str(loop["file"]), loop["box"], loop["frames"], loop["hframes"])  # type: ignore[arg-type]
    kept = np.zeros((rgba(project.cwd / PLATE).shape[0], rgba(project.cwd / PLATE).shape[1]), dtype=bool)
    kept[y:y + height, x:x + width] = second[..., 3] > 0
    assert kept.any()
    for tag in ("day", "night"):
        off, zero, one = (rgba(drawn / f"{tag}_{name}.png") for name in ("off", "0", "1"))
        assert (zero == off).all(), f"{tag}: frame 0 draws exactly the room without the Loop (no box)"
        changed = (one != off).any(axis=-1)
        assert changed.any() and not (changed & ~kept).any(), f"{tag}: only the strip's kept pixels differ"
    plate = rgba(project.cwd / PLATE)
    lit = rgba(drawn / "day_off.png")
    box = (slice(y, y + height), slice(x, x + width))
    brighter = (lit[box][..., :3] != plate[box][..., :3]).any(axis=-1)
    assert brighter.any() and not brighter.all(), "the light changes the Plate under part of the box, not all of it"
    assert brighter[:, :width // 2].mean() > brighter[:, width // 2:].mean(), "the lit part is the box's left half"
    imported = rgba(drawn / "strip.png")
    exported = np.asarray(Image.open(project.cwd / FOLDER / str(loop["file"])).convert("RGBA"))
    assert imported.shape == exported.shape and (imported[..., 3] == exported[..., 3]).all()
    opaque = exported[..., 3] > 0
    assert (imported[opaque] == exported[opaque]).all(), "the strip's opaque pixels survive the import"
    assert "WARNING" not in done.stdout + done.stderr and "ERROR" not in done.stdout + done.stderr
