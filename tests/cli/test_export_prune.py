"""`kiripix export --prune` (spec §9, ADR 0003, ticket 0048): a deleted Asset's files go, under the hash rule."""

import shutil
from pathlib import Path

import jsonschema
from conftest import Kiripix
from test_export import MANIFEST, SCENE, exportable_room
from test_export_ownership import ALLEY_EXIT, STREET, STREET_EXIT, STREET_MANIFEST, STREET_SCENE, backups, put, street
from test_masks import ROOM
from test_place import findings, place

STREET_PLATE = "game/kiripix/room/street/plate.png"
STREET_FOLDER = "game/kiripix/room/street"
STREET_FILES = [STREET_SCENE, STREET_PLATE, STREET_MANIFEST]
STREET_RES = ["res://kiripix/manifest/room.street.json", "res://kiripix/room/street/plate.png",
              "res://kiripix/room/street/street.tscn"]


def exported_pair(project: Kiripix) -> None:
    """Two exported rooms; the street's Asset is then deleted from the Project."""
    exportable_room(project)
    street(project)
    project.json("run", STREET)
    project.json("export", "--all")
    shutil.rmtree(project.cwd / "assets" / "room" / "street")


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_prune_removes_the_deleted_assets_files_and_manifest_and_nothing_else(project: Kiripix) -> None:
    exported_pair(project)
    alley = snapshot(project.cwd / "game" / "kiripix" / "room" / "alley")
    alley_manifest = (project.cwd / MANIFEST).read_bytes()

    data = project.json("export", "--prune")["data"]

    assert sorted(data["removed"]) == STREET_RES and data["would_remove"] == [] and data["written"] == []
    assert not any((project.cwd / name).exists() for name in STREET_FILES)
    assert not (project.cwd / STREET_FOLDER).exists(), "the emptied folder goes too"
    assert snapshot(project.cwd / "game" / "kiripix" / "room" / "alley") == alley
    assert (project.cwd / MANIFEST).read_bytes() == alley_manifest and not backups(project)


def test_without_prune_the_files_stay(project: Kiripix) -> None:
    exported_pair(project)

    project.json("export", ROOM)
    project.json("export", "--all")

    assert all((project.cwd / name).is_file() for name in STREET_FILES)


def test_prune_alone_exports_nothing(project: Kiripix) -> None:
    exported_pair(project)
    place(project, "spawn.second", "spawn", at=(34, 16))
    project.json("run", ROOM)
    before = (project.cwd / SCENE).read_bytes()

    data = project.json("export", "--prune")["data"]

    assert (project.cwd / SCENE).read_bytes() == before and data["assets"] == []


def test_prune_with_all_exports_then_prunes(project: Kiripix) -> None:
    exported_pair(project)
    place(project, "spawn.second", "spawn", at=(34, 16))
    project.json("run", ROOM)

    data = project.json("export", "--all", "--prune")["data"]

    assert "res://kiripix/room/alley/alley.tscn" in data["written"]
    assert sorted(data["removed"]) == STREET_RES and not (project.cwd / STREET_MANIFEST).exists()
    assert "spawn.second" in (project.cwd / SCENE).read_text("utf-8")


def test_prune_with_all_changes_nothing_when_one_file_is_refused(project: Kiripix) -> None:
    exported_pair(project)
    (project.cwd / STREET_SCENE).write_text("my edit\n", "utf-8")
    place(project, "spawn.second", "spawn", at=(34, 16))
    project.json("run", ROOM)
    before = (project.cwd / SCENE).read_bytes()

    project.json("export", "--all", "--prune", expect=3)

    assert (project.cwd / SCENE).read_bytes() == before and (project.cwd / STREET_MANIFEST).is_file()


def test_prune_of_one_asset_removes_that_asset_only(project: Kiripix) -> None:
    exported_pair(project)

    data = project.json("export", STREET, "--prune")["data"]

    assert data["asset"] == STREET and sorted(data["removed"]) == STREET_RES
    assert (project.cwd / MANIFEST).is_file()


def test_prune_of_an_asset_that_exists_refuses(project: Kiripix) -> None:
    exported_pair(project)

    [finding] = project.json("export", ROOM, "--prune", expect=1)["findings"]

    assert finding["code"] == "export.asset_exists" and (project.cwd / MANIFEST).is_file()
    assert finding["fix"] is None and finding["owner_action"]


def test_prune_of_an_asset_that_was_never_exported_says_so(project: Kiripix) -> None:
    exported_pair(project)

    [finding] = project.json("export", "room.never", "--prune", expect=1)["findings"]

    assert finding["code"] == "export.not_exported"


def test_an_edited_file_refuses_with_nothing_removed_and_names_the_file(project: Kiripix) -> None:
    exported_pair(project)
    (project.cwd / STREET_SCENE).write_text("my edit\n", "utf-8")

    result = project.json("export", "--prune", expect=3)

    [finding] = findings(result, "export.file_changed")
    assert "street.tscn" in finding["message"] and "--force" in finding["owner_action"] and finding["fix"] is None
    assert all((project.cwd / name).is_file() for name in STREET_FILES) and not backups(project)


