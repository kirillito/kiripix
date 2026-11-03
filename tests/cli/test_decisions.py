"""`set`, `decide`, `undo`, `redo` and the Decision journal (spec §5, §10.5), on the demo Kind's `choose` Stage."""

import json
import tomllib
from pathlib import Path
from typing import Any

from conftest import Kiripix, make_demo, stage_status


def asset_toml(folder: Path) -> dict[str, Any]:
    return tomllib.loads((folder / "asset.toml").read_text(encoding="utf-8"))


# set


def test_set_writes_the_stage_table_and_turns_the_stage_and_below_stale(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("run", "demo.a")

    data = project.json("set", "demo.a", "concat", "sep=-")["data"]

    assert data["stage"] == "concat" and data["params"] == {"sep": "-"}
    assert asset_toml(folder)["stages"] == {"concat": {"sep": "-"}}
    assert stage_status(project, "demo.a") == {"copy": "done", "concat": "stale", "hold": "stale", "fail": "stale",
                                               "choose": "done"}
    project.json("run", "demo.a")
    assert (folder / "work" / "concat" / "out.txt").read_text(encoding="utf-8").startswith("input-extra")


def test_set_types_each_value_by_the_parameter(project: Kiripix) -> None:
    folder = make_demo(project)

    project.json("set", "demo.a", "choose", "level=7")

    assert asset_toml(folder)["stages"]["choose"] == {"level": 7}


def test_set_keeps_the_other_values_of_the_stage(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("set", "demo.a", "choose", "level=7")

    project.json("set", "demo.a", "concat", "sep=*")

    assert asset_toml(folder)["stages"] == {"choose": {"level": 7}, "concat": {"sep": "*"}}


def test_set_with_an_unknown_key_fails_and_writes_nothing(project: Kiripix) -> None:
    folder = make_demo(project)
    before = (folder / "asset.toml").read_bytes()

    result = project.json("set", "demo.a", "concat", "colour=red", expect=1)

    finding = result["findings"][0]
    assert finding["code"] == "set.unknown_parameter"
    assert "colour" in finding["message"] and "sep" in finding["message"]
    assert finding["position"]["field"] == "stages.concat.colour"
    assert (finding["fix"] is None) != (finding["owner_action"] is None)
    assert (folder / "asset.toml").read_bytes() == before


def test_set_out_of_range_names_the_parameter_and_its_range(project: Kiripix) -> None:
    folder = make_demo(project)
    before = (folder / "asset.toml").read_bytes()

    result = project.json("set", "demo.a", "choose", "level=11", expect=1)

    finding = result["findings"][0]
    assert finding["code"] == "set.invalid_value"
    assert "level" in finding["message"] and "0" in finding["message"] and "10" in finding["message"]
    assert finding["position"]["field"] == "stages.choose.level"
    assert (folder / "asset.toml").read_bytes() == before


def test_set_one_bad_value_rejects_the_whole_call(project: Kiripix) -> None:
    folder = make_demo(project)
    before = (folder / "asset.toml").read_bytes()

    result = project.json("set", "demo.a", "concat", "sep=-", "nope=1", expect=1)

    assert [f["code"] for f in result["findings"]] == ["set.unknown_parameter"]
    assert (folder / "asset.toml").read_bytes() == before


def test_set_refuses_text_that_is_not_the_parameters_type(project: Kiripix) -> None:
    make_demo(project)

    result = project.json("set", "demo.a", "choose", "level=high", expect=1)

    assert result["findings"][0]["code"] == "set.invalid_value"


def test_set_without_key_equals_value_is_an_input_error(project: Kiripix) -> None:
    make_demo(project)

    result = project.json("set", "demo.a", "choose", "level", expect=1)

    assert result["findings"][0]["code"] == "set.invalid_assignment"


def test_set_on_an_unknown_stage_fails(project: Kiripix) -> None:
    make_demo(project)

    result = project.json("set", "demo.a", "paint", "x=1", expect=1)

    assert result["findings"][0]["code"] == "stage.unknown"


# decide


def journal_lines(folder: Path, stage: str = "choose") -> list[dict[str, Any]]:
    path = folder / "decisions" / f"{stage}.jsonl"
    if not path.exists():
        return []
    raw = path.read_bytes().decode("utf-8")
    assert "\r" not in raw and (raw == "" or raw.endswith("\n"))
    return [json.loads(line) for line in raw.splitlines()]


def mark(label: str, **extra: Any) -> str:
    return json.dumps({"decision": "mark", "data": {"label": label, **extra}})


def decide(project: Kiripix, label: str, *, expect: int = 0, **extra: Any) -> dict[str, Any]:
    return project.json("decide", "demo.a", "choose", "--decision", mark(label, **extra), expect=expect)


def current_labels(project: Kiripix, folder: Path) -> list[str]:
    """What the Stage's run function was handed: run it, then read its output."""
    project.json("run", "demo.a", "copy")
    project.json("run", "demo.a", "choose", "--force")
    output = json.loads((folder / "work" / "choose" / "out.json").read_text(encoding="utf-8"))
    return [d["data"]["label"] for d in output["decisions"]]


def test_decide_appends_an_entry_with_a_ulid_a_parent_and_the_data(project: Kiripix) -> None:
    folder = make_demo(project)

    first = decide(project, "door", count=2)["data"]
    second = decide(project, "window")["data"]

    lines = journal_lines(folder)
    assert [line["id"] for line in lines] == [first["id"], second["id"]]
    assert len(first["id"]) == 26 and first["id"] < second["id"]
    assert lines[0] == {"id": first["id"], "parent": None, "decision": "mark", "data": {"label": "door", "count": 2}}
    assert lines[1]["parent"] == first["id"]


def test_decide_reads_the_decision_from_a_file(project: Kiripix) -> None:
    folder = make_demo(project)
    (project.cwd / "d.json").write_text(mark("door"), encoding="utf-8")

    project.json("decide", "demo.a", "choose", "--file", "d.json")

    assert journal_lines(folder)[0]["data"] == {"label": "door"}


def test_decide_needs_exactly_one_source(project: Kiripix) -> None:
    make_demo(project)

    result = project.json("decide", "demo.a", "choose", expect=1)

    assert result["findings"][0]["code"] == "input.invalid"


def test_decide_with_data_that_does_not_match_the_schema_appends_nothing(project: Kiripix) -> None:
    folder = make_demo(project)
    decide(project, "door")
    before = (folder / "decisions" / "choose.jsonl").read_bytes()

    wrong_type = decide(project, "door", expect=1, count="two")
    missing = project.json("decide", "demo.a", "choose", "--decision",
                           json.dumps({"decision": "mark", "data": {}}), expect=1)
    extra = decide(project, "door", expect=1, colour="red")

    assert wrong_type["findings"][0]["code"] == "decision.invalid" and "count" in wrong_type["findings"][0]["message"]
    assert "label" in missing["findings"][0]["message"]
    assert "colour" in extra["findings"][0]["message"]
    assert (folder / "decisions" / "choose.jsonl").read_bytes() == before


def test_decide_with_an_unknown_decision_or_bad_json_fails(project: Kiripix) -> None:
    folder = make_demo(project)

    unknown = project.json("decide", "demo.a", "choose", "--decision",
                           json.dumps({"decision": "pick", "data": {}}), expect=1)
    bad_json = project.json("decide", "demo.a", "choose", "--decision", "{nope", expect=1)
    no_decisions = project.json("decide", "demo.a", "copy", "--decision", mark("x"), expect=1)

    assert unknown["findings"][0]["code"] == "decision.unknown"
    assert bad_json["findings"][0]["code"] == "decide.invalid_json"
    assert no_decisions["findings"][0]["code"] == "decision.unknown"
    assert journal_lines(folder) == [] and journal_lines(folder, "copy") == []


def test_decide_records_the_image_hash_a_click_was_made_on(project: Kiripix) -> None:
    folder = make_demo(project)
    document = {"decision": "mark", "data": {"label": "door"}, "image_hash": "abc123"}

    data = project.json("decide", "demo.a", "choose", "--decision", json.dumps(document))["data"]

    assert journal_lines(folder)[0]["image_hash"] == "abc123"
    assert data["current"][0]["image_hash"] == "abc123"


def test_a_decision_makes_the_stage_stale_and_reaches_its_run_function(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("run", "demo.a")

    decide(project, "door")

    assert stage_status(project, "demo.a")["choose"] == "stale"
    assert stage_status(project, "demo.a")["concat"] == "done"
    assert current_labels(project, folder) == ["door"]
    assert stage_status(project, "demo.a")["choose"] == "done"


# undo and redo


def test_undo_redo_undo_leaves_the_expected_decisions_and_the_journal_only_grows(project: Kiripix) -> None:
    folder = make_demo(project)
    path = folder / "decisions" / "choose.jsonl"
    snapshots: list[bytes] = []

    def record(result: dict[str, Any]) -> dict[str, Any]:
        snapshots.append(path.read_bytes())
        data: dict[str, Any] = result["data"]
        return data

    first = record(decide(project, "door"))
    assert [d["name"] for d in first["current"]] == ["mark"]
    undone = record(project.json("undo", "demo.a", "choose"))
    assert undone["current"] == [] and undone["target"] == first["id"]
    redone = record(project.json("redo", "demo.a", "choose"))
    assert [d["id"] for d in redone["current"]] == [first["id"]]
    undone_again = record(project.json("undo", "demo.a", "choose"))
    assert undone_again["current"] == []

    for before, after in zip(snapshots, snapshots[1:], strict=False):
        assert after.startswith(before) and len(after) > len(before)  # only ever appended to
    lines = journal_lines(folder)
    assert [next(k for k in ("decision", "undo", "redo") if k in line) for line in lines] == [
        "decision", "undo", "redo", "undo"]
    assert lines[1]["undo"] == first["id"] and lines[2]["redo"] == first["id"]
    assert [line["parent"] for line in lines] == [None] + [line["id"] for line in lines[:-1]]
    assert current_labels(project, folder) == []


def test_undo_takes_the_latest_decision_and_redo_brings_it_back(project: Kiripix) -> None:
    folder = make_demo(project)
    decide(project, "one")
    decide(project, "two")

    project.json("undo", "demo.a", "choose")
    assert current_labels(project, folder) == ["one"]
    project.json("redo", "demo.a", "choose")
    assert current_labels(project, folder) == ["one", "two"]
    project.json("undo", "demo.a", "choose")
    project.json("undo", "demo.a", "choose")
    assert current_labels(project, folder) == []
    project.json("redo", "demo.a", "choose")
    assert current_labels(project, folder) == ["one"]


def test_a_new_decision_after_an_undo_clears_what_could_be_redone(project: Kiripix) -> None:
    make_demo(project)
    decide(project, "one")
    project.json("undo", "demo.a", "choose")
    decide(project, "two")

    result = project.json("redo", "demo.a", "choose", expect=1)

    assert result["findings"][0]["code"] == "decision.nothing_to_redo"


def test_undo_with_nothing_to_undo_fails_and_appends_nothing(project: Kiripix) -> None:
    folder = make_demo(project)

    result = project.json("undo", "demo.a", "choose", expect=1)

    finding = result["findings"][0]
    assert finding["code"] == "decision.nothing_to_undo"
    assert (finding["fix"] is None) != (finding["owner_action"] is None)
    assert journal_lines(folder) == []


def test_undo_and_redo_refuse_an_unknown_stage(project: Kiripix) -> None:
    make_demo(project)

    assert project.json("undo", "demo.a", "paint", expect=1)["findings"][0]["code"] == "stage.unknown"
    assert project.json("redo", "demo.a", "paint", expect=1)["findings"][0]["code"] == "stage.unknown"


def test_a_journal_line_that_is_not_an_entry_is_an_error_naming_the_file(project: Kiripix) -> None:
    folder = make_demo(project)
    (folder / "decisions" / "choose.jsonl").write_text('{"id": "x", "parent": null, "colour": 1}\n', encoding="utf-8")

    result = project.json("status", expect=1)

    finding = result["findings"][0]
    assert finding["code"] == "journal.invalid"
    assert "choose.jsonl:1" in finding["message"] and finding["owner_action"]


# divergence


def write_journal(folder: Path, entries: list[dict[str, Any]]) -> None:
    text = "".join(json.dumps(e, separators=(",", ":")) + "\n" for e in entries)
    (folder / "decisions" / "choose.jsonl").write_text(text, encoding="utf-8")


def test_two_entries_with_the_same_parent_need_review_and_next_names_the_owner_action(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("run", "demo.a")
    first = decide(project, "base")["data"]["id"]
    # What merge=union of two branches leaves: both entries followed `first`.
    lines = journal_lines(folder)
    lines.append({"id": "01JZZZZZZZZZZZZZZZZZZZZZZA", "parent": first, "decision": "mark", "data": {"label": "left"}})
    lines.append({"id": "01JZZZZZZZZZZZZZZZZZZZZZZB", "parent": first, "decision": "mark", "data": {"label": "right"}})
    write_journal(folder, lines)

    states = {s["stage"]: s for s in project.json("status")["data"]["assets"][0]["stages"]}
    step = project.json("next", "demo.a")["data"]

    assert states["choose"]["status"] == "needs-review" and states["choose"]["reason"] == "divergent Decisions"
    assert step["stage"] == "choose" and step["status"] == "needs-review"
    assert step["command"] is None and step["owner_action"]
    assert "divergent Decisions" in (step["reason"] or "")


def test_run_does_not_build_past_divergent_decisions(project: Kiripix) -> None:
    folder = make_demo(project)
    write_journal(folder, [
        {"id": "01JZZZZZZZZZZZZZZZZZZZZZZA", "parent": None, "decision": "mark", "data": {"label": "left"}},
        {"id": "01JZZZZZZZZZZZZZZZZZZZZZZB", "parent": None, "decision": "mark", "data": {"label": "right"}},
    ])

    result = project.json("run", "demo.a", expect=3)

    assert [f["code"] for f in result["findings"]] == ["stage.needs_review"]
    assert result["findings"][0]["owner_action"]
    assert result["data"]["results"][-1]["outcome"] == "needs-review"
    assert not (folder / "work" / "choose").exists()


def test_a_linear_journal_is_never_divergent(project: Kiripix) -> None:
    make_demo(project)
    decide(project, "one")
    project.json("undo", "demo.a", "choose")
    project.json("redo", "demo.a", "choose")
    decide(project, "two")

    assert stage_status(project, "demo.a")["choose"] == "todo"
