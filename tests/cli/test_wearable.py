"""The `wearable` Kind (ticket 0290): an Asset that names its body, a character, and follows it.

What follows the body's hashes is tested on the test Kind `demo_wearable` (`kiripix_test_recipes.py`): the real Wearable's
`body` and its `render` inputs, with a `render` that runs and reads none of the body's files. The real Wearable's `model`, `rig`
and `render` (ticket 0291) are tested on the fake Blender at the end of this file; the Stages after `render` are in
`test_wearable_palette.py` and `test_export_wearable.py`. The body is a character built on the fake Blender."""

import json
import shutil
from pathlib import Path
from typing import Any

from conftest import Kiripix, stage_status

FIXTURES = Path(__file__).parent.parent / "fixtures" / "characters"
BODY = "character.zed"
HAIR = "demo_wearable.hair"
IDLE = {"name": "idle", "source": "idle", "start": 0, "end": 24, "fps": 12, "loop": True, "stationary": True}
WALK = {"name": "walk", "source": "walk", "start": 0, "end": 30, "fps": 10, "loop": True}
HIT = {"name": "hit", "source": "walk", "start": 0, "end": 6, "fps": 15, "loop": False}


def decide_clip(project: Kiripix, data: dict[str, Any]) -> None:
    project.json("decide", BODY, "clips", "--decision", json.dumps({"decision": "clip", "data": data}))


def body(project: Kiripix) -> None:
    """character.zed: the rigged fixture, with idle and walk; model, rig and clips built."""
    project.json("new", "character", "zed")
    shutil.copy(FIXTURES / "rigged.glb", project.cwd / "zed.glb")
    project.json("pick", BODY, project.json("import", BODY, "zed.glb")["data"]["variant"])
    for data in (IDLE, WALK):
        decide_clip(project, data)
    for stage in ("model", "rig", "clips"):
        project.json("run", BODY, stage)


def stage_state(project: Kiripix, asset: str, stage: str) -> dict[str, Any]:
    row = next(a for a in project.json("status")["data"]["assets"] if a["asset"] == asset)
    return next(s for s in row["stages"] if s["stage"] == stage)


def render_state(project: Kiripix, asset: str) -> dict[str, Any]:
    return stage_state(project, asset, "render")


def worn(project: Kiripix) -> None:
    """A demo_wearable on the body, its render built."""
    body(project)
    project.json("new", "demo_wearable", "hair", "--body", BODY)
    project.json("run", HAIR, "render")
    assert render_state(project, HAIR)["status"] == "done"


def test_describe_lists_the_recipe_without_clips(project: Kiripix) -> None:
    kind = project.json("describe", "wearable")["data"]["kinds"][0]

    assert kind["recipe"] == ["model", "rig", "render", "palette", "finish", "sheet", "export"]
    assert [p["name"] for p in kind["params"]] == ["body"] and kind["params"][0]["required"]
    stages = {s["name"]: s for s in kind["stages"]}
    assert stages["model"]["implemented"] and stages["render"]["implemented"] and stages["sheet"]["implemented"] and stages["export"]["implemented"]
    assert "wearable.outside_cell" in {c["code"] for c in stages["render"]["checks"]}
    assert "wearable" in {k["name"] for k in project.json("describe", "project")["data"]["kinds"]}


def test_new_help_lists_the_kind(project: Kiripix) -> None:
    help_text = project("new", "--help").stdout

    assert "wearable" in help_text and "--body" in help_text


def test_new_names_the_body(project: Kiripix) -> None:
    body(project)

    result = project.json("new", "wearable", "hair", "--body", BODY)

    assert result["data"]["asset"] == "wearable.hair"
    assert 'body = "character.zed"' in (project.cwd / "assets" / "wearable" / "hair" / "asset.toml").read_text("utf-8")
    assert project.json("status", "--kind", "wearable")["data"]["assets"][0]["asset"] == "wearable.hair"


def test_a_wearable_needs_a_body(project: Kiripix) -> None:
    result = project.json("new", "wearable", "hair", expect=1)

    assert result["findings"][0]["code"] == "asset.param_required"
    assert not (project.cwd / "assets" / "wearable").exists()


def test_a_body_that_is_missing_is_unknown(project: Kiripix) -> None:
    result = project.json("new", "wearable", "hair", "--body", "character.nobody", expect=1)

    finding = result["findings"][0]
    assert finding["code"] == "wearable.body_unknown" and "no such Asset" in finding["message"]
    assert (finding["fix"] is None) != (finding["owner_action"] is None)
    assert not (project.cwd / "assets" / "wearable").exists()


