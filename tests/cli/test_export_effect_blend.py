"""A sprite's `blend` and `lit` (ticket 0364, spec §9 and §6.4): `character.json` carries them (schema_version 8, written only when
either is not its default), and the scene gives the AnimatedSprite2D a shared CanvasItemMaterial. A sprite without them exports
exactly as before. The real Godot test is marked."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Kiripix
from test_sprite import decide, load, new_sprite, png_sheet, spark

SPARK = "sprite.spark"
PUFF = "sprite.puff"
GAME = "game/kiripix/sprite"
EFFECT = ("fit anchor=centre effect=true", "finish outline=false")


def effect(project: Kiripix, asset: str, *export: str) -> Path:
    """A one-shot effect sprite (a 24 px cross that grows), centred, exported with the given `export` parameters."""
    name = asset.split(".", 1)[1]
    folder = new_sprite(project, name)
    png_sheet(project, spark(24, 3, blank_last=False), 3, asset, directions=["s"], file=f"{name}.png")
    project.json("set", asset, "frames", "directions=1")
    for setting in EFFECT:
        stage, _, assignment = setting.partition(" ")
        project.json("set", asset, stage, *assignment.split())
    if export:
        project.json("set", asset, "export", *export)
    decide(project, "frames", "clip", {"name": "idle", "loop": False}, asset)
    project.json("run", asset)
    project.json("export", asset)
    return folder


def scene(project: Kiripix, name: str) -> str:
    return (project.cwd / GAME / name / f"{name}.tscn").read_text("utf-8")


def character(folder: Path) -> dict[str, Any]:
    return load(folder / "out" / "export" / "character.json")


def test_an_additive_unshaded_spark_has_its_material_in_the_scene_and_in_character_json(project: Kiripix) -> None:
    folder = effect(project, SPARK, "blend=add", "lit=false")

    record = character(folder)
    text = scene(project, "spark")

    assert record["schema_version"] == 8 and record["blend"] == "add" and record["lit"] is False
    assert record["pivot"] == {"x": 12, "y": 12}
    assert '[sub_resource type="CanvasItemMaterial" id="effect_material"]\nblend_mode = 1\nlight_mode = 1\n' in text
    assert 'material = SubResource("effect_material")' in text
    assert "offset = Vector2(-12, -12)" in text and "[gd_scene load_steps=3 format=3]" in text
    assert (project.cwd / GAME / "spark" / "character.json").read_bytes() == (folder / "out" / "export" / "character.json").read_bytes()


def test_a_mix_lit_puff_is_the_default_and_exports_as_before(project: Kiripix) -> None:
    folder = effect(project, PUFF)
    text = scene(project, "puff")

    record = character(folder)

    assert record["schema_version"] == 7 and "blend" not in record and "lit" not in record
    assert "CanvasItemMaterial" not in text and "material" not in text and "load_steps=2" in text


def test_the_parameters_at_their_defaults_change_nothing(project: Kiripix) -> None:
    folder = effect(project, PUFF)
    before = {p: p.read_bytes() for p in sorted((project.cwd / GAME / "puff").iterdir())}
    built = (folder / "out" / "export" / "character.json").read_bytes()

    project.json("set", PUFF, "export", "blend=mix", "lit=true")

    stages = project.json("status", "--kind", "sprite")["data"]["assets"][0]["stages"]
    assert {s["stage"]: s["status"] for s in stages}["export"] == "done"
    assert (folder / "out" / "export" / "character.json").read_bytes() == built
    assert before == {p: p.read_bytes() for p in sorted((project.cwd / GAME / "puff").iterdir())}


def test_lit_alone_or_add_alone_writes_only_its_own_property(project: Kiripix) -> None:
    effect(project, SPARK, "lit=false")
    effect(project, PUFF, "blend=add")

    unlit, additive = scene(project, "spark"), scene(project, "puff")

    assert 'id="effect_material"]\nlight_mode = 1\n' in unlit and "blend_mode" not in unlit
    assert 'id="effect_material"]\nblend_mode = 1\n' in additive and "light_mode" not in additive


def test_the_scene_is_the_same_on_every_run_and_the_clip_ids_are_still_frozen(project: Kiripix) -> None:
    folder = effect(project, SPARK, "blend=add", "lit=false")
    first = scene(project, "spark")
    manifest = project.cwd / "game" / "kiripix" / ".kiripix" / "manifests" / "sprite.spark.json"

    project.json("run", SPARK, "export", "--force")
    project.json("export", SPARK)

    assert scene(project, "spark") == first and "\r" not in first
    assert character(folder)["clips"][0]["name"] == "idle"
    recorded = list((project.cwd / "game").rglob("sprite.spark.json")) or [manifest]
    assert recorded and "idle_s" in recorded[0].read_text("utf-8")


def test_an_old_version_7_file_migrates_to_mix_and_lit(project: Kiripix) -> None:
    folder = effect(project, SPARK, "blend=add", "lit=false")
    path = folder / "out" / "export" / "character.json"
    old = json.loads(path.read_text("utf-8"))
    old["schema_version"] = 7
    del old["blend"], old["lit"]
    path.write_text(json.dumps(old, indent=2) + "\n", "utf-8")

    result = project.json("export", SPARK, "--force")

    assert result["ok"] is True
    text = scene(project, "spark")
    assert "CanvasItemMaterial" not in text  # a version 7 file was drawn as mix and lit
    assert json.loads((project.cwd / GAME / "spark" / "character.json").read_text("utf-8"))["schema_version"] == 7


def test_a_newer_version_is_refused(project: Kiripix) -> None:
    folder = effect(project, SPARK, "blend=add")
    path = folder / "out" / "export" / "character.json"
    newer = json.loads(path.read_text("utf-8"))
    newer["schema_version"] = 9
    path.write_text(json.dumps(newer, indent=2) + "\n", "utf-8")

    result = project.json("export", SPARK, "--force", expect=1)

    assert [f["code"] for f in result["findings"]] == ["export.character_invalid"]


def test_a_blend_other_than_mix_or_add_is_refused(project: Kiripix) -> None:
    new_sprite(project, "spark")

    project.json("set", SPARK, "export", "blend=multiply", expect=1)


PROBE = """extends SceneTree

