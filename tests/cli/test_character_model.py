"""The `model` Stage and the Blender seam (ticket 0101, spec §6.3): Blender runs headless as a separate process, found
through `[character] blender` or PATH, and only Blender 5.2 is accepted. The CLI tests run on the fake Blender of
`kiripix_test_recipes.py`, whose files are `blender-calls.jsonl`, `hold-blender` / `blender-holding` and `blender-fails`.
The marked test runs the real one on the fixture Models and is skipped without Blender 5.2."""

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest
from conftest import Kiripix, stage_status
from test_locks import wait_for
from test_serve import Server, server  # noqa: F401 - the `server` fixture

FIXTURES = Path(__file__).parent.parent / "fixtures" / "characters"
HERO = "character.hero"


def picked_hero(project: Kiripix, file: str = "rigged.glb", **kwargs: Any) -> Path:
    project.json("new", "character", "hero", **kwargs)
    shutil.copy(FIXTURES / file, project.cwd / file)
    variant = project.json("import", HERO, file, **kwargs)["data"]["variant"]
    project.json("pick", HERO, variant, **kwargs)
    return project.cwd / "assets" / "character" / "hero"


def calls(project: Kiripix) -> list[dict[str, Any]]:
    path = project.cwd / "blender-calls.jsonl"
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []


def test_run_builds_model_and_next_names_rig(project: Kiripix) -> None:
    folder = picked_hero(project)

    result = project.json("run", HERO, "model")

    assert [(r["stage"], r["outcome"]) for r in result["data"]["results"]] == [("model", "done")]
    document = json.loads((folder / "work" / "model" / "model.json").read_text("utf-8"))
    assert document["schema_version"] == 2 and document["up"] == "+Z" and document["height"] == 2.0
    assert document["bones"] and document["armature"] and document["actions"]
    assert {"name", "start", "end"} <= set(document["actions"][0])
    assert set(document["bounds"]) == {"min", "max"}
    assert (folder / "work" / "model" / "model.blend").is_file()
    [call] = calls(project)
    assert call["script"] == "normalise_model" and call["args"]["input"].endswith(".glb")
    assert call["args"]["height"] == 2.0

    again = project.json("run", HERO, "model")
    assert again["data"]["results"][0]["outcome"] == "skipped" and len(calls(project)) == 1
    nxt = project.json("next", HERO)["data"]
    assert nxt["stage"] == "rig"


def test_a_failed_blender_fails_the_stage_with_its_message(project: Kiripix) -> None:
    picked_hero(project)
    (project.cwd / "blender-fails").write_text("the fake Blender was told to fail", encoding="utf-8")

    result = project.json("run", HERO, "model", expect=1)

    assert result["findings"][0]["code"] == "stage.failed"
    assert "told to fail" in result["findings"][0]["message"]
    assert stage_status(project, HERO)["model"] == "failed"


def test_a_cancelled_run_leaves_the_stage_todo_and_nothing_written(project: Kiripix, server: Server) -> None:  # noqa: F811
    folder = picked_hero(project)
    hold = project.cwd / "hold-blender"
    hold.write_text("", encoding="utf-8")
    replies: list[Any] = []
    body = {"asset": HERO, "stage": "model"}
    caller = threading.Thread(
        target=lambda: replies.append(server.call("/api/run", body, headers={"X-Kiripix-Job": "m"})))
    try:
        caller.start()
        wait_for(project.cwd / "blender-holding")
        server.call("/api/jobs/m/cancel")
        caller.join(timeout=30)
    finally:
        hold.unlink(missing_ok=True)

    [reply] = replies
    assert reply.codes == ["run.cancelled"]
    assert stage_status(project, HERO)["model"] == "todo"
    assert not (folder / "work" / "model").exists()


def set_blender(project: Kiripix, executable: str) -> None:
    path = project.cwd / "kiripix.toml"
    text = path.read_text("utf-8")
    assert "# blender = " in text
    quoted = json.dumps(executable)  # a TOML basic string takes the same escapes for a path
    path.write_text(text.replace("# blender = ", f"blender = {quoted}  # blender = ", 1), encoding="utf-8")