def test_a_wearable_is_never_a_body(project: Kiripix) -> None:
    body(project)
    project.json("new", "wearable", "hair", "--body", BODY)

    result = project.json("new", "wearable", "cap", "--body", "wearable.hair", expect=1)

    assert result["findings"][0]["code"] == "wearable.body_unknown"
    assert "it is a wearable" in result["findings"][0]["message"]


def test_a_body_that_is_not_an_asset_id_is_unknown(project: Kiripix) -> None:
    result = project.json("new", "wearable", "hair", "--body", "Zed!", expect=1)

    assert result["findings"][0]["code"] == "wearable.body_unknown"


def test_a_body_removed_by_hand_is_unknown_on_the_wearable(project: Kiripix) -> None:
    body(project)
    project.json("new", "wearable", "hair", "--body", BODY)
    shutil.rmtree(project.cwd / "assets" / "character" / "zed")

    result = project.json("run", "wearable.hair", "model", expect=1)

    finding = result["findings"][0]
    assert finding["code"] == "wearable.body_unknown" and finding["owner_action"] and not finding["fix"]
    assert finding["position"]["file"].endswith("assets/wearable/hair/asset.toml")


def test_body_is_only_for_a_wearable(project: Kiripix) -> None:
    body(project)

    result = project.json("new", "prop", "bench", "--body", BODY, expect=1)

    assert result["findings"][0]["code"] == "asset.param_unknown"


def test_a_wearable_takes_a_model_but_not_clips(project: Kiripix) -> None:
    body(project)
    project.json("new", "wearable", "hair", "--body", BODY)
    shutil.copy(FIXTURES / "rigged.glb", project.cwd / "hair.glb")

    imported = project.json("import", "wearable.hair", "hair.glb")
    project.json("pick", "wearable.hair", imported["data"]["variant"])
    refused = project.json("import", "wearable.hair", "hair.glb", "--role", "clip-source", expect=1)

    assert project.json("run", "wearable.hair", "model")["ok"]
    assert refused["findings"][0]["code"] == "import.wearable_uses_body_clips"
    states = stage_status(project, "wearable.hair")
    assert states["model"] == "done" and states["rig"] != "done" and states["export"] == "needs-input"


def test_a_change_to_the_bodys_clips_makes_render_stale_naming_the_body(project: Kiripix) -> None:
    worn(project)

    decide_clip(project, HIT)

    state = render_state(project, HAIR)
    assert state["status"] == "stale"
    assert f"its body {BODY} (clips" in state["reason"]
    project.json("run", HAIR, "render")
    assert render_state(project, HAIR)["status"] == "done"


def test_a_change_to_the_bodys_model_makes_render_stale(project: Kiripix) -> None:
    worn(project)

    project.json("set", BODY, "model", "facing=+y")

    state = render_state(project, HAIR)
    assert state["status"] == "stale" and f"its body {BODY} (" in state["reason"] and "model" in state["reason"]


def test_a_change_to_another_character_leaves_the_wearable_alone(project: Kiripix) -> None:
    worn(project)
    project.json("new", "character", "other")

    project.json("set", "character.other", "model", "facing=+y")

    assert render_state(project, HAIR)["status"] == "done"


def test_a_change_below_the_bodys_render_leaves_the_wearable_alone(project: Kiripix) -> None:
    worn(project)

    project.json("set", BODY, "palette", "colors=8")

    assert render_state(project, HAIR)["status"] == "done"


# the real Wearable on the fake Blender (ticket 0291) ------------------------------------------------------------------------

WEARABLE = "wearable.hair"
CLIPS = {"idle": 12, "walk": 10}  # the body's clips and, of the fake's 30 frames a second, their fps


def calls(project: Kiripix, script: str = "render_frames") -> list[dict[str, Any]]:
    path = project.cwd / "blender-calls.jsonl"
    lines = path.read_text("utf-8").splitlines() if path.exists() else []
    return [c for c in map(json.loads, lines) if c["script"] == script]


def hair(project: Kiripix, rendered: bool = True) -> None:
    """character.zed with its render built (unless `rendered` is off), and wearable.hair on it with a Model picked and `model`
    and `rig` run."""
    body(project)
    if rendered:
        project.json("run", BODY, "render")
    project.json("new", "wearable", "hair", "--body", BODY)
    shutil.copy(FIXTURES / "rigged.glb", project.cwd / "hair.glb")
    project.json("pick", WEARABLE, project.json("import", WEARABLE, "hair.glb")["data"]["variant"])
    for stage in ("model", "rig"):
        project.json("run", WEARABLE, stage)


