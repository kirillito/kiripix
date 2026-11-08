"""`kiripix export` ownership flags, the ID freeze and Exit pairing (spec §6.1 and §9, ADR 0003, ticket 0022)."""

import json
from pathlib import Path
from typing import Any

import jsonschema
from conftest import Kiripix
from PIL import Image
from test_export import MANIFEST, PLATE, SCENE, exportable_room, manifest, scene
from test_masks import ROOM, WIDTH, plate
from test_place import findings, place

STREET = "room.street"
STREET_SCENE = "game/kiripix/room/street/street.tscn"
STREET_MANIFEST = "game/kiripix/manifest/room.street.json"
ALLEY_EXIT = {"target_room": STREET, "target_exit": "exit.west"}
STREET_EXIT = {"target_room": ROOM, "target_exit": "exit.east"}
SCENE_RES = "res://kiripix/room/alley/alley.tscn"


def put(project: Kiripix, asset: str, marker_id: str, marker_type: str, at: tuple[int, int] = (30, 16),
        **fields: Any) -> None:
    data = {"id": marker_id, "type": marker_type, "x": at[0], "y": at[1], **fields}
    project.json("decide", asset, "place", "--decision", json.dumps({"decision": "marker", "data": data}))


def street(project: Kiripix) -> None:
    """A second room, built like the first: a walled Plate, a Spawn, and every Stage run."""
    project.json("new", "room", "street", "--view", "top")
    project.json("set", STREET, "brief", f"width={WIDTH}", "height=32")
    project.json("set", STREET, "fit", "scale=1")
    Image.fromarray(plate(), "RGBA").save(project.cwd / "street.png")
    variant = project.json("import", STREET, "street.png")["data"]["variant"]
    project.json("pick", STREET, str(variant))
    project.json("run", STREET, expect=3)
    flood = {"decision": "flood", "data": {"x": 0, "y": 0, "mask": "solid"}}
    project.json("decide", STREET, "masks", "--decision", json.dumps(flood))
    put(project, STREET, "spawn.main", "spawn", at=(34, 16))


def two_paired_rooms(project: Kiripix) -> None:
    exportable_room(project)
    place(project, "exit.east", "exit", at=(30, 12), **ALLEY_EXIT)
    street(project)
    put(project, STREET, "exit.west", "exit", at=(30, 12), **STREET_EXIT)
    project.json("run", ROOM)
    project.json("run", STREET)


def backups(project: Kiripix) -> list[Path]:
    root = project.cwd / ".kiripix" / "backups"
    return sorted(root.iterdir()) if root.is_dir() else []


def edit_scene(project: Kiripix) -> str:
    edited = scene(project) + "\n# my own edit\n"
    (project.cwd / SCENE).write_text(edited, "utf-8", newline="")
    return edited


# --force


def test_a_refusal_names_the_flag_that_would_overwrite(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)
    edit_scene(project)

    [finding] = findings(project.json("export", ROOM, expect=3), "export.file_changed")

    assert finding["fix"] is None and "--force" in finding["owner_action"] and "backed up" in finding["owner_action"]


def test_force_backs_up_the_edited_file_and_writes_the_new_one(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)
    edited = edit_scene(project)
    place(project, "spawn.main", "spawn", at=(31, 16))
    project.json("run", ROOM)

    data = project.json("export", ROOM, "--force")["data"]

    [folder] = backups(project)
    assert (folder / SCENE).read_text("utf-8") == edited, "the game's edit is kept whole"
    assert data["backed_up"] == [SCENE_RES] and data["written"] == [SCENE_RES]
    assert "position = Vector2(31, 16)" in scene(project) and "my own edit" not in scene(project)
    assert manifest(project)["counter"] == 2 and "replacing" not in manifest(project)
    assert project.json("export", ROOM)["data"]["written"] == [], "the file is the game's again to edit, owned again"


def test_force_does_not_adopt_an_unmanaged_file(project: Kiripix) -> None:
    exportable_room(project)
    (project.cwd / SCENE).parent.mkdir(parents=True)
    (project.cwd / SCENE).write_text("the game's own scene\n", "utf-8")

    result = project.json("export", ROOM, "--force", expect=3)

    assert findings(result, "export.file_unmanaged") and not backups(project)
    assert (project.cwd / SCENE).read_text("utf-8") == "the game's own scene\n"


