"""Ticket 0233: `check --all` passing doesn't mean the Project is finished, so it says which Assets aren't, with what `next`
says of each. In the real acceptance run of 2026-11-19 the agent ended on a clean `check --all` with its character never
built."""

from conftest import Kiripix, make_demo


def test_check_all_names_an_unfinished_asset_with_what_next_says_and_still_passes(project: Kiripix) -> None:
    make_demo(project)

    result = project.json("check", "--all")  # exit 0: an unfinished Asset is no failed Check

    assert result["data"]["unfinished"] == [project.json("next", "demo.a")["data"]]
    assert result["data"]["unfinished"][0]["command"] == "kiripix run demo.a"
    assert result["findings"] == [], "the findings stay the Checks' own"
    human = project("check", "--all")
    assert human.code == 0 and "not finished: demo.a copy is todo; run: kiripix run demo.a" in human.stdout


def test_check_all_says_nothing_of_an_asset_that_is_finished(project: Kiripix) -> None:
    make_demo(project)
    project.json("run", "demo.a")
    assert project.json("next", "demo.a")["data"]["done"]

    assert project.json("check", "--all")["data"]["unfinished"] == []
    assert "not finished" not in project("check", "--all").stdout


def test_check_of_one_asset_leaves_it_to_next(project: Kiripix) -> None:
    make_demo(project)

    assert project.json("check", "demo.a")["data"]["unfinished"] == []
