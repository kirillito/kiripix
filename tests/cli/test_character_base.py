"""A character made from a base (ADR 0012, ticket 0165): its Model carries the base's skeleton, it starts with the base's
clips and clip sources, its unset Stage parameters take the base's, and its height follows the two Models' heights.

On the fake Blender of `kiripix_test_recipes.py`: a Model whose content is JSON says what it holds (`bones`, `parents`,
`source_height`), and its skeleton is what `validate_rig` then reads; without `parents` the bones are one chain. Any other
Model, such as the base's `rigged.glb`, has the fake rig (`BONES`) and stands 1.8 units tall."""

import json
import shutil
from pathlib import Path
from typing import Any

from conftest import Kiripix, stage_status
from test_character_clips import IDLE, WALK, clips_json
from test_character_model import FIXTURES, calls
from test_character_render import render_json
from test_character_rig import rig_json, rigged_json

BODY = "character.zed"  # the base sorts after the characters made from it, so nothing is built first by its name alone
GUARD = "character.guard"
BONES = ["root", *(f"mixamorig:{n}" for n in (
    "Hips", "Spine", "Spine1", "Neck", "Head", "LeftShoulder", "LeftArm", "LeftForeArm", "RightShoulder", "RightArm",
    "RightForeArm", "LeftUpLeg", "LeftLeg", "LeftFoot", "RightUpLeg", "RightLeg", "RightFoot"))]
ACTIONS = [{"name": "Armature|mixamo.com|Layer0", "start": 1, "end": 31, "travel": 0.0}]
WAVE = {"name": "wave", "source": "wave", "start": 1, "end": 31, "fps": 10, "loop": False}


def folder_of(project: Kiripix, asset: str) -> Path:
    return project.cwd / "assets" / "character" / asset.split(".", 1)[1]