# --adopt


def test_an_unmanaged_refusal_names_adopt(project: Kiripix) -> None:
    exportable_room(project)
    (project.cwd / SCENE).parent.mkdir(parents=True)
    (project.cwd / SCENE).write_text("the game's own scene\n", "utf-8")

    [finding] = findings(project.json("export", ROOM, expect=3), "export.file_unmanaged")

    assert "--adopt" in finding["owner_action"]


def test_adopt_backs_up_the_unmanaged_file_and_takes_it_over(project: Kiripix) -> None:
    exportable_room(project)
    (project.cwd / SCENE).parent.mkdir(parents=True)
    (project.cwd / SCENE).write_text("the game's own scene\n", "utf-8")

    data = project.json("export", ROOM, "--adopt")["data"]

    [folder] = backups(project)
    assert (folder / SCENE).read_text("utf-8") == "the game's own scene\n"
    assert data["backed_up"] == [SCENE_RES] and (project.cwd / PLATE).is_file()
    assert scene(project).startswith("; generated by kiripix")
    assert SCENE_RES in manifest(project)["files"]
    assert project.json("export", ROOM)["data"]["written"] == []


def test_adopt_does_not_overwrite_an_edited_file_the_manifest_lists(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)
    edited = edit_scene(project)
    place(project, "spawn.main", "spawn", at=(31, 16))
    project.json("run", ROOM)

    result = project.json("export", ROOM, "--adopt", expect=3)

    assert findings(result, "export.file_changed") and (project.cwd / SCENE).read_text("utf-8") == edited


# --dry-run


def test_dry_run_writes_nothing_and_lists_what_would_be_written(project: Kiripix) -> None:
    exportable_room(project)

    data = project.json("export", ROOM, "--dry-run")["data"]

    assert data["dry_run"] is True and data["written"] == []
    assert sorted(data["would_write"]) == ["res://kiripix/manifest/room.alley.json", SCENE_RES,
                                           "res://kiripix/room/alley/plate.png"]
    assert data["changed"] == [] and data["unmanaged"] == [] and data["counter"] == 1
    assert not (project.cwd / MANIFEST).exists() and not (project.cwd / SCENE).exists() and not backups(project)


def test_dry_run_lists_the_two_conflicts_separately_and_still_writes_nothing(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)
    edited = edit_scene(project)
    (project.cwd / PLATE).write_bytes(b"the game's own picture")
    record = manifest(project)
    plate_res = "res://kiripix/room/alley/plate.png"
    (project.cwd / MANIFEST).write_text(json.dumps({**record, "files": {SCENE_RES: record["files"][SCENE_RES]}}), "utf-8")
    place(project, "spawn.main", "spawn", at=(31, 16))
    project.json("run", ROOM)
    before = (project.cwd / MANIFEST).read_bytes()

    result = project.json("export", ROOM, "--dry-run")

    assert result["data"]["changed"] == [SCENE_RES] and result["data"]["unmanaged"] == [plate_res]
    assert result["data"]["would_write"] == ["res://kiripix/manifest/room.alley.json"], "not the files it would refuse"
    assert {f["code"] for f in result["findings"]} == {"export.file_changed", "export.file_unmanaged"}
    assert all(f["severity"] == "warning" and f["owner_action"] for f in result["findings"])
    assert (project.cwd / SCENE).read_text("utf-8") == edited and (project.cwd / MANIFEST).read_bytes() == before
    assert (project.cwd / PLATE).read_bytes() == b"the game's own picture" and not backups(project)


def test_dry_run_with_force_and_adopt_says_what_would_be_backed_up(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)
    edit_scene(project)
    place(project, "spawn.main", "spawn", at=(31, 16))
    project.json("run", ROOM)

    data = project.json("export", ROOM, "--dry-run", "--force")["data"]

    assert data["backed_up"] == [SCENE_RES] and data["changed"] == [] and data["written"] == []
    assert not backups(project) and "my own edit" in scene(project)


def test_dry_run_of_a_room_not_built_refuses_like_export(project: Kiripix) -> None:
    exportable_room(project)
    place(project, "spawn.main", "spawn", at=(31, 16))

    [finding] = project.json("export", ROOM, "--dry-run", expect=1)["findings"]

    assert finding["code"] == "export.not_ready"


