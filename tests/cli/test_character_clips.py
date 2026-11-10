"""The `clips` Stage (ticket 0103, spec §6.3). The CLI tests run on the fake Blender of `kiripix_test_recipes.py`: a clip
source or rigged file whose content is JSON says which actions it holds, and any other file holds the fake Model's `idle`
(0-24) and `walk` (0-30) at 30 frames a second. The marked tests run the real Blender 5.2 on the fixture Models."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Kiripix, stage_status
from test_character_model import FIXTURES, HERO, calls, picked_hero, set_blender

IDLE = {"name": "idle", "source": "idle", "start": 0, "end": 24, "fps": 12, "loop": True, "stationary": True}
WALK = {"name": "walk", "source": "walk", "start": 0, "end": 30, "fps": 10, "loop": True}
HIT = {"name": "hit", "source": "walk", "start": 0, "end": 6, "fps": 15, "loop": False}


def clip(project: Kiripix, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return project.json("decide", HERO, "clips", "--decision", json.dumps({"decision": "clip", "data": data}), **kwargs)


def clips_json(folder: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((folder / "work" / "clips" / "clips.json").read_text("utf-8"))
    return document


def rigged_hero(project: Kiripix) -> Path:
    folder = picked_hero(project)
    project.json("run", HERO, "model")
    project.json("run", HERO, "rig")
    return folder


def add_source(project: Kiripix, name: str, **content: Any) -> None:
    path = project.cwd / f"{name}.fbx"
    path.write_text(json.dumps(content), encoding="utf-8")
    project.json("import", HERO, str(path), "--role", "clip-source")


def test_no_clips_is_needs_input_with_the_decisions_shape(project: Kiripix) -> None:
    rigged_hero(project)

    result = project.json("run", HERO, "clips", expect=3)

    [finding] = result["findings"]
    assert finding["code"] == "stage.needs_input"
    text = json.dumps(finding)
    assert "kiripix decide character.hero clips --decision" in text
    for field in ("name", "source", "start", "end", "fps", "loop"):
        assert field in text
    assert stage_status(project, HERO)["clips"] == "needs-input"
    assert project.json("next", HERO)["data"]["stage"] == "clips"


def test_three_clips_build_clips_json_with_the_sampled_frames_and_undo_removes_one(project: Kiripix) -> None:
    folder = rigged_hero(project)
    for data in (WALK, IDLE, HIT):
        clip(project, data)

    result = project.json("run", HERO, "clips")

    assert [(r["stage"], r["outcome"]) for r in result["data"]["results"]] == [("clips", "done")]
    document = clips_json(folder)
    assert document["schema_version"] == 1
    by_name = {c["name"]: c for c in document["clips"]}
    assert list(by_name) == ["hit", "idle", "walk"]  # sorted by name
    # idle: 24 source frames at 30 fps, 12 fps samples every 2.5 frames; a loop stops before its end
    assert by_name["idle"]["frames"] == [0, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5]
    assert by_name["idle"]["stationary"] is True and by_name["walk"]["stationary"] is False
    assert by_name["walk"]["frames"] == [0, 3, 6, 9, 12, 15, 18, 21, 24, 27]
    assert by_name["hit"]["frames"] == [0, 2, 4, 6]  # not a loop: the end frame is the last sample
    walk = by_name["walk"]
    assert walk["source"] == "walk" and walk["action"] == "walk" and len(walk["source_hash"]) == 16
    assert (walk["start"], walk["end"], walk["fps"], walk["source_fps"], walk["loop"]) == (0, 30, 10, 30, True)
    assert walk["root_motion"] is False
    assert project.json("next", HERO)["data"]["stage"] == "render"

    project.json("undo", HERO, "clips")
    assert stage_status(project, HERO)["clips"] == "stale"
    project.json("run", HERO, "clips")
    assert [c["name"] for c in clips_json(folder)["clips"]] == ["idle", "walk"]


def test_a_clip_source_file_resolves_its_stem_and_its_hash_follows_the_file(project: Kiripix) -> None:
    folder = rigged_hero(project)
    actions = [{"name": "Armature|mixamo.com|Layer0", "start": 1, "end": 31, "travel": 0.0}]
    add_source(project, "wave", actions=actions)
    clip(project, {"name": "wave", "source": "wave", "start": 1, "end": 31, "fps": 10, "loop": False})
    project.json("run", HERO, "clips")
    first = clips_json(folder)["clips"][0]
    assert first["action"] == "Armature|mixamo.com|Layer0" and first["frames"][-1] == 31

    add_source(project, "wave", actions=actions, fps=24)
    assert stage_status(project, HERO)["clips"] == "stale"
    project.json("run", HERO, "clips")
    second = clips_json(folder)["clips"][0]
    assert second["source_hash"] != first["source_hash"] and second["source_fps"] == 24


def test_a_file_with_several_actions_needs_the_action_named(project: Kiripix) -> None:
    folder = rigged_hero(project)
    add_source(project, "moves", actions=[{"name": "a", "start": 0, "end": 10, "travel": 0.0},
                                           {"name": "b", "start": 0, "end": 10, "travel": 0.0}])
    clip(project, {"name": "move", "source": "moves", "start": 0, "end": 10, "fps": 10, "loop": False})

    finding = project.json("run", HERO, "clips", expect=3)["findings"][0]
    assert finding["code"] == "clips.source_missing" and "moves/<action>" in finding["message"]

    project.json("undo", HERO, "clips")
    clip(project, {"name": "move", "source": "moves/b", "start": 0, "end": 10, "fps": 10, "loop": False})
    project.json("run", HERO, "clips")
    assert clips_json(folder)["clips"][0]["action"] == "b"


def test_a_missing_source_gives_clips_source_missing(project: Kiripix) -> None:
    folder = rigged_hero(project)
    clip(project, {**WALK, "name": "run", "source": "sprint"})

    result = project.json("run", HERO, "clips", expect=3)

    [finding] = result["findings"]
    assert finding["code"] == "clips.source_missing" and finding["fix"] is None
    assert "sprint" in finding["message"] and "idle, walk" in finding["message"]
    assert "--role clip-source" in finding["owner_action"]
    assert stage_status(project, HERO)["clips"] == "failed" and not (folder / "work" / "clips").exists()


def test_an_end_past_the_action_gives_clips_range(project: Kiripix) -> None:
    rigged_hero(project)
    clip(project, {**IDLE, "end": 25})

    [finding] = project.json("run", HERO, "clips", expect=1)["findings"]

    assert finding["code"] == "clips.range" and "idle" in finding["message"] and "0-24" in finding["message"]
    assert finding["fix"] == "kiripix undo character.hero clips"
    project.json("undo", HERO, "clips")
    clip(project, {**IDLE, "start": 10, "end": 5})
    assert project.json("run", HERO, "clips", expect=1)["findings"][0]["code"] == "clips.range"


def test_a_duplicate_name_gives_clips_duplicate_name(project: Kiripix) -> None:
    rigged_hero(project)
    clip(project, IDLE)
    clip(project, {**WALK, "name": "idle"})

    [finding] = project.json("run", HERO, "clips", expect=1)["findings"]

    assert finding["code"] == "clips.duplicate_name" and "idle" in finding["message"]
    assert finding["fix"] == "kiripix undo character.hero clips"
    project.json("undo", HERO, "clips")
    assert project.json("run", HERO, "clips")["data"]["results"][-1]["outcome"] == "done"


@pytest.mark.parametrize("name", ["Walk", "walk-fast", "walk_sw", "idle_s", "attack_ne", "", "a b"])
def test_a_bad_clip_name_is_refused_at_decide(project: Kiripix, name: str) -> None:
    rigged_hero(project)

    result = clip(project, {**WALK, "name": name}, expect=1)

    assert result["findings"]


@pytest.mark.parametrize("name", ["walk", "walk_fast", "attack_2", "s", "ko", "walk_sword"])
def test_a_good_clip_name_is_taken(project: Kiripix, name: str) -> None:
    rigged_hero(project)

    clip(project, {**WALK, "name": name})


def test_root_motion_is_a_warning_with_the_in_place_owner_action(project: Kiripix) -> None:
    folder = rigged_hero(project)
    add_source(project, "stroll", height=2.0, actions=[{"name": "stroll", "start": 0, "end": 30, "travel": 1.5}])
    clip(project, {"name": "stroll", "source": "stroll", "start": 0, "end": 30, "fps": 10, "loop": True})
    clip(project, IDLE)

    result = project.json("run", HERO, "clips")

    assert [f["code"] for f in result["findings"]] == ["clips.root_motion"]
    finding = result["findings"][0]
    assert finding["severity"] == "warning" and finding["fix"] is None
    assert "In Place" in finding["owner_action"] and "stroll" in finding["message"]
    by_name = {c["name"]: c for c in clips_json(folder)["clips"]}
    assert by_name["stroll"]["root_motion"] is True and by_name["stroll"]["root_travel"] == 0.75
    assert by_name["idle"]["root_motion"] is False
    codes = [f["code"] for f in project.json("check", HERO)["findings"] if f["code"].startswith("clips.")]
    assert codes == ["clips.root_motion"]


def test_the_same_clips_are_skipped_and_a_new_clip_makes_the_stage_stale(project: Kiripix) -> None:
    rigged_hero(project)
    clip(project, IDLE)
    project.json("run", HERO, "clips")
    before = len(calls(project))

    again = project.json("run", HERO, "clips")

    assert again["data"]["results"][0]["outcome"] == "skipped" and len(calls(project)) == before
    clip(project, WALK)
    assert stage_status(project, HERO)["clips"] == "stale"


def test_blender_is_asked_once_per_file(project: Kiripix) -> None:
    rigged_hero(project)
    for data in (IDLE, WALK, HIT):
        clip(project, data)
    project.json("run", HERO, "clips")

    assert [c["script"] for c in calls(project)].count("read_actions") == 1


def test_describe_shows_the_final_schema(project: Kiripix) -> None:
    [kind] = project.json("describe", "character", "--stage", "clips")["data"]["kinds"]
    [stage] = kind["stages"]

    [decision] = stage["decisions"]
    properties = decision["entry_schema"]["properties"]
    assert set(properties) == {"name", "source", "start", "end", "fps", "loop", "stationary"}
    assert properties["stationary"]["default"] is False
    assert decision["entry_schema"]["required"] == ["name", "source", "start", "end", "fps", "loop"]
    assert [c["code"] for c in stage["checks"]] == [
        "clips.source_missing", "clips.range", "clips.duplicate_name", "clips.bad_name", "clips.root_motion"]


# the real Blender


def real_hero(project: Kiripix, file: str = "rigged.fbx") -> Path:
    folder = picked_hero(project, file, test_recipes=False)
    set_blender(project, os.environ["KIRIPIX_BLENDER"])
    project.json("run", HERO, "model", test_recipes=False, timeout=900)
    project.json("run", HERO, "rig", test_recipes=False, timeout=900)
    return folder


def blender_script(project: Kiripix, source: str, name: str) -> None:
    script = project.cwd / f"{name}.py"
    script.write_text(source, encoding="utf-8")
    subprocess.run([os.environ["KIRIPIX_BLENDER"], "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                    str(script)], check=True, capture_output=True, timeout=300)


@pytest.mark.blender
@pytest.mark.parametrize("file", ["rigged.fbx", "rigged.glb"])
def test_the_fixtures_actions_resolve_on_real_blender(project: Kiripix, file: str) -> None:
    folder = real_hero(project, file)
    clip(project, {"name": "idle", "source": "idle", "start": 1, "end": 25, "fps": 12, "loop": True, "stationary": True},
         test_recipes=False)
    clip(project, {"name": "walk", "source": "walk", "start": 1, "end": 25, "fps": 8, "loop": True}, test_recipes=False)

    result = project.json("run", HERO, "clips", test_recipes=False, timeout=900)

    assert result["findings"] == []
    by_name = {c["name"]: c for c in clips_json(folder)["clips"]}
    assert by_name["walk"]["root_motion"] is False and by_name["idle"]["root_motion"] is False
    assert by_name["idle"]["source_fps"] > 0 and by_name["walk"]["frames"][0] == 1
    assert len(by_name["walk"]["frames"]) == round(24 / by_name["walk"]["source_fps"] * 8)


@pytest.mark.blender
def test_a_clip_source_file_whose_root_travels_is_root_motion_on_real_blender(project: Kiripix) -> None:
    folder = real_hero(project)
    travelling = project.cwd / "stroll.fbx"
    blender_script(project, (
        "import bpy\n"
        f"bpy.ops.import_scene.fbx(filepath={str(FIXTURES / 'rigged.fbx')!r})\n"
        "rig = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]\n"
        "for a in list(bpy.data.actions):\n"
        "    if not a.name.endswith('walk'):\n"
        "        bpy.data.actions.remove(a)\n"
        "rig.animation_data_create()\n"
        "action = bpy.data.actions[0]\n"
        "rig.animation_data.action = action\n"
        "if hasattr(action, 'slots') and action.slots:\n"
        "    rig.animation_data.action_slot = action.slots[0]\n"
        "bpy.context.view_layer.objects.active = rig\n"
        "bpy.ops.object.mode_set(mode='POSE')\n"
        "root = rig.pose.bones['root']\n"
        "for frame, d in ((1, 0.0), (25, 3.0)):\n"
        "    root.location = (d, 0, d)\n"  # the bone's own axes: one is on the ground, whatever its roll
        "    root.keyframe_insert('location', frame=frame)\n"
        "bpy.ops.object.mode_set(mode='OBJECT')\n"
        f"bpy.ops.export_scene.fbx(filepath={str(travelling)!r}, bake_anim=True, bake_anim_use_all_actions=False,\n"
        "                         bake_anim_use_nla_strips=False, add_leaf_bones=False)\n"), "make_stroll")
    project.json("import", HERO, str(travelling), "--role", "clip-source", test_recipes=False)
    clip(project, {"name": "stroll", "source": "stroll", "start": 2, "end": 100, "fps": 8, "loop": True},
         test_recipes=False)

    result = project.json("run", HERO, "clips", test_recipes=False, timeout=900)

    assert [f["code"] for f in result["findings"]] == ["clips.root_motion"]
    [built] = clips_json(folder)["clips"]
    assert built["root_motion"] is True and built["root_travel"] > 0.5


@pytest.mark.blender
def test_an_end_past_a_real_action_gives_clips_range(project: Kiripix) -> None:
    real_hero(project)
    clip(project, {"name": "idle", "source": "idle", "start": 1, "end": 999, "fps": 12, "loop": True}, test_recipes=False)

    finding = project.json("run", HERO, "clips", expect=1, test_recipes=False, timeout=900)["findings"][0]

    assert finding["code"] == "clips.range"
