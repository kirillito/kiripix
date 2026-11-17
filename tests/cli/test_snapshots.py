"""Settings trials across a cast (ticket 0248, spec §10): `set` on several Assets, `snapshot`, `cast-sheet --snapshots`."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_cast_sheet import ELDER, hand_sheet, png
from test_character_model import HERO
from test_character_sheet import sheet_of


def settings(project: Kiripix, name: str) -> str:
    return (project.cwd / "assets" / "character" / name / "asset.toml").read_text(encoding="utf-8")


def two_characters(project: Kiripix) -> None:
    sheet_of(project)  # character.hero, built
    hand_sheet(project, "elder")


def test_set_on_two_assets_changes_both(project: Kiripix) -> None:
    project.json("new", "character", "a")
    project.json("new", "character", "b")

    result = project.json("set", "character.a,character.b", "finish", "placement=edge", "outline=false")

    data = result["data"]
    assert data["asset"] == "character.a,character.b" and data["stage"] == "finish"
    assert [(a["asset"], a["params"]["placement"], a["params"]["outline"]) for a in data["assets"]] == [
        ("character.a", "edge", False), ("character.b", "edge", False)]
    assert all(a["stages"] for a in data["assets"])
    for name in ("a", "b"):
        assert "placement" in settings(project, name)


def test_an_unknown_asset_in_the_list_changes_none(project: Kiripix) -> None:
    project.json("new", "character", "a")
    before = settings(project, "a")

    result = project.json("set", "character.a,character.nobody", "finish", "placement=edge", expect=1)

    assert [f["code"] for f in result["findings"]] == ["asset.not_found"]
    assert settings(project, "a") == before


def test_an_invalid_value_refuses_every_asset(project: Kiripix) -> None:
    project.json("new", "character", "a")
    project.json("new", "character", "b")
    before = settings(project, "a"), settings(project, "b")

    result = project.json("set", "character.a,character.b", "finish", "normal_levels=0", expect=1)

    assert [f["code"] for f in result["findings"]] == ["set.invalid_value"] * 2
    assert {f["position"]["asset"] for f in result["findings"]} == {"character.a", "character.b"}
    assert (settings(project, "a"), settings(project, "b")) == before


def test_set_on_one_asset_keeps_its_result(project: Kiripix) -> None:
    project.json("new", "character", "a")

    data = project.json("set", "character.a", "finish", "placement=edge")["data"]

    assert data["asset"] == "character.a" and data["params"]["placement"] == "edge" and data["stages"]
    assert data["assets"] == []  # the per-Asset list is for several


def snapshot_dir(project: Kiripix, label: str, asset: str = "") -> Path:
    return project.cwd / ".kiripix" / "snapshots" / label / asset


def test_a_snapshot_copies_the_sheet_with_its_parameters(project: Kiripix) -> None:
    folder, sheet = sheet_of(project)
    project.json("set", HERO, "finish", "placement=edge")  # now the sheet is behind its inputs

    result = project.json("snapshot", HERO, "--label", "edge")

    [kept] = result["data"]["snapshots"]
    assert kept["asset"] == HERO and kept["path"] == f".kiripix/snapshots/edge/{HERO}"
    assert kept["params"]["finish"]["placement"] == "edge" and "render" in kept["params"] and "sheet" in kept["params"]
    assert "sheet" in kept["stale"] and "finish" in kept["stale"]
    assert [f["code"] for f in result["findings"]] == ["snapshot.stale"]
    copy = snapshot_dir(project, "edge", HERO)
    assert json.loads((copy / "sheet.json").read_text("utf-8")) == sheet
    assert (copy / "color.png").read_bytes() == (folder / "work" / "sheet" / "color.png").read_bytes()
    assert json.loads((copy / "snapshot.json").read_text("utf-8"))["stale"] == kept["stale"]


def test_an_existing_label_needs_replace_and_replace_keeps_the_others(project: Kiripix) -> None:
    two_characters(project)
    project.json("snapshot", ELDER, "--label", "first")

    refused = project.json("snapshot", HERO, "--label", "first", expect=1)
    assert [f["code"] for f in refused["findings"]] == ["snapshot.label_exists"]
    assert not snapshot_dir(project, "first", HERO).exists()

    project.json("snapshot", HERO, "--label", "first", "--replace")

    listed = project.json("snapshot", "--list")["data"]["labels"]
    assert listed == [{"label": "first", "assets": [ELDER, HERO]}]


def test_a_label_is_snake_case(project: Kiripix) -> None:
    two_characters(project)

    result = project.json("snapshot", HERO, "--label", "Bad Label", expect=1)

    assert [f["code"] for f in result["findings"]] == ["snapshot.invalid_label"]


def test_an_unbuilt_asset_is_a_finding_and_the_others_are_kept(project: Kiripix) -> None:
    two_characters(project)
    project.json("new", "character", "kid")

    result = project.json("snapshot", f"character.kid,{HERO}", "--label", "all")

    assert [s["asset"] for s in result["data"]["snapshots"]] == [HERO]
    [finding] = [f for f in result["findings"] if f["code"] == "snapshot.not_built"]
    assert finding["position"]["asset"] == "character.kid" and finding["fix"] == "kiripix run character.kid sheet"
    assert not snapshot_dir(project, "all", "character.kid").exists()
    assert (snapshot_dir(project, "all", HERO) / "sheet.json").is_file()


def test_nothing_to_snapshot_is_an_error_and_leaves_no_label(project: Kiripix) -> None:
    project.json("new", "character", "kid")

    result = project.json("snapshot", "character.kid", "--label", "none", expect=1)

    assert [f["code"] for f in result["findings"]] == ["snapshot.not_built", "snapshot.empty"]
    assert project.json("snapshot", "--list")["data"]["labels"] == []


def test_an_asset_without_a_sheet_stage_is_refused(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")

    result = project.json("snapshot", "room.alley", "--label", "x", expect=1)

    assert [f["code"] for f in result["findings"]] == ["snapshot.no_sheet"]


def test_drop_deletes_a_label(project: Kiripix) -> None:
    two_characters(project)
    project.json("snapshot", HERO, "--label", "one")
    project.json("snapshot", HERO, "--label", "two")

    dropped = project.json("snapshot", "--drop", "one")["data"]["dropped"]

    assert dropped == {"label": "one", "assets": [HERO]}
    assert [e["label"] for e in project.json("snapshot", "--list")["data"]["labels"]] == ["two"]
    assert project.json("snapshot", "--drop", "one", expect=1)["findings"][0]["code"] == "snapshot.unknown_label"


def test_a_snapshot_records_nothing_in_the_project(project: Kiripix) -> None:
    two_characters(project)
    files = lambda: {p: p.stat().st_mtime_ns for p in (project.cwd / "assets").rglob("*") if p.is_file()}  # noqa: E731
    before = files()

    project.json("snapshot", f"{HERO},{ELDER}", "--label", "x")
    project.json("snapshot", "--list")
    project.json("snapshot", "--drop", "x")

    assert files() == before


def test_the_modes_are_exclusive(project: Kiripix) -> None:
    result = project.json("snapshot", "--list", "--drop", "x", expect=1)

    assert result["findings"][0]["code"] == "input.invalid"


def test_two_snapshots_give_a_cast_sheet_with_two_rows(project: Kiripix) -> None:
    two_characters(project)
    project.json("snapshot", f"{HERO},{ELDER}", "--label", "outline")
    project.json("set", f"{HERO},{ELDER}", "finish", "placement=edge", "outline=false")
    project.json("snapshot", f"{HERO},{ELDER}", "--label", "edge")

    result = project.json("cast-sheet", f"{HERO},{ELDER}", "--snapshots", "outline,edge", "--scale", "2")

    data = result["data"]
    image = png(project, data)
    assert image.shape[:2] == (data["height"], data["width"])
    assert [r["label"] for r in data["rows"]] == ["outline", "edge"]
    first, second = data["rows"]
    assert second["y"] == first["y"] + first["height"] and first["height"] + second["height"] == data["height"]
    assert first["title"].startswith("outline: ") and "finish.placement=outside" in first["title"]
    assert "finish.placement=edge" in second["title"] and "finish.outline=False" in second["title"]
    cells = data["cells"]
    assert [(c["row"], c["asset"]) for c in cells] == [("outline", HERO), ("outline", ELDER), ("edge", HERO),
                                                       ("edge", ELDER)]
    rows = {r["label"]: r for r in data["rows"]}
    for cell in cells:
        assert cell["y"] + cell["pivot"]["y"] == rows[cell["row"]]["ground"]  # each row's feet on its own line
        assert rows[cell["row"]]["y"] < cell["y"] < rows[cell["row"]]["y"] + rows[cell["row"]]["height"]
    differing = {(d["stage"], d["param"]): d["values"] for d in data["differing"]}
    assert set(differing) == {("finish", "placement"), ("finish", "outline")}
    assert differing[("finish", "placement")] == {"outline": {HERO: "outside", ELDER: "outside"},
                                                   "edge": {HERO: "edge", ELDER: "edge"}}
    # The elder's cell in each row holds its hand-written frame, scaled.
    inside = image[cells[1]["y"] + 2: cells[1]["y"] + 4, cells[1]["x"] + 2: cells[1]["x"] + 4]
    assert (inside[..., :3] == (200, 30, 30)).all()


def test_the_rows_read_the_snapshots_not_the_current_sheets(project: Kiripix) -> None:
    two_characters(project)
    project.json("snapshot", ELDER, "--label", "red")
    atlas = project.cwd / "assets" / "character" / "elder" / "work" / "sheet" / "color.png"
    Image.fromarray(np.zeros((50, 80, 4), np.uint8), "RGBA").save(atlas)  # the sheet changes after the snapshot

    data = project.json("cast-sheet", ELDER, "--snapshots", "red")["data"]

    cell = data["cells"][0]
    inside = png(project, data)[cell["y"] + 1: cell["y"] + 3, cell["x"] + 1: cell["x"] + 3]
    assert (inside[..., :3] == (200, 30, 30)).all()
    assert data["differing"] == []


def test_a_label_without_an_asset_is_a_finding_and_the_row_is_drawn(project: Kiripix) -> None:
    two_characters(project)
    project.json("snapshot", ELDER, "--label", "only_elder")
    project.json("snapshot", f"{HERO},{ELDER}", "--label", "both")

    result = project.json("cast-sheet", f"{HERO},{ELDER}", "--snapshots", "only_elder,both")

    assert [(c["row"], c["asset"]) for c in result["data"]["cells"]] == [
        ("only_elder", ELDER), ("both", HERO), ("both", ELDER)]
    [finding] = [f for f in result["findings"] if f["code"] == "cast.not_snapshotted"]
    assert finding["position"]["asset"] == HERO and "only_elder" in finding["message"]


def test_an_unknown_snapshot_label_is_refused(project: Kiripix) -> None:
    two_characters(project)

    result = project.json("cast-sheet", ELDER, "--snapshots", "nope", expect=1)

    assert [f["code"] for f in result["findings"]] == ["snapshot.unknown_label"]


def test_without_snapshots_the_sheet_is_as_before(project: Kiripix) -> None:
    two_characters(project)

    data = project.json("cast-sheet", f"{HERO},{ELDER}")["data"]

    assert data["rows"] == [] and data["differing"] == [] and all(c["row"] is None for c in data["cells"])