func _init() -> void:
	var found := {}
	for name in ["spark", "puff"]:
		var root: Node = load("res://kiripix/sprite/%s/%s.tscn" % [name, name]).instantiate()
		var sprite: AnimatedSprite2D = root.get_node("Sprite")
		var material := sprite.material as CanvasItemMaterial
		found[name] = [material != null, material.blend_mode if material else -1, material.light_mode if material else -1,
			sprite.offset.x, sprite.offset.y, sprite.sprite_frames.get_frame_count(&"idle_s"), sprite.sprite_frames.get_animation_loop(&"idle_s")]
	print("PROBE ", JSON.stringify(found))
	quit()
"""


@pytest.mark.godot
def test_godot_loads_the_additive_unshaded_spark_and_the_mix_lit_puff(project: Kiripix) -> None:
    """Marked: real Godot 4.7 loads both scenes headlessly; the spark's material is additive and unshaded, the puff has none (the
    engine's own mix and lit)."""
    effect(project, SPARK, "blend=add", "lit=false")
    effect(project, PUFF)
    game = project.cwd / "game"
    (game / "probe.gd").write_text(PROBE, "utf-8")
    godot = os.environ["KIRIPIX_GODOT"]
    subprocess.run([godot, "--headless", "--path", str(game), "--import", "--quit"], capture_output=True, timeout=300, check=False)

    done = subprocess.run([godot, "--headless", "--path", str(game), "-s", "res://probe.gd"], capture_output=True, text=True,
                          encoding="utf-8", timeout=120, check=False)

    [line] = [line for line in done.stdout.splitlines() if line.startswith("PROBE ")]
    found = json.loads(line.removeprefix("PROBE "))
    assert found["spark"] == [True, 1, 1, -12.0, -12.0, 3, False]  # add, unshaded, pivot at the root, a one-shot
    assert found["puff"] == [False, -1, -1, -12.0, -12.0, 3, False]
    assert "Parse Error" not in done.stderr + done.stdout
