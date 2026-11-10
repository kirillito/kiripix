"""The `inspect` Probe (ticket 0123): what a character's file holds. The CLI tests run on the fake Blender of
`kiripix_test_recipes.py`; the marked tests run the real Blender 5.2 and compare with what the `clips` Stage resolves."""

import json
import os
from pathlib import Path
from typing import Any

import pytest
from conftest import Kiripix
from test_character_clips import IDLE, WALK, add_source, clip, clips_json, real_hero, rigged_hero
from test_character_model import FIXTURES, HERO, calls, picked_hero, set_blender


def inspect(project: Kiripix, name: str, **kwargs: Any) -> dict[str, Any]:
    result: dict[str, Any] = project.json("probe", "inspect", HERO, name, **kwargs)
    return result


def reads(project: Kiripix) -> int:
    return [c["script"] for c in calls(project)].count("read_actions")


def variant_name(folder: Path) -> str:
    return sorted(p.stem for p in (folder / "src").glob("*.glb"))[0]


def test_a_rigged_file_lists_its_bones_and_actions(project: Kiripix) -> None:
    folder = picked_hero(project)

    found = inspect(project, variant_name(folder))["data"]["result"]

    assert found["role"] == "variant" and found["armature"] == "Armature" and found["cached"] is False
    assert "mixamorig:Hips" in found["bones"] and found["fps"] == 30
    assert [(a["name"], a["start"], a["end"]) for a in found["actions"]] == [("idle", 0, 24), ("walk", 0, 30)]
    args = calls(project)[0]["args"]
    assert args["travel"] is False and args["optional"] is True


def test_a_second_call_does_not_start_blender(project: Kiripix) -> None:
    folder = picked_hero(project)
    name = variant_name(folder)
    first = inspect(project, name)["data"]["result"]

    second = inspect(project, name)["data"]["result"]

    assert reads(project) == 1 and second["cached"] is True
    assert {**second, "cached": False} == first


def test_a_clip_source_and_the_rigged_file_are_listed(project: Kiripix) -> None:
    rigged_hero(project)
    add_source(project, "run", actions=[{"name": "Armature|run", "start": 1, "end": 20, "travel": 0.0}], fps=24,
               bones=["root", "Hips"])

    source = inspect(project, "run")["data"]["result"]

    assert source["role"] == "clip-source" and source["fps"] == 24 and source["bones"] == ["root", "Hips"]
    assert source["actions"] == [{"name": "Armature|run", "short": "run", "start": 1, "end": 20}]
    assert "travel" not in source["actions"][0]

    rigged = project.cwd / "mixamo.fbx"
    rigged.write_text(json.dumps({"actions": [], "bones": ["root"], "armature": "Rig"}), encoding="utf-8")
    project.json("import", HERO, str(rigged), "--role", "rigged")
    assert inspect(project, "rigged")["data"]["result"]["role"] == "rigged"


def test_a_model_with_no_armature_lists_none(project: Kiripix) -> None:
    project.json("new", "character", "hero")
    flat = project.cwd / "flat.fbx"
    flat.write_text(json.dumps({"armature": None, "bones": [], "actions": []}), encoding="utf-8")
    name = project.json("import", HERO, str(flat))["data"]["variant"]

    found = inspect(project, name)["data"]["result"]

    assert found["armature"] is None and found["bones"] == [] and found["actions"] == []


def test_an_unknown_file_names_the_files(project: Kiripix) -> None:
    picked_hero(project)

    result = inspect(project, "nothing", expect=1)

    [finding] = result["findings"]
    assert finding["code"] == "inspect.file_unknown" and finding["fix"] == f"kiripix show {HERO}"
    assert calls(project) == []


def test_a_failed_blender_is_a_finding_and_is_not_cached(project: Kiripix) -> None:
    folder = picked_hero(project)
    (project.cwd / "blender-fails").write_text("told to fail", encoding="utf-8")

    result = inspect(project, variant_name(folder), expect=1)

    [finding] = result["findings"]
    assert finding["code"] == "inspect.failed" and "told to fail" in finding["message"] and finding["fix"]
    (project.cwd / "blender-fails").unlink()
    assert inspect(project, variant_name(folder))["data"]["result"]["cached"] is False


def test_a_missing_blender_gives_the_stage_finding(project: Kiripix) -> None:
    folder = picked_hero(project, test_recipes=False)
    set_blender(project, str(project.cwd / "no" / "such" / "blender.exe"))

    result = inspect(project, variant_name(folder), expect=3, test_recipes=False)

    [finding] = result["findings"]
    assert finding["code"] == "blender.not_found" and finding["owner_action"] and not finding.get("fix")


def test_a_probe_records_nothing(project: Kiripix) -> None:
    folder = picked_hero(project)
    before = sorted(p for p in folder.rglob("*") if p.is_file())

    inspect(project, variant_name(folder))

    assert sorted(p for p in folder.rglob("*") if p.is_file()) == before


def test_other_kinds_are_refused(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")

    result = project.json("probe", "inspect", "room.alley", "x", expect=1)

    assert result["findings"][0]["code"] == "inspect.not_character"


# the real Blender


@pytest.mark.blender
def test_rigged_fbx_lists_what_clips_resolves_on_real_blender(project: Kiripix) -> None:
    folder = real_hero(project)
    name = variant_name_any(folder)

    found = inspect(project, name, test_recipes=False, timeout=900)["data"]["result"]

    assert found["armature"] and "root" in found["bones"] and found["fps"] > 0
    by_name = {a["short"]: a for a in found["actions"]}
    assert {"idle", "walk"} <= set(by_name)
    for action in ("idle", "walk"):
        a = by_name[action]
        clip(project, {"name": action, "source": action, "start": a["start"], "end": a["end"], "fps": 8, "loop": True},
             test_recipes=False)
    result = project.json("run", HERO, "clips", test_recipes=False, timeout=900)
    assert result["findings"] == []  # every range inspect listed is one clips accepts
    built = {c["name"]: c for c in clips_json(folder)["clips"]}
    for action in ("idle", "walk"):
        assert built[action]["start"] == by_name[action]["start"] and built[action]["end"] == by_name[action]["end"]
        assert built[action]["action"] == by_name[action]["name"]
        assert built[action]["source_fps"] == found["fps"]
    assert inspect(project, name, test_recipes=False)["data"]["result"]["cached"] is True


@pytest.mark.blender
def test_a_model_without_an_armature_lists_none_on_real_blender(project: Kiripix) -> None:
    project.json("new", "character", "hero", test_recipes=False)
    set_blender(project, os.environ["KIRIPIX_BLENDER"])
    import shutil

    shutil.copy(FIXTURES / "no_rig.fbx", project.cwd / "no_rig.fbx")
    name = project.json("import", HERO, "no_rig.fbx", test_recipes=False)["data"]["variant"]

    found = inspect(project, name, test_recipes=False, timeout=900)["data"]["result"]

    assert found["armature"] is None and found["bones"] == [] and found["actions"] == []


def variant_name_any(folder: Path) -> str:
    return sorted(p.stem for p in (folder / "src").glob("*.fbx"))[0]