def test_without_blender_the_finding_names_the_setting_and_the_version(project: Kiripix) -> None:
    picked_hero(project, test_recipes=False)
    set_blender(project, str(project.cwd / "no" / "such" / "blender.exe"))

    result = project.json("run", HERO, "model", expect=3, test_recipes=False)

    finding = result["findings"][0]
    assert finding["code"] == "blender.not_found" and finding["fix"] is None
    assert "[character] blender" in finding["owner_action"] and "5.2" in finding["owner_action"]
    assert "5.2" in finding["message"] and "[character] blender" in finding["message"]
    assert not (project.cwd / "assets" / "character" / "hero" / "work" / "model").exists()


def test_a_program_that_is_not_blender_5_2_is_a_finding_not_a_guess(project: Kiripix) -> None:
    picked_hero(project, test_recipes=False)
    set_blender(project, sys.executable)  # runs, but prints no "Blender x.y"

    finding = project.json("run", HERO, "model", expect=3, test_recipes=False)["findings"][0]

    assert finding["code"] == "blender.wrong_version" and finding["owner_action"] and finding["fix"] is None
    assert "5.2" in finding["owner_action"]


def test_an_unskinned_mesh_is_reported_and_warned_about(project: Kiripix) -> None:
    folder = picked_hero(project, "rigged_stray.glb")

    result = project.json("run", HERO, "model")

    [finding] = [f for f in result["findings"] if f["code"] == "model.unskinned_mesh"]
    assert finding["severity"] == "warning" and finding["fix"] is None and "Icosphere" in finding["message"]
    assert "dropped" in finding["message"]
    assert "Remove" in finding["owner_action"] and "skinned" in finding["owner_action"]
    assert "rigged_stray.glb (stored as" in finding["owner_action"]  # the name the Owner imported, not the hash
    document = json.loads((folder / "work" / "model" / "model.json").read_text("utf-8"))
    assert [i["name"] for i in document["ignored"]] == ["Icosphere"] and document["ignored"][0]["vertices"] > 0
    assert [f["code"] for f in project.json("check", HERO)["findings"] if f["code"].startswith("model.")] == [
        "model.unskinned_mesh"]


def test_a_clean_model_has_nothing_ignored_and_no_warning(project: Kiripix) -> None:
    folder = picked_hero(project)

    result = project.json("run", HERO, "model")

    assert result["findings"] == []
    assert json.loads((folder / "work" / "model" / "model.json").read_text("utf-8"))["ignored"] == []


@pytest.mark.blender
def test_the_stray_mesh_is_left_out_of_the_measurement_on_real_blender(project: Kiripix) -> None:
    folder = picked_hero(project, "rigged_stray.glb", test_recipes=False)
    set_blender(project, os.environ["KIRIPIX_BLENDER"])

    result = project.json("run", HERO, "model", test_recipes=False, timeout=300)

    document = json.loads((folder / "work" / "model" / "model.json").read_text("utf-8"))
    assert document["height"] == pytest.approx(2.0, abs=0.01)
    # the importer's own bone shape isn't reported; the fixture's sphere (20 faces, 60 vertices once split by the glTF round trip) is, under whichever name is free
    assert [i["vertices"] for i in document["ignored"]] == [60] and document["ignored"][0]["name"].startswith("Icosphere")
    assert [f["code"] for f in result["findings"]] == ["model.unskinned_mesh"]
    clean = picked_hero_in(project, "rigged.fbx")
    assert clean["height"] == pytest.approx(document["height"], rel=0.01)
    assert clean["ignored"] == [] and clean["vertices"] == document["vertices"]


def picked_hero_in(project: Kiripix, file: str) -> dict[str, Any]:
    """Normalise `file` as another character on real Blender and return its model.json."""
    project.json("new", "character", "other", test_recipes=False)
    shutil.copy(FIXTURES / file, project.cwd / file)
    variant = project.json("import", "character.other", file, test_recipes=False)["data"]["variant"]
    project.json("pick", "character.other", variant, test_recipes=False)
    project.json("run", "character.other", "model", test_recipes=False, timeout=300)
    path = project.cwd / "assets" / "character" / "other" / "work" / "model" / "model.json"
    document: dict[str, Any] = json.loads(path.read_text("utf-8"))
    return document


