"""A Wearable follows its body's cell per clip (ticket 0311): a body clip that reaches past the body's cell has its own, larger
cell and pivot (ticket 0303); the Wearable's `render` draws that clip at them, its `sheet` lays it out there, and
`wearable.body_not_exported` compares every clip's cell and pivot. On the fake Blender."""

import json
import shutil
from pathlib import Path
from typing import Any

from conftest import Kiripix
from PIL import Image
from test_cell_per_clip import BODY, built
from test_character_model import HERO
from test_character_render import render_calls, render_json
from test_export import godot_project, set_target

FIXTURES = Path(__file__).parent.parent / "fixtures" / "characters"
HAIR = "wearable.hair"
WIDE = "hit"


def wear(project: Kiripix, reach: dict[str, list[float]] | None = None) -> Path:
    """character.hero with a wider `hit` clip, its render built, and wearable.hair on it with `model` and `rig` run."""
    built(project)
    project.json("run", HERO, "render")
    if reach:
        (project.cwd / "blender-wearable-reach").write_text(json.dumps(reach), encoding="utf-8")
    project.json("new", "wearable", "hair", "--body", HERO)
    shutil.copy(FIXTURES / "rigged.glb", project.cwd / "hair.glb")
    project.json("pick", HAIR, project.json("import", HAIR, "hair.glb")["data"]["variant"])
    for stage in ("model", "rig"):
        project.json("run", HAIR, stage)
    return project.cwd / "assets" / "wearable" / "hair"


def clips_of(document: dict[str, Any]) -> dict[str, Any]:
    return {c["name"]: c for c in document["clips"]}


def test_a_wearable_draws_each_clip_at_its_bodys_cell_and_pivot(project: Kiripix) -> None:
    folder = wear(project)

    project.json("run", HAIR, "render")

    mine = json.loads((folder / "work" / "render" / "render.json").read_text("utf-8"))
    theirs = render_json(project.cwd / "assets" / "character" / "hero")
    side = clips_of(theirs)[WIDE]["frame"]["width"]
    assert side > BODY
    ours, body_clips = clips_of(mine), clips_of(theirs)
    for name, entry in ours.items():
        assert entry["frame"] == body_clips[name]["frame"] and entry["pivot"] == body_clips[name]["pivot"]
        for direction, frames in entry["directions"].items():
            assert [f["pivot"] for f in frames] == [f["pivot"] for f in body_clips[name]["directions"][direction]]
            assert Image.open(folder / "work" / "render" / frames[0]["files"]["color"]).size == (
                body_clips[name]["frame"]["width"], body_clips[name]["frame"]["height"])
    assert mine["frame"] == theirs["frame"] and mine["pivot"] == theirs["pivot"]  # the body's cell stays the top level
    sizes = {tuple(c["args"]["frame"]) for c in render_calls(project) if c["args"].get("wearable")}
    assert sizes == {(BODY, BODY), (side, side)}  # one launch for each cell size


def test_frames_inside_the_clips_own_cell_but_past_the_bodys_are_not_outside_the_cell(project: Kiripix) -> None:
    folder = wear(project, {WIDE: [-10.0, -60.0, 60.0, -40.0]})  # 60 px right of the pivot: past the body's 39, inside the clip's

    result = project.json("run", HAIR, "render")

    assert result["findings"] == []
    assert json.loads((folder / "work" / "render" / "render.json").read_text("utf-8"))["outside_cell"] == []


def test_frames_past_a_clips_own_cell_are_named_with_the_clip(project: Kiripix) -> None:
    wear(project, {"idle": [-10.0, -60.0, 60.0, -40.0]})  # idle keeps the body's cell: 60 px is past it

    result = project.json("run", HAIR, "render", expect=2)

    assert [f["code"] for f in result["findings"]] == ["wearable.outside_cell"]
    assert "idle" in result["findings"][0]["message"] and WIDE not in result["findings"][0]["message"]


