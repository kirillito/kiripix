"""The `rig` Stage and the Mixamo round trip (ticket 0102, spec §6.3). The CLI tests run on the fake Blender of
`kiripix_test_recipes.py`: a rigged file whose content is JSON says what it holds, so a test makes a rig from another
Model or a rig with a bone missing by writing that JSON. The marked tests run the real Blender 5.2 on the fixture Models."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Kiripix, stage_status
from test_character_model import FIXTURES, HERO, calls, picked_hero, set_blender

MIXAMO = ["mixamorig:" + n for n in (
    "Hips", "Spine", "Neck", "Head", "LeftArm", "RightArm", "LeftUpLeg", "RightUpLeg", "LeftFoot", "RightFoot")]


def rigged_json(tmp: Path, name: str = "mixamo.fbx", **changes: Any) -> Path:
    """A fake rigged file: the fake Blender reads its content as JSON."""
    document = {"armature": "Armature", "bones": MIXAMO, "vertices": 100, "size": [1.0, 0.5, 2.0], **changes}
    path = tmp / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def rig_json(folder: Path) -> dict[str, Any]:
    return json.loads((folder / "work" / "rig" / "rig.json").read_text("utf-8"))


def test_a_rigged_model_makes_rig_done_and_next_names_clips(project: Kiripix) -> None:
    folder = picked_hero(project)
    project.json("run", HERO, "model")

    result = project.json("run", HERO, "rig")

    assert [(r["stage"], r["outcome"]) for r in result["data"]["results"]] == [("rig", "done")]
    document = rig_json(folder)
    assert document["schema_version"] == 1 and document["source"] == "model" and document["armature"] == "Armature"
    assert document["mapping"]["hips"] == "mixamorig:Hips" and document["mapping"]["left_leg"] == "mixamorig:LeftUpLeg"
    assert {"hips", "spine", "head", "left_arm", "right_arm", "left_leg", "right_leg"} <= set(document["mapping"])
    assert [c["script"] for c in calls(project)] == ["normalise_model", "validate_rig"]
    assert project.json("next", HERO)["data"]["stage"] == "clips"
    again = project.json("run", HERO, "rig")
    assert [r["outcome"] for r in again["data"]["results"]] == ["skipped"]


def test_an_unrigged_model_needs_the_mixamo_steps_and_the_rigged_file_makes_it_done(project: Kiripix) -> None:
    folder = picked_hero(project, "no_rig.glb")
    project.json("run", HERO, "model")

    result = project.json("run", HERO, "rig", expect=3)

    [finding] = result["findings"]
    assert finding["code"] == "stage.needs_input" and finding["fix"] is None
    steps = finding["owner_action"]
    upload = "assets/character/hero/work/model/mixamo_upload.fbx"
    assert upload in steps and "mixamo.com" in steps.lower() and "T-pose" in steps and "FBX" in steps
    assert f"kiripix import {HERO} <downloaded.fbx> --role rigged" in steps
    assert (project.cwd / upload).is_file()
    assert stage_status(project, HERO)["rig"] == "needs-input"
    assert project.json("next", HERO)["data"]["stage"] == "rig"

    project.json("import", HERO, str(rigged_json(project.cwd)), "--role", "rigged")
    done = project.json("run", HERO, "rig")

    assert [(r["stage"], r["outcome"]) for r in done["data"]["results"]] == [("rig", "done")]
    assert rig_json(folder)["source"] == "rigged" and stage_status(project, HERO)["rig"] == "done"
    [*_, last] = calls(project)
    assert last["script"] == "validate_rig" and "rigged" in Path(last["args"]["input"]).parts


def test_a_rigged_file_made_from_another_model_fails_model_mismatch(project: Kiripix) -> None:
    picked_hero(project, "no_rig.glb")
    project.json("run", HERO, "model")
    for changes in ({"vertices": 160}, {"size": [1.0, 1.0, 2.0]}):
        project.json("import", HERO, str(rigged_json(project.cwd, **changes)), "--role", "rigged")

        result = project.json("run", HERO, "rig", expect=3)

        [finding] = result["findings"]
        assert finding["code"] == "rig.model_mismatch" and finding["fix"] is None
        assert "mixamo_upload.fbx" in finding["owner_action"] and "--role rigged" in finding["owner_action"]
        assert stage_status(project, HERO)["rig"] == "failed"
    project.json("import", HERO, str(rigged_json(project.cwd, vertices=100, size=[3.0, 1.5, 6.0])), "--role", "rigged")
    assert project.json("run", HERO, "rig")["data"]["results"][-1]["outcome"] == "done"  # size's units don't matter


def test_a_rig_without_a_bone_fails_with_the_decision_that_maps_it(project: Kiripix) -> None:
    folder = picked_hero(project, "no_rig.glb")
    project.json("run", HERO, "model")
    others = [b for b in MIXAMO if "LeftArm" not in b] + ["Arm.L"]
    project.json("import", HERO, str(rigged_json(project.cwd, bones=others)), "--role", "rigged")

    result = project.json("run", HERO, "rig", expect=1)

    [finding] = result["findings"]
    assert finding["code"] == "rig.bone_missing" and finding["owner_action"] is None
    assert "left_arm" in finding["message"] and "kiripix decide character.hero rig --decision" in finding["fix"]
    assert not (folder / "work" / "rig").exists()

    decision = {"decision": "bone", "data": {"role": "left_arm", "bone": "Arm.L"}}
    project.json("decide", HERO, "rig", "--decision", json.dumps(decision))
    project.json("run", HERO, "rig")
    assert rig_json(folder)["mapping"]["left_arm"] == "Arm.L"

    bad = {"decision": "bone", "data": {"role": "tail", "bone": "Tail"}}
    assert project.json("decide", HERO, "rig", "--decision", json.dumps(bad), expect=1)["findings"]


def test_a_rigged_file_without_an_armature_is_rig_missing(project: Kiripix) -> None:
    picked_hero(project, "no_rig.glb")
    project.json("run", HERO, "model")
    project.json("import", HERO, str(rigged_json(project.cwd, armature=None, bones=[])), "--role", "rigged")

    finding = project.json("run", HERO, "rig", expect=3)["findings"][0]

    assert finding["code"] == "rig.missing" and "mixamo_upload.fbx" in finding["owner_action"]


# the real Blender


def real_project(project: Kiripix, file: str) -> Path:
    folder = picked_hero(project, file, test_recipes=False)
    set_blender(project, os.environ["KIRIPIX_BLENDER"])
    return folder


@pytest.mark.blender
@pytest.mark.parametrize("file", ["rigged.glb", "rigged.fbx"])
def test_a_rigged_fixture_validates_on_real_blender(project: Kiripix, file: str) -> None:
    folder = real_project(project, file)
    project.json("run", HERO, "model", test_recipes=False, timeout=600)

    project.json("run", HERO, "rig", test_recipes=False, timeout=600)

    document = rig_json(folder)
    assert document["source"] == "model" and document["bones"] >= 18
    assert document["mapping"]["hips"] == "mixamorig:Hips" and document["mapping"]["right_foot"] == "mixamorig:RightFoot"
    assert document["mapping"]["left_arm"] == "mixamorig:LeftArm" and document["vertices"] > 0
    assert not (folder / "work" / "model" / "mixamo_upload.fbx").exists()


@pytest.mark.blender
@pytest.mark.parametrize("file", ["no_rig.glb", "no_rig.fbx"])
def test_an_unrigged_fixture_writes_the_upload_and_takes_the_rigged_file_back(project: Kiripix, file: str) -> None:
    folder = real_project(project, file)
    project.json("run", HERO, "model", test_recipes=False, timeout=600)

    waiting = project.json("run", HERO, "rig", expect=3, test_recipes=False, timeout=600)

    assert waiting["findings"][0]["code"] == "stage.needs_input"
    upload = folder / "work" / "model" / "mixamo_upload.fbx"
    assert upload.stat().st_size > 0 and "mixamo_upload.fbx" in waiting["findings"][0]["owner_action"]
    shown = project.cwd / "upload_probe.json"
    probe = Path(__file__).parent.parent.parent / "kiripix" / "blender" / "validate_rig.py"
    arguments = project.cwd / "probe_args.json"
    arguments.write_text(json.dumps({"input": str(upload)}), encoding="utf-8")
    subprocess.run([os.environ["KIRIPIX_BLENDER"], "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                    str(probe), "--", str(arguments), str(shown)], check=True, capture_output=True, timeout=300)
    uploaded = json.loads(shown.read_text("utf-8"))
    assert uploaded["armature"] is None and uploaded["vertices"] > 0
    assert uploaded["size"][2] == pytest.approx(2.0, abs=0.02)  # upright, at the Model's normalised height

    # what comes back from Mixamo, here the fixture's own rigged FBX: made from the same body
    shutil_copy = project.cwd / "back.fbx"
    shutil_copy.write_bytes((FIXTURES / "rigged.fbx").read_bytes())
    project.json("import", HERO, "back.fbx", "--role", "rigged", test_recipes=False)
    project.json("run", HERO, "rig", test_recipes=False, timeout=600)

    document = rig_json(folder)
    assert document["source"] == "rigged" and document["mapping"]["head"] == "mixamorig:Head"


@pytest.mark.blender
def test_a_rigged_file_from_another_model_fails_on_real_blender(project: Kiripix) -> None:
    folder = real_project(project, "no_rig.fbx")
    project.json("run", HERO, "model", test_recipes=False, timeout=600)
    other = project.cwd / "other.fbx"
    script = project.cwd / "make_other.py"
    script.write_text(
        "import bpy\n"
        f"bpy.ops.import_scene.fbx(filepath={str(FIXTURES / 'rigged.fbx')!r})\n"
        "for o in bpy.data.objects:\n"
        "    if o.type == 'MESH':\n"
        "        bpy.context.view_layer.objects.active = o\n"
        "        bpy.ops.object.mode_set(mode='EDIT')\n"
        "        bpy.ops.mesh.select_all(action='SELECT')\n"
        "        bpy.ops.mesh.subdivide(number_cuts=2)\n"
        "        bpy.ops.object.mode_set(mode='OBJECT')\n"
        f"bpy.ops.export_scene.fbx(filepath={str(other)!r})\n",
        encoding="utf-8")
    subprocess.run([os.environ["KIRIPIX_BLENDER"], "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                    str(script)], check=True, capture_output=True, timeout=300)
    project.json("import", HERO, "other.fbx", "--role", "rigged", test_recipes=False)

    result = project.json("run", HERO, "rig", expect=3, test_recipes=False, timeout=600)

    assert result["findings"][0]["code"] == "rig.model_mismatch"
    assert not (folder / "work" / "rig").exists()


@pytest.mark.blender
def test_a_rigged_file_with_a_stray_mesh_still_matches_its_model_on_real_blender(project: Kiripix) -> None:
    folder = real_project(project, "no_rig.fbx")
    project.json("run", HERO, "model", test_recipes=False, timeout=600)
    project.json("run", HERO, "rig", expect=3, test_recipes=False, timeout=600)
    shutil.copy(FIXTURES / "rigged_stray.glb", project.cwd / "back.glb")  # the body plus a sphere that isn't skinned
    project.json("import", HERO, "back.glb", "--role", "rigged", test_recipes=False)

    result = project.json("run", HERO, "rig", test_recipes=False, timeout=600)

    assert not [f for f in result["findings"] if f["code"] == "rig.model_mismatch"]
    assert rig_json(folder)["source"] == "rigged"
