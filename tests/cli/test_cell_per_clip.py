"""A cell per clip (ticket 0303), on the fake Blender: a clip that holds a thing and reaches past the body's cell gets its own,
larger cell and pivot; every other clip keeps the body's. `render.json`, `sheet.json` and `character.json` carry them per clip;
an older `character.json` migrates. The real draw is in `test_blender_held.py`."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_character_clips import IDLE, WALK, clip, rigged_hero
from test_character_model import HERO
from test_character_render import render_calls, render_json
from test_clip_attach import SOCKET, attached, held
from test_export import godot_project, set_target
from test_render_held import laid

BODY = 78  # the default cell of a 52 px character
REACH = {"hit": [-13.0, -52.0, 70.5, 0.0]}  # the held clip reaches 70.5 px right of the pivot: past the body's 39


def built(project: Kiripix, reach: dict[str, list[float]] | None = REACH) -> Path:
    folder = rigged_hero(project)
    (project.cwd / "blender-bones").write_text(json.dumps(["root", SOCKET]), encoding="utf-8")
    laid(folder, "phone")
    if reach:
        (project.cwd / "blender-reach").write_text(json.dumps(reach), encoding="utf-8")
    clip(project, IDLE)
    clip(project, WALK)
    clip(project, attached(held("phone")))
    project.json("run", HERO, "clips")
    return folder


def exported(project: Kiripix, reach: dict[str, list[float]] | None = REACH) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    folder = built(project, reach)
    godot_project(project)
    set_target(project)
    project.json("run", HERO)
    sheet: dict[str, Any] = json.loads((folder / "work" / "sheet" / "sheet.json").read_text("utf-8"))
    character: dict[str, Any] = json.loads((folder / "out" / "export" / "character.json").read_text("utf-8"))
    return folder, sheet, character


def by_name(document: dict[str, Any]) -> dict[str, Any]:
    return {c["name"]: c for c in document["clips"]}


def test_a_held_clip_that_doesnt_fit_gets_its_own_cell_and_the_others_keep_the_bodys(project: Kiripix) -> None:
    folder = built(project)

    project.json("run", HERO, "render")

    document = render_json(folder)
    clips = by_name(document)
    assert document["frame"] == {"width": BODY, "height": BODY} and document["pivot"] == [39.0, 72.0]  # the body's
    for name in ("idle", "walk"):
        assert clips[name]["frame"] == {"width": BODY, "height": BODY} and clips[name]["pivot"] == [39.0, 72.0]
    assert clips["hit"]["frame"]["width"] == clips["hit"]["frame"]["height"] > BODY
    assert clips["hit"]["pivot"][0] == clips["hit"]["frame"]["width"] / 2  # the cell is wider, the pivot stays at its centre column
    side = clips["hit"]["frame"]["width"]
    assert side >= 2 * 72  # 70.5 px right plus the pixel to spare and the outline
    # the frames are the cell's size, in Blender: one launch for each cell size
    sizes = {tuple(c["args"]["frame"]) for c in render_calls(project)}
    assert sizes == {(BODY, BODY), (side, side)}
    for frames in clips["hit"]["directions"].values():
        assert Image.open(folder / "work" / "render" / frames[0]["files"]["color"]).size == (side, side)
    assert Image.open(folder / "work" / "render" / clips["idle"]["directions"]["s"][0]["files"]["color"]).size == (BODY, BODY)


def test_a_held_clip_that_fits_keeps_the_bodys_cell(project: Kiripix) -> None:
    folder = built(project, {"hit": [-13.0, -52.0, 30.0, 0.0]})

    project.json("run", HERO, "render")

    document = render_json(folder)
    assert {(c["frame"]["width"], tuple(c["pivot"])) for c in document["clips"]} == {(BODY, (39.0, 72.0))}


def test_the_bodys_cell_is_fitted_to_the_clips_that_hold_nothing(project: Kiripix) -> None:
    folder = built(project, {"hit": [-13.0, -52.0, 70.5, 0.0], "walk": [-13.0, -52.0, 45.0, 0.0]})

    project.json("run", HERO, "render")

    clips = by_name(render_json(folder))
    assert clips["walk"]["frame"]["width"] == clips["idle"]["frame"]["width"] == render_json(folder)["frame"]["width"] > BODY
    assert clips["hit"]["frame"]["width"] > clips["walk"]["frame"]["width"]  # never smaller than the body's


def test_the_clip_that_grew_is_the_only_one_rendered_again_when_its_hold_changes(project: Kiripix) -> None:
    folder = built(project)
    project.json("run", HERO, "render")
    first = {c["name"]: c["key"] for c in render_json(folder)["clips"]}

    (project.cwd / "blender-reach").write_text(json.dumps({"hit": [-13.0, -52.0, 90.5, 0.0]}), encoding="utf-8")
    clip(project, attached(held("phone", offset=[0, 0.1, 0])))  # the thing held further out: only this clip's entry changes
    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")

    second = {c["name"]: c["key"] for c in render_json(folder)["clips"]}
    assert second["idle"] == first["idle"] and second["walk"] == first["walk"] and second["hit"] != first["hit"]
    last = render_calls(project)[-1]["args"]
    assert [c["name"] for c in last["clips"]] == ["hit"]  # the body's clips were reused


def test_sheet_lays_out_each_clip_at_its_own_cell_and_character_json_lists_them(project: Kiripix) -> None:
    folder, sheet, character = exported(project)

    side = by_name(render_json(folder))["hit"]["frame"]["width"]
    assert sheet["cell"] == {"width": BODY, "height": BODY} and sheet["pivot"] == {"x": 39, "y": 72}  # the body's
    clips = by_name(sheet)
    assert clips["idle"]["cell"] == clips["walk"]["cell"] == sheet["cell"] and clips["idle"]["pivot"] == sheet["pivot"]
    assert clips["hit"]["cell"] == {"width": side, "height": side} and clips["hit"]["pivot"] == {"x": side // 2, "y": side - 6}
    atlas = np.array(Image.open(folder / "work" / "sheet" / "color.png").convert("RGBA"))
    assert (atlas.shape[1], atlas.shape[0]) == (sheet["atlas"]["width"], sheet["atlas"]["height"])
    taken = np.zeros(atlas.shape[:2], dtype=bool)
    for name, entry in clips.items():
        want = entry["cell"]
        for direction, listed in entry["directions"].items():
            for frame in listed:
                r, o = frame["rect"], frame["offset"]  # the box is in the clip's own cell (ticket 0308)
                assert o["x"] + r["width"] <= want["width"] and o["y"] + r["height"] <= want["height"]
                assert r["x"] + r["width"] <= atlas.shape[1] and r["y"] + r["height"] <= atlas.shape[0]
                assert not taken[r["y"]:r["y"] + r["height"], r["x"]:r["x"] + r["width"]].any()  # no two frames overlap
                taken[r["y"]:r["y"] + r["height"], r["x"]:r["x"] + r["width"]] = True
                source = np.array(Image.open(folder / "work" / "finish" / "color" / f"{name}/{direction}/{frame['index']:03d}.png"))
                cell = np.zeros((want["height"], want["width"], 4), dtype=np.uint8)
                cell[o["y"]:o["y"] + r["height"], o["x"]:o["x"] + r["width"]] = atlas[r["y"]:r["y"] + r["height"], r["x"]:r["x"] + r["width"]]
                assert (cell == source[:want["height"], :want["width"]]).all()  # restored from rect + offset
    depth = np.array(Image.open(folder / "work" / "sheet" / "depth.png"))
    assert depth.shape == atlas.shape[:2]

    assert character["schema_version"] == 7
    assert character["cell"] == sheet["cell"] and character["pivot"] == sheet["pivot"]
    for name, entry in by_name(character).items():
        assert entry["cell"] == clips[name]["cell"] and entry["pivot"] == clips[name]["pivot"]
        assert entry["directions"] == clips[name]["directions"]


def test_a_character_whose_clips_share_the_bodys_cell_keeps_it_in_every_clip(project: Kiripix) -> None:
    folder, sheet, character = exported(project, None)

    assert character["schema_version"] == 7
    assert {(c["cell"]["width"], c["pivot"]["x"]) for c in character["clips"]} == {(BODY, 39)}
    assert all(c["cell"] == character["cell"] and c["pivot"] == character["pivot"] for c in character["clips"])
    assert "columns" not in sheet  # the atlas is packed, not a grid (ticket 0308)


def test_sheet_checks_run_per_clip(project: Kiripix) -> None:
    folder, sheet, _ = exported(project)

    # the held clip's frames are bigger than the body's cell, so they overflow it unless they are checked against their own
    assert project.json("check", HERO)["findings"] == []

    path = folder / "work" / "finish" / "render.json"
    document = json.loads(path.read_text("utf-8"))
    for item in document["clips"]:
        if item["name"] == "hit":  # a cell too small for the frames: they overflow it
            item["frame"] = {"width": 40, "height": 40}
            item["pivot"] = [20.0, 36.0]
    path.write_text(json.dumps(document), encoding="utf-8")
    result = project.json("check", HERO, expect=2)
    assert {f["code"] for f in result["findings"]} == {"sheet.frame_overflow"}
    assert {f["position"]["field"].split("/")[0] for f in result["findings"]} == {"hit"}


def test_an_older_character_json_is_read_with_a_cell_per_clip_and_an_unreadable_one_names_the_rebuild(project: Kiripix) -> None:
    folder, _, character = exported(project, None)
    path = folder / "out" / "export" / "character.json"
    old = {**character, "schema_version": 4, "clips": [{k: v for k, v in c.items() if k not in ("cell", "pivot")} for c in character["clips"]]}
    path.write_text(json.dumps(old, indent=2) + "\n", encoding="utf-8")

    result = project.json("export", HERO)  # reads the older file: each clip is the character's cell and pivot (migrated)

    assert result["ok"] is True
    path.write_text(json.dumps({**old, "schema_version": 3}, indent=2) + "\n", encoding="utf-8")
    result = project.json("export", HERO, expect=1)
    assert [f["code"] for f in result["findings"]] == ["export.character_invalid"]
    assert result["findings"][0]["fix"] == f"kiripix run {HERO} export --force"
