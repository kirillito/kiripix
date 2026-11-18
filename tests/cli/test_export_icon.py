"""The icon's export (ticket 0263, spec §9): `icon.png` and `icon.json` under `icons/`, listed in the Manifest, and no scene."""

import json
import shutil
from pathlib import Path
from typing import Any

from conftest import Kiripix
from test_export import godot_project, set_target
from test_icon import ICON, made_icon, run_to_finish

FOLDER = "game/kiripix/icons"
RES = "res://kiripix/icons"
MANIFEST = "game/kiripix/manifest/icon.key.json"
GAMES = b"the game's own\n"


def exportable_icon(project: Kiripix) -> Path:
    folder = made_icon(project, 16, 28)
    run_to_finish(project)
    godot_project(project)
    set_target(project)
    project.json("run", ICON)
    return folder


def manifest(project: Kiripix) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((project.cwd / MANIFEST).read_text("utf-8"))
    return value


def test_the_stage_leaves_the_icon_and_its_record_in_out_export(project: Kiripix) -> None:
    folder = exportable_icon(project)

    out = folder / "out" / "export"

    assert json.loads((out / "icon.json").read_text("utf-8")) == {"schema_version": 1, "asset": ICON, "size": 16}
    assert (out / "icon.png").read_bytes() == (folder / "work" / "finish" / "finish.png").read_bytes()
    assert sorted(p.name for p in out.iterdir() if p.name != ".stage.json") == ["icon.json", "icon.png"]


def test_an_icon_exports_both_files_listed_in_the_manifest_and_a_second_export_writes_nothing(project: Kiripix) -> None:
    folder = exportable_icon(project)

    data = project.json("export", ICON)["data"]

    assert sorted(data["written"]) == [f"{RES}/key.json", f"{RES}/key.png"] and data["counter"] == 1
    assert (project.cwd / FOLDER / "key.png").read_bytes() == (folder / "out" / "export" / "icon.png").read_bytes()
    assert (project.cwd / FOLDER / "key.json").read_bytes() == (folder / "out" / "export" / "icon.json").read_bytes()
    assert not list((project.cwd / "game" / "kiripix").glob("**/*.tscn")), "no scene"
    record = manifest(project)
    assert record["asset"] == ICON and record["exported"] is True
    assert sorted(record["files"]) == [f"{RES}/key.json", f"{RES}/key.png"]
    before = (project.cwd / MANIFEST).read_bytes()

    again = project.json("export", ICON)["data"]

    assert again["written"] == [] and again["counter"] == 1
    assert (project.cwd / MANIFEST).read_bytes() == before


def test_export_all_exports_the_icon(project: Kiripix) -> None:
    exportable_icon(project)

    data = project.json("export", "--all")["data"]

    assert (project.cwd / FOLDER / "key.png").is_file() and (project.cwd / MANIFEST).is_file()
    assert f"{RES}/key.png" in json.dumps(data)


def test_a_file_the_game_changed_is_refused_and_force_backs_it_up(project: Kiripix) -> None:
    exportable_icon(project)
    project.json("export", ICON)
    (project.cwd / FOLDER / "key.png").write_bytes(GAMES)

    refused = project.json("export", ICON, expect=3)

    assert refused["findings"][0]["code"] == "export.file_changed"
    assert (project.cwd / FOLDER / "key.png").read_bytes() == GAMES
    project.json("export", ICON, "--force")
    assert (project.cwd / FOLDER / "key.png").read_bytes() != GAMES
    assert list((project.cwd / ".kiripix" / "backups").glob("*/game/kiripix/icons/key.png"))


def test_prune_removes_a_deleted_icons_files_and_their_import_sidecars(project: Kiripix) -> None:
    folder = exportable_icon(project)
    project.json("export", ICON)
    sidecar = project.cwd / FOLDER / "key.png.import"
    sidecar.write_text("[remap]\n", "utf-8")
    shutil.rmtree(folder)

    project.json("export", "--all", "--prune")

    assert not (project.cwd / FOLDER / "key.png").exists() and not (project.cwd / FOLDER / "key.json").exists()
    assert not sidecar.exists() and not (project.cwd / MANIFEST).exists()