def test_force_backs_the_edited_file_up_and_removes_it(project: Kiripix) -> None:
    exported_pair(project)
    (project.cwd / STREET_SCENE).write_text("my edit\n", "utf-8")

    data = project.json("export", "--prune", "--force")["data"]

    [folder] = backups(project)
    assert (folder / STREET_SCENE).read_text("utf-8") == "my edit\n"
    assert data["backed_up"] == ["res://kiripix/room/street/street.tscn"] and len(data["removed"]) == 3
    assert not (project.cwd / STREET_FOLDER).exists()


def test_dry_run_removes_nothing_and_lists_both_cases(project: Kiripix) -> None:
    exported_pair(project)
    (project.cwd / STREET_SCENE).write_text("my edit\n", "utf-8")
    before = snapshot(project.cwd / "game")

    result = project.json("export", "--prune", "--dry-run")

    data = result["data"]
    assert data["removed"] == [] and data["changed"] == ["res://kiripix/room/street/street.tscn"]
    assert sorted(data["would_remove"]) == ["res://kiripix/manifest/room.street.json",
                                            "res://kiripix/room/street/plate.png"]
    assert [f["code"] for f in result["findings"]] == ["export.file_changed"]
    assert result["findings"][0]["severity"] == "warning"
    assert snapshot(project.cwd / "game") == before and not backups(project)


def test_dry_run_with_force_says_what_would_be_backed_up(project: Kiripix) -> None:
    exported_pair(project)
    (project.cwd / STREET_SCENE).write_text("my edit\n", "utf-8")

    data = project.json("export", "--prune", "--dry-run", "--force")["data"]

    assert data["backed_up"] == ["res://kiripix/room/street/street.tscn"] and len(data["would_remove"]) == 3
    assert (project.cwd / STREET_SCENE).is_file() and not backups(project)


def test_a_file_the_manifest_does_not_list_is_left_alone(project: Kiripix) -> None:
    exported_pair(project)
    (project.cwd / STREET_FOLDER / "notes.txt").write_text("mine\n", "utf-8")

    project.json("export", "--prune")

    assert (project.cwd / STREET_FOLDER / "notes.txt").read_text("utf-8") == "mine\n"
    assert not (project.cwd / STREET_SCENE).exists()


def test_a_listed_file_already_gone_is_fine_and_a_stopped_prune_can_run_again(project: Kiripix) -> None:
    exported_pair(project)
    (project.cwd / STREET_PLATE).unlink()

    data = project.json("export", "--prune")["data"]

    assert "res://kiripix/room/street/plate.png" not in data["removed"] and not (project.cwd / STREET_MANIFEST).exists()
    assert project.json("export", "--prune")["data"]["removed"] == []


def test_godot_sidecars_are_ignored(project: Kiripix) -> None:
    exported_pair(project)
    sidecar = project.cwd / (STREET_PLATE + ".import")
    sidecar.write_text("[remap]\n", "utf-8")

    project.json("export", "--prune")

    assert sidecar.read_text("utf-8") == "[remap]\n" and not (project.cwd / STREET_SCENE).exists()


def test_another_rooms_exit_still_naming_the_pruned_asset_is_a_warning(project: Kiripix) -> None:
    exportable_room(project)
    place(project, "exit.east", "exit", at=(30, 12), **ALLEY_EXIT)
    street(project)
    put(project, STREET, "exit.west", "exit", at=(30, 12), **STREET_EXIT)
    project.json("run", ROOM)
    project.json("run", STREET)
    project.json("export", "--all")
    shutil.rmtree(project.cwd / "assets" / "room" / "street")

    result = project.json("export", "--prune")

    [warning] = findings(result, "export.exit_to_pruned")
    assert warning["severity"] == "warning" and ROOM in warning["message"] and "exit.east" in warning["message"]
    assert warning["owner_action"] and not (project.cwd / STREET_MANIFEST).exists()


def test_a_manifest_naming_a_file_outside_the_export_root_is_refused(project: Kiripix) -> None:
    exported_pair(project)
    (project.cwd / "game" / "project.godot").write_text("keep\n", "utf-8")
    text = (project.cwd / STREET_MANIFEST).read_text("utf-8")
    (project.cwd / STREET_MANIFEST).write_text(text.replace("res://kiripix/room/street/plate.png", "res://project.godot"),
                                               "utf-8")

    [finding] = project.json("export", "--prune", expect=1)["findings"]

    assert finding["code"] == "export.manifest_invalid"
    assert (project.cwd / "game" / "project.godot").read_text("utf-8") == "keep\n"


def test_prune_without_a_game_project_refuses(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")

    [finding] = project.json("export", "--prune", expect=3)["findings"]

    assert finding["code"] == "export.no_target"


def test_prune_with_nothing_deleted_does_nothing(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)

    data = project.json("export", "--prune")["data"]

    assert data["removed"] == [] and (project.cwd / MANIFEST).is_file()


def test_the_prune_results_validate_against_the_schema(project: Kiripix) -> None:
    exported_pair(project)
    schema = project.json("schema", "export")["data"]["commands"]["export"]["output"]

    for arguments in (("--prune", "--dry-run"), ("--prune",)):
        jsonschema.validate(project.json("export", *arguments), schema)
