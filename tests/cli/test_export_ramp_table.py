"""`ramps.png` and `character.json` in the order of the Project's ramp table (ticket 0169, spec §9): a row per part of the table,
the same on every character, a part a character lacks a transparent row. On the fake Blender, as in test_palette_table.py: the
hero's materials are `cloth` and `skin`, the twin's `face` and `jacket`; the hero has `hair` and no `top`, the twin the other way."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import Kiripix
from PIL import Image
from test_character_model import HERO
from test_clips_copy import TWIN
from test_export import godot_project, set_target
from test_export_character import SWAP, SWAP_PROBE, built
from test_palette_table import AMBER, RUST, SKIN, twin_named_otherwise
from test_ramp_table import hero, row, table

TABLE = ("skin", "hair", "top")
FOLDERS = {HERO: "game/kiripix/character/hero", TWIN: "game/kiripix/character/twin"}


def exported(project: Kiripix) -> dict[str, Path]:
    """Both characters built through `export` against the table skin (shared), hair (shared), top, and exported."""
    table(project, row("skin", 3, SKIN), row("hair", 2, [RUST, AMBER]), row("top", 2))
    folders = {HERO: hero(project, "hair=cloth,skin"), TWIN: twin_named_otherwise(project, "top=face,skin=jacket")}
    godot_project(project)
    set_target(project)
    for asset in folders:
        project.json("set", asset, "finish", "outline=false")
        project.json("run", asset)
        project.json("export", asset)
    return folders


def ramps(project: Kiripix, asset: str) -> np.ndarray:
    return np.array(Image.open(project.cwd / FOLDERS[asset] / "ramps.png").convert("RGBA"))


def parts_line(project: Kiripix, asset: str) -> str:
    name = asset.split(".")[1]
    [line] = [x for x in (project.cwd / FOLDERS[asset] / f"{name}.tscn").read_text("utf-8").splitlines()
              if x.startswith("metadata/kiripix_parts")]
    return line


def test_ramps_png_has_a_row_per_part_of_the_table_and_a_lacking_part_is_transparent(project: Kiripix) -> None:
    exported(project)

    first, second = ramps(project, HERO), ramps(project, TWIN)

    assert first.shape == second.shape == (3, 3, 4)  # three rows, padded to the longest ramp of the table
    assert first[0, :, :3].tolist() == second[0, :, :3].tolist() == SKIN and (first[0, :, 3] == 255).all()
    assert first[1, :2].tolist() == [[*RUST, 255], [*AMBER, 255]] and (first[1, 2] == 0).all()
    assert (second[1] == 0).all()  # the twin has no hair
    assert (first[2] == 0).all() and (second[2, :2, 3] == 255).all() and (second[2, 2] == 0).all()
    assert parts_line(project, HERO) == parts_line(project, TWIN) == 'metadata/kiripix_parts = PackedStringArray("skin", ' \
                                                                     '"hair", "top")'


def test_character_json_carries_each_parts_row_and_shared_in_row_order(project: Kiripix) -> None:
    folders = exported(project)

    character = built(folders[TWIN])

    assert character["schema_version"] == 4
    assert [(p["name"], p["row"], p["shared"], p["materials"]) for p in character["parts"]] == [
        ("skin", 0, True, ["jacket"]), ("top", 2, False, ["face"])]
    assert character["rows"] == [{"name": "skin", "length": 3}, {"name": "hair", "length": 2}, {"name": "top", "length": 2}]
    assert [p["name"] for p in built(folders[HERO])["parts"]] == ["skin", "hair"]
    assert project.json("check", "--all", expect=0)["findings"] == []


def test_a_re_export_writes_nothing(project: Kiripix) -> None:
    exported(project)

    for asset in (HERO, TWIN):
        assert project.json("export", asset)["data"]["written"] == []


def test_an_old_character_json_is_refused_with_a_re_export(project: Kiripix) -> None:
    folders = exported(project)
    path = folders[HERO] / "out" / "export" / "character.json"
    old: dict[str, Any] = json.loads(path.read_text("utf-8"))
    old["schema_version"] = 2
    path.write_text(json.dumps(old), encoding="utf-8")

    result = project.json("export", HERO, "--force", expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "export.character_invalid"]
    assert finding["fix"] == f"kiripix run {HERO} export --force"


@pytest.mark.godot
def test_godot_one_swap_of_the_skin_row_recolours_only_skin_on_every_character(project: Kiripix) -> None:
    """Marked: real Godot 4.7, headless, as 0151's test: the probe applies the swap shader's rule for row 0 to each character's
    atlas, and only skin changes on both."""
    exported(project)
    game = project.cwd / "game"
    (game / "swap.gdshader").write_text(SWAP, "utf-8")
    godot = os.environ["KIRIPIX_GODOT"]
    for asset in (HERO, TWIN):
        name = asset.split(".")[1]
        (game / f"probe_{name}.gd").write_text(SWAP_PROBE.replace("character/hero/hero.tscn", f"character/{name}/{name}.tscn"),
                                               "utf-8")
    subprocess.run([godot, "--headless", "--path", str(game), "--import", "--quit"], capture_output=True, timeout=300, check=False)

    for asset in (HERO, TWIN):
        name = asset.split(".")[1]
        done = subprocess.run([godot, "--headless", "--path", str(game), "-s", f"res://probe_{name}.gd"], capture_output=True,
                              text=True, encoding="utf-8", timeout=120, check=False, env={**os.environ, "KIRIPIX_SWAP_ROW": "0"})
        [line] = [line for line in done.stdout.splitlines() if line.startswith("PROBE ")]
        result = json.loads(line.removeprefix("PROBE "))
        assert result["parts"] == list(TABLE), asset
        assert set(result["changed"]) == {"skin"}, (asset, result)
        assert "skin" not in result["kept"], (asset, result)