@pytest.mark.blender
@pytest.mark.parametrize("file", ["rigged.glb", "rigged.fbx", "no_rig.glb", "no_rig.fbx"])
def test_each_fixture_normalises_to_the_same_height_and_up_axis(project: Kiripix, file: str) -> None:
    folder = picked_hero(project, file, test_recipes=False)
    set_blender(project, os.environ["KIRIPIX_BLENDER"])

    project.json("run", HERO, "model", test_recipes=False, timeout=300)

    document = json.loads((folder / "work" / "model" / "model.json").read_text("utf-8"))
    assert document["schema_version"] == 2 and document["up"] == "+Z"
    low, high = document["bounds"]["min"], document["bounds"]["max"]
    assert high[2] - low[2] == pytest.approx(2.0, abs=0.01) and low[2] == pytest.approx(0.0, abs=0.01)
    assert document["height"] == pytest.approx(2.0, abs=0.01)
    assert (folder / "work" / "model" / "model.blend").stat().st_size > 0
    if file.startswith("rigged"):
        assert "root" in document["bones"] and "mixamorig:Hips" in document["bones"]
        assert len(document["actions"]) >= 2 and document["armature"]
    else:
        assert document["bones"] == [] and document["armature"] is None


# ticket 0121: which way the Model faces


def test_facing_is_a_choice_parameter_of_model_with_a_default_of_minus_y(project: Kiripix) -> None:
    [kind] = project.json("describe", "character", "--stage", "model")["data"]["kinds"]

    [stage] = kind["stages"]

    [facing] = [p for p in stage["params"] if p["name"] == "facing"]
    assert facing["default"] == "-y" and facing["choices"] == ["-y", "+y", "-x", "+x"]


def test_facing_reaches_blender_is_recorded_and_changing_it_makes_model_and_the_rest_stale(project: Kiripix) -> None:
    folder = picked_hero(project)
    project.json("run", HERO, "model")
    project.json("run", HERO, "rig")
    document = json.loads((folder / "work" / "model" / "model.json").read_text("utf-8"))
    assert document["facing"] == "-y" and calls(project)[0]["args"]["facing"] == "-y"
    assert stage_status(project, HERO)["model"] == "done" and stage_status(project, HERO)["rig"] == "done"

    project.json("set", HERO, "model", "facing=+y")

    status = stage_status(project, HERO)
    assert status["model"] == "stale" and status["rig"] == "stale"
    project.json("run", HERO, "model")
    document = json.loads((folder / "work" / "model" / "model.json").read_text("utf-8"))
    assert document["facing"] == "+y" and calls(project)[-1]["args"]["facing"] == "+y"


def test_an_unknown_facing_is_refused(project: Kiripix) -> None:
    picked_hero(project)

    result = project.json("set", HERO, "model", "facing=up", expect=1)

    assert result["ok"] is False