def render_json(project: Kiripix, asset: str = WEARABLE) -> dict[str, Any]:
    kind, name = asset.split(".")
    document: dict[str, Any] = json.loads((project.cwd / "assets" / kind / name / "work" / "render" / "render.json").read_text("utf-8"))
    return document


def cap(project: Kiripix, content: dict[str, Any]) -> None:
    """wearable.cap on the body, its Model a file that says which bones it has, and `model` run."""
    body(project)
    project.json("new", "wearable", "cap", "--body", BODY)
    (project.cwd / "cap.glb").write_text(json.dumps({"armature": "Armature", **content}), encoding="utf-8")
    project.json("pick", "wearable.cap", project.json("import", "wearable.cap", "cap.glb")["data"]["variant"])
    project.json("run", "wearable.cap", "model")


def test_a_wearable_renders_the_bodys_clip_names_and_frame_counts_with_the_body_as_holdout(project: Kiripix) -> None:
    hair(project)

    result = project.json("run", WEARABLE, "render")

    assert result["findings"] == []
    mine, theirs = render_json(project), render_json(project, BODY)
    assert [c["name"] for c in mine["clips"]] == [c["name"] for c in theirs["clips"]] == list(CLIPS)
    for ours, body_clip in zip(mine["clips"], theirs["clips"], strict=True):
        assert {d: len(f) for d, f in ours["directions"].items()} == {d: len(f) for d, f in body_clip["directions"].items()}
        assert len(ours["directions"]) == 8
    assert mine["frame"] == theirs["frame"] and mine["pivot"] == theirs["pivot"] and mine["directions"] == theirs["directions"]
    assert mine["depth_range"] == theirs["depth_range"] and mine["toon"] == theirs["toon"]
    assert set(mine["passes"]) == {"color", "normal", "depth", "mask", "material"}
    first = mine["clips"][0]["directions"]["s"][0]
    assert all((project.cwd / "assets" / "wearable" / "hair" / "work" / "render" / f).is_file() for f in first["files"].values())
    # the holdout goes through to Blender: the body's file, the Wearable's, the body's camera and cell, and the body's clips
    measure, render = calls(project)[-2:]
    assert measure["args"]["measure"] is True and "measure" not in render["args"]
    for call in (measure, render):
        args = call["args"]
        assert args["wearable"]["holdout"] is True
        assert args["wearable"]["file"].replace("\\", "/").endswith("wearable/hair/work/model/model.blend")
        assert args["rig_file"].replace("\\", "/").endswith("character/zed/work/model/model.blend")
        assert args["frame"] == [theirs["frame"]["width"], theirs["frame"]["height"]] and args["pivot"] == theirs["pivot"]
        assert [c["name"] for c in args["clips"]] == list(CLIPS) and "eyes" not in args
        assert args["px_per_unit"] == theirs["px_per_unit"] and args["elevation"] == theirs["elevation"]


def test_a_wearable_records_its_render_seconds_and_numbers_its_materials_after_the_bodys(project: Kiripix) -> None:
    hair(project)

    project.json("run", WEARABLE, "render")

    document = render_json(project)
    assert document["seconds"]["frames"] == 8 * sum(len(c["directions"]["s"]) for c in document["clips"])
    assert document["seconds"]["render"] >= 0 and document["seconds"]["per_frame"] >= 0
    assert document["materials"] == [{"index": 3, "name": "hat"}] and document["body"] == {"asset": BODY, "materials": 2}


def test_the_wearables_model_is_put_on_the_body_not_scaled_to_its_own_height(project: Kiripix) -> None:
    hair(project)

    args = calls(project, "normalise_model")[-1]["args"]

    assert args["like"].replace("\\", "/").endswith("character/zed/work/model/model.blend") and "upload" not in args


def test_render_waits_for_the_bodys_built_stages_naming_the_stage_and_the_command(project: Kiripix) -> None:
    hair(project, rendered=False)  # the body's model, rig and clips are built; its render is not

    state = render_state(project, WEARABLE)
    result = project.json("run", WEARABLE, "render", expect=3)

    assert state["status"] == "needs-input"
    assert f"its body {BODY} has no built render" in state["reason"]
    assert f"kiripix run {BODY} render" in json.dumps(result["findings"][0])
    assert calls(project) == []  # Blender was not asked to render


def test_model_waits_for_the_bodys_model(project: Kiripix) -> None:
    project.json("new", "character", "zed")
    project.json("new", "wearable", "hair", "--body", BODY)

    state = stage_state(project, WEARABLE, "model")

    assert state["status"] == "needs-input" and f"its body {BODY} has no built model" in state["reason"]