# the ID freeze


def test_before_the_first_export_a_rename_is_free(project: Kiripix) -> None:
    exportable_room(project)
    project.json("undo", ROOM, "place")
    place(project, "spawn.renamed", "spawn")
    project.json("run", ROOM)

    project.json("check", ROOM)
    project.json("export", ROOM)

    assert manifest(project)["ids"]["markers"] == ["spawn.renamed"]


def test_renaming_an_exported_spawn_fails_check_and_export_with_the_old_id(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)
    project.json("undo", ROOM, "place")
    place(project, "spawn.renamed", "spawn")
    project.json("run", ROOM)
    record = (project.cwd / MANIFEST).read_bytes()

    checked = project.json("check", ROOM, expect=2)
    exported = project.json("export", ROOM, expect=2)

    for result in (checked, exported):
        [finding] = findings(result, "export.id_frozen")
        assert finding["severity"] == "error" and finding["fix"] is None and finding["owner_action"]
        assert "spawn.main" in finding["message"] and "res://kiripix/manifest/room.alley.json" in finding["message"]
        assert SCENE_RES in finding["message"] and finding["position"]["asset"] == ROOM
    assert (project.cwd / MANIFEST).read_bytes() == record


def test_force_does_not_lift_the_freeze(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)
    project.json("undo", ROOM, "place")
    place(project, "spawn.renamed", "spawn")
    project.json("run", ROOM)

    project.json("export", ROOM, "--force", "--adopt", expect=2)

    assert "spawn.main" in scene(project)


def test_removing_an_exported_marker_fails_the_freeze_even_before_the_room_is_run_again(project: Kiripix) -> None:
    exportable_room(project)
    place(project, "lamp.one", "light", at=(30, 8), colour="#FF8000", radius=24, energy=0.5)
    project.json("run", ROOM)
    project.json("export", ROOM)
    project.json("undo", ROOM, "place")

    [finding] = findings(project.json("check", ROOM, expect=2), "export.id_frozen")

    assert "lamp.one" in finding["message"]


def test_adding_a_second_spawn_exports(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)
    place(project, "spawn.second", "spawn", at=(34, 16))
    project.json("run", ROOM)

    project.json("check", ROOM)
    data = project.json("export", ROOM)["data"]

    assert data["counter"] == 2
    assert manifest(project)["ids"]["markers"] == ["spawn.main", "spawn.second"]