@pytest.mark.blender
def test_the_stray_mesh_is_deleted_from_model_blend_on_real_blender(project: Kiripix) -> None:
    folder = picked_hero(project, "rigged_stray.glb", test_recipes=False)
    set_blender(project, os.environ["KIRIPIX_BLENDER"])
    project.json("run", HERO, "model", test_recipes=False, timeout=300)
    clean = picked_hero_in(project, "rigged.glb")
    script = project.cwd / "list_meshes.py"
    out = project.cwd / "meshes.json"

    def meshes(blend: Path) -> list[str]:
        script.write_text(
            "import bpy, json\n"
            f"bpy.ops.wm.open_mainfile(filepath={str(blend)!r})\n"
            "shapes = {b.custom_shape for o in bpy.data.objects if o.type == 'ARMATURE' for b in o.pose.bones if b.custom_shape}\n"
            f"open({str(out)!r}, 'w').write(json.dumps(sorted(o.name for o in bpy.data.objects if o.type == 'MESH' and o not in shapes)))\n",
            encoding="utf-8")
        subprocess.run([os.environ["KIRIPIX_BLENDER"], "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                        str(script)], check=True, capture_output=True, timeout=300)
        found: list[str] = json.loads(out.read_text("utf-8"))
        return found

    stray = meshes(folder / "work" / "model" / "model.blend")
    other = meshes(project.cwd / "assets" / "character" / "other" / "work" / "model" / "model.blend")
    document = json.loads((folder / "work" / "model" / "model.json").read_text("utf-8"))
    assert stray == other == ["Body"] and len(document["ignored"]) == 1
    assert document["bounds"] == clean["bounds"] and document["vertices"] == clean["vertices"]


# ticket 0122: a still of the Model


def test_the_model_stage_lists_a_still_in_its_outputs_and_it_is_no_input_of_rig(project: Kiripix) -> None:
    folder = picked_hero(project)

    project.json("run", HERO, "model")

    assert (folder / "work" / "model" / "still.png").is_file()
    assert calls(project)[0]["args"]["still"].endswith("still.png")
    [model] = [s for s in project.json("show", HERO)["data"]["stages"] if s["stage"] == "model"]
    assert "assets/character/hero/work/model/still.png" in model["outputs"]
    document = json.loads((folder / "work" / "model" / "model.json").read_text("utf-8"))
    assert "still" not in document


def test_changing_the_camera_preset_leaves_model_and_its_still_alone(project: Kiripix) -> None:
    picked_hero(project)
    project.json("run", HERO, "model")

    project.json("set", HERO, "render", "camera=top34_8")

    assert stage_status(project, HERO)["model"] == "done"


@pytest.mark.blender
@pytest.mark.parametrize("file", ["rigged.glb", "rigged.fbx", "no_rig.glb", "no_rig.fbx"])
def test_each_fixture_writes_a_256_px_still_with_the_feet_on_the_same_row(project: Kiripix, file: str) -> None:
    from PIL import Image

    folder = picked_hero(project, file, test_recipes=False)
    set_blender(project, os.environ["KIRIPIX_BLENDER"])

    project.json("run", HERO, "model", test_recipes=False, timeout=300)

    with Image.open(folder / "work" / "model" / "still.png") as image:
        still = image.convert("RGBA")
    assert still.size == (256, 256)
    alpha = still.getchannel("A")
    assert set(alpha.tobytes()) <= {0, 255}, "no anti-aliasing"
    box = alpha.getbbox()
    assert box is not None and box[0] > 0 and box[2] < 256 and box[1] > 0 and box[3] <= 256 - 8
    assert 241 <= box[3] <= 245, f"the feet are at row {box[3]}"  # the pivot row is 232; the feet's front edge is ~11 px below it
    assert len({still.getpixel((x, y)) for x in range(0, 256, 4) for y in range(0, 256, 4)}) > 3, "colour, not a silhouette"


def nose_pixels(path: Path) -> int:
    """How many pixels of the still are the fixtures' red nose (flat colour, so no bands)."""
    from PIL import Image

    with Image.open(path) as image:
        rgba = image.convert("RGBA")
    return sum(1 for r, g, b, a in rgba.get_flattened_data() if a == 255 and r > 150 and g < 90 and b < 90)


@pytest.mark.blender
@pytest.mark.parametrize("file", ["rigged.glb", "rigged.fbx", "no_rig.glb", "no_rig.fbx", "rigged_stray.glb"])
def test_the_still_shows_the_nose_at_the_default_facing_and_not_when_turned_away(project: Kiripix, file: str) -> None:
    folder = picked_hero(project, file, test_recipes=False)
    set_blender(project, os.environ["KIRIPIX_BLENDER"])
    still = folder / "work" / "model" / "still.png"
    project.json("run", HERO, "model", test_recipes=False, timeout=300)
    assert nose_pixels(still) > 20

    project.json("set", HERO, "model", "facing=+y", test_recipes=False)
    project.json("run", HERO, "model", test_recipes=False, timeout=300)

    assert nose_pixels(still) == 0


@pytest.mark.blender
def test_the_still_shows_the_facing_after_it_is_applied(project: Kiripix) -> None:
    from PIL import Image, ImageChops

    folder = picked_hero(project, "no_rig.glb", test_recipes=False)
    set_blender(project, os.environ["KIRIPIX_BLENDER"])
    still = folder / "work" / "model" / "still.png"
    project.json("run", HERO, "model", test_recipes=False, timeout=300)
    front = Image.open(still).convert("RGBA").copy()

    project.json("set", HERO, "model", "facing=+y", test_recipes=False)
    project.json("run", HERO, "model", test_recipes=False, timeout=300)
    turned = Image.open(still).convert("RGBA").copy()

    assert ImageChops.difference(front, turned).getbbox() is not None, "a turned Model looks different"
