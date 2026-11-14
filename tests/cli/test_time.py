"""`track` and `stats` (ticket 0182): the Owner's measured active time, from `time.jsonl` and the Decision journals."""

import json
import sys
import time
from datetime import datetime
from types import SimpleNamespace

from conftest import MARK, Kiripix, make_demo
from test_manifest_merge import git

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ulid_at(moment: datetime, n: int = 0) -> str:
    """A ULID for `moment` (local time), the random part being `n`."""
    number = (int(moment.timestamp() * 1000) << 80) | n
    return "".join(_ALPHABET[(number >> (5 * i)) & 31] for i in reversed(range(26)))


def span_line(moment: datetime, stage: str, seconds: int, source: str = "ui", n: int = 0) -> str:
    return json.dumps({"schema_version": 1, "id": ulid_at(moment, n), "stage": stage, "seconds": seconds,
                       "source": source}) + "\n"


def stage_row(data: dict[str, object], asset: str, stage: str) -> dict[str, object]:
    [entry] = [a for a in data["assets"] if a["asset"] == asset]  # type: ignore[index, attr-defined]
    [row] = [s for s in entry["stages"] if s["stage"] == stage]
    return row  # type: ignore[no-any-return]


def test_track_refuses_without_the_owner(project: Kiripix) -> None:
    make_demo(project)

    result = project.json("track", "demo.a", "copy", "--seconds", "30", expect=3)

    assert result["findings"][0]["code"] == "owner.required"
    assert not (project.cwd / "assets" / "demo" / "a" / "time.jsonl").exists()


def test_track_appends_a_span_with_the_owner(project: Kiripix) -> None:
    folder = make_demo(project)

    first = project.json("track", "demo.a", "copy", "--seconds", "30", owner=True)
    project.json("track", "demo.a", "extend", "--seconds", "45", owner=True)

    assert first["data"]["seconds"] == 30 and first["data"]["source"] == "cli"
    lines = (folder / "time.jsonl").read_bytes().decode("utf-8").split("\n")
    assert lines[-1] == "" and b"\r" not in (folder / "time.jsonl").read_bytes()
    spans = [json.loads(line) for line in lines[:-1]]
    assert [(s["stage"], s["seconds"], s["source"], s["schema_version"]) for s in spans] == [
        ("copy", 30, "cli", 1), ("extend", 45, "cli", 1)]
    assert spans[0]["id"] == first["data"]["id"] and spans[0]["id"] < spans[1]["id"]


def test_track_refuses_a_bad_span(project: Kiripix) -> None:
    make_demo(project)

    for seconds in ("0", "3601", "-5"):
        result = project.json("track", "demo.a", "copy", "--seconds", seconds, owner=True, expect=1)
        assert result["findings"][0]["code"] == "time.seconds_invalid"
    unknown = project.json("track", "demo.a", "nope", "--seconds", "30", owner=True, expect=1)
    assert unknown["findings"][0]["code"] == "time.stage_unknown"
    assert project.json("track", "demo.a", "copy", "--seconds", "3600", owner=True)["ok"]


def test_track_warns_when_the_merge_attribute_is_missing(project: Kiripix) -> None:
    make_demo(project)
    attributes = project.cwd / ".gitattributes"
    attributes.write_text("\n".join(line for line in attributes.read_text(encoding="utf-8").splitlines()
                                    if not line.startswith("time.jsonl")) + "\n", encoding="utf-8")

    result = project.json("track", "demo.a", "copy", "--seconds", "30", owner=True)

    [finding] = result["findings"]
    assert finding["code"] == "time.merge_attribute_missing" and finding["owner_action"]