def decide(project: Kiripix, asset: str, decision: str, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return project.json("decide", asset, "clips", "--decision", json.dumps({"decision": decision, "data": data}), **kwargs)


def clip_source(project: Kiripix, asset: str, name: str, **content: Any) -> None:
    path = project.cwd / f"{name}.fbx"
    path.write_text(json.dumps(content), encoding="utf-8")
    project.json("import", asset, str(path), "--role", "clip-source")


def body(project: Kiripix, build: bool = True) -> Path:
    """The base: the rigged fixture, with idle and walk (actions of its Model) and wave (a clip-source file)."""
    project.json("new", "character", "zed")
    shutil.copy(FIXTURES / "rigged.glb", project.cwd / "zed.glb")
    project.json("pick", BODY, project.json("import", BODY, "zed.glb")["data"]["variant"])
    clip_source(project, BODY, "wave", actions=ACTIONS)
    for data in (IDLE, WALK, WAVE):
        decide(project, BODY, "clip", data)
    if build:
        for stage in ("model", "rig", "clips"):
            project.json("run", BODY, stage)
    return folder_of(project, BODY)


def guard(project: Kiripix, name: str = "guard", bones: list[str] | None = None, height: float = 1.62,
          **model: Any) -> Path:
    """A character made from the base, with a Model of its own on the base's skeleton, 0.9 of the base's height."""
    asset = f"character.{name}"
    project.json("new", "character", name, "--base", BODY)
    path = project.cwd / f"{name}.glb"
    path.write_text(json.dumps({"bones": BONES if bones is None else bones, "source_height": height, **model}), encoding="utf-8")
    project.json("pick", asset, project.json("import", asset, path.name)["data"]["variant"])
    return folder_of(project, asset)


def stage(project: Kiripix, asset: str, name: str) -> dict[str, Any]:
    shown = project.json("show", asset)["data"]
    found: dict[str, Any] = next(s for s in shown["stages"] if s["stage"] == name)
    return found


def test_a_character_made_from_a_base_reaches_render_with_the_bases_clips_and_no_rigged_file(project: Kiripix) -> None:
    zed = body(project)
    folder = guard(project)

    for name in ("model", "rig", "clips", "render"):
        result = project.json("run", GUARD, name)
        assert [(r["stage"], r["outcome"]) for r in result["data"]["results"]] == [(name, "done")], name

    rig = rig_json(folder)
    assert rig["source"] == "model" and rig["parents"]["mixamorig:Hips"] == "root"
    assert rig["mapping"]["hips"] == "mixamorig:Hips"
    assert [c["name"] for c in clips_json(folder)["clips"]] == ["idle", "walk", "wave"]
    assert not (folder / "src" / "clips").exists() and not (folder / "src" / "rigged").exists(), "nothing is copied"
    [render] = [c for c in calls(project) if c["script"] == "render_frames" and not c["args"].get("measure")]
    wave = next(c for c in render["args"]["clips"] if c["name"] == "wave")
    assert Path(wave["file"]).parent.resolve() == (zed / "src" / "clips").resolve(), "the base's clip source is read where it is"

    shown = project.json("show", GUARD)["data"]
    assert shown["base"] == BODY and shown["params"] == {"base": BODY}
    [source] = shown["clip_sources"]
    assert source["name"] == "wave" and source["file"].startswith("assets/character/zed/src/clips/wave.")
    decisions = stage(project, GUARD, "clips")["decisions"]
    assert [(d["data"]["name"], d["from_base"]) for d in decisions] == [("idle", True), ("walk", True), ("wave", True)]
    assert f"made from {BODY}" in project("show", GUARD).stdout


def test_a_clip_changed_on_the_character_does_not_change_the_bases_and_undo_never_reaches_the_base(project: Kiripix) -> None:
    zed = body(project)
    folder = guard(project)
    for name in ("model", "rig"):
        project.json("run", GUARD, name)

    decide(project, GUARD, "clip", {**IDLE, "end": 12})
    project.json("run", GUARD, "clips")

    assert next(c for c in clips_json(folder)["clips"] if c["name"] == "idle")["end"] == 12
    assert [c["name"] for c in clips_json(folder)["clips"]] == ["idle", "walk", "wave"]
    assert stage_status(project, BODY)["clips"] == "done"
    assert next(c for c in clips_json(zed)["clips"] if c["name"] == "idle")["end"] == 24
    decisions = stage(project, GUARD, "clips")["decisions"]
    assert [d["from_base"] for d in decisions] == [True, True, True, False]

    project.json("undo", GUARD, "clips")
    [finding] = project.json("undo", GUARD, "clips", expect=1)["findings"]

    assert finding["code"] == "decision.nothing_to_undo"
    assert len(stage(project, BODY, "clips")["decisions"]) == 3
    project.json("run", GUARD, "clips")
    assert next(c for c in clips_json(folder)["clips"] if c["name"] == "idle")["end"] == 24


def test_remove_takes_a_base_clip_and_its_transitions_away_from_the_character_only(project: Kiripix) -> None:
    zed = body(project, build=False)
    decide(project, BODY, "transition", {"name": "idle_to_walk", "from": {"clip": "idle"}, "to": {"clip": "walk"}})
    for name in ("model", "rig", "clips"):
        project.json("run", BODY, name)
    folder = guard(project)
    for name in ("model", "rig"):
        project.json("run", GUARD, name)

    decide(project, GUARD, "remove", {"name": "walk"})
    result = project.json("run", GUARD, "clips")

    assert result["findings"] == []
    assert [c["name"] for c in clips_json(folder)["clips"]] == ["idle", "wave"]
    assert [c["name"] for c in clips_json(zed)["clips"]] == ["idle", "idle_to_walk", "walk", "wave"]
    assert stage_status(project, BODY)["clips"] == "done"

    decide(project, GUARD, "clip", WALK)  # deciding it again brings the clip back, without the base's transition
    decide(project, GUARD, "remove", {"name": "jump"})
    result = project.json("run", GUARD, "clips")

    assert [c["name"] for c in clips_json(folder)["clips"]] == ["idle", "walk", "wave"]
    [finding] = result["findings"]
    assert finding["code"] == "clips.remove_unknown" and finding["severity"] == "warning" and "jump" in finding["message"]


def test_unset_parameters_take_the_bases_and_one_set_on_the_character_wins(project: Kiripix) -> None:
    body(project)
    guard(project)
    project.json("set", BODY, "render", "bands=4", "shadow=0.7")
    project.json("set", BODY, "finish", "outline_colour=3")
    project.json("set", BODY, "model", "facing=+y")

    project.json("set", GUARD, "render", "shadow=0.2")

    render = stage(project, GUARD, "render")
    assert render["params"]["bands"] == 4 and render["param_sources"]["bands"] == "base"
    assert render["params"]["shadow"] == 0.2 and render["param_sources"]["shadow"] == "asset"
    assert render["param_sources"]["camera"] == "default"
    finish = stage(project, GUARD, "finish")
    assert finish["params"]["outline_colour"] == 3 and finish["param_sources"]["outline_colour"] == "base"
    model = stage(project, GUARD, "model")
    assert model["params"]["facing"] == "-y" and model["param_sources"]["facing"] == "default", \
        "the way a Model faces is its own file's, never the base's"
    assert "bands=4 (base)" in project("show", GUARD).stdout
    assert stage(project, BODY, "render")["param_sources"]["bands"] == "asset"


def test_a_changed_base_parameter_makes_the_characters_stage_stale(project: Kiripix) -> None:
    body(project)
    guard(project)
    for name in ("model", "rig", "clips", "render"):
        project.json("run", GUARD, name)
    assert stage_status(project, GUARD)["render"] == "done"

    project.json("set", BODY, "render", "bands=4")

    status = stage_status(project, GUARD)
    assert status["clips"] == "done" and status["render"] == "stale"


def test_the_height_follows_the_two_models_heights_unless_the_character_sets_it(project: Kiripix) -> None:
    body(project)
    folder = guard(project)  # 1.62 against the base's 1.8: 0.9 of its height
    for name in ("model", "rig", "clips", "render"):
        project.json("run", GUARD, name)

    assert render_json(folder)["height"] == 47, "0.9 of the Project's 52 px, rounded"
    assert "height" not in stage(project, GUARD, "render")["params"]

    project.json("set", BODY, "render", "height=60")

    assert stage_status(project, GUARD)["render"] == "stale", "the base's height is an input of the character's render"
    project.json("run", GUARD, "render")
    assert render_json(folder)["height"] == 54
    assert "height" not in stage(project, GUARD, "render")["params"], "the base's height is scaled, never copied"

    project.json("set", GUARD, "render", "height=40")
    project.json("run", GUARD, "render")

    assert render_json(folder)["height"] == 40


def test_the_bases_height_is_its_rigged_files_when_it_has_one(project: Kiripix) -> None:
    """Mixamo's file comes back at the size of the upload, not of the Model's file, and a Model on the base's skeleton is
    built from it: on the Owner's mc03, 2.0 against the Model's 1.78."""
    project.json("new", "character", "zed")
    shutil.copy(FIXTURES / "no_rig.glb", project.cwd / "zed.glb")
    project.json("pick", BODY, project.json("import", BODY, "zed.glb")["data"]["variant"])
    project.json("run", BODY, "model")  # the fake Model's own height is 1.8
    rigged = rigged_json(project.cwd, bones=BONES, size=[1.8, 0.9, 3.6])
    project.json("import", BODY, str(rigged), "--role", "rigged")
    project.json("run", BODY, "rig")
    assert rig_json(folder_of(project, BODY))["height"] == 3.6
    folder = guard(project, height=3.24)
    for name in ("model", "rig"):
        project.json("run", GUARD, name)
    assert rig_json(folder)["height"] == 3.24
    decide(project, GUARD, "clip", IDLE)

    project.json("run", GUARD, "clips")
    project.json("run", GUARD, "render")

    assert render_json(folder)["height"] == 47, "0.9 of 52 px: 3.24 against the rigged file's 3.6, not the Model's 1.8"


def test_a_base_that_cannot_be_one_is_refused_and_nothing_is_created(project: Kiripix) -> None:
    body(project, build=False)
    guard(project)
    project.json("new", "room", "alley", "--view", "top")

    for name, base, why in (("a", "character.nobody", "no such Asset"), ("b", "room.alley", "is a room"),
                            ("c", "character.c", "its own base"), ("d", GUARD, f"made from {BODY}"),
                            ("e", "Zed", "not an Asset ID")):
        [finding] = project.json("new", "character", name, "--base", base, expect=1)["findings"]

        assert finding["code"] == "asset.base_invalid" and why in finding["message"], name
        assert finding["fix"] and finding["position"]["field"] == "params.base"
        assert not folder_of(project, f"character.{name}").exists()

    [finding] = project.json("new", "room", "yard", "--view", "top", "--base", BODY, expect=1)["findings"]
    assert finding["code"] == "asset.param_unknown"


def test_a_base_edited_into_asset_toml_is_checked_when_the_asset_is_read(project: Kiripix) -> None:
    body(project, build=False)
    folder = guard(project)
    path = folder / "asset.toml"
    path.write_text(path.read_text("utf-8").replace(BODY, "character.gone"), encoding="utf-8")

    result = project.json("status", expect=1)

    [finding] = result["findings"]
    assert finding["code"] == "asset.base_invalid" and "character.gone" in finding["message"]
    assert finding["owner_action"] and finding["position"]["file"] == "assets/character/guard/asset.toml"
    assert [a["asset"] for a in result["data"]["assets"]] == [BODY], "the other Assets are still shown"


def test_a_model_whose_skeleton_is_not_the_bases_fails_rig_with_the_bones_named(project: Kiripix) -> None:
    body(project)
    folder = guard(project, bones=[b for b in BONES if b != "mixamorig:Neck"])
    project.json("run", GUARD, "model")

    [finding] = project.json("run", GUARD, "rig", expect=3)["findings"]

    assert finding["code"] == "rig.base_mismatch" and BODY in finding["message"]
    assert "lacks mixamorig:Neck" in finding["message"]
    assert "mixamorig:Head (under mixamorig:Spine1, the base has it under mixamorig:Neck)" in finding["message"]
    assert "skeleton" in finding["owner_action"] and "mixamo.com" not in finding["owner_action"].lower()
    assert not (folder / "work" / "rig").exists() and stage_status(project, GUARD)["rig"] == "failed"


def test_more_bones_than_the_base_has_are_allowed_and_rest_proportions_are_not_compared(project: Kiripix) -> None:
    body(project)
    folder = guard(project, bones=[*BONES, "skirt_front", "skirt_back"], height=1.2)
    project.json("run", GUARD, "model")

    project.json("run", GUARD, "rig")

    assert rig_json(folder)["bones"] == len(BONES) + 2 and rig_json(folder)["parents"]["skirt_back"] == "skirt_front"


def test_a_model_without_an_armature_is_rig_missing_and_is_never_sent_to_mixamo(project: Kiripix) -> None:
    body(project)
    project.json("new", "character", "guard", "--base", BODY)
    shutil.copy(FIXTURES / "no_rig.glb", project.cwd / "no_rig.glb")
    project.json("pick", GUARD, project.json("import", GUARD, "no_rig.glb")["data"]["variant"])
    project.json("run", GUARD, "model")

    [finding] = project.json("run", GUARD, "rig", expect=3)["findings"]

    assert finding["code"] == "rig.missing" and BODY in finding["message"]
    assert "skeleton" in finding["owner_action"] and "mixamo.com" not in finding["owner_action"].lower()


def test_a_change_to_the_bases_clip_source_or_clips_makes_the_characters_clips_and_render_stale(project: Kiripix) -> None:
    body(project)
    folder = guard(project)
    for name in ("model", "rig", "clips", "render"):
        project.json("run", GUARD, name)
    first = next(c for c in clips_json(folder)["clips"] if c["name"] == "wave")

    clip_source(project, BODY, "wave", actions=ACTIONS, fps=24)

    status = stage_status(project, GUARD)
    assert status["rig"] == "done" and status["clips"] == "stale" and status["render"] == "stale"
    project.json("run", GUARD, "clips")
    second = next(c for c in clips_json(folder)["clips"] if c["name"] == "wave")
    assert second["source_hash"] != first["source_hash"] and second["source_fps"] == 24
    project.json("run", GUARD, "render")

    decide(project, BODY, "clip", {**WALK, "fps": 12})

    assert stage_status(project, GUARD)["clips"] == "stale"
    project.json("run", GUARD, "clips")
    assert next(c for c in clips_json(folder)["clips"] if c["name"] == "walk")["fps"] == 12


def test_the_characters_own_clip_source_wins_the_bases_of_the_same_name(project: Kiripix) -> None:
    body(project)
    folder = guard(project)
    for name in ("model", "rig"):
        project.json("run", GUARD, name)

    clip_source(project, GUARD, "wave", actions=ACTIONS, fps=15)
    project.json("run", GUARD, "clips")

    assert next(c for c in clips_json(folder)["clips"] if c["name"] == "wave")["source_fps"] == 15
    [source] = project.json("show", GUARD)["data"]["clip_sources"]
    assert source["file"].startswith("assets/character/guard/src/clips/wave.")


def test_a_base_that_is_not_built_is_needs_input_with_the_command_that_builds_it(project: Kiripix) -> None:
    body(project, build=False)
    guard(project)
    project.json("run", GUARD, "model")

    result = project.json("run", GUARD, "rig", expect=3)

    [finding] = result["findings"]
    assert finding["code"] == "stage.needs_input" and finding["fix"] == f"kiripix run {BODY} rig" and BODY in finding["message"]
    nxt = project.json("next", GUARD)["data"]
    assert nxt["stage"] == "rig" and nxt["command"] == f"kiripix run {BODY} rig"

    project.json("run", BODY, "model")
    project.json("run", BODY, "rig")
    assert project.json("run", GUARD, "rig")["data"]["results"][0]["outcome"] == "done"

    project.json("set", BODY, "model", "facing=+y")  # the base's Model changed: its rig is stale, so the character waits

    assert stage_status(project, GUARD)["rig"] == "needs-input"
    project.json("run", BODY, "model")
    project.json("run", BODY, "rig")
    assert stage_status(project, GUARD)["rig"] == "stale"


def test_run_all_builds_a_base_before_the_characters_made_from_it(project: Kiripix) -> None:
    body(project, build=False)
    guard(project)

    result = project("run", "--all", "--json", timeout=300).json  # `export` has no target here, so both stop there

    done = [(r["asset"], r["stage"]) for r in result["data"]["results"] if r["outcome"] == "done"]
    assert done.index((BODY, "rig")) < done.index((GUARD, "rig"))
    assert (GUARD, "render") in done and (BODY, "render") in done


def test_a_bases_rig_json_from_an_older_kiripix_is_rebuilt_first(project: Kiripix) -> None:
    zed = body(project)
    guard(project)
    project.json("run", GUARD, "model")
    path = zed / "work" / "rig" / "rig.json"
    old = json.loads(path.read_text("utf-8"))
    del old["parents"], old["height"]
    path.write_text(json.dumps({**old, "schema_version": 1}), encoding="utf-8")

    [finding] = project.json("run", GUARD, "rig", expect=3)["findings"]

    assert finding["code"] == "stage.needs_input" and finding["fix"] == f"kiripix run {BODY} rig --force"
    project.json("run", BODY, "rig", "--force")
    assert project.json("run", GUARD, "rig")["data"]["results"][0]["outcome"] == "done"


def test_the_bases_roles_hold_for_the_character(project: Kiripix) -> None:
    """A `bone` Decision made on the base maps the same bone on a character made from it."""
    project.json("new", "character", "zed")
    odd = [b for b in BONES if b != "mixamorig:LeftArm"] + ["Arm.L"]
    path = project.cwd / "zed.glb"
    path.write_text(json.dumps({"bones": odd}), encoding="utf-8")
    project.json("pick", BODY, project.json("import", BODY, "zed.glb")["data"]["variant"])
    project.json("run", BODY, "model")
    project.json("decide", BODY, "rig", "--decision", json.dumps({"decision": "bone", "data": {"role": "left_arm", "bone": "Arm.L"}}))
    project.json("run", BODY, "rig")
    folder = guard(project, bones=odd)
    project.json("run", GUARD, "model")

    project.json("run", GUARD, "rig")

    assert rig_json(folder)["mapping"]["left_arm"] == "Arm.L"


def test_clips_copy_from_a_character_made_from_a_base_copies_the_bases_clips_and_files(project: Kiripix) -> None:
    zed = body(project)
    guard(project)
    project.json("new", "character", "twin")

    data = project.json("clips", "copy", "character.twin", "--from", GUARD)["data"]

    assert data["copied"] == ["idle", "walk", "wave"]
    [copied] = data["files"]
    twin = folder_of(project, "character.twin")
    assert (twin / "src" / "clips" / Path(copied).name).read_bytes() == next((zed / "src" / "clips").glob("wave.*")).read_bytes()

    again = project.json("clips", "copy", GUARD, "--from", "character.twin")

    assert again["data"]["skipped"] == ["idle", "walk", "wave"] and again["data"]["files"] == []
    assert not (folder_of(project, GUARD) / "src" / "clips").exists(), "its base has the same file already"
    assert next((zed / "src" / "clips").glob("wave.*")).is_file()