def test_the_freeze_refuses_rather_than_guesses_when_the_game_is_not_at_its_path(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", ROOM)
    project.json("undo", ROOM, "place")
    place(project, "spawn.renamed", "spawn")
    project.json("run", ROOM)
    settings = project.cwd / "kiripix.toml"
    settings.write_text(settings.read_text("utf-8").replace('project = "game"', 'project = "elsewhere"'), "utf-8")

    for result in (project.json("check", ROOM, expect=2), project.json("check", "--all", expect=2)):
        [finding] = findings(result, "export.no_project")
        assert finding["severity"] == "error" and finding["owner_action"]


# Exit pairing


def test_two_rooms_whose_exits_point_at_each_other_pass_check_all(project: Kiripix) -> None:
    two_paired_rooms(project)

    result = project.json("check", "--all")

    assert [f for f in result["findings"] if f["code"] not in ("masks.open_edge", "palette.mapping_error")] == []  # info: an edge left open
    assert result["data"]["project_checks"] is True


def test_removing_one_sides_exit_fails_check_all_and_a_single_export_only_warns(project: Kiripix) -> None:
    two_paired_rooms(project)
    project.json("undo", ROOM, "place")  # the alley's exit.east: the last Decision
    project.json("run", ROOM)

    [finding] = findings(project.json("check", "--all", expect=2), "exit.no_exit")
    assert finding["severity"] == "error" and finding["position"]["asset"] == STREET
    assert "exit.west" in finding["message"] and "exit.east" in finding["message"] and finding["owner_action"]

    result = project.json("export", STREET)
    [warning] = findings(result, "exit.no_exit")
    assert warning["severity"] == "warning" and (project.cwd / STREET_SCENE).is_file()


def test_an_exit_to_a_room_that_does_not_exist_or_back_at_another_exit_fails(project: Kiripix) -> None:
    two_paired_rooms(project)
    project.json("undo", STREET, "place")
    put(project, STREET, "exit.west", "exit", at=(30, 12), target_room="room.nowhere", target_exit="exit.east")
    project.json("run", STREET)
    assert [f["code"] for f in project.json("check", "--all", expect=2)["findings"] if f["code"].startswith("exit.")] == [
        "exit.not_paired", "exit.no_room"]

    project.json("undo", STREET, "place")
    put(project, STREET, "exit.west", "exit", at=(30, 12), target_room=ROOM, target_exit="exit.nope")
    project.json("run", STREET)
    codes = [f["code"] for f in project.json("check", "--all", expect=2)["findings"] if f["code"].startswith("exit.")]
    assert codes == ["exit.not_paired", "exit.no_exit"]


# export --all


def test_export_all_exports_every_room_and_a_second_run_writes_nothing(project: Kiripix) -> None:
    two_paired_rooms(project)

    data = project.json("export", "--all")["data"]

    assert [a["asset"] for a in data["assets"]] == [ROOM, STREET] and data["asset"] is None
    assert len(data["written"]) == 4 and (project.cwd / STREET_SCENE).is_file() and (project.cwd / SCENE).is_file()
    assert json.loads((project.cwd / STREET_MANIFEST).read_text("utf-8"))["counter"] == 1
    again = project.json("export", "--all")["data"]
    assert again["written"] == [] and len(again["unchanged"]) == 4


def test_export_all_fails_on_exit_pairing_before_writing_anything(project: Kiripix) -> None:
    two_paired_rooms(project)
    project.json("undo", ROOM, "place")
    project.json("run", ROOM)

    result = project.json("export", "--all", expect=2)

    assert findings(result, "exit.no_exit")
    assert not (project.cwd / MANIFEST).exists() and not (project.cwd / STREET_MANIFEST).exists()
    assert not (project.cwd / SCENE).exists() and not (project.cwd / STREET_SCENE).exists()


def test_export_all_is_all_or_nothing_when_one_room_conflicts(project: Kiripix) -> None:
    two_paired_rooms(project)
    (project.cwd / STREET_SCENE).parent.mkdir(parents=True)
    (project.cwd / STREET_SCENE).write_text("the game's own scene\n", "utf-8")

    result = project.json("export", "--all", expect=3)

    [finding] = findings(result, "export.file_unmanaged")
    assert "street.tscn" in finding["message"]
    assert not (project.cwd / SCENE).exists() and not (project.cwd / MANIFEST).exists()
    project.json("export", "--all", "--adopt")
    assert (project.cwd / SCENE).is_file() and len(backups(project)) == 1


def test_export_all_dry_run_writes_nothing(project: Kiripix) -> None:
    two_paired_rooms(project)

    data = project.json("export", "--all", "--dry-run")["data"]

    assert len(data["would_write"]) == 6 and not (project.cwd / SCENE).exists()  # two rooms' two files and Manifest


def test_export_wants_an_asset_or_all_but_not_both(project: Kiripix) -> None:
    exportable_room(project)

    assert project.json("export", expect=1)["findings"][0]["code"] == "input.invalid"
    assert project.json("export", ROOM, "--all", expect=1)["findings"][0]["code"] == "input.invalid"


def test_export_all_with_no_game_project_refuses(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")

    [finding] = project.json("export", "--all", expect=3)["findings"]

    assert finding["code"] == "export.no_target"


# what an agent sees once a room is ready


def test_once_every_room_is_exported_next_is_done_and_check_all_passes(project: Kiripix) -> None:
    two_paired_rooms(project)
    assert project.json("next", ROOM)["data"]["command"] == f"kiripix export {ROOM}"

    project.json("export", "--all")

    assert project.json("next", ROOM)["data"]["done"] and project.json("next", STREET)["data"]["done"]
    assert [f for f in project.json("check", "--all")["findings"] if f["code"] not in ("masks.open_edge", "palette.mapping_error")] == []


def test_the_new_results_validate_against_the_schema(project: Kiripix) -> None:
    two_paired_rooms(project)
    schema = project.json("schema", "export")["data"]["commands"]["export"]["output"]

    for arguments in (("--all", "--dry-run"), ("--all",), (ROOM, "--force")):
        jsonschema.validate(project.json("export", *arguments), schema)