def test_stats_counts_minutes_and_decisions_per_stage(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("decide", "demo.a", "choose", "--decision", MARK)
    project.json("decide", "demo.a", "choose", "--decision", MARK)
    project.json("undo", "demo.a", "choose")
    project.json("redo", "demo.a", "choose")
    project.json("undo", "demo.a", "choose")
    now = datetime.now()
    (folder / "time.jsonl").write_text(
        span_line(now, "choose", 120, "ui", 1) + span_line(now, "choose", 60, "cli", 2)
        + span_line(now, "copy", 30, "ui", 3) + span_line(now, "extend", 90, "cli", 4), encoding="utf-8")

    data = project.json("stats", "demo.a")["data"]

    choose = stage_row(data, "demo.a", "choose")
    assert (choose["ui_minutes"], choose["cli_minutes"], choose["minutes"]) == (2.0, 1.0, 3.0)
    assert (choose["decisions"], choose["undos"], choose["redos"]) == (2, 2, 1)
    assert stage_row(data, "demo.a", "copy")["minutes"] == 0.5
    assert stage_row(data, "demo.a", "extend")["cli_minutes"] == 1.5
    assert data["total"]["minutes"] == 5.0 and data["total"]["decisions"] == 2
    assert data["assets"][0]["total"]["minutes"] == 5.0


def test_stats_since_drops_the_older_entries(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("decide", "demo.a", "choose", "--decision", MARK)
    old, recent = datetime(2020, 1, 1, 12), datetime.now()
    (folder / "time.jsonl").write_text(
        span_line(old, "choose", 600, "ui", 1) + span_line(recent, "choose", 60, "ui", 2), encoding="utf-8")

    everything = project.json("stats", "--all")["data"]
    lately = project.json("stats", "--all", "--since", "2024-06-01")["data"]
    future = project.json("stats", "--all", "--since", "2999-01-01")["data"]

    assert everything["total"]["minutes"] == 11.0
    assert lately["total"]["minutes"] == 1.0 and lately["total"]["decisions"] == 1 and lately["since"] == "2024-06-01"
    assert future["total"]["minutes"] == 0 and future["total"]["decisions"] == 0
    bad = project.json("stats", "--all", "--since", "yesterday", expect=1)
    assert bad["findings"][0]["code"] == "stats.since_invalid"


def test_stats_needs_an_asset_or_all(project: Kiripix) -> None:
    assert project.json("stats", expect=1)["findings"][0]["code"] == "input.invalid"


def test_stats_reports_a_broken_line(project: Kiripix) -> None:
    folder = make_demo(project)
    (folder / "time.jsonl").write_text("not json\n", encoding="utf-8")

    result = project.json("stats", "demo.a", expect=1)

    assert result["findings"][0]["code"] == "time.invalid"


def test_stats_lists_nothing_for_an_empty_project(project: Kiripix) -> None:
    data = project.json("stats", "--all")["data"]

    assert data["assets"] == [] and data["total"]["minutes"] == 0


def test_two_branches_that_both_log_time_merge_and_stats_counts_both(project: Kiripix) -> None:
    folder = make_demo(project)
    root = project.cwd
    project.json("track", "demo.a", "copy", "--seconds", "60", owner=True)
    assert git(root, "init", "-b", "main").returncode == 0
    assert git(root, "add", ".").returncode == 0
    assert git(root, "commit", "-m", "base").returncode == 0
    assert git(root, "checkout", "-b", "other").returncode == 0
    project.json("track", "demo.a", "copy", "--seconds", "120", owner=True)
    assert git(root, "commit", "-am", "other").returncode == 0
    assert git(root, "checkout", "main").returncode == 0
    time.sleep(0.01)
    project.json("track", "demo.a", "choose", "--seconds", "180", owner=True)
    assert git(root, "commit", "-am", "main").returncode == 0

    merged = git(root, "merge", "other")

    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert len((folder / "time.jsonl").read_text(encoding="utf-8").splitlines()) == 3
    assert project.json("stats", "demo.a")["data"]["total"]["minutes"] == 6.0


def test_an_interactive_command_counts_the_time_since_the_previous_one(project: Kiripix, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The CLI half. A pty isn't available everywhere, so the Command seam (`invoke`, as the CLI calls it) is driven
    with an interactive Context; `KIRIPIX_TEST_OWNER` must not count, because it isn't a terminal."""
    from kiripix.commands import REGISTRY, Context, invoke

    project.json("new", "room", "alley", "--view", "top")
    folder = project.cwd / "assets" / "room" / "alley"
    clock = iter([1000.0, 1001.0, 1060.0, 1061.0, 1400.0, 1401.0, 1500.0, 1501.0])
    monkeypatch.setattr(sys.modules["kiripix.commands.invoke"], "time", SimpleNamespace(time=lambda: next(clock)))

    def run(interactive: bool, width: int) -> None:
        context = Context(cwd=project.cwd, command_line="kiripix set", interactive=interactive)
        envelope, code = invoke(REGISTRY["set"], {"asset": "room.alley", "stage": "brief",
                                                  "assignments": [f"width={width}"]}, context)
        assert code == 0, envelope

    run(True, 400)   # starts at 1000 s: the first one has nothing before it
    run(True, 401)   # starts at 1060: 59 s after the first ended at 1001
    run(True, 402)   # starts at 1400: more than the idle threshold after 1061, so nothing
    run(False, 403)  # not interactive: nothing, and no state kept

    spans = [json.loads(line) for line in (folder / "time.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(s["stage"], s["seconds"], s["source"]) for s in spans] == [("brief", 59, "cli")]
