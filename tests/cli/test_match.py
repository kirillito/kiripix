"""`--match <glob>` on status, check, run, export and stats (ticket 0327): a district is the Assets an ID glob matches."""

from conftest import Kiripix, make_demo
from test_character_base import BODY, GUARD, body, guard
from test_export import SCENE, exportable_room
from test_export_ownership import STREET, put, two_paired_rooms
from test_masks import ROOM


def demos(project: Kiripix) -> None:
    """Two Assets of a district and one outside it."""
    for name in ("d_one", "d_two", "other"):
        make_demo(project, name)


def asset_ids(data: dict[str, object], key: str = "assets") -> list[str]:
    rows = data[key]
    assert isinstance(rows, list)
    return [r if isinstance(r, str) else r["asset"] for r in rows]


# status


def test_status_match_shows_only_the_matched_assets(project: Kiripix) -> None:
    demos(project)

    result = project.json("status", "--match", "demo.d_*")

    assert asset_ids(result["data"]) == ["demo.d_one", "demo.d_two"]


def test_status_match_narrows_kind_and_is_case_sensitive(project: Kiripix) -> None:
    demos(project)
    project.json("new", "sketch", "d_one")

    narrowed = project.json("status", "--match", "*.d_one", "--kind", "sketch")

    assert asset_ids(narrowed["data"]) == ["sketch.d_one"]
    assert project.json("status", "--match", "DEMO.*", expect=1)["findings"][0]["code"] == "match.none"


# a glob that matches nothing


def test_a_glob_matching_nothing_is_match_none_on_every_command(project: Kiripix) -> None:
    exportable_room(project)
    demos(project)

    for command in ("status", "check", "run", "export", "stats"):
        result = project.json(command, "--match", "demo.zz*", expect=1)

        [finding] = result["findings"]
        assert finding["code"] == "match.none" and "demo.zz*" in finding["message"], command
        assert finding["fix"] and finding["owner_action"] is None
        assert result["ok"] is False


def test_match_with_an_asset_id_is_refused(project: Kiripix) -> None:
    demos(project)

    for command in ("check", "run", "stats", "export"):
        assert project(command, "demo.d_one", "--match", "demo.*", "--json").code == 1, command


# check


def test_check_match_checks_only_the_matched_assets(project: Kiripix) -> None:
    demos(project)
    project.json("run", "--all")

    result = project.json("check", "--match", "demo.d_*")

    assert result["data"]["assets"] == ["demo.d_one", "demo.d_two"]
    assert all(s.startswith(("demo.d_one ", "demo.d_two ")) for s in result["data"]["stages"]) and result["data"]["stages"]
    assert result["data"]["project_checks"] is True


def test_check_match_reports_an_exit_of_a_matched_room_that_points_outside_but_not_between_unmatched_rooms(
        project: Kiripix) -> None:
    two_paired_rooms(project)
    project.json("undo", STREET, "place")
    put(project, STREET, "exit.west", "exit", at=(30, 12), target_room="room.nowhere", target_exit="exit.east")
    project.json("run", STREET)
    make_demo(project, "d_one")

    inside = project.json("check", "--match", "room.al*", expect=2)
    assert [f["code"] for f in inside["findings"] if f["code"].startswith("exit.")] == ["exit.not_paired"]
    assert inside["findings"][0]["position"]["asset"] == ROOM  # points at the street, which isn't matched

    elsewhere = project.json("check", "--match", "demo.*")
    assert [f for f in elsewhere["findings"] if f["code"].startswith("exit.")] == []
    assert project.json("check", "--all", expect=2)["findings"]


# run


def test_run_match_builds_only_the_matched_assets(project: Kiripix) -> None:
    demos(project)

    result = project.json("run", "--match", "demo.d_*")

    assert set(asset_ids(result["data"], "results")) == {"demo.d_one", "demo.d_two"}
    status = {a["asset"]: [s["status"] for s in a["stages"]] for a in project.json("status")["data"]["assets"]}
    assert set(status["demo.d_one"]) == {"done"} and "done" not in status["demo.other"]


def test_run_match_on_characters_made_from_an_unmatched_base_builds_the_base_first(project: Kiripix) -> None:
    body(project, build=False)
    guard(project)

    result = project("run", "--match", GUARD, "--json", timeout=300).json

    done = [(r["asset"], r["stage"]) for r in result["data"]["results"] if r["outcome"] == "done"]
    assert done.index((BODY, "rig")) < done.index((GUARD, "rig"))
    [note] = [f for f in result["findings"] if f["code"] == "match.base_built"]
    assert BODY in note["message"] and note["severity"] == "info"


# export


def test_export_match_exports_only_the_matched_rooms_and_check_rules_hold(project: Kiripix) -> None:
    two_paired_rooms(project)

    data = project.json("export", "--match", "room.al*")["data"]

    assert asset_ids(data) == [ROOM] and (project.cwd / SCENE).is_file()
    assert not (project.cwd / "game/kiripix/room/street").exists()


def test_export_match_refuses_a_broken_exit_of_a_matched_room_only(project: Kiripix) -> None:
    two_paired_rooms(project)
    project.json("undo", STREET, "place")
    put(project, STREET, "exit.west", "exit", at=(30, 12), target_room="room.nowhere", target_exit="exit.east")
    project.json("run", STREET)
    make_demo(project, "d_one")

    refused = project.json("export", "--match", "room.al*", expect=2)
    assert [f["code"] for f in findings_of(refused, "exit.")] == ["exit.not_paired"]
    assert not (project.cwd / SCENE).exists()

    assert project.json("export", "--match", "demo.*")["data"]["assets"] == []  # no demo exporter; the rooms' pairing isn't its


def findings_of(result: dict[str, object], prefix: str) -> list[dict[str, str]]:
    found = result["findings"]
    assert isinstance(found, list)
    return [f for f in found if f["code"].startswith(prefix)]


def test_export_match_prune_works_as_with_all(project: Kiripix) -> None:
    two_paired_rooms(project)
    project.json("export", "--all")

    result = project.json("export", "--match", "room.al*", "--prune", "--dry-run")

    assert asset_ids(result["data"]) == [ROOM] and result["data"]["would_remove"] == []


# stats


def test_stats_match_totals_only_the_matched_assets(project: Kiripix) -> None:
    demos(project)

    result = project.json("stats", "--match", "demo.d_*")

    assert asset_ids(result["data"]) == ["demo.d_one", "demo.d_two"]