def test_a_changed_body_clip_makes_the_wearable_wait_for_the_body_to_build_again(project: Kiripix) -> None:
    hair(project)
    decide_clip(project, HIT)

    state = render_state(project, WEARABLE)

    assert state["status"] == "needs-input" and f"its body {BODY} has no built clips (it is stale)" in state["reason"]


def test_rig_names_the_bones_the_wearable_lacks(project: Kiripix) -> None:
    cap(project, {"bones": ["root", "mixamorig:Hips", "mixamorig:Spine"], "mixamorig": True})

    result = project.json("run", "wearable.cap", "rig", expect=3)  # only the Owner can export the file again

    finding = result["findings"][0]
    assert finding["code"] == "wearable.rig_mismatch" and "it lacks the bones mixamorig:Spine1" in finding["message"]
    assert finding["owner_action"] and not finding["fix"]


def test_rig_refuses_a_bone_the_body_doesnt_have(project: Kiripix) -> None:
    names = ("Hips", "Spine", "Spine1", "Neck", "Head", "LeftShoulder", "LeftArm", "LeftForeArm", "RightShoulder", "RightArm",
             "RightForeArm", "LeftUpLeg", "LeftLeg", "LeftFoot", "RightUpLeg", "RightLeg", "RightFoot")  # the fake body's bones
    cap(project, {"bones": ["root", *(f"mixamorig:{n}" for n in names), "ponytail"], "mixamorig": True})

    result = project.json("run", "wearable.cap", "rig", expect=3)

    assert result["findings"][0]["code"] == "wearable.rig_mismatch"
    assert "bones the body doesn't: ponytail" in result["findings"][0]["message"]


def test_frames_outside_the_bodys_cell_are_a_finding_with_the_cell_margin_that_holds_them(project: Kiripix) -> None:
    hair(project)
    cell = render_json(project, BODY)["frame"]["width"]
    # a part reaching 5 px past the cell's right edge in every frame of walk
    (project.cwd / "blender-wearable-reach").write_text(json.dumps({"walk": [-10, -50, cell / 2 + 5, 0]}), encoding="utf-8")

    result = project.json("run", WEARABLE, "render", expect=2)

    finding = next(f for f in result["findings"] if f["code"] == "wearable.outside_cell")
    assert finding["severity"] == "error" and "walk s 0" in finding["message"]
    assert f"{cell} px cell of its body {BODY}" in finding["message"]
    assert (finding["fix"] is None) != (finding["owner_action"] is None)
    margin = int(finding["fix"].rsplit("cell_margin=", 1)[1])
    assert finding["fix"] == f"kiripix set {BODY} render cell_margin={margin}" and margin >= 5
    outside = render_json(project)["outside_cell"]
    assert {f["clip"] for f in outside} == {"walk"} and outside[0] == {"clip": "walk", "direction": "s", "frame": 0}
    assert len(outside) == 8 * len(render_json(project)["clips"][1]["directions"]["s"])


def test_the_cell_margin_fix_clears_the_finding_once_the_body_and_the_wearable_render_again(project: Kiripix) -> None:
    hair(project)
    cell = render_json(project, BODY)["frame"]["width"]
    (project.cwd / "blender-wearable-reach").write_text(json.dumps({"walk": [-10, -50, cell / 2 + 5, 0]}), encoding="utf-8")
    result = project.json("run", WEARABLE, "render", expect=2)
    fix = next(f for f in result["findings"] if f["code"] == "wearable.outside_cell")["fix"]

    project.json(*fix.split()[1:])  # kiripix set character.zed render cell_margin=N
    project.json("run", BODY, "render")

    state = render_state(project, WEARABLE)
    assert state["status"] == "stale" and f"its body {BODY} (" in state["reason"]
    again = project.json("run", WEARABLE, "render")
    assert again["findings"] == [] and render_json(project)["outside_cell"] == []
    assert render_json(project)["frame"] == render_json(project, BODY)["frame"] and render_json(project)["frame"]["width"] > cell


def test_a_palette_change_of_the_body_leaves_the_wearables_render_alone_and_a_height_change_makes_it_stale(project: Kiripix) -> None:
    hair(project)
    project.json("run", WEARABLE, "render")

    project.json("set", BODY, "palette", "colors=8")
    assert render_state(project, WEARABLE)["status"] == "done"
    project.json("set", BODY, "render", "height=40")
    project.json("run", BODY, "render")

    assert render_state(project, WEARABLE)["status"] == "stale"
