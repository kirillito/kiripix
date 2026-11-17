"""Ticket 0250: the M4 gate's small findings."""

from conftest import Kiripix, make_demo
from test_export import exportable_room
from test_export_prune import STREET_FOLDER, STREET_PLATE, exported_pair
from test_masks import ROOM
from test_place import findings, place


def test_new_help_lists_every_registered_kind(project: Kiripix) -> None:
    kinds = project.json("describe", "project")["data"]["kinds"]
    names = [kind["name"] for kind in kinds]
    assert "sprite" in names

    text = project("new", "--help").stdout

    for name in names:
        assert name in text


def test_prune_removes_the_import_sidecar_and_the_empty_folder(project: Kiripix) -> None:
    exported_pair(project)
    sidecar = project.cwd / (STREET_PLATE + ".import")
    sidecar.write_text("[remap]\n", "utf-8")
    other = project.cwd / "game" / "kiripix" / "room" / "alley" / "plate.png.import"
    other.write_text("[remap]\n", "utf-8")

    project.json("export", "--prune")

    assert not sidecar.exists() and not (project.cwd / STREET_FOLDER).exists()
    assert other.read_text("utf-8") == "[remap]\n", "only a pruned file's sidecar goes"


def test_exit_no_room_is_a_warning_in_check_and_in_export_of_one_room_and_an_error_in_check_all(project: Kiripix) -> None:
    exportable_room(project)
    place(project, "exit.east", "exit", at=(30, 12), target_room="room.nowhere", target_exit="exit.west")
    project.json("run", ROOM)

    [checked] = findings(project.json("check", ROOM), "exit.no_room")
    [exported] = findings(project.json("export", ROOM), "exit.no_room")
    [everything] = findings(project.json("check", "--all", expect=2), "exit.no_room")

    assert checked["severity"] == exported["severity"] == "warning"
    assert everything["severity"] == "error"
    assert "check --all" in checked["message"]


def test_force_from_rebuilds_that_stage_and_every_stage_after_it(project: Kiripix) -> None:
    make_demo(project)
    project.json("run", "demo.a")

    forced = project.json("run", "demo.a", "--force", "--from", "concat")["data"]["results"]
    plain = project.json("run", "demo.a", "--force", "concat")["data"]["results"]

    assert [r["stage"] for r in forced] == ["concat", "hold", "fail", "choose"]
    assert all(r["outcome"] != "skipped" for r in forced)
    assert [r["stage"] for r in plain] == ["concat"]


def test_from_needs_force_and_no_stage(project: Kiripix) -> None:
    make_demo(project)
    project.json("run", "demo.a")

    project.json("run", "demo.a", "--from", "concat", expect=1)
    project.json("run", "demo.a", "concat", "--force", "--from", "concat", expect=1)
    project.json("run", "demo.a", "--force", "--from", "nope", expect=1)

