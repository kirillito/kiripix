"""`kiripix queue`: what waits on the Owner across the Assets (ticket 0325)."""

from pathlib import Path
from typing import Any

from conftest import Kiripix, make_demo, make_sketch, in_review


def src(project: Kiripix, name: str) -> Path:
    return project.cwd / "assets" / "demo" / name / "src"


def stops(project: Kiripix, *args: str) -> list[dict[str, Any]]:
    return list(project.json("queue", *args)["data"]["stops"])


def test_one_item_of_each_type_and_the_fixable_finding_only_counted(project: Kiripix) -> None:
    in_review(project)  # sketch.a draw: needs-review
    project.json("new", "gated", "door")  # `gate` waits on src/ok.txt: an owner-only needs-input
    make_demo(project, "a")  # copy says "bad": a fixable finding
    (src(project, "a") / "input.txt").write_text("bad", encoding="utf-8")
    make_demo(project, "b")  # an owner-action finding of copy
    (src(project, "b") / "input.txt").write_text("owner", encoding="utf-8")
    project.json("run", "demo.a", expect=2)
    project.json("run", "demo.b", expect=2)
    project.json("note", "sketch.a", "draw", "check the outline")

    result = project.json("queue")

    assert result["ok"] is True and result["findings"] == []
    rows = [(i["asset"], i["stage"], i["type"]) for i in result["data"]["stops"]]
    assert rows == [("demo.b", "copy", "finding"), ("gated.door", "gate", "input"), ("sketch.a", "draw", "review")]
    review = result["data"]["stops"][2]
    assert review["command"] == "kiripix accept sketch.a draw" and review["input_hash"]
    assert [n["text"] for n in review["notes"]] == ["check the outline"]
    finding = result["data"]["stops"][0]
    assert finding["code"] == "demo.owner_text" and finding["owner_action"] and finding["severity"] == "error"
    [fixable] = result["data"]["agent_fixable"]
    assert fixable["asset"] == "demo.a" and fixable["count"] == 1
    assert fixable["fixes"][0]["code"] == "demo.bad_text" and fixable["fixes"][0]["command"].startswith("kiripix set demo.a")
    counts = result["data"]["counts"]
    assert (counts["review"], counts["input"], counts["finding"], counts["total"], counts["agent_fixable"]) == (1, 1, 1, 3, 1)
    assert counts["assets_clear"] == []


def test_match_and_kind_narrow_the_stops_and_a_project_check_names_each_asset(project: Kiripix) -> None:
    in_review(project)
    for name in ("a", "b"):
        make_demo(project, name)
        (src(project, name) / "mirror.txt").write_text("m", encoding="utf-8")
        project.json("run", f"demo.{name}")

    mirrored = [i for i in stops(project) if i["code"] == "demo.mirrored"]
    assert [i["asset"] for i in mirrored] == ["demo.a", "demo.b"]
    assert {i["asset"] for i in stops(project, "--kind", "sketch")} == {"sketch.a"}
    assert {i["asset"] for i in stops(project, "--match", "demo.b")} == {"demo.b"}
    assert all(i["asset"].startswith("demo.") for i in stops(project, "--match", "demo.*"))


def test_an_asset_with_nothing_waiting_is_clear_and_the_exit_is_zero(project: Kiripix) -> None:
    make_sketch(project)
    project.json("run", "sketch.a")

    result = project.json("queue")

    assert result["data"]["stops"] == [] and result["data"]["counts"]["assets_clear"] == ["sketch.a"]


def test_an_item_carries_its_stages_live_note(project: Kiripix) -> None:
    project.json("new", "gated", "door")
    project.json("note", "gated.door", "gate", "waiting for src/ok.txt")
    [waiting] = stops(project)
    assert [n["text"] for n in waiting["notes"]] == ["waiting for src/ok.txt"]


def test_a_glob_that_matches_nothing_is_refused(project: Kiripix) -> None:
    make_demo(project)

    result = project("queue", "--match", "room.*", "--json")

    assert result.code == 1 and result.json["findings"][0]["code"] == "match.none"


def test_a_broken_asset_is_a_finding_and_the_exit_is_still_zero(project: Kiripix) -> None:
    make_demo(project, "a")
    broken = make_demo(project, "b")
    (broken / "asset.toml").write_text('schema_version = 1\nkind = "demo"\ncolour = "red"\n', encoding="utf-8")

    result = project.json("queue")

    assert result["findings"][0]["code"] == "config.unknown_key"
    assert "demo.b" not in result["data"]["counts"]["assets_clear"]