def exported(project: Kiripix) -> Path:
    folder = wear(project)
    project.json("set", HERO, "palette", "colors=4")
    for stage in ("palette", "finish", "sheet"):
        project.json("run", HERO, stage)
    project.json("set", HAIR, "palette", "colors=4")
    godot_project(project)
    set_target(project)
    for stage in ("render", "palette", "finish", "sheet", "export"):
        project.json("run", HAIR, stage)
    project.json("run", HERO, "export")
    project.json("export", HERO)
    return folder


def test_the_sheet_lays_each_clip_out_at_its_bodys_cell(project: Kiripix) -> None:
    folder = exported(project)

    mine = json.loads((folder / "work" / "sheet" / "sheet.json").read_text("utf-8"))
    theirs = json.loads((project.cwd / "assets" / "character" / "hero" / "work" / "sheet" / "sheet.json").read_text("utf-8"))
    assert clips_of(theirs)[WIDE]["cell"]["width"] > BODY
    for name, entry in clips_of(mine).items():
        assert entry["cell"] == clips_of(theirs)[name]["cell"] and entry["pivot"] == clips_of(theirs)[name]["pivot"]
    assert project.json("export", HAIR)["ok"] is True


def test_a_body_whose_clip_cell_changed_makes_the_export_check_fail_naming_the_clip(project: Kiripix) -> None:
    exported(project)
    path = project.cwd / "game" / "kiripix" / "character" / "hero" / "character.json"
    record = json.loads(path.read_text("utf-8"))
    for entry in record["clips"]:
        if entry["name"] == WIDE:
            entry["cell"] = {"width": entry["cell"]["width"] + 2, "height": entry["cell"]["height"] + 2}
    path.write_text(json.dumps(record), "utf-8")

    refused = project.json("export", HAIR, expect=1)

    finding = refused["findings"][0]
    assert finding["code"] == "wearable.body_not_exported" and f"clip {WIDE}" in finding["message"]
    assert finding["fix"] == f"kiripix export {HERO}"


def test_a_body_whose_clip_pivot_changed_names_the_clip(project: Kiripix) -> None:
    exported(project)
    path = project.cwd / "game" / "kiripix" / "character" / "hero" / "character.json"
    record = json.loads(path.read_text("utf-8"))
    for entry in record["clips"]:
        if entry["name"] == "walk":
            entry["pivot"] = {"x": entry["pivot"]["x"] + 1, "y": entry["pivot"]["y"]}
    path.write_text(json.dumps(record), "utf-8")

    refused = project.json("export", HAIR, expect=1)

    assert refused["findings"][0]["code"] == "wearable.body_not_exported" and "clip walk" in refused["findings"][0]["message"]


def test_a_body_clip_the_wearable_lacks_is_named_and_the_fix_rebuilds_the_wearable(project: Kiripix) -> None:
    exported(project)
    path = project.cwd / "game" / "kiripix" / "character" / "hero" / "character.json"
    record = json.loads(path.read_text("utf-8"))
    record["clips"].append({**record["clips"][0], "name": "wave"})  # the body gained a clip since the Wearable was rendered
    path.write_text(json.dumps(record), "utf-8")

    refused = project.json("export", HAIR, expect=1)

    finding = refused["findings"][0]
    assert finding["code"] == "wearable.body_not_exported" and "clip wave" in finding["message"]
    assert finding["fix"] == f"kiripix run {HAIR}"


def test_an_older_body_record_migrates_before_the_clips_are_compared(project: Kiripix) -> None:
    exported(project)
    path = project.cwd / "game" / "kiripix" / "character" / "hero" / "character.json"
    record = json.loads(path.read_text("utf-8"))
    record["schema_version"] = 6
    for entry in record["clips"]:
        for listed in entry["directions"].values():
            for frame in listed:
                frame.pop("offset")
    path.write_text(json.dumps(record), "utf-8")

    assert project.json("export", HAIR)["ok"] is True
