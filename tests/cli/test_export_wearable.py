"""A Wearable's `sheet` and `export` (ticket 0293, spec §6.3 and §9): the body's cell and layout in three atlases, `wearable.json`,
the files in the game and the Manifest, `wearable.body_not_exported`, `--prune`, and the stacking `order` that the Check reads.
On the fake Blender."""

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_export import godot_project, set_target
from test_wearable import BODY, WEARABLE, hair

FOLDER = "game/kiripix/wearable/hair"
RES = "res://kiripix/wearable/hair"
MANIFEST = "game/kiripix/manifest/wearable.hair.json"
FILES = [f"{RES}/color.png", f"{RES}/depth.png", f"{RES}/frames.tres", f"{RES}/hair.tscn", f"{RES}/normal.png",
         f"{RES}/texture.tres", f"{RES}/wearable.json"]
GAMES = b"the game's own\n"
DIRECTIONS = ("s", "sw", "w", "nw", "n", "ne", "e", "se")


def assets(project: Kiripix, kind: str, name: str) -> Path:
    return project.cwd / "assets" / kind / name


def build_body(project: Kiripix) -> None:
    project.json("set", BODY, "palette", "colors=4")
    for stage in ("palette", "finish", "sheet"):
        project.json("run", BODY, stage)


def built_wearable(project: Kiripix) -> Path:
    """The body built through `sheet` (not exported), wearable.hair built through `export`, a Godot project as the target."""
    hair(project)
    build_body(project)
    project.json("set", WEARABLE, "palette", "colors=4")
    godot_project(project)
    set_target(project)
    for stage in ("render", "palette", "finish", "sheet", "export"):
        project.json("run", WEARABLE, stage)
    return assets(project, "wearable", "hair")


def exportable(project: Kiripix) -> Path:
    folder = built_wearable(project)
    project.json("run", BODY, "export")
    project.json("export", BODY)
    return folder


def wearable_json(project: Kiripix) -> dict[str, Any]:
    path = assets(project, "wearable", "hair") / "out" / "export" / "wearable.json"
    value: dict[str, Any] = json.loads(path.read_text("utf-8"))
    return value


def manifest(project: Kiripix) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((project.cwd / MANIFEST).read_text("utf-8"))
    return value


def test_the_sheet_has_the_bodys_cell_pivot_and_layout_with_colour_normal_and_depth_atlases(project: Kiripix) -> None:
    folder = built_wearable(project)

    mine = json.loads((folder / "work" / "sheet" / "sheet.json").read_text("utf-8"))
    theirs = json.loads((assets(project, "character", "zed") / "work" / "sheet" / "sheet.json").read_text("utf-8"))

    for key in ("cell", "pivot", "directions"):  # the atlas and each frame's rect and offset are the Wearable's own (ticket 0308)
        assert mine[key] == theirs[key]
    assert [(c["name"], c["cell"], c["pivot"], {d: [f["index"] for f in fs] for d, fs in c["directions"].items()}) for c in mine["clips"]] == [
        (c["name"], c["cell"], c["pivot"], {d: [f["index"] for f in fs] for d, fs in c["directions"].items()}) for c in theirs["clips"]]
    assert mine["files"] == {"color": "color.png", "normal": "normal.png", "depth": "depth.png"} and mine["order"] == 10
    sizes = {name: Image.open(folder / "work" / "sheet" / name).size for name in ("color.png", "normal.png", "depth.png")}
    assert set(sizes.values()) == {(mine["atlas"]["width"], mine["atlas"]["height"])}
    assert np.asarray(Image.open(folder / "work" / "sheet" / "depth.png")).dtype == np.uint16
    assert Image.open(folder / "work" / "sheet" / "color.png").mode == "P"  # indexed (ticket 0310); the normal atlas stays RGBA
    assert Image.open(folder / "work" / "sheet" / "normal.png").mode == "RGBA"


def test_order_is_a_sheet_parameter_that_lands_in_wearable_json(project: Kiripix) -> None:
    built_wearable(project)

    project.json("set", WEARABLE, "sheet", "order=30")
    project.json("run", WEARABLE, "sheet")
    project.json("run", WEARABLE, "export")

    assert wearable_json(project)["order"] == 30


def test_the_stage_leaves_three_atlases_and_wearable_json_in_out_export(project: Kiripix) -> None:
    folder = built_wearable(project)

    out = folder / "out" / "export"
    record = wearable_json(project)
    sheet = json.loads((folder / "work" / "sheet" / "sheet.json").read_text("utf-8"))

    assert sorted(p.name for p in out.iterdir() if p.name != ".stage.json") == ["color.png", "depth.png", "normal.png", "wearable.json"]
    assert record["schema_version"] == 2 and record["asset"] == WEARABLE and record["body"] == BODY and record["order"] == 10
    assert record["files"] == {"color": "color.png", "normal": "normal.png", "depth": "depth.png"}
    keys = ("cell", "pivot", "atlas", "directions", "clips")
    assert {k: record[k] for k in keys} == {k: sheet[k] for k in keys}
    assert isinstance(record["parts"], list)
    for name in ("color.png", "normal.png", "depth.png"):
        assert (out / name).read_bytes() == (folder / "work" / "sheet" / name).read_bytes()


def test_a_wearable_exports_listed_in_the_manifest_and_a_second_export_writes_nothing(project: Kiripix) -> None:
    exportable(project)

    data = project.json("export", WEARABLE)["data"]

    assert sorted(data["written"]) == FILES and data["counter"] == 1
    record = manifest(project)
    assert record["asset"] == WEARABLE and record["exported"] is True and sorted(record["files"]) == FILES
    assert record["ids"]["clips"] == sorted(f"{c}_{d}" for c in ("idle", "walk") for d in DIRECTIONS)
    assert "walk_ne" in (project.cwd / FOLDER / "frames.tres").read_text("utf-8")
    before = (project.cwd / MANIFEST).read_bytes()

    again = project.json("export", WEARABLE)["data"]

    assert again["written"] == [] and again["counter"] == 1 and (project.cwd / MANIFEST).read_bytes() == before


def test_the_export_is_byte_identical_after_a_rebuild(project: Kiripix) -> None:
    exportable(project)
    project.json("export", WEARABLE)
    before = {p.name: p.read_bytes() for p in (project.cwd / FOLDER).iterdir()}

    for stage in ("sheet", "export"):
        project.json("run", WEARABLE, stage, "--force")

    assert project.json("export", WEARABLE)["data"]["written"] == []
    assert {p.name: p.read_bytes() for p in (project.cwd / FOLDER).iterdir()} == before


def test_a_wearable_is_refused_until_its_body_has_been_exported(project: Kiripix) -> None:
    built_wearable(project)

    refused = project.json("export", WEARABLE, expect=1)

    assert refused["findings"][0]["code"] == "wearable.body_not_exported"
    assert BODY in refused["findings"][0]["message"] and refused["findings"][0]["fix"] == f"kiripix export {BODY}"
    assert not (project.cwd / FOLDER).exists()


def test_a_wearable_is_refused_when_the_game_has_the_body_with_another_cell(project: Kiripix) -> None:
    exportable(project)
    path = project.cwd / "game" / "kiripix" / "character" / "zed" / "character.json"
    record = json.loads(path.read_text("utf-8"))
    record["cell"]["width"] += 2
    path.write_text(json.dumps(record), "utf-8")

    refused = project.json("export", WEARABLE, expect=1)

    assert refused["findings"][0]["code"] == "wearable.body_not_exported" and "cell" in refused["findings"][0]["message"]


def test_export_all_exports_a_body_and_its_wearable_together(project: Kiripix) -> None:
    built_wearable(project)
    project.json("run", BODY, "export")

    project.json("export", "--all")

    assert (project.cwd / FOLDER / "wearable.json").is_file()
    assert (project.cwd / "game" / "kiripix" / "character" / "zed" / "character.json").is_file()


def test_a_file_the_game_changed_is_refused_and_force_backs_it_up(project: Kiripix) -> None:
    exportable(project)
    project.json("export", WEARABLE)
    (project.cwd / FOLDER / "depth.png").write_bytes(GAMES)

    refused = project.json("export", WEARABLE, expect=3)

    assert refused["findings"][0]["code"] == "export.file_changed" and "depth.png" in refused["findings"][0]["message"]
    project.json("export", WEARABLE, "--force")
    assert (project.cwd / FOLDER / "depth.png").read_bytes() != GAMES
    assert list((project.cwd / ".kiripix" / "backups").glob("*/game/kiripix/wearable/hair/depth.png"))


def test_a_file_the_manifest_doesnt_list_is_refused_and_adopt_takes_it(project: Kiripix) -> None:
    exportable(project)
    (project.cwd / FOLDER).mkdir(parents=True)
    (project.cwd / FOLDER / "color.png").write_bytes(GAMES)

    refused = project.json("export", WEARABLE, expect=3)

    assert refused["findings"][0]["code"] == "export.file_unmanaged"
    project.json("export", WEARABLE, "--adopt")
    assert (project.cwd / FOLDER / "color.png").read_bytes() != GAMES


def test_prune_removes_a_deleted_wearables_files_and_their_import_sidecars(project: Kiripix) -> None:
    folder = exportable(project)
    project.json("export", WEARABLE)
    sidecar = project.cwd / FOLDER / "color.png.import"
    sidecar.write_text("[remap]\n", "utf-8")
    shutil.rmtree(folder)

    project.json("export", "--all", "--prune")

    assert not (project.cwd / FOLDER).exists() and not (project.cwd / MANIFEST).exists()
    assert (project.cwd / "game" / "kiripix" / "character" / "zed" / "character.json").is_file()
